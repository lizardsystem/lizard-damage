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

from lizard_damage.models import Unit


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


class DamageWorksheet(object):
    """ Container for worksheet and handy methods. """

    def __init__(self, worksheet):
        self.units = dict((u.name, u) for u in Unit.objects.all())
        self.worksheet = worksheet
        self.blocks = self._get_block_indices()

    def _get_block_indices(self):
        """ Return block indices based on top row headers. """
        block_starts = [i for i, c in enumerate(self.worksheet.rows[0])
                      if c.value is not None] + [len(self.worksheet.rows[0])]
        block_ends = [i - 1 for i in block_starts]
        blocks = zip(block_starts[:-1], block_ends[1:])
      
        # Append single column blocks for headerless columns
        blocks = [(i, i) for i in range(blocks[0][0])] + blocks
       
        return blocks

    def _to_number(self, value):
        """
        Return corrected values for common oddities.
        """
        if isinstance(value, float):
            return value
        if isinstance(value, int):
            return float(value)
        if value == '-':
            return 0.
        if ',' in value:
            return float(value.replace(',', '.'))
        try:
            return float(value)
        except ValueError:
            return value

    def _convert(self, text):
        """
        Convert a field of the form '5,2 /uur' to a valid number in
        si units.
        """
        value, unit = text.split()
        return self.units[unit].to_si(self._to_number(value))
    
    def get_values(self, row, block, correct=False, convert=False):
        """
        Return values for a specific block.
        """
        row = self.worksheet.rows[row]
        blockslice = slice(
            self.blocks[block][0],
            self.blocks[block][1] + 1,
        )
        values = [cell.value for cell in row[blockslice]]
        if correct:
            return map(self._to_number, values)
        if convert:
            return map(self._convert, values)
        return values

    def _merge_headers(self, row1, row2):
        """ Integrate top row and second row headers. """
        h1 = None
        result = []
        for c1, c2 in zip(row1, row2):
            h1 = c1.value if c1.value is not None else h1
            h2 = c2.value 
            if h1 is not None:
                result.append(h1 + ':' + h2)
            else:
                result.append(h2)
        return result
    
