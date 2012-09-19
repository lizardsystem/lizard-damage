# -*- coding: utf-8 -*-
# (c) Nelen & Schuurmans.  GPL licensed, see LICENSE.rst.
from __future__ import (
  print_function,
  unicode_literals,
  absolute_import,
  division,
)

import numpy as np
import logging
import os
import tempfile
import Image
import collections


import zipfile
from django.conf import settings
from lizard_damage import raster
from lizard_damage import table
from lizard_damage import tools

from osgeo import gdal
from matplotlib import cm
from matplotlib import colors

logger = logging.getLogger(__name__)

CALC_TYPE_MIN = 1
CALC_TYPE_MAX = 2
CALC_TYPE_AVG = 3

CALC_TYPES = {
    1: 'min',
    2: 'max',
    3: 'avg',
}

# {landuse-code: gridcode} mapping for roads
ROAD_GRIDCODE = {21: 21, 22: 22}
BUILDING_SOURCES = ('BAG', )


def result_indirect_roads_part(
        code, geo, depth, index, damage_per_pixel,
    ):
    """

    """
    area_per_pixel = raster.geo2cellsize(geo)
    result_indirect = np.zeros(depth.shape)
    roads = raster.get_roads(ROAD_GRIDCODE[code], geo, depth.shape)

    for road in roads:
        mask = raster.get_mask(road, depth.shape, geo)
        flooded_m2 = (mask * area_per_pixel).sum()
        logger.debug('This road is {} m2 flooded'.format(flooded_m2))
        if flooded_m2 > 50:
            result_indirect += mask * damage_per_pixel

    return result_indirect[index]


