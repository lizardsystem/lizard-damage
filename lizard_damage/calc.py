# -*- coding: utf-8 -*-
# (c) Nelen & Schuurmans.  GPL licensed, see LICENSE.rst.
from __future__ import (
  print_function,
  unicode_literals,
  absolute_import,
  division,
)

import numpy as np

import collections
import logging
import os
import shutil
import tempfile
import traceback
import zipfile

from django.conf import settings
from lizard_damage import raster
from lizard_damage import table
from lizard_damage import tools
from lizard_damage import models

from osgeo import gdal
from matplotlib import cm
from matplotlib import colors
from PIL import Image

logger = logging.getLogger(__name__)

CALC_TYPE_MIN = 1
CALC_TYPE_MAX = 2
CALC_TYPE_AVG = 3

CALC_TYPES = {
    1: 'min',
    2: 'max',
    3: 'avg',
}


def mkstemp_and_close():
    """
    Make a tempfile and close it. It can be reopened later on.

    Return filename.

    Use this instead of tempfile.mktemp(), because there is a
    racecondition going on there.
    """
    handle, filename = tempfile.mkstemp()
    os.close(handle)
    return filename


def landuse_legend():
    result = []
    # defaults
    for i in range(100):
        result.append('#dddddd')

    # specifics
    result[2] = '#cc0000'  # Woonfunctie
    result[3] = result[2]
    result[4] = result[2]
    result[5] = result[2]
    result[6] = result[2]
    result[7] = result[2]  # Kassen
    result[8] = result[2]
    result[9] = result[2]
    result[10] = result[2]
    result[11] = result[2]
    result[12] = result[2]
    result[13] = result[2]
    result[14] = result[2]

    result[21] = '#5555ee'  # Water

    result[22] = '#888888'  # Primaire Wegen
    result[23] = result[22]
    result[24] = result[22]

    result[25] = '#007000'  # Bos/Natuur
    result[26] = '#00bb00'  # bebouwd gebied
    result[27] = result[25]
    result[28] = result[25]

    result[29] = result[26]  # Begraafplaats, medium groen
    result[30] = '#33ff33'  # Gras
    result[31] = result[30]

    result[32] = result[22]  #Spoorbaanlichaam

    result[41] = result[30]

    result[42] = '#ffff00'  # Mais

    result[43] = '#db5800'  # Aardappelen
    result[44] = result[43]

    result[45] = result[42]  # Granen

    result[46] = result[43]  # Overige akkerbouw

    #result[48] = result[42]  # Braakliggend terrein tussen kassen Glastuinbouw

    result[49] = result[43]  # Boomgaard

    result[50] = result[43]  # Bloembollen

    result[52] = result[30]  # Gras overig

    result[53] = result[25]  # Bos/Natuur

    result[56] = result[21]  # Water (LGN)

    #result[58] = result[25]  # Bebouwd gebied

    result[61] = result[22]  # Spoorwegen terrein
    result[62] = result[22]  # Primaire wegen
    result[63] = result[22]
    result[64] = result[22]
    result[65] = result[22]

    result[66] = result[29]  # Sportterrein
    result[67] = result[29]  # Volkstuinen

    result[68] = result[22]  # Recreatief terrein
    result[69] = result[22]  # Glastuinbouwterrein

    result[70] = result[25]  # Bos/Natuur
    result[71] = result[25]

    result[72] = result[21]  # Zee
    result[73] = result[21]  # Zoet water

    #result[98] = result[2]  # erf

    #result[99] = result[2]  # Overig/Geen landgebruik

    return result


def slug_for_landuse(ahn_name):
    """Name as slug in GeoImage"""
    return 'landuse_%s' % ahn_name


def slug_for_height(ahn_name, min_value, max_value):
    """Name as slug in GeoImage"""
    return 'height_%s_%d_%d' % (
        ahn_name, int(min_value*1000), int(max_value*1000))


def slug_for_depth(ahn_name, min_value, max_value):
    """Name as slug in GeoImage

    min_value and max_values are depths
    """
    return 'depth_%s_%d_%d' % (
        ahn_name, int(min_value*1000), int(max_value*1000))


