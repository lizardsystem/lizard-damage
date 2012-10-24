# -*- coding: utf-8 -*-
# (c) Nelen & Schuurmans.  GPL licensed, see LICENSE.rst.

from __future__ import print_function
from __future__ import unicode_literals
from __future__ import absolute_import
from __future__ import division

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

from lizard_damage import raster
from lizard_damage import calc
from lizard_damage import table

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
            #os.path.join(settings.DATA_ROOT, 'waterlevel', 'utrechtq.asc'),
            #os.path.join(settings.DATA_ROOT, 'waterlevel', 'i37_en2_09_delfgauw.asc'),
            #os.path.join(settings.DATA_ROOT, 'waterlevel', 'goudswaard.asc'),
            #os.path.join(settings.DATA_ROOT, 'waterlevel', '1_ha_gras.asc'),
            #os.path.join(settings.DATA_ROOT, 'waterlevel', 'ws1.asc'),
            os.path.join(settings.DATA_ROOT, 'waterlevel', 'overwaard_gorinchem_5.asc'),

        ]
        calc.calc_damage_for_waterlevel(
            repetition_time=None,
            ds_wl_filenames=ds_wl_filenames,
            dt_path='data/damagetable/dt.cfg',
            month=5, floodtime=20*3600,
            repairtime_roads=5*24*3600,
            repairtime_buildings=10*24*3600,
            )
