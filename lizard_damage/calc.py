# -*- coding: utf-8 -*-
# (c) Nelen & Schuurmans.  GPL licensed, see LICENSE.rst.
from __future__ import (
  print_function,
  unicode_literals,
  absolute_import,
  division,
)

import numpy
import logging
import os
import tempfile
import Image

import zipfile
from django.conf import settings
from lizard_damage import raster
from lizard_damage import table
from osgeo import gdal

logger = logging.getLogger(__name__)


def calculate(use, depth,
              area_per_pixel, table,
              month, floodtime,
              repairtime_roads,
              repairtime_buildings,
              logger=logger):
    """
    Calculate damage for an area.

    Input: land use, water depth, area_per_pixel, damage table, month
    of flooding, flood time and repair time.
    """
    result = numpy.ma.zeros(depth.shape)
    result.mask = depth.mask

    count = {}
    damage = {}
    damage_area = {}

    for code, dr in table.data.items():
        index = (numpy.ma.equal(use, code))

        # Only for new numpies
        #count[code] = numpy.count_nonzero(index)
        # Old numpies, works just as well. tested.
        count[code] = len(index[numpy.nonzero(index)])

        result[index] = (
            area_per_pixel *
            dr.to_direct_damage('max') *
            dr.to_gamma_depth(depth[index]) *
            dr.to_gamma_floodtime(floodtime) *
            dr.to_gamma_month(month)
        )

        # New numpy
        # damage_area[code] = numpy.count_nonzero(
        #     numpy.greater(result[index], 0)
        # ) * area_per_pixel
        # The hard way...
        result_greater = numpy.greater(result[index], 0)
        damage_area[code] = len(result[index][numpy.nonzero(result_greater)]) * area_per_pixel
        #logger.info("damage_area_code: %r %r" % (damage_area[code], damage_area_code))

        # The sum of an empty masked array is 'masked', so check that.
        if count[code] > 0:
            damage[code] = result[index].sum()
        else:
            damage[code] = 0.

        logger.debug(dr.source + ' - ' +
                     dr.description + ': ' + unicode(damage[code]))

    return damage, count, damage_area, result


def write_result(name, ma_result, ds_template):
    ds_result = raster.init_dataset(ds_template, nodatavalue=-1234)
    raster.fill_dataset(ds_result, ma_result)
    raster.export_dataset(
        filepath=name,
        ds=ds_result,
    )