def get_colorizer(max_damage):
    """ Return colormap and normalizer. """
    # Note the hardcoded area_per_pixel
    area_per_pixel = 0.25
    f = 1 / max_damage * area_per_pixel

    cdict = {
        'red': (
            (0.0,       0, 0),
            (00.01 * f, 0, 1),
            (1.0,       1, 1),
        ),
        'green': (
            (0.,        0.00, 0.00),
            (00.01 * f, 0.00, 1.00),
            (00.50 * f, 1.00, 0.65),
            (10.00 * f, 0.65, 0.00),
            (1.,        0.00, 0.00),
        ),
        'blue': (
            (0., 0, 0),
            (1., 0, 0),
        ),
    }

    # Beware of the amount of quantization levels, it DOES matter
    colormap = colors.LinearSegmentedColormap('damage', cdict, N=1024)
    normalize = colors.Normalize(vmin=0, vmax=max_damage)

    def colorize(data):
        return colormap(normalize(data), bytes=True)

    return colorize

# {landuse-code: gridcode} mapping for roads
ROAD_GRIDCODE = {32: 20, 22: 21, 23: 22}
BUILDING_SOURCES = ('BAG', )


def get_roads_flooded_for_tile_and_code(code, depth, geo):
    """ Return dict {road: flooded_m2}. """
    area_per_pixel = raster.geo2cellsize(geo)
    roads_flooded_for_tile_and_code = {}
    roads = raster.get_roads(ROAD_GRIDCODE[code], geo, depth.shape)
    for road in roads:
        mask = raster.get_mask([road], depth.shape, geo)
        flooded_m2 = (mask * area_per_pixel * np.greater(depth, 0)).sum()
        if flooded_m2:
            roads_flooded_for_tile_and_code[road.pk] = flooded_m2

    return roads_flooded_for_tile_and_code


def calculate(use, depth, geo,
              calc_type, table,
              month, floodtime,
              repairtime_roads,
              repairtime_buildings,
              logger=logger):
    """
    Calculate damage for an area.

    Input: land use, water depth, area_per_pixel, damage table, month
    of flooding, flood time and repair time.
    """
    logger.info('Calculating damage')
    result = np.ma.zeros(depth.shape)
    result.mask = depth.mask
    roads_flooded_for_tile = {}

    count = {}
    damage = {}
    damage_area = {}
    roads_flooded = {}

    area_per_pixel = raster.geo2cellsize(geo)
    default_repairtime = table.header.get_default_repairtime()


    codes_in_use = np.unique(use.compressed())
    for code, dr in table.data.items():
        if not code in codes_in_use:
            damage_area[code] = 0
            damage[code] = 0
            continue

        if dr.source in BUILDING_SOURCES:
            repairtime = repairtime_buildings
        else:
            repairtime = default_repairtime

        index = np.logical_and(
            np.equal(use.data, code),
            ~use.mask,
        )
        count[code] = index.sum()

        partial_result_direct = (
            area_per_pixel *
            dr.to_direct_damage(CALC_TYPES[calc_type]) *
            dr.to_gamma_depth(depth[index]) *
            dr.to_gamma_floodtime(floodtime[index]) *
            dr.to_gamma_month(month)
        )

        if code in ROAD_GRIDCODE:
            # Here only the roads involved in this ahn are recorded, indirect
            # damage will be added to overall results.
            roads_flooded_for_tile[code] = get_roads_flooded_for_tile_and_code(
                code=code, depth=depth, geo=geo,
            )
            partial_result_indirect = np.array(0)
        else:
            partial_result_indirect = (
                area_per_pixel *
                dr.to_gamma_repairtime(repairtime) *
                dr.to_indirect_damage(CALC_TYPES[calc_type])
            ) * np.greater(depth[index], 0)  # True evaluates to 1

        result[index] = partial_result_direct + partial_result_indirect


        damage_area[code] = np.where(
            np.greater(result[index], 0), area_per_pixel, 0,
        ).sum()

        # The sum of an empty masked array is 'masked', so check that.
        if count[code] > 0:
            damage[code] = result[index].sum()
        else:
            damage[code] = 0.


        logger.debug(
            '%s - %s - %s: %.2f dir + %.2f ind = %.2f tot' %
            (
                dr.code,
                dr.source,
                dr.description,
                partial_result_direct.sum(),
                partial_result_indirect.sum(),
                damage[code],
            ),
        )
        #logger.debug(dr.source + ' - ' +
                     #dr.description + ': ' + unicode(damage[code]))

    return damage, count, damage_area, result, roads_flooded_for_tile


