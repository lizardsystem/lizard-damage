# -*- coding: utf-8 -*-
# (c) Nelen & Schuurmans.  GPL licensed, see LICENSE.rst.
from __future__ import (
  print_function,
  unicode_literals,
  absolute_import,
  division,
)

from django.core.management.base import BaseCommand, CommandError
from django.db import connections
from django.conf import settings

import subprocess
import optparse
import logging
import shlex
import sys
import os

PREPARE = '-p'
APPEND = '-a'
MASTER = 'all.sql'

logger = logging.getLogger(__name__)
if os.path.exists(MASTER):
    os.remove(MASTER)

SQL_TEMPLATE = (
    'UPDATE {table} SET filename={filename}_old WHERE filename={filename};\n'
    'UPDATE {table} SET filename={filename} WHERE filename={filename}_new;\n'
    'DELETE FROM {table} WHERE filename={filename}_old;\n'
)

class Main(object):
    """
    find data/ahn_proc/ -maxdepth 2 -mindepth 2 -regex .*_[0-9][0-9]$ > somelist
    cat filelist | ~/code/schademodule/bin/django loadrasters data_lgn -z -s
    """
    def __init__(self, *args, **options):
        for k, v in options.iteritems():
            setattr(self, k, v)
       
        self.table = args[-1]
        self.psql_command = self._psql_command()
       
        if self.use_stdin:
            self.raster_files = [f.rstrip() for f in sys.stdin.readlines()]
        elif self.ignore_aux_xml_files:
            self.raster_files = [f for f in args[:-1]
                                 if not f.endswith('.aux.xml')]
        else:
            self.raster_files = args[:-1]

        if self.save_as_zip:
            self._save = self._to_zipfile
        else:
            self._save = self._to_database

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

    def _to_database(self, action, path, number=None):
        p2 = self._pgsql2raster(action, path, subprocess.PIPE)
        p3 = subprocess.Popen(self.psql_command, stdin=p2.stdout)
        p3.communicate()

    def _to_zipfile(self, action, path, number=None):
        if number is None:
            fifo_name = '0000_create_table.sql'
        else:
            fifo_name = '%s_%08i_%s.sql' % (
                self.table, number, os.path.basename(path),
            )
        os.mkfifo(fifo_name)
        try:
            zip_command = shlex.split(
                'zip %(fifo_name)s.zip --fifo %(fifo_name)s' % 
                dict(fifo_name=fifo_name),
            )
            p1 = subprocess.Popen(zip_command)
            fifo = open(fifo_name, 'w')
            p2 = self._pgsql2raster(action, path, fifo)
            p2.communicate()
            fifo.close()
        except Exception as e:
            raise e
        finally:
            os.remove(fifo_name)
        with open(MASTER, 'a') as master:
            master.write('\i %s\n' % fifo_name)
            master.write(SQL_TEMPLATE.format(
                table=self.table,
                filename=os.path.basename(path),
            ))

    def _pgsql2raster(self, action, path, destination):
        """ Return the subprocess that writes the sql to destination """

        raster2pgsql_command = shlex.split(
            'raster2pgsql -s 28992 %(action)s -F %(path)s %(table)s' %
            dict(action=action, path=path, table=self.table),
        )
        p1 = subprocess.Popen(raster2pgsql_command, stdout=subprocess.PIPE)

        sed_command = shlex.split(
            '''sed "s/'{name}');$/'{name}_new');/"'''.format(
            name=os.path.basename(path),
        ))
        p2 = subprocess.Popen(sed_command, stdin=p1.stdout, stdout=destination)
        
        return p2

    def run(self):
        connection = connections['raster']
        table_exists = self.table in connection.introspection.table_names()
        if table_exists:
            cursor = connection.cursor()
            cursor.execute('select filename from %s' % self.table)
            existing_records = [r[0] for r in cursor.fetchall()]
        else:
            existing_records = []

        total = len(self.raster_files)

        for i, path in enumerate(self.raster_files):
            logger.debug('Saving raster %s/%s' % (i,total))

            filename = os.path.basename(path)
            if i==0 and not table_exists:
                    self._save(action=PREPARE, path=path)

            if filename in existing_records:
                logger.debug('%s already in %s' %
                    (filename, self.table),
                )
                # continue
            self._save(action=APPEND, path=path, number=i)


class Command(BaseCommand):
    option_list = BaseCommand.option_list + (
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
        optparse.make_option('-s', '--stdin',
            action='store_true',
            dest='use_stdin',
            default=False,
            help='Use filenames from stdin'),
    )
    args = 'RASTER_FILE(S) DATABASE_TABLE'
    help = 'Load one or more raster files into raster database.'

    def handle(self, *args, **options):
        Main(*args, **options).run()
