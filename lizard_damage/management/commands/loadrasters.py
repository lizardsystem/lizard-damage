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
import shlex
import sys
import os


class Main(object):
    def __init__(self, *args, **options):
        for k, v in options.iteritems():
            setattr(self, k, v)
       
        self.table = args[-1]
        self.psql_command = self._psql_command()
        
        if self.ignore_aux_xml_files:
            self.raster_files = [f for f in args[:-1]
                                 if not f.endswith('.aux.xml')]
        else:
            self.raster_files = args[:-1]

    def _psql_command(self):
        db = settings.DATABASES['raster']
        host_option = '--host %s' % db['HOST'] if db['HOST'] else ''
        psql_command = shlex.split(
            'psql %(db)s --username %(user)s %(host_option)s' % dict(
                db=db['NAME'],
                user=db['USER'],
                host_option=host_option,
            ),
        )
        return psql_command

    def _to_database(self, action, path):
        p2 = self._pgsql2raster(action, path, subprocess.PIPE)
        p3 = subprocess.Popen(self.psql_command, stdin=p2.stdout)
        p3.communicate()

    def _to_zipfile(self, action, path, number):
        fifo_name = '%s_%08i_%s.sql' % (
            self.table, number, os.path.basename(path),
        )
        os.mkfifo(fifo_name)
        zip_command = shlex.split(
            'zip %(fifo_name)s.zip --fifo %(fifo_name)s' % 
            dict(fifo_name=fifo_name),
        )
        p1 = subprocess.Popen(zip_command)
        fifo = open(fifo_name, 'w')
        p2 = self._pgsql2raster(action, path, fifo)
        p2.communicate()
        fifo.close()
        os.remove(fifo_name)
        with open('all.sql', 'a') as master:
            master.write('\i %s\n' % fifo_name)

    

    def _pgsql2raster(self, action, path, destination):
        """ Return the subprocess that writes the sql to destination """

        raster2pgsql_command = shlex.split(
            'raster2pgsql -s 28992 %(action)s -F %(path)s %(table)s' %
            dict(action=action, path=path, table=self.table),
        )
        p1 = subprocess.Popen(raster2pgsql_command, stdout=subprocess.PIPE)

        sed_command = shlex.split(
            '''sed "s/'');$/'%(name)s');/"''' %
            dict(name=os.path.basename(path)),
        )
        p2 = subprocess.Popen(sed_command, stdin=p1.stdout, stdout=destination)
        
        return p2

    def run(self):
        connection = connections['raster']
        table_exists = self.table in connection.introspection.table_names()
        
        if self.drop_existing_table and not table_exists:
            raise CommandError(
                'Cannot drop non-existing table %s' %
                self.table,
            )

        if table_exists and not self.drop_existing_table:
            # Need to know which files are already loaded
            cursor = connection.cursor()
            cursor.execute('select filename from %s' % self.table)
            existing_records = [r[0] for r in cursor.fetchall()]
        else:
            existing_records = []


        for i, path in enumerate(self.raster_files):
            filename = os.path.basename(path)
            if i==0 and self.drop_existing_table:
                action = '-d'
            elif i==0 and not table_exists:
                action = '-c'
            else:
                action = '-a'
                if filename in existing_records:
                    raise CommandError('Filename %s already in %s.' %
                                       (filename, self.table))
            if self.save_as_zip:
                self._to_zipfile(action=action, path=path, number=i)
            else:
                self._to_database(action=action, path=path)


class Command(BaseCommand):
    option_list = BaseCommand.option_list + (
        optparse.make_option('-d', '--drop',
            action='store_true',
            dest='drop_existing_table',
            default=False,
            help='Drop table first instead of appending rasters.'),
        optparse.make_option('-i', '--ignore',
            action='store_true',
            dest='ignore_aux_xml_files',
            default=False,
            help='Ignore *.aux.xml files'),
        optparse.make_option('-z', '--zipfile',
            action='store_true',
            dest='save_as_zip',
            default=False,
            help='Save as zipped sql instead of loading in database'),
    )
    args = 'RASTER_FILE(S) DATABASE_TABLE'
    help = 'Load one or more raster files into raster database.'

    def handle(self, *args, **options):
        Main(*args, **options).run()
