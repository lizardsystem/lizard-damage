# -*- coding: utf-8 -*-
# (c) Nelen & Schuurmans.  GPL licensed, see LICENSE.rst.
from __future__ import (
  print_function,
  unicode_literals,
  absolute_import,
  division,
)

from django.core.management.base import BaseCommand
from django.conf import settings

import subprocess
import sys
import os

def main():

    table = sys.argv[-1]
    filenames = sys.argv[2:-1]
    db = settings.DATABASES['raster']
    psql_args = [
        'psql', db['NAME'],
        '--username', db['USER'],
    ]
    if db['HOST'] != '':
        psql_args.extend(
            ['--host', db['HOST']],
        )
    if db['PORT'] != '':
        psql_args.extend(
            ['--port', db['PORT']],
        )

    for i, filename in enumerate(filenames):
        action = '-a' if i else '-d'  # Only drop table for first file.
        p1 = subprocess.Popen(
            [
                'raster2pgsql',
                '-s',
                '28992', 
                action,
                '-F',
                filename, 
                table,
            ],
            stdout=subprocess.PIPE,
        )
        p2 = subprocess.Popen(
            ['sed', "s/'');$/'" + os.path.basename(filename) + "');/"],
            stdin=p1.stdout,
            stdout=subprocess.PIPE,
        )
        p3 = subprocess.Popen(
            psql_args,
            stdin=p2.stdout,
            stdout=sys.stdout,
            stderr=sys.stderr,
        )
        p3.communicate()



class Command(BaseCommand):
    args = 'file [ file [file] ] schema.table'
    help = 'Example: bin/django loadrasters i14ez2_19 i14ez2_20 public.data_ahn'

    def handle(self, *args, **options):
        main()
