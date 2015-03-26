# -*- coding: utf-8 -*-
# (c) Nelen & Schuurmans.  GPL licensed, see LICENSE.rst.
from __future__ import (
    print_function,
    absolute_import,
    division,
)

from django.core.management.base import BaseCommand

from lizard_damage import models
from lizard_task.models import SecuredPeriodicTask

import logging
import datetime

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    args = 'Command args'
    help = 'Command help'

    def handle(self, *args, **options):
        logger.info("Cleaning up scenarios which are expired...")
        now = datetime.datetime.now()
        exp = models.DamageScenario.objects.filter(expiration_date__lte=now)
        for damage_scenario in exp:

            logger.info(
                "Deleting scenario %d (%s), tasks, events and results..." % (
                    damage_scenario.id, str(damage_scenario)))

            damage_scenario.delete()

            SecuredPeriodicTask.objects.filter(
                name__contains='Scenario (%05d)' % damage_scenario.id).delete()

        logger.info("Finished.")
