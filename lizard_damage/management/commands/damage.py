# -*- coding: utf-8 -*-
# (c) Nelen & Schuurmans.  GPL licensed, see LICENSE.rst.
from __future__ import (
  print_function,
  # unicode_literals,
  absolute_import,
  division,
)

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

from lizard_damage import (
    raster,
    calc,
    table,
)

import numpy
import os


def show(arr):
        """ Visualize an array with PIL """
        import Image
        tmp = numpy.ma.copy(arr)
        tmp = (tmp - tmp.min()) * 255. / (tmp.max() - tmp.min())
        tmp[tmp.mask] = 0
        Image.fromarray(tmp[::4,::4]).show()


def main():
    ds_wl_filename = os.path.join(
        settings.DATA_ROOT, 'waterlevel', 'ws_test1.asc',
    )
    ds_wl_original = raster.import_dataset(ds_wl_filename, 'AAIGrid')
    with open('data/damagetable/Schadetabel.xlsx', 'rb') as xlsx:
        dt = table.DamageTable.read_xlsx(xlsx)
    #with open('data/damagetable/dt.cfg', 'w') as cfg:
        #dt.write_cfg(cfg)
    #with open('data/damagetable/dt.cfg') as cfg:
        #dt = table.DamageTable.read_cfg(cfg)

    for ahn_name in raster.get_ahn_names(ds_wl_original):
        ds_wl, ds_ahn, ds_lgn = raster.get_ds_for_tile(
            ahn_name=ahn_name,
            ds_wl_original=ds_wl_original,
            method='database',
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
        
        damage, count, area, result = calc.calculate(
            use=lgn, depth=depth,
            area_per_pixel=area_per_pixel,
            table=dt, month=6, time=20 * 3600,
        )
        print(result.sum())
        exit()
        

        #ds_result = raster.init_dataset(ds_ahn, nodatavalue=-1234)
        #raster.fill_dataset(ds_result, result)
        
        #raster.export_dataset(
            #filepath='/tmp/result.asc',
            #ds=ds_result,
        #)

        del ds_wl, ds_ahn, ds_lgn
        del lgn, depth, wl
        del result



class Command(BaseCommand):
    args = 'Command args'
    help = 'Command help'

    def handle(self, *args, **options):
        main()
