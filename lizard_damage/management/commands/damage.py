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
    osr,
)

import numpy
import os


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
    return dataset
        
def rd():
    """ some caching here? """
    sr = osr.SpatialReference()
    sr.ImportFromEPSG(28992)
    return sr.ExportToWkt()

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


def main():
    """
    import waterlevels
    find filenames
    per tile:
        resample waterlevels
        calculate
        store results in table
        
    """
    #ahn_filename = 'data_landheight/i37en1_13'
    #ahnds = import_dataset(ahn_filename, 'PostGISRaster')
    wlds_filename = os.path.join(
        settings.DATA_ROOT, 'waterlevel', 'ws_test2.asc',
    )
    ahn_filename = os.path.join(
        settings.DATA_ROOT, 'landheight', 'i37en1_13',
    )
    wlds = import_dataset(wlds_filename, 'AAIGrid')
    ahnds = import_dataset(ahn_filename, 'AIG')

    wlpoly = ds2poly(wlds)
    ahn_tiles = AhnIndex.objects.filter(
        geom__intersects=wlpoly,
    ).values_list('bladnr', flat=True)
    for tile in ahn_tiles:
        print(tile)


class Command(BaseCommand):
    args = 'Command args'
    help = 'Command help'

    def handle(self, *args, **options):
        main()
