# -*- coding: utf-8 -*-
# (c) Nelen & Schuurmans.  GPL licensed, see LICENSE.rst.
from __future__ import (
  print_function,
#  unicode_literals,
  absolute_import,
  division,
)

from osgeo import (
    gdal,
    gdalconst,
    osr,
)

from django.contrib.gis.geos import Polygon
from django.db import connections
from django.conf import settings

from lizard_damage import models

import logging
import numpy
import os

logger = logging.getLogger(__name__) 

# Get RD projection string
spatial_reference_rd = osr.SpatialReference()
spatial_reference_rd.ImportFromEPSG(28992)
PROJECTION_RD = spatial_reference_rd.ExportToWkt()


def get_postgisraster_argument(dbname, table, filename):
    """
    Return argument for PostGISRaster driver.

    dbname is the Django database name from the project settings.
    """
    template = ' '.join("""
        PG:host=%(host)s
        port=%(port)s
        dbname='%(dbname)s'
        user='%(user)s'
        password='%(password)s'
        schema='public'
        table='%(table)s'
        where='filename=\\'%(filename)s\\''
        mode=1
    """.split())

    db = settings.DATABASES[dbname]

    if db['HOST'] == '':
        host = 'localhost'
    else:
        host = db['HOST']

    if db['PORT'] == '':
        port = '5432'
    else:
        port = db['HOST']

    return template % dict(
        host=host,
        port=port,
        dbname=db['NAME'],
        user=db['USER'],
        password=db['PASSWORD'],
        table=table,
        filename=filename,
    )


def get_postgisraster_nodatavalue(dbname, table, filename):
    """
    Return the nodatavalue.
    """
    cursor = connections[dbname].cursor()

    # Data retrieval operation - no commit required
    cursor.execute(
        """
        SELECT
            ST_BandNoDataValue(rast)
        FROM
            %(table)s
        WHERE
            filename='%(filename)s'
        """ % dict(table=table, filename=filename),
    )
    row = cursor.fetchall()

    return row[0][0]


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


def get_area_per_pixel(ds):
    gs = ds.GetGeoTransform()
    area_per_pixel = abs(gs[1] * gs[5])
    return area_per_pixel


def get_ahn_names(ds):
    """ Return the names of the ahn tiles that cover this dataset. """
    polygon = get_polygon(ds)
    ahn_names = models.AhnIndex.objects.filter(
        the_geom__intersects=polygon,
    ).values_list('bladnr', flat=True)
    return ahn_names


def init_dataset(ds, nodatavalue=None):
    """
    Return new dataset with same geometry and datatype as ds.

    If nodatavalue is specified, it is set on the new dataset and the
    array is initialized to nodatavalue
    """
    # Create destination dataset

    result = gdal.GetDriverByName('MEM').Create(
        '',  # No filename
        ds.RasterXSize,
        ds.RasterYSize,
        1,  # number of bands
        ds.GetRasterBand(1).DataType
    )

    result.SetProjection(PROJECTION_RD)
    result.SetGeoTransform(ds.GetGeoTransform())

    if nodatavalue is None:
        result.GetRasterBand(1).SetNoDataValue(
            ds.GetRasterBand(1).GetNoDataValue()
        )
        return result

    result.GetRasterBand(1).SetNoDataValue(nodatavalue)
    result.GetRasterBand(1).Fill(nodatavalue)
    return result


def reproject(ds_source, ds_match):
    """
    Reproject source to match the raster layout of match.

    Accepts and resturns gdal datasets.
    """
    nodatavalue_source = ds_source.GetRasterBand(1).GetNoDataValue()

    # Create destination dataset
    ds_destination = init_dataset(ds_match, nodatavalue=nodatavalue_source)

    # Do nearest neigbour interpolation to retain the nodata value
    projection_source = ds_source.GetProjection()
    projection_match = ds_match.GetProjection()

    gdal.ReprojectImage(
        ds_source, ds_destination,
        projection_source, projection_match,
        gdalconst.GRA_NearestNeighbour,
    )

    return ds_destination


def import_dataset(filepath, driver):
    """
    Driver can be 'AIG', 'AAIGrid', 'PostGISRaster'

    When using the PostGISRaster driver, use 'tablename/filename' as
    the filepath
    """
    gdal.GetDriverByName(driver)
    if driver == 'PostGISRaster':
        table, filename = os.path.split(filepath)
        open_argument = get_postgisraster_argument(
            'raster', table, filename,
        )
    else:
        open_argument = filepath
    dataset = gdal.Open(open_argument)

    logger.debug('Opening dataset: %s', open_argument)

    # PostGISRaster driver in GDAL 1.9.1 sets nodatavalue to 0.
    # In that case we get it from the database
    if (driver == 'PostGISRaster' and
        dataset.GetRasterBand(1).GetNoDataValue() == 0):
        nodatavalue = get_postgisraster_nodatavalue(
            'raster', table, filename,
        )
        dataset.GetRasterBand(1).SetNoDataValue(nodatavalue)

    return dataset


def export_dataset(filepath, ds, driver='AAIGrid'):
    """
    Save ds at filepath using driver.
    """
    gdal.GetDriverByName(driver).CreateCopy(filepath, ds)


def get_ds_for_tile(ahn_name, ds_wl_original, method='filesystem'):
    """
    Return datasets (waterlevel, height, landuse).

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

    return ds_wl, ds_ahn, ds_lgn


def fill_dataset(ds, masked_array):
    """
    Set ds band to array data, or nodatavalue where masked.
    """
    array = numpy.array(masked_array, copy=True)
    array[masked_array.mask] = ds.GetRasterBand(1).GetNoDataValue()
    ds.GetRasterBand(1).WriteArray(array)


def to_masked_array(ds, mask=None):
    """
    Read masked array from dataset.

    If mask is given, use that instead of creating mask from nodatavalue,
    and check for nodatavalue in the remaining unmasked data
    """
    array = ds.ReadAsArray()
    nodatavalue = ds.GetRasterBand(1).GetNoDataValue()

    if mask is None:
        result = numpy.ma.array(
            array,
            mask=numpy.equal(array, nodatavalue),
        )
        return result

    result = numpy.ma.array(array, mask=mask)

    if numpy.equal(result, nodatavalue).any():
        raise ValueError('Nodata value found outside mask')

    return result
