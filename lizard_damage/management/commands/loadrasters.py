# -*- coding: utf-8 -*-
# (c) Nelen & Schuurmans.  GPL licensed, see LICENSE.rst.
from __future__ import (
  print_function,
  unicode_literals,
  absolute_import,
  division,
)

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.db import connections

import subprocess
import optparse
import sys
import os

def main(*args, **options):
    table_name = args[-1]
    drop_first = options['drop']
    connection = connections['raster']
    
    if options['ignore']:
        raster_files = [f for f in args[:-1] if not f.endswith('.aux.xml')]
    else:
        raster_files = args[:-1]
    
    table_exists = table_name in connection.introspection.table_names()

    if drop_first and not table_exists:
        raise CommandError('Cannot drop non-existing table %s' % table)

    if table_exists and not drop_first:
        # Need to know which files are already loaded
        cursor = connection.cursor()
        cursor.execute('select filename from %s' % table_name)
        existing_basenames = [r[0] for r in cursor.fetchall()]
    else:
        existing_basenames = []

    # Connection parameters
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

    for i, path in enumerate(raster_files):
        basename = os.path.basename(path)
        if i==0 and drop_first:
            action = '-d'
        elif i==0 and not table_exists:
            action = '-c'
        else:
            action = '-a'
            if basename in existing_basenames:
                raise CommandError('Filename %s already in %s.' %
                                   (basename, table_name))

        p1 = subprocess.Popen(
            [
                'raster2pgsql',
                '-s',
                '28992', 
                action,
                '-F',
                path, 
                table_name,
            ],
            stdout=subprocess.PIPE,
        )
        p2 = subprocess.Popen(
            ['sed', "s/'');$/'" + os.path.basename(basename) + "');/"],
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
    option_list = BaseCommand.option_list + (
        optparse.make_option('-d', '--drop',
            action='store_true',
            dest='drop',
            default=False,
            help='Drop table first instead of appending rasters.'),
        optparse.make_option('-i', '--ignore',
            action='store_true',
            dest='ignore',
            default=False,
            help='Ignore *.aux.xml files'),
    )
    args = 'RASTER_FILE(S) DATABASE_TABLE'
    help = 'Load one or more raster files into raster database.'

    def handle(self, *args, **options):
        main(*args, **options)
