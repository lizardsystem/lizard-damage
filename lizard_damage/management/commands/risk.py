# -*- coding: utf-8 -*-
# (c) Nelen & Schuurmans.  GPL licensed, see LICENSE.rst.

from __future__ import print_function
from __future__ import unicode_literals
from __future__ import absolute_import
from __future__ import division

from django.core.management.base import BaseCommand
from lizard_damage import models
from lizard_damage import risk

import sys
import logging


class Command(BaseCommand):
    args = 'Command args'
    help = 'Command help'

    def handle(self, *args, **options):
        damage_scenario = models.DamageScenario.objects.get(id=sys.argv[2])
        risk.create_risk_map(damage_scenario=damage_scenario, logger=logging)
