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
        Image.fromarray(tmp).show()


def main():
    ds_wl_filename = os.path.join(
        settings.DATA_ROOT, 'waterlevel', 'ws_test1.asc',
    )
    ds_wl = raster.import_dataset(ds_wl_filename, 'AAIGrid')
    with open('data/damagetable/Schadetabel.xlsx', 'rb') as xlsx:
        dt = table.DamageTable.read_xlsx(xlsx)
    with open('data/damagetable/dt.cfg') as cfg:
        dt = table.DamageTable.read_cfg(cfg)

    import utils;mon=utils.monitor.Monitor()
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
        del use, depth, app, damage, count, area, result
        mon.check(name) 


def temp():
    with open('data/damagetable/Schadetabel.xlsx', 'rb') as xlsx:
        dt = table.DamageTable.read_xlsx(xlsx)
    with open('data/damagetable/dt.cfg', 'w') as cfg:
        dt.write_cfg(cfg)
    with open('data/damagetable/dt.cfg') as cfg:
        dt2 = table.DamageTable.read_cfg(cfg)
        dt2.data[1].to_direct_damage()



class Command(BaseCommand):
    args = 'Command args'
    help = 'Command help'

    def handle(self, *args, **options):
        main()
