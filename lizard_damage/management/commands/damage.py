# -*- coding: utf-8 -*-
# (c) Nelen & Schuurmans.  GPL licensed, see LICENSE.rst.
from __future__ import (
  print_function,
#  unicode_literals,
  absolute_import,
  division,
)

from django.core.management.base import BaseCommand, CommandError
from django.contrib.gis.geos import Polygon, MultiPolygon
from django.conf import settings

from lizard_damage import (
    models,
    utils,
    table,
)

from osgeo import (
    gdal,
    gdalconst,
    osr,
)

import numpy
import os

# Get RD projection string
spatial_reference_rd = osr.SpatialReference()
spatial_reference_rd.ImportFromEPSG(28992)
PROJECTION_RD = spatial_reference_rd.ExportToWkt()


def import_dataset(filepath, driver):
    """
    Driver can be 'AIG', 'AAIGrid', 'PostGISRaster'

    When using the PostGISRaster driver, use 'tablename/filename' as the filepath
    """
    gdal.GetDriverByName(driver)
    if driver == 'PostGISRaster':
        table, filename = os.path.split(filepath)
        open_argument = utils.get_postgisraster_argument(
            'raster', table, filename,
        )
    else:
        open_argument = filepath
    dataset = gdal.Open(open_argument)

    # Post processing
    if dataset.GetProjection() == '':
        dataset.SetProjection(PROJECTION_RD)

    # PostGISRaster driver in GDAL 1.9.1 sets nodatavalue to 0.
    # In that case we get it from the database
    if (driver == 'PostGISRaster' and
        dataset.GetRasterBand(1).GetNoDataValue() == 0):
        nodatavalue = utils.get_postgisraster_nodatavalue(
            'raster', table, filename,
        )
        dataset.GetRasterBand(1).SetNoDataValue(nodatavalue)
   
    return dataset
        

def show(arr):
        """ Visualize an array with PIL """
        import Image
        tmp = numpy.ma.copy(arr)
        tmp = (tmp - tmp.min()) * 255. / (tmp.max() - tmp.min())
        tmp[tmp.mask] = 0
        Image.fromarray(tmp).show()       


def get_polygon(ds):
    gs = ds.GetGeoTransform()
    x1 = gs[0]
    x2 = x1 + ds.RasterXSize * gs[1]
    y2 = gs[3]
    y1 = y2 + ds.RasterYSize * gs[5]
    coordinates = (
        (x1, y1),
        (x2, y1),
        (x2, y2),
        (x1, y2),
        (x1, y1),
    )
    return Polygon(coordinates, srid=28992)


def reproject(ds_source, ds_match):
    """
    Reproject source to match the raster layout of match.
    """
   
    projection_source = ds_source.GetProjection()
    nodatavalue_source = ds_source.GetRasterBand(1).GetNoDataValue()

    projection_match = ds_match.GetProjection()
    geotransform_match = ds_match.GetGeoTransform()
    width = ds_match.RasterXSize
    height = ds_match.RasterYSize

    # Create destination dataset
    ds_destination = gdal.GetDriverByName('MEM').Create(
        '', 
        width, 
        height, 
        1,  # number of bands
        gdalconst.GDT_Float32,
    )
    ds_destination.SetGeoTransform(geotransform_match)
    ds_destination.SetProjection(projection_match)
    ds_destination.GetRasterBand(1).SetNoDataValue(nodatavalue_source)
    ds_destination.GetRasterBand(1).Fill(nodatavalue_source)

    # Do nearest neigbour interpolation to retain the nodata value
    gdal.ReprojectImage(
        ds_source, ds_destination,
        projection_source, projection_match,
        gdalconst.GRA_NearestNeighbour,
    )

    return ds_destination

def get_masked_array(ds):
    """
    Return numpy masked array from dataset using nodata value.
    """
    arr = ds.ReadAsArray()
    mask = (arr == ds.GetRasterBand(1).GetNoDataValue())
    masked_arr = numpy.ma.array(arr, mask=mask)

    return masked_arr

def getnod(ds):
    return ds.GetRasterBand(1).GetNoDataValue()

def setnod(ds, val):
    ds.GetRasterBand(1).SetNoDataValue(val)

def getarr(ds):
    return ds.ReadAsArray()

def getset(ds):
    return set(getarr(ds).flatten())