def get_roads_flooded_for_tile_and_code(code, depth, geo):
    """ Return dict {road: flooded_m2}. """
    area_per_pixel = raster.geo2cellsize(geo)
    roads_flooded_for_tile_and_code = {}
    roads = raster.get_roads(ROAD_GRIDCODE[code], geo, depth.shape)
    for road in roads:
        mask = raster.get_mask(road, depth.shape, geo)
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
    result = np.ma.zeros(depth.shape)
    result.mask = depth.mask
    roads_flooded_for_tile = {}

    count = {}
    damage = {}
    damage_area = {}
    roads_flooded = {}

    area_per_pixel = raster.geo2cellsize(geo)
    default_repairtime = table.header.get_default_repairtime()

    for code, dr in table.data.items():
        if code in BUILDING_SOURCES:
            repairtime = repairtime_buildings
        else:
            repairtime = default_repairtime

        index = (np.ma.equal(use, code))
        count[code] = index.sum()

        partial_result_direct = (
            area_per_pixel *
            dr.to_direct_damage(CALC_TYPES[calc_type]) *
            dr.to_gamma_depth(depth[index]) *
            dr.to_gamma_floodtime(floodtime[index]) *
            dr.to_gamma_month(month)
        )

        if code in ROAD_GRIDCODE:
            roads_flooded_for_tile[code] = get_roads_flooded_for_tile_and_code(
                code=code, depth=depth, geo=geo,
            )
            partial_result_indirect = np.array(0)
            #damage_per_pixel = (
                #area_per_pixel *
                #repairtime_roads *
                #dr.to_gamma_repairtime(repairtime_roads) *
                #dr.to_indirect_damage(CALC_TYPES[calc_type]) /
                #(3600 * 24)  # Indirect damage is specified per day
            #)
            #partial_result_indirect = result_indirect_roads_part(
                #code=code, geo=geo, depth=depth, index=index,
                #damage_per_pixel=damage_per_pixel,
            #)
        else:
            partial_result_indirect = (
                area_per_pixel *
                dr.to_gamma_repairtime(repairtime) *
                dr.to_indirect_damage(CALC_TYPES[calc_type]) /
                (3600 * 24)  # Indirect damage is specified per day
            ) * np.ones(depth.shape)[index]

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
    Create jpg image from values.

    Values is a 2d np array
    """
    rgba = np.zeros((values.shape[0], values.shape[1], 4), dtype=np.uint8)
    normalize = colors.LogNorm(vmin=0.001, vmax=100)
    rgba = cm.jet(normalize(values), bytes=True)
    rgba[:,:,3] = rgba[:,:,0]
    #rgba[:,:,0] = values * 3
    #rgba[:,:,1] = values * 0.5
    #rgba[:,:,2] = values * 0.5
    #rgba[:,:,3] = values * 3
    Image.fromarray(rgba).save(name, 'PNG')


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
    zip_result = []  # store all the file references for zipping. {'filename': .., 'arcname': ...}
    img_result = []

    logger.info('water level: %s' % ds_wl_filenames)
    logger.info('damage table: %s' % dt_path)
    waterlevel_ascfiles = ds_wl_filenames
    # if isinstance(ds_wl_filenames, (unicode, str)):
    #     waterlevel_ascfiles = [ds_wl_filenames]
    # else:
    #     waterlevel_ascfiles = ds_wl_filenames
    waterlevel_datasets = [raster.import_dataset(waterlevel_ascfile, 'AAIGrid')
                           for waterlevel_ascfile in waterlevel_ascfiles]
    for fn, ds in zip(waterlevel_ascfiles, waterlevel_datasets):
        if ds is None:
            logger.error('data source is not available,'
                         ' please check folder %s' % fn)
            return

    if dt_path is None:
        damage_table_path = 'data/damagetable/dt.cfg'
        dt_path = os.path.join(settings.BUILDOUT_DIR, damage_table_path)
    with open(dt_path) as cfg:
        dt = table.DamageTable.read_cfg(cfg)
    zip_result.append({'filename': dt_path, 'arcname': 'dt.cfg'})

    overall_area = {}
    overall_damage = {}
    roads_flooded_global = {i: collections.defaultdict(float)
                            for i in ROAD_GRIDCODE}

    for ahn_index in raster.get_ahn_indices(waterlevel_datasets[0]):
        ahn_name = ahn_index.bladnr
        logger.info("calculating damage for tile %s..." % ahn_name)

        # Prepare data for calculation
        landuse, depth, geo, floodtime_px, ds_height = raster.get_calc_data(
            waterlevel_datasets=waterlevel_datasets,
            method=settings.RASTER_SOURCE,
            floodtime=floodtime,
            ahn_name=ahn_name,
            logger=logger,
        )

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
                roads_flooded_global[code][road] += flooded_m2

        #print(result.sum())
        logger.debug("result sum: %f" % result.sum())
        arcname = 'schade_{}'.format(ahn_name)
        if repetition_time:
            arcname += '_T%.1f' % repetition_time
        asc_result = {'filename': tempfile.mktemp(), 'arcname': arcname + '.asc',
            'delete_after': True}
        write_result(
            name=asc_result['filename'],
            ma_result=result,
            ds_template=ds_height,
        )
        zip_result.append(asc_result)

        # Generate image. First in .tif, then convert it to .png
        image_result = {
            'filename_png': tempfile.mktemp(),
            'dstname': 'schade_%s_' + ahn_name + '.tiff',
            'extent': ahn_index.extent_wgs84}  # %s is for the damage_event.slug
        write_image(name=image_result['filename_png'], values=result)
        img_result.append(image_result)

        csv_result = {'filename': tempfile.mktemp(), 'arcname': arcname + '.csv',
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



    csv_result = {'filename': tempfile.mktemp(), 'arcname': 'schade_totaal.csv',
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

    # Now zip all files listed in zip_result
    output_zipfile = tempfile.mktemp()
    logger.info('zipping result into %s' % output_zipfile)
    with zipfile.ZipFile(output_zipfile, 'w', zipfile.ZIP_DEFLATED) as myzip:
        for file_in_zip in zip_result:
            logger.info('writing %s' % file_in_zip['arcname'])
            myzip.write(file_in_zip['filename'], file_in_zip['arcname'])

    logger.info('zipfile: %s' % output_zipfile)
    # Clean up
    logger.info('Cleaning up tempdir')
    for file_in_zip in zip_result:
        if file_in_zip.get('delete_after', False):
            os.remove(file_in_zip['filename'])

    return output_zipfile, img_result, result_table
