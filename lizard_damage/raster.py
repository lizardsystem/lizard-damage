# -*- coding: utf-8 -*-
# (c) Nelen & Schuurmans.  GPL licensed, see LICENSE.rst.

from __future__ import print_function
# from __future__ import unicode_literals
from __future__ import absolute_import
from __future__ import division

import logging
import numpy
import os

from osgeo import gdal
from osgeo import gdalconst
from osgeo import ogr
from osgeo import osr

from django.contrib.gis.geos import Polygon
from django.conf import settings

from lizard_damage import models

logger = logging.getLogger(__name__)

PROJECTION_RD = osr.GetUserInputAsWKT('epsg:28992')


def transform_extent(extent, source='epsg:28992', target='epsg:4326'):
    """
    Transform an extent.
    """
    x1, y1, x2, y2 = extent
    ct = osr.CoordinateTransformation(
        osr.SpatialReference(osr.GetUserInputAsWKT(source)),
        osr.SpatialReference(osr.GetUserInputAsWKT(target)),
    )
    (p1, q1, r1), (p2, q2, r2) = ct.TransformPoints(((x1, y1), (x2, y2)))
    return p1, q1, p2, q2


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
    return ds.GetProjection(), ds.GetGeoTransform()


def set_geo(ds, geo):
    """ Put geo in ds """
    ds.SetProjection(geo[0])
    ds.SetGeoTransform(geo[1])


def geo2cellsize(geo):
    """ Return cell size. """
    return abs(geo[1][1] * geo[1][5])


def get_index_info(ds):
    """
    Return the ahn leaf numbers that cover this dataset.

    Only the portions with data are considered in determining the leaf
    numbers for the data tiles.
    """
    logger.info('Determine relevant portions of ahn2 tiles.')
    # create an ogr datasource
    driver = ogr.GetDriverByName('Memory')
    datasource = driver.CreateDataSource('')
    layer = datasource.CreateLayer(
        '', osr.SpatialReference(PROJECTION_RD),
    )
    field_defn = ogr.FieldDefn(b'class', ogr.OFTInteger)
    layer.CreateField(field_defn)
    # need a projection and asc does not support update, so create tmp dataset
    driver = gdal.GetDriverByName('mem')
    dataset = driver.Create(
        '', ds.RasterXSize, ds.RasterYSize, ds.RasterCount, gdal.GDT_Byte,
    )
    band = dataset.GetRasterBand(1)
    band.WriteArray(ds.GetRasterBand(1).GetMaskBand().ReadAsArray())
    band.SetNoDataValue(255)
    dataset.SetGeoTransform(ds.GetGeoTransform())
    dataset.SetProjection(ds.GetProjection())
    # polygonize the mask band
    gdal.Polygonize(band, band, layer, 0)
    # put all features in a multipolygon
    geometry = ogr.Geometry(ogr.wkbMultiPolygon)
    for feature in layer:
        geometry.AddGeometry(feature.geometry())
    # read from the index
    index_datasource = ogr.Open(
        os.path.join(settings.BUILDOUT_DIR, 'data', 'index')
    )
    index_layer = index_datasource[0]
    index_layer.SetSpatialFilter(geometry)

    def feature2extent(feature):
        x1, x2, y1, y2 = feature.geometry().GetEnvelope()
        return x1, y1, x2, y2

    result = {feature['BLADNR']: feature2extent(feature)
              for feature in index_layer}
    return result


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


def export_dataset(filepath, ds, driver='AAIGrid'):
    """
    Save ds at filepath using driver.

    ds is GDAL Dataset Shadow ?
    """
    gdal.GetDriverByName(driver).CreateCopy(str(filepath), ds)


def get_ds_for_tile(ahn_name, logger=None):
    """
    Return datasets (waterlevel, height, landuse).

    Input:
        ahn_name: ahn subunit name
    """
    basepath = settings.DATA_ROOT
    # ahn
    ds_ahn_filename = os.path.join(
        basepath, 'data_ahn', ahn_name[1:4], ahn_name + '.tif'
    )
    ds_ahn = gdal.Open(str(ds_ahn_filename))
    if ds_ahn is None:
        logger.warning('No height data for {}'.format(ahn_name))
    # lgn
    ds_lgn_filename = os.path.join(
        basepath, 'data_lgn', ahn_name[1:4], ahn_name + '.tif'
    )
    ds_lgn = gdal.Open(str(ds_lgn_filename))
    if ds_lgn is None:
        logger.warning('No landuse data for {}'.format(ahn_name))

    return ds_ahn, ds_lgn


def get_calc_data(waterlevel_datasets, floodtime, ahn_name, logger):
    """ Return a tuple with data. """

    logger.info('Reading datasets for %s' % ahn_name)
    ds_height, ds_landuse = get_ds_for_tile(
        ahn_name=ahn_name, logger=logger,
    )  # ds_height: part of result
    if ds_height is None or ds_landuse is None:
        return None

    logger.info('landuse, etc...')
    geo = get_geo(ds_height)  # part of result

    logger.info('height to masked array...')
    height = to_masked_array(ds_height)
    if height.mask.any():
        logger.warn(
            '%s nodata pixels in height tile %s',
            height.mask.sum(), ahn_name,
        )

    logger.info('landuse to masked array...')
    landuse = to_masked_array(ds_landuse)  # part of result
    if landuse.mask.any():
        logger.warn(
            '%s nodata pixels in landuse tile %s',
            landuse.mask.sum(), ahn_name,
        )

    logger.info('Reprojecting waterlevels to height data %s' % ahn_name)

    # Here all the datasets are read in one big array.
    # Mem reduction could be achieved here by incrementally read and update.
    depths = numpy.ma.array(
        [to_masked_array(reproject(ds_waterlevel, ds_height))
         for ds_waterlevel in waterlevel_datasets],
    ) - height

    depth = depths.max(0)  # part of result
    floodtime_px = floodtime * numpy.greater(depths, 0).sum(0)
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


def get_mask(roads, shape, geo):
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
        for road in roads:
            feature = ogr.Feature(layerdefinition)
            feature.SetGeometry(
                ogr.CreateGeometryFromWkb(str(road.the_geom.wkb)))
            layer.CreateFeature(feature)

        # Prepare in-memory copy of ds_gdal
        ds_road = gdal.GetDriverByName(b'mem').Create(
            '', shape[1], shape[0], 1, gdalconst.GDT_Byte,
        )
        set_geo(ds_road, geo)

        # Rasterize and return
        gdal.RasterizeLayer(ds_road, (1,), layer, burn_values=(1,))
        return ds_road.GetRasterBand(1).ReadAsArray()
