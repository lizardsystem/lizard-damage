# -*- coding: utf-8 -*-
# (c) Nelen & Schuurmans.  GPL licensed, see LICENSE.rst.
from __future__ import (
  print_function,
#  unicode_literals,
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

import logging
import numpy
import os

logger = logging.getLogger(__name__)


def show(arr):
    """ Visualize an array with PIL """
    import Image
    tmp = numpy.ma.copy(arr)
    tmp = (tmp - tmp.min()) * 255. / (tmp.max() - tmp.min())
    tmp[tmp.mask] = 0
    Image.fromarray(tmp[::4,::4]).show()


class Command(BaseCommand):
    args = 'Command args'
    help = 'Command help'

    def handle(self, *args, **options):
        ds_wl_filename = os.path.join(
            settings.DATA_ROOT, 'waterlevel', 'ws_test1.asc',
        )
        calc.calc_damage_for_waterlevel(
            repetition_time=None,
            ds_wl_filename=ds_wl_filename,
            dt_path='data/damagetable/dt.cfg',
            month=9, floodtime=20*3600,
            repairtime_roads=5*24*3600,
            repairtime_buildings=10*24*3600,
            )