def write_result(name, ma_result, ds_template):
    ds_result = raster.init_dataset(ds_template, nodatavalue=-9999)
    raster.fill_dataset(ds_result, ma_result)
    raster.export_dataset(
        filepath=name,
        ds=ds_result,
    )


def write_table(name, damage, area, dt, meta=[], include_total=False):
    """
    Write results in a csv table on disk.

    Optionally provide meta in a list and they are on top.

    i.e. [['name', 'amahoela'], ['description','moehaha']]
    """
    with open(name, 'w') as resultfile:
        # Some meta data
        for l in meta:
            resultfile.write('%s\r\n' % (','.join(l)))

        resultfile.write(
            '"%s","%s","%s","%s","%s"\r\n' %
            (
                'bron',
                'code',
                'omschrijving',
                'oppervlakte met schade [ha]',
                'schade',
            )
        )
        if include_total:
            resultfile.write(
                '%s,%s,%s,%s,%s\r\n' %
                (
                    '-',
                    '-',
                    'Totaal',
                    sum(area.values()) / 10000.,
                    sum(damage.values()),
                )
            )
        for code, dr in dt.data.items():
            resultfile.write(
                '%s,%s,%s,%s,%s\r\n' %
                (
                    dr.source,
                    dr.code,
                    dr.description,
                    area[dr.code] / 10000.,
                    damage[dr.code],
                )
            )


def result_as_dict(name, damage, area, damage_table):
    """
    return data structure of result which can be stored and looped
    """
    data = []
    data.append({
        'source': None,
        'code': None,
        'description': 'Totaal',
        'area_ha': sum(area.values()) / 10000.,
        'damage': sum(damage.values()),
    })
    head = [{'display': 'bron', 'key': 'source'},
            {'display': 'code', 'key': 'code'},
            {'display': 'omschrijving', 'key': 'description'},
            {'display': 'oppervlakte met schade [ha]', 'key': 'area_ha'},
            {'display': 'schade', 'key': 'damage'}]
    for code, dr in damage_table.data.items():
        data.append({
                'source': dr.source,
                'code': dr.code,
                'description': dr.description,
                'area_ha': area[dr.code] / 10000.,
                'damage': damage[dr.code],
                })
    return (head, data)


def write_image(name, values):
    """
    Create png image from values.

    Values is a 2d np array
    """
    colorize = get_colorizer(max_damage=11)
    rgba = colorize(values)
    rgba[:,:,3] = np.where(rgba[:,:,0], 153 , 0)
    Image.fromarray(rgba).save(name, 'PNG')


def correct_single_ascfile(ascpath):
    """ Remove non-native headers in ascfile. """
    asc_headers = [
        'ncols', 'nrows', 'xllcorner', 'yllcorner', 'cellsize', 'nodata_value',
    ]
    ascfile = open(ascpath)
    for i, line in enumerate (ascfile):
        if line.split()[0].lower() in asc_headers:
            if i == 0:
            # File ok, nothing to do.
                return
            break

    # Write the last (correct) line and remaining lines to tempfile
    logger.warning('Correcting file: %s' % ascpath)
    tempfd, temppath = tempfile.mkstemp()

    with os.fdopen(tempfd, 'w') as asctempfile:
        asctempfile.write(line)  # First good line
        asctempfile.writelines(ascfile)  # Remaining lines
    ascfile.close()

    shutil.move(temppath, ascpath)


def correct_ascfiles(input_list):
    """
    test ascfiles for known faulty behaviour and correct them if needed
    """
    for filename in input_list:
        # Skip anything non-asc
        if not os.path.splitext(filename)[-1].lower() == '.asc':
            continue
        correct_single_ascfile(ascpath=filename)


