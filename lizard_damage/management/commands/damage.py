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


class Command(BaseCommand):
    args = 'Command args'
    help = 'Command help'

    def handle(self, *args, **options):
        ds_wl_filenames = [os.path.join(
            settings.DATA_ROOT, 'waterlevel', 'ws%i.asc' % i
        ) for i in range(5)]
        ds_wl_filenames = [
            os.path.join(settings.DATA_ROOT, 'waterlevel', '1_ha_gras.asc'),
        ]
        #ds_wl_filenames = [
            #os.path.join(settings.DATA_ROOT, 'waterlevel', 'ws1.asc'),
        #]
        calc.calc_damage_for_waterlevel(
            repetition_time=None,
            ds_wl_filenames=ds_wl_filenames,
            dt_path='data/damagetable/dt.cfg',
            month=5, floodtime=20*3600,
            repairtime_roads=5*24*3600,
            repairtime_buildings=10*24*3600,
            )
