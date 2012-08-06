# -*- coding: utf-8 -*-
# (c) Nelen & Schuurmans.  GPL licensed, see LICENSE.rst.
from __future__ import (
  print_function,
  unicode_literals,
  absolute_import,
  division,
)

from django.conf import settings
from django.db import connections


def get_postgisraster_argument(dbname, table, filename):
    """
    Return argument for PostGISRaster driver.

    dbname is the Django database name from the project settings.
    """
    template = ' '.join("""
        PG:host=%(host)s
        port=%(port)s
        dbname='%(dbname)s'
        user='%(user)s'
        password='%(password)s'
        schema='public'
        table='%(table)s'
        where='filename=\\'%(filename)s\\''
        mode=1
    """.split())

    db = settings.DATABASES[dbname]

    if db['HOST'] == '':
        host = 'localhost'
    else:
        host = db['HOST']
    
    if db['PORT'] == '':
        port = '5432'
    else:
        port = db['HOST']
    
    return template % dict(
        host=host,
        port=port,
        dbname=db['NAME'],
        user=db['USER'],
        password=db['PASSWORD'],
        table=table,
        filename=filename,
    )


def get_postgisraster_nodatavalue(dbname, table, filename):
    """
    Return the nodatavalue.
    """
    cursor = connections[dbname].cursor()

    # Data retrieval operation - no commit required
    cursor.execute(
        """
        SELECT
            ST_BandNoDataValue(rast)
        FROM
            %(table)s
        WHERE
            filename='%(filename)s'
        """ % dict(table=table, filename=filename),
    )
    row = cursor.fetchall()

    return row[0][0]
    
