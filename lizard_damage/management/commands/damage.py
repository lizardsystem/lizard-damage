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
    raster,
    calc,
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


def show(arr):
        """ Visualize an array with PIL """
        import Image
        tmp = numpy.ma.copy(arr)
        tmp = (tmp - tmp.min()) * 255. / (tmp.max() - tmp.min())
        tmp[tmp.mask] = 0
        Image.fromarray(tmp).show()       


def main():
    ds_wl_filename = os.path.join(
        settings.DATA_ROOT, 'waterlevel', 'ws_test1.asc',
    )
    ds_wl = raster.import_dataset(ds_wl_filename, 'AAIGrid')
    dt = table.DamageTable.read_xlsx('data/damagetable/Schadetabel.xlsx')

    for name in raster.get_ahn_names(ds_wl):
        try:
            use, depth, app = raster.get_data_for_tile(
                name, ds_wl, method='filesystem')
        except ValueError as e:
            raise CommandError(e)

        damage, count, area, result = calc.calculate(
            use=use, depth=depth, area_per_pixel=app,
            table=dt, month=6, time=20 * 3600,
        )
        print(result.sum())
        import ipdb; ipdb.set_trace() 

def temp():
    dt = table.DamageTable.read_xlsx('data/damagetable/Schadetabel.xlsx')
    with open('data/damagetable/dt.cfg', 'w') as cfg:
        dt.write_cfg(cfg)



class Command(BaseCommand):
    args = 'Command args'
    help = 'Command help'

    def handle(self, *args, **options):
        main()