def add_to_zip(output_zipfile, zip_result, logger):
    """
    Now zip all files listed in zip_result

    zip_result is a list with keys:
    - filename: filename on disc
    - arcname: target filename in archive
    - delete_after: set this to remove file from file system after zipping
    """
    logger.info('zipping result into %s' % output_zipfile)
    with zipfile.ZipFile(output_zipfile, 'a', zipfile.ZIP_DEFLATED) as myzip:
        for file_in_zip in zip_result:
            logger.info('zipping %s...' % file_in_zip['arcname'])
            myzip.write(file_in_zip['filename'], file_in_zip['arcname'])
            if file_in_zip.get('delete_after', False):
                logger.info('removing %r (%s in arc)' % (file_in_zip['filename'], file_in_zip['arcname']))
                os.remove(file_in_zip['filename'])


def calc_damage_for_waterlevel(
    repetition_time,
    ds_wl_filenames,
    dt_path=None,
    month=9, floodtime=20*3600,
    repairtime_roads=None, repairtime_buildings=None,
    calc_type=CALC_TYPE_MAX,
    logger=logger):
    """
    Calculate damage for provided waterlevel file.

    in:

    - waterlevel file (provided by user)

    - damage table (optionally provided by user, else default)

    - AHN: models.AhnIndex refer to ahn tiles available on
      <settings.DATA_ROOT>/...

    - month, floodtime (s), repairtime_roads/buildings (s): provided
      by user, used by calc.calculate

    out:

    - per ahn tile an .asc and .csv (see write_result and write_table)

    - schade_totaal.csv (see write_table)

    """
    cdict_water_depth = {
        'red': ((0.0, 170./256, 170./256),
                (0.5, 65./256, 65./256),
                (1.0, 4./256, 4./256)),
        'green': ((0.0, 200./256, 200./256),
                  (0.5, 120./256, 120./256),
                  (1.0, 65./256, 65./256)),
        'blue': ((0.0, 255./256, 255./256),
                 (0.5, 221./256, 221./256),
                 (1.0, 176./256, 176./256)),
        }

    zip_result = []  # store all the file references for zipping. {'filename': .., 'arcname': ...}
    img_result = []
    landuse_slugs = []  # slugs for landuse geo images
    height_slugs = []  # slugs for height geo images
    depth_slugs = []  # slugs for depth geo images

    logger.info('water level: %s' % ds_wl_filenames)
    logger.info('damage table: %s' % dt_path)
    output_zipfile = mkstemp_and_close()
    waterlevel_ascfiles = ds_wl_filenames
    correct_ascfiles(waterlevel_ascfiles)  # TODO: do it elsewhere
    waterlevel_datasets = [raster.import_dataset(waterlevel_ascfile, 'AAIGrid')
                           for waterlevel_ascfile in waterlevel_ascfiles]
    logger.info('waterlevel_ascfiles: %r' % waterlevel_ascfiles)
    logger.info('waterlevel_datasets: %r' % waterlevel_datasets)
    for fn, ds in zip(waterlevel_ascfiles, waterlevel_datasets):
        if ds is None:
            logger.error('data source is not available,'
                         ' please check %s' % fn)
            return

    if dt_path is None:
        damage_table_path = 'data/damagetable/dt.cfg'
        dt_path = os.path.join(settings.BUILDOUT_DIR, damage_table_path)
    with open(dt_path) as cfg:
        dt = table.DamageTable.read_cfg(cfg)
    zip_result.append({'filename': dt_path, 'arcname': 'dt.cfg'})

    overall_area = collections.defaultdict(float)
    overall_damage = collections.defaultdict(float)
    roads_flooded_global = {i: {} for i in ROAD_GRIDCODE}
    result_images = []  # Images to be modified for indirect road damage.

    min_height = None
    max_height = None
    min_depth = 0.0  # Set defaults for testing... depth is always >= 0
    max_depth = 0.1

    ahn_indices = raster.get_ahn_indices(waterlevel_datasets[0])
    for ahn_index in ahn_indices:
        ahn_name = ahn_index.bladnr
        logger.info("Preparing calculation for tile %s..." % ahn_name)

        # Prepare data for calculation
        try:
            alldata = raster.get_calc_data(
                waterlevel_datasets=waterlevel_datasets,
                method=settings.RASTER_SOURCE,
                floodtime=floodtime,
                ahn_name=ahn_name,
                logger=logger,
            )
            if alldata is None:
                logger.warning(
                    'Skipping damage calculation for {}'.format(ahn_name),
                )
                continue

            landuse, depth, geo, floodtime_px, ds_height, height = alldata
        except:
            # Log this error and all previous normal logs, instead of hard crashing
            logger.error('Exception')
            for exception_line in traceback.format_exc().split('\n'):
                logger.error(exception_line)
            return

        extent = ahn_index.the_geom.extent  # 1000x1250 meters = 2000x2500 pixels

        # For height map
        new_min_height = np.amin(height)
        if min_height is None or new_min_height < min_height:
            min_height = new_min_height
        new_max_height = np.amax(height)
        if max_height is None or new_max_height < max_height:
            max_height = new_max_height

        # For depth map
        new_min_depth = np.amin(depth)
        if min_depth is None or new_min_depth < min_depth:
            min_depth = new_min_depth
        new_max_depth = np.amax(depth)
        if max_depth is None or new_max_depth < max_depth:
            max_depth = new_max_depth

        # For landuse map
        landuse_slug = slug_for_landuse(ahn_name)
        landuse_slugs.append(landuse_slug)  # part of result
        # note: multiple objects with the same slug can exist if they
        # enter this function at the same time
        if models.GeoImage.objects.filter(slug=landuse_slug).count() == 0:
            logger.info("Generating landuse GeoImage: %s" % landuse_slug)
            models.GeoImage.from_data_with_legend(landuse_slug, landuse.data, extent, landuse_legend())

        # Result is a np array
        damage, count, area, result, roads_flooded_for_tile = calculate(
            use=landuse, depth=depth, geo=geo, calc_type=calc_type,
            table=dt, month=month, floodtime=floodtime_px,
            repairtime_roads=repairtime_roads,
            repairtime_buildings=repairtime_buildings,
            logger=logger,
        )
        for code, roads_flooded in roads_flooded_for_tile.iteritems():
            for road, flooded_m2 in roads_flooded.iteritems():
                if road in roads_flooded_global[code]:
                    roads_flooded_global[code][road]['area'] += flooded_m2
                else:
                    roads_flooded_global[code][road] = dict(
                        shape=depth.shape,
                        area=flooded_m2,
                        geo=geo,
                    )

        logger.debug("result sum: %f" % result.sum())
        arcname = 'schade_{}'.format(ahn_name)
        if repetition_time:
            arcname += '_T%.1f' % repetition_time
        asc_result = {'filename': mkstemp_and_close(), 'arcname': arcname + '.asc',
            'delete_after': True}
        write_result(
            name=asc_result['filename'],
            ma_result=result,
            ds_template=ds_height,
        )
        zip_result.append(asc_result)

        # Generate image in .png
        # Subdivide tiles
        x_tiles = 1
        y_tiles = 1
        tile_x_size = (extent[2] - extent[0]) / x_tiles
        tile_y_size = (extent[3] - extent[1]) / y_tiles
        result_tile_size_x = result.shape[1] / x_tiles
        result_tile_size_y = result.shape[0] / y_tiles
        #print ('result tile size: %r %r' % (result_tile_size_x, result_tile_size_y))
        for tile_x in range(x_tiles):
            for tile_y in range(y_tiles):
                e = (extent[0] + tile_x * tile_x_size, extent[1] + tile_y * tile_y_size,
                    extent[0] + (tile_x + 1) * tile_x_size, extent[1] + (tile_y + 1) * tile_y_size)
                # We are writing a png + pgw now, but in the task a tiff will be created and uploaded
                base_filename = mkstemp_and_close()
                image_result = {
                    'filename_tif': base_filename + '.tif',
                    'filename_png': base_filename + '.png',
                    'filename_pgw': base_filename + '.pgw',
                    'dstname': 'schade_%s_' + ahn_name + '.png',
                    'extent': ahn_index.extent_wgs84(e=e)}  # %s is for the damage_event.slug
                write_image(
                    name=image_result['filename_png'],
                    values=result[(y_tiles-tile_y-1)*result_tile_size_y:(y_tiles-tile_y)*result_tile_size_y,
                                (tile_x)*result_tile_size_x:(tile_x+1)*result_tile_size_x])
                result_images.append({
                    'extent': e,
                    'path': image_result['filename_png'],
                })
                models.write_pgw(
                    name=image_result['filename_pgw'],
                    extent=e)
                img_result.append(image_result)

        csv_result = {'filename': mkstemp_and_close(), 'arcname': arcname + '.csv',
            'delete_after': True}
        meta = [
            ['schade module versie', tools.version()],
            ['waterlevel', waterlevel_ascfiles[0]],
            ['damage table', dt_path],
            ['maand', str(month)],
            ['duur overstroming (s)', str(floodtime)],
            ['hersteltijd wegen (s)', str(repairtime_roads)],
            ['hersteltijd bebouwing (s)', str(repairtime_buildings)],
            ['berekening', {1: 'Minimum', 2: 'Maximum', 3: 'Gemiddelde'}[calc_type]],
            ['ahn_name', ahn_name],
            ]
        write_table(
            name=csv_result['filename'],
            damage=damage,
            area=area,
            dt=dt,
            meta=meta,
        )
        zip_result.append(csv_result)

        for k in damage.keys():
            if k in overall_damage:
                overall_damage[k] += damage[k]
            else:
                overall_damage[k] = damage[k]

        for k in area.keys():
            if k in overall_area:
                overall_area[k] += area[k]
            else:
                overall_area[k] = area[k]

        add_to_zip(output_zipfile, zip_result, logger)
        zip_result = []

    def generate_height_tiles():
        """
        This is in a subroutine because it
        must be possible to not use it.
        """
        logger.info('Generating height and depth tiles...')
        logger.debug(
            'height min max=%f, %f, depth min max=%f, %f' %
            (min_height, max_height, min_depth, max_depth),
        )
        for ahn_index in ahn_indices:
            ahn_name = ahn_index.bladnr
            height_slug = slug_for_height(ahn_name, min_height, max_height)
            height_slugs.append(height_slug)  # part of result
            geo_image_depth_count = -1
            try:
                depth_slug = slug_for_depth(ahn_name, min_depth, max_depth)
                depth_slugs.append(depth_slug)  # part of result
                geo_image_depth_count = models.GeoImage.objects.filter(
                    slug=depth_slug,
                ).count()
            except:
                logger.warning('GeoImage for depth failed because of fully masked')

            geo_image_height_count = models.GeoImage.objects.filter(
                slug=height_slug,
            ).count()
            if (geo_image_height_count == 0 or geo_image_depth_count == 0):
                # Copied from above
                try:
                    alldata = raster.get_calc_data(
                        waterlevel_datasets=waterlevel_datasets,
                        method=settings.RASTER_SOURCE,
                        floodtime=floodtime,
                        ahn_name=ahn_name,
                        logger=logger,
                    )
                    if alldata is None:
                        logger.warning(
                            'Skipping height tiles generation for {}'
                            .format(ahn_name),
                        )
                        continue

                    landuse, depth, geo, floodtime_px, ds_height, height = alldata
                except:
                    # Log this error and all previous normal logs,
                    # instead of hard crashing
                    logger.error('Exception')
                    for exception_line in traceback.format_exc().split('\n'):
                        logger.error(exception_line)
                    return

            if geo_image_height_count == 0:
                # 1000x1250 meters = 2000x2500 pixels
                extent = ahn_index.the_geom.extent
                # Actually create tile
                logger.info("Generating height GeoImage: %s" % height_slug)
                models.GeoImage.from_data_with_min_max(
                    height_slug, height, extent, min_height, max_height)
            if geo_image_depth_count == 0:
                # 1000x1250 meters = 2000x2500 pixels
                extent = ahn_index.the_geom.extent
                # Actually create tile
                logger.info("Generating depth GeoImage: %s" % depth_slug)
                try: #if isinstance(min_depth, float) and isinstance(max_depth, float):
                    models.GeoImage.from_data_with_min_max(
                        depth_slug, depth, extent, min_depth, max_depth,
                        cdict=cdict_water_depth)
                    depth_slugs.append(depth_slug)  # part of result
                except:
                    logger.info("Skipped depth GeoImage because of masked only or unknown error")

    if ((min_height is not None) and
        (max_height is not None) and
        (min_depth is not None) and
        (max_depth is not None)):
        generate_height_tiles()

    # Only after all tiles have been processed, calculate overall indirect
    # Road damage. This is not visible in the per-tile-damagetable.
    roads_flooded_over_threshold = []
    for code, roads_flooded in roads_flooded_global.iteritems():
        for road, info in roads_flooded.iteritems():
            if info['area'] >= 100:
                roads_flooded_over_threshold.append(road)
                indirect_road_damage = (
                    dt.data[code].to_indirect_damage(CALC_TYPES[calc_type]) *
                    dt.data[code].to_gamma_repairtime(repairtime_roads)
                )
                logger.debug(
                    '%s - %s - %s: %.2f ind' %
                    (
                        dt.data[code].code,
                        dt.data[code].source,
                        dt.data[code].description,
                        indirect_road_damage,
                    ),
                )
                overall_damage[code] += indirect_road_damage


    def add_roads_to_image(roads, image_path, extent):
        """ This function could be moved to top level. """

        # Get old image that needs indirect road damage visualized
        image = Image.open(result_image['path'])

        # Rasterize all roads that have indirect damage
        size = image.size
        geotransform = [
            extent[0],
            (extent[2] - extent[0]) / size[0],
            0,
            extent[3],
            0,
            (extent[1] - extent[3]) / size[1],
        ]
        roadgrid = raster.get_mask(
            roads=road_objects,
            shape=image.size[::-1],
            geo=(b'', geotransform),
        )

        # Paste it into the old image and overwrite the image file
        rgba = np.uint8([[[0, 0, 0, 153]]]) * roadgrid.reshape(
            roadgrid.shape[0], roadgrid.shape[1], 1
        )
        image_roads_rgb = Image.fromstring(
            'RGB',
            (rgba.shape[1], rgba.shape[0]),
            rgba[:, :, 0:3].tostring(),
        )
        image_roads_mask = Image.fromstring(
            'L',
            (rgba.shape[1], rgba.shape[0]),
            rgba[:, :, 3].tostring(),
        )
        image.paste(image_roads_rgb, None, image_roads_mask)
        image.save(result_image['path'])

    road_objects = models.Roads.objects.filter(
        pk__in=roads_flooded_over_threshold,
    )
    for result_image in result_images:
        add_roads_to_image(
            roads=road_objects,
            image_path=result_image['path'],
            extent=result_image['extent'],
        )

    csv_result = {'filename': mkstemp_and_close(), 'arcname': 'schade_totaal.csv',
        'delete_after': True}
    meta = [
        ['schade module versie', tools.version()],
        ['waterlevel', waterlevel_ascfiles[0]],
        ['damage table', dt_path],
        ['maand', str(month)],
        ['duur overstroming (s)', str(floodtime)],
        ['hersteltijd wegen (s)', str(repairtime_roads)],
        ['hersteltijd bebouwing (s)', str(repairtime_buildings)],
        ['berekening', {1: 'Minimum', 2: 'Maximum', 3: 'Gemiddelde'}[calc_type]],
        ]
    write_table(
        name=csv_result['filename'],
        damage=overall_damage,
        area=overall_area,
        dt=dt,
        meta=meta,
        include_total=True,
        )
    result_table = result_as_dict(
        name=csv_result['filename'],
        damage=overall_damage,
        area=overall_area,
        damage_table=dt
        )
    zip_result.append(csv_result)

    add_to_zip(output_zipfile, zip_result, logger)
    zip_result = []

    logger.info('zipfile: %s' % output_zipfile)

    return output_zipfile, img_result, result_table, landuse_slugs, height_slugs, depth_slugs
