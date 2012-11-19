# -*- coding: utf-8 -*-
# (c) Nelen & Schuurmans.  GPL licensed, see LICENSE.rst.

from __future__ import print_function
from __future__ import unicode_literals
from __future__ import absolute_import
from __future__ import division

from django.core.management.base import BaseCommand, CommandError

import sys
from lizard_damage import tasks

class Command(BaseCommand):
    args = 'Command args'
    help = 'Command help'

    def handle(self, *args, **options):
        result = tasks.calculate_damage(sys.argv[2])
        # result = tasks.calculate_benefit(sys.argv[2])
        print(result)