def write_table(name, damage, area, dt):
    with open(name, 'w') as resultfile:
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

    Values is a 2d numpy array
    """
    raster_r = values*3
    raster_g = values*0.5
    raster_b = values*0.5
    raster_a = values*3

    #max is 87.5 for demo set.
    #print("max %r min %r" % (numpy.max(values), numpy.min(values)))

    format = "GTiff"

    driver = gdal.GetDriverByName(str(format))
    metadata = driver.GetMetadata()
    #print('image driver supports: %r' % metadata)
    #print dir(driver)
    #dst_ds = driver.Create("out.tif", 512, 512, 1, gdal.GDT_Byte )
    dst_ds = driver.Create(str(name), len(values[0]), len(values), 4, gdal.GDT_Byte )
    #raster = zeros( (512, 512) )
    #raster = 128*ones( (len(a), len(a[0])) )
    #raster = zeros( (512, 512), dtype = uint8)
    dst_ds.GetRasterBand(1).WriteArray(raster_r)
    dst_ds.GetRasterBand(2).WriteArray(raster_g)
    dst_ds.GetRasterBand(3).WriteArray(raster_b)
    dst_ds.GetRasterBand(4).WriteArray(raster_a)
    #dst_ds.GetRasterBand(4).WriteArray(255*ones( (len(a), len(a[0]))))
    #outBand.SetNoDataValue(-99)
    #dst_ds.GetRasterBand(1).WriteArray(raster)

    # Once we're done, close properly the dataset
    dst_ds = None


def calc_damage_for_waterlevel(
    ds_wl_filename,
    dt_path=None,
    month=9, floodtime=20*3600,
    repairtime_roads=None, repairtime_buildings=None,
    logger=logger):
    """
    Calculate damage for provided waterlevel file.

    in:
    - waterlevel file (provided by user)
    - damage table (optionally provided by user, else default)
    - AHN: models.AhnIndex refer to ahn tiles available on <settings.DATA_ROOT>/...
    - month, floodtime (s), repairtime (s): provided by user, used by calc.calculate

    out:
    - per ahn tile an .asc and .csv (see write_result and write_table)
    - schade_totaal.csv (see write_table)
    """
    zip_result = []  # store all the file references for zipping. {'filename': .., 'arcname': ...}
    img_result = []

    ds_wl_original = raster.import_dataset(ds_wl_filename, 'AAIGrid')
    logger.info('water level: %s' % ds_wl_filename)
    logger.info('damage table: %s' % dt_path)
    if ds_wl_original is None:
        logger.error('data source is not available, please check folder %s' % ds_wl_filename)
        return

    if dt_path is None:
        damage_table_path = 'data/damagetable/dt.cfg'
        dt_path = os.path.join(settings.BUILDOUT_DIR, damage_table_path)
    with open(dt_path) as cfg:
        dt = table.DamageTable.read_cfg(cfg)

    overall_area = {}
    overall_damage = {}
    for ahn_index in raster.get_ahn_indices(ds_wl_original):
        ahn_name = ahn_index.bladnr
        logger.info("calculating damage for tile %s..." % ahn_name)
        ds_wl, ds_ahn, ds_lgn = raster.get_ds_for_tile(
            ahn_name=ahn_name,
            ds_wl_original=ds_wl_original,
            method='filesystem',
        )

        # Prepare data for calculation
        wl = raster.to_masked_array(ds_wl)
        try:
            ahn = raster.to_masked_array(ds_ahn, mask=wl.mask)
            lgn = raster.to_masked_array(ds_lgn, mask=wl.mask)
        except ValueError as e:
            raise CommandError(e)
        depth = wl - ahn
        area_per_pixel = raster.get_area_per_pixel(ds_wl)

        # Result is a numpy array
        damage, count, area, result = calculate(
            use=lgn, depth=depth,
            area_per_pixel=area_per_pixel,
            table=dt, month=month,
            floodtime=floodtime,
            repairtime_roads=repairtime_roads,
            repairtime_buildings=repairtime_buildings,
            logger=logger
        )
        #print(result.sum())
        logger.debug("result sum: %f" % result.sum())
        asc_result = {'filename': tempfile.mktemp(), 'arcname': 'schade_' + ahn_name + '.asc'}
        write_result(
            name=asc_result['filename'],
            ma_result=result,
            ds_template=ds_ahn,
        )
        zip_result.append(asc_result)

        # Generate image. First in .tif, then convert it to .png
        image_result = {
            'filename_tiff': tempfile.mktemp(),
            'filename_png': tempfile.mktemp(),
            'dstname': 'schade_%s_' + ahn_name + '.tiff',
            'extent': ahn_index.extent_wgs84}  # %s is for the damage_event.slug
        write_image(
            name=image_result['filename_tiff'],
            values=result)
        img = Image.open(image_result['filename_tiff'])
        img.save(image_result['filename_png'], 'PNG')
        img_result.append(image_result)

        csv_result = {'filename': tempfile.mktemp(), 'arcname': 'schade_' + ahn_name + '.csv'}
        write_table(
            name=csv_result['filename'],
            damage=damage,
            area=area,
            dt=dt,
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

        del ds_wl, ds_ahn, ds_lgn
        del lgn, depth, wl
        del result

    csv_result = {'filename': tempfile.mktemp(), 'arcname': 'schade_totaal.csv'}
    write_table(
        name=csv_result['filename'],
        damage=overall_damage,
        area=overall_area,
        dt=dt
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
        os.remove(file_in_zip['filename'])

    return output_zipfile, img_result, result_table
