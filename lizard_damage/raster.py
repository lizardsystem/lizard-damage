# -*- coding: utf-8 -*-
# (c) Nelen & Schuurmans.  GPL licensed, see LICENSE.rst.
from __future__ import (
  print_function,
#  unicode_literals,
  absolute_import,
  division,
)

from osgeo import gdal
from osgeo import gdalconst
from osgeo import ogr
from osgeo import osr

from django.contrib.gis.geos import Polygon
from django.db import connections
from django.conf import settings

from lizard_damage import models

from django.core.cache import cache
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


def get_polygon_from_geo_and_shape(geo, shape):
    gt = geo[1]
    x1 = gt[0]
    x2 = x1 + shape[1] * gt[1]
    y2 = gt[3]
    y1 = y2 + shape[0] * gt[5]
    coordinates = (
        (x1, y1),
        (x2, y1),
        (x2, y2),
        (x1, y2),
        (x1, y1),
    )
    return Polygon(coordinates, srid=28992)



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


def get_geo(ds):
    """ Return tuple (projection, geotransform) """
    return  ds.GetProjection(), ds.GetGeoTransform()


def set_geo(ds, geo):
    """ Put geo in ds """
    ds.SetProjection(geo[0])
    ds.SetGeoTransform(geo[1])


def geo2cellsize(geo):
    """ Return cell size. """
    return abs(geo[1][1] * geo[1][5])


def get_ahn_indices(ds):
    """ Return the ahn index objects that cover this dataset. """
    polygon = get_polygon(ds)
    ahn_indices = models.AhnIndex.objects.filter(
        the_geom__intersects=polygon,
    )
    return ahn_indices


def get_roads(gridcode, geo, shape):
    """ Return roads contained by dataset with gridcode gridcode. """
    polygon = get_polygon_from_geo_and_shape(geo, shape)
    roads = models.Roads.objects.filter(
        the_geom__intersects=polygon, gridcode=gridcode,
    )
    return roads


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
    gdal.GetDriverByName(str(driver))
    if driver == 'PostGISRaster':
        table, filename = os.path.split(filepath)
        open_argument = get_postgisraster_argument(
            'raster', table, filename,
        )
    else:
        open_argument = filepath
    dataset = gdal.Open(str(open_argument))

    logger.debug('Opening dataset: %s', open_argument)

    # PostGISRaster driver in GDAL 1.9.1 sets nodatavalue to 0.
    # In that case we get it from the database
    if (driver == 'PostGISRaster' and
        dataset is not None and
        dataset.GetRasterBand(1).GetNoDataValue() == 0):
        nodatavalue = get_postgisraster_nodatavalue(
            'raster', table, filename,
        )
        dataset.GetRasterBand(1).SetNoDataValue(nodatavalue)

    return dataset


def export_dataset(filepath, ds, driver='AAIGrid'):
    """
    Save ds at filepath using driver.

    ds is GDAL Dataset Shadow ?
    """
    gdal.GetDriverByName(driver).CreateCopy(str(filepath), ds)


def disk_free():
    stat = os.statvfs('/')
    return stat.f_bavail * stat.f_frsize


def get_ds_for_tile(ahn_name, method='filesystem'):
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

    return ds_ahn, ds_lgn


def get_calc_data(waterlevel_datasets, method, floodtime, ahn_name, logger, caching=True):
    def hash_code(ahn_name):
        """make hash for ahn tile"""
        return ahn_name
    logger.info('Reading datasets for %s' % ahn_name)
    ds_height, ds_landuse = get_ds_for_tile(
        ahn_name=ahn_name, method=method,
    )  # ds_height: part of result
    cached = cache.get(hash_code(ahn_name))
    if cached is not None and caching:
        logger.info('data from cache')
        geo, height, landuse = cached
    else:
        logger.info('landuse, etc...')
        geo = get_geo(ds_height)  # part of result

        logger.info('height to masked array...')
        height = to_masked_array(ds_height)
        if height.mask.any():
            logger.warn('%s nodata pixels in height tile %s',
            height.mask.sum(), ahn_name,
        )

        logger.info('landuse to masked array...')
        landuse = to_masked_array(ds_landuse)  # part of result
        if landuse.mask.any():
            logger.warn('%s nodata pixels in landuse tile %s',
            landuse.mask.sum(), ahn_name,
        )

        df = disk_free()
        logger.info('caching data... (Disk free: %iGB)' % (df / 1024/1024/1024))
        if df > 2*1024*1024*1024:
            cache.set(hash_code(ahn_name), (geo, height, landuse), 1*24*3600)
        else:
            logger.warning('Less than 2 GB free. Increase disk size for cache, or reduce cache time.')

    logger.info('Reprojecting waterlevels to height data %s' % ahn_name)

    # Here all the datasets are read in one big array.
    # Mem reduction could be achieved here by incrementally read and update.
    depths = numpy.ma.array(
        [to_masked_array(reproject(ds_waterlevel, ds_height))
         for ds_waterlevel in waterlevel_datasets],
    ) - height

    depth = depths.max(0)  # part of result
    floodtime_px = floodtime * numpy.greater(depths, 0).sum(0)  # part of result
    landuse.mask = depth.mask

    return landuse, depth, geo, floodtime_px, ds_height, height


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

    return result


def get_mask(road, shape, geo):
        """
        Return boolean array True where the road is. Shape is the
        numpy shape of the raster.
        """
        sr = osr.SpatialReference()
        sr.ImportFromWkt(geo[0])

        # Prepare in-memory ogr layer
        ds_ogr = ogr.GetDriverByName(b'Memory').CreateDataSource('')
        layer = ds_ogr.CreateLayer(b'', sr)
        layerdefinition = layer.GetLayerDefn()
        feature = ogr.Feature(layerdefinition)
        feature.SetGeometry(ogr.CreateGeometryFromWkb(str(road.the_geom.wkb)))
        layer.CreateFeature(feature)

        # Prepare in-memory copy of ds_gdal
        ds_road = gdal.GetDriverByName(b'mem').Create(
            '', shape[1], shape[0], 1, gdalconst.GDT_Byte,
        )
        set_geo(ds_road, geo)

        # Rasterize and return
        gdal.RasterizeLayer(ds_road,(1,),layer, burn_values=(1,))
        return ds_road.GetRasterBand(1).ReadAsArray()
