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

from lizard_damage.models import AhnIndex

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
        open_argument = settings.CONNECTION_TEMPLATE % dict(
            table=table, filename=filename,
        )
    else:
        open_argument = filepath
    dataset = gdal.Open(open_argument)
    if dataset.GetProjection() == '':
        dataset.SetProjection(PROJECTION_RD)
    return dataset
        

def show(arr):
        """ Visualize an array with PIL """
        import Image
        mask = arr == arr.min()
        ma = numpy.ma.array(arr, mask=mask)
        ma *= 255 / (ma.max() - ma.min())
        ma -= ma.min()
        ma.mask = ma.mask == False  # Invert the mask
        ma[ma.mask == False] = 0
        ma.mask = False
        Image.fromarray(ma).show()


def ds2poly(ds):
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

    # Do nearest neigbour interpolation to retain the nodata value
    gdal.ReprojectImage(
        ds_source, ds_destination,
        projection_source, projection_match,
        gdalconst.GRA_NearestNeighbour,
    )
    # Set the nodata value from the source
    ds_destination.GetRasterBand(1).SetNoDataValue(
        ds_source.GetRasterBand(1).GetNoDataValue(),
    )
    return ds_destination

def ds2ma(ds):
    """
    Return numpy masked array from dataset using nodata value.
    """
    arr = ds.ReadAsArray()
    mask = (arr == ds.GetRasterBand(1).GetNoDataValue())
    masked_arr = numpy.ma.array(arr, mask=mask)

    return masked_arr


def data_for_tile(ahn_name, waterlevel_dataset, method='fs'):
    """
    Return arrays (height, land_use, water_level).

    waterlevel is a masked array, height and land use are normal arrays.
    land use and water level are checked to have data where waterlevel has data.

    Input tile is the name according to ahn
    """
    driver = 'AIG' if method == 'fs' else 'PostGISRaster'

    filename_ahn = os.path.join(
        settings.DATA_ROOT, 'landheight', tile,
    )
    ds_ahn = import_dataset(ahn_filename, driver)

    filename_lgn = os.path.join(
        settings.DATA_ROOT, 'landuse', tile,
    )
    ds_lgn = import_dataset(, driver)

    ds_wl_wl_dataset_resampled = reproject(wl_dataset, ahn_dataset)

    


def ahn_names(dataset):
    """ Return the names of the ahn tiles that cover this dataset. """
    polygon = dataset2polygon(dataset)
    ahn_names = AhnIndex.objects.filter(
        geom__intersects=wlpoly,
    ).values_list('bladnr', flat=True)
    return ahn_names


def main():
    """
    """
    #ahnds = import_dataset(ahn_filename, 'PostGISRaster')
    wlds_filename = os.path.join(
        settings.DATA_ROOT, 'waterlevel', 'ws_test1.asc',
    )
    wlds = import_dataset(wlds_filename, 'AAIGrid')

    wlpoly = ds2poly(wlds)
    for tile in ahn_tiles[0:1]:
        
        print(tile)
    wlds_r = reproject(wlds, ahnds)
    marr = ds2ma(wlds_r)
    print(marr)


class Command(BaseCommand):
    args = 'Command args'
    help = 'Command help'

    def handle(self, *args, **options):
        main()
