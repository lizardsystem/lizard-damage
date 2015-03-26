# -*- coding: utf-8 -*-
# (c) Nelen & Schuurmans.  GPL licensed, see LICENSE.rst.
from __future__ import (
    print_function,
    unicode_literals,
    absolute_import,
    division,
)

from django.core.management.base import BaseCommand

from lizard_damage_calculation import table


def main(*args, **options):
    with open(args[0], 'rb') as xlsx:
        dt = table.DamageTable.read_xlsx(xlsx)
    with open(args[1], 'w') as cfg:
        dt.write_cfg(cfg)
    with open(args[1]) as cfg:
        dt = table.DamageTable.read_cfg(cfg)


class Command(BaseCommand):
    args = 'Command args'
    help = 'Command help'

    def handle(self, *args, **options):
        main(*args, **options)