def data_for_tile(ahn_name, ds_wl_original, method='filesystem'):
    """
    Return arrays (waterlevel, height, landuse, depth).

    waterlevel is a masked array, height and land use are normal arrays.
    land use and water level are checked to have data where waterlevel has data.

    Input:
        ahn_name: ahn subunit name
        ds_wl_original: supplied waterlevel dataset
        method can be 'filesystem' or 'database'
    """
    if method == 'filesystem':
        driver = 'AIG'
        basepath = settings.DATA_ROOT
    elif method == 'database':
        driver = 'PostGISRaster'
        basepath = ''

    ds_ahn_filename = os.path.join(basepath, 'data_ahn', ahn_name)
    ds_lgn_filename = os.path.join(basepath, 'data_lgn', ahn_name)
    ds_ahn = import_dataset(ds_ahn_filename, driver)
    ds_lgn = import_dataset(ds_lgn_filename, driver)

    ds_wl = reproject(ds_wl_original, ds_ahn)

    ds_wl_gt = ds_wl.GetGeoTransform()
    area_per_pixel = abs(ds_wl_gt[1] * ds_wl_gt[5])

    arr_wl = ds_wl.ReadAsArray() 
    arr_ahn = ds_ahn.ReadAsArray()
    arr_lgn = ds_lgn.ReadAsArray()

    ndv_wl = ds_wl.GetRasterBand(1).GetNoDataValue()
    ndv_ahn = ds_ahn.GetRasterBand(1).GetNoDataValue()
    ndv_lgn = ds_lgn.GetRasterBand(1).GetNoDataValue()

    # Create masked arrays with nodata from waterlevel masked
    mask = (numpy.equal(arr_wl, ndv_wl))
    wl = numpy.ma.array(arr_wl, mask=mask)
    ahn = numpy.ma.array(arr_ahn, mask=mask)
    lgn = numpy.ma.array(arr_lgn, mask=mask)

    # Check for nodatavalue in unmasked parts of ahn and lgn
    if numpy.equal(ahn, ndv_ahn).any():
        raise CommandError('Nodata value found in landheight %s!' % ahn_name)
    if numpy.equal(lgn, ndv_lgn).any():
        raise CommandError('Nodata value found in landuse %s!' % ahn_name)

    depth = wl - ahn

    return lgn, depth, area_per_pixel


def ahn_names(ds):
    """ Return the names of the ahn tiles that cover this dataset. """
    polygon = get_polygon(ds)
    ahn_names = models.AhnIndex.objects.filter(
        geom__intersects=polygon,
    ).values_list('bladnr', flat=True)
    return ahn_names


def calculate(use, depth, area_per_pixel, table, month, time):
    """
    Calculate stuff. Note the hardcoded area_per_pixel!
    """

    result = numpy.ma.zeros(depth.shape)
    result.mask = depth.mask

    count = {}
    damage = {}
    damage_area = {}

    for code, dr in table.data.items():

        index = (numpy.ma.equal(use, code))
        count[code] = numpy.count_nonzero(index)

        result[index] = (
            area_per_pixel *
            dr.direct_damage.max *
            dr.gamma_depth(depth[index]) *
            dr.gamma_time(time) *
            dr.gamma_month(month)
        )

        damage_area[code] = numpy.count_nonzero(
            numpy.greater(result[index], 0)
        ) * area_per_pixel

        # The sum of an empty masked array is 'masked', so check that.
        if count[code] > 0:
            damage[code] = result[index].sum()
        else:
            damage[code] = 0.

    return damage, count, damage_area, result


def main():
    ds_wl_filename = os.path.join(
        settings.DATA_ROOT, 'waterlevel', 'ws_test1.asc',
    )
    ds_wl = import_dataset(ds_wl_filename, 'AAIGrid')
    dt = table.DamageTable.read_xlsx('data/damagetable/Schadetabel.xlsx')

    for name in ahn_names(ds_wl):
        use, depth, app = data_for_tile(name, ds_wl, method='filesystem')

        damage, count, area, result = calculate(
            use=use, depth=depth, area_per_pixel=app,
            table=dt, month=6, time=20 * 3600,
        )
        print(result.sum())
        exit()

def temp():
    dt = table.DamageTable.read_xlsx('data/damagetable/Schadetabel.xlsx')
    with open('data/damagetable/dt.cfg', 'w') as cfg:
        dt.write_cfg(cfg)



class Command(BaseCommand):
    args = 'Command args'
    help = 'Command help'

    def handle(self, *args, **options):
        temp()
