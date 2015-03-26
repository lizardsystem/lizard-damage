# -*- coding: utf-8 -*-
# (c) Nelen & Schuurmans.  GPL licensed, see LICENSE.rst.

from __future__ import print_function
# from __future__ import unicode_literals
from __future__ import absolute_import
from __future__ import division

import logging
import numpy

from osgeo import gdal
from osgeo import gdalconst
from osgeo import ogr
from osgeo import osr

from django.contrib.gis.geos import Polygon

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
    """geo is a (projection, geotransform) tuple of which only the geotransform
    is used."""
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


def get_area_with_data(ds):
    """Return area of dataset in m2, not counting the nodata cells"""
    return 0
    band = ds.GetRasterBand(1)
    nodatavalue = band.GetNoDataValue()
    if nodatavalue is not None:
        cells_with_data = (
            band.ReadAsArray() != nodatavalue).sum()
    else:
        cells_with_data = ds.RasterXSize * ds.RasterYSize
    return cells_with_data * get_area_per_pixel(ds)


def get_geo(ds):
    """ Return tuple (projection, geotransform) """
    return ds.GetProjection(), ds.GetGeoTransform()


def set_geo(ds, geo):
    """Put geo in ds. geo is a (projection, geotransform) tuple.
    """
    ds.SetProjection(geo[0])
    ds.SetGeoTransform(geo[1])


def geo2cellsize(geo):
    """Return cell size. geo is a (projection, geotransform) tuple of
    which only the geotransform is used.
    """
    return abs(geo[1][1] * geo[1][5])


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


def export_dataset(filepath, ds, driver='AAIGrid'):
    """
    Save ds at filepath using driver.

    ds is GDAL Dataset Shadow ?
    """
    gdal.GetDriverByName(driver).CreateCopy(str(filepath), ds)


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
        """Return boolean array True where the road is. Shape is the
        numpy shape of the raster.

        geo is a (projection, geotransform) tuple.

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


def extent_within_extent(outer_extent, inner_extent):
    ominx, ominy, omaxx, omaxy = outer_extent
    iminx, iminy, imaxx, imaxy = inner_extent

    return (
        (ominx <= iminx <= imaxx <= omaxx) and
        (ominy <= iminy <= imaxy <= omaxy))
