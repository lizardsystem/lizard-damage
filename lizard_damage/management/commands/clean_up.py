# -*- coding: utf-8 -*-
# (c) Nelen & Schuurmans.  GPL licensed, see LICENSE.rst.
from __future__ import (
  print_function,
#  unicode_literals,
  absolute_import,
  division,
)

from django.core.management.base import BaseCommand, CommandError

from lizard_damage import models

import logging
import datetime

logger = logging.getLogger(__name__)



class Command(BaseCommand):
    args = 'Command args'
    help = 'Command help'

    def handle(self, *args, **options):
        logger.info("Cleaning up scenarios older than one week...")
        expiration_date = datetime.datetime.now() - datetime.timedelta(days=7)
        for damage_scenario in models.DamageScenario.objects.filter(
            datetime_created__lte=expiration_date):

            logger.info("Deleting scenario %d (%s), events and results..." % (
                    damage_scenario.id, str(damage_scenario)))

            for damage_event in damage_scenario.damageevent_set.all():
                for damage_event_result in damage_event.damageeventresult_set.all():
                    if damage_event_result.image:
                        damage_event_result.image.delete()
                    damage_event_result.delete()
                if damage_event.result:
                    damage_event.result.delete()
                if damage_event.waterlevel:
                    damage_event.waterlevel.delete()
                damage_event.delete()
            damage_scenario.delete()

        logger.info("Finished.")
