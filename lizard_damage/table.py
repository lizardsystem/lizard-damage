# -*- coding: utf-8 -*-
# (c) Nelen & Schuurmans.  GPL licensed, see LICENSE.rst.
from __future__ import (
  print_function,
  unicode_literals,
  absolute_import,
  division,
)

import openpyxl
import numpy

from lizard_damage.models import Unit
from lizard_damage.utils import DamageWorksheet

class DirectDamage(object):
    """ Everything per square meter. """
    def __init__(self, avg, min, max, unit):
        self.unit = Unit.objects.get(name=unit)
        self.avg, self.min, self.max = self.unit.to_si(
            (avg, min, max),
        )


class DamageHeader(object):
    """ Store header ranges, added from table importer."""
    def __init__(self, depth, time, period):
        self.depth = depth
        self.time = time
        self.period = period


class DamageRow(object):
    """ Container for single land use data. """
    def __init__(
        self, code, description, direct_damage,
        gamma_depth, gamma_time, gamma_month, header
    ):
        self.code = code
        self.description = description
        self.direct_damage = direct_damage

        self._header = header
        self._gamma_depth = gamma_depth
        self._gamma_time = gamma_time
        self._gamma_month = gamma_month

    def gamma_depth(self, depth):
        """ Return gamma array for depth array. """
        return numpy.interp(depth, self._header.depth, self._gamma_depth)

    def gamma_time(self, time):
        """ Return gamma for time. """
        return numpy.interp(time, self._header.time, self._gamma_time)

    def gamma_month(self, month):
        """ Return gamma for period. """
        return self._gamma_month[month - 1]


class DamageTable(object):
    """
    Container for damagetable properties, including import and export methods
    """

    XLSX_TYPE = 1

    def __init__(self, from_type, from_filename):
        self.importers[from_type](self, from_filename)

        
    @classmethod
    def from_xlsx(cls, filename):
        return cls(from_type=cls.XLSX_TYPE, from_filename=filename)
        

    def _import_from_xlsx(self, filename):
        workbook = openpyxl.reader.excel.load_workbook(filename)
        worksheet = DamageWorksheet(workbook.get_active_sheet())


        time_with_units = worksheet.get_values(1,5)

        self.header = DamageHeader(
            depth=worksheet.get_values(1, 4, correct=True),
            time=worksheet.get_values(1, 5, convert=True),
            period=range(1, len(worksheet.get_values(1, 6)) + 1),

        )
        
        self.data = {}
        for i in range(2, len(worksheet.worksheet.rows)):
            damage_row = DamageRow(
                code = worksheet.get_values(i, 0)[0],
                description = worksheet.get_values(i, 1)[0],
                direct_damage = DirectDamage(
                    *worksheet.get_values(i, 2, correct=True)),
                gamma_depth = worksheet.get_values(i, 4, correct=True),
                gamma_time = worksheet.get_values(i, 5, correct=True),
                gamma_month =  worksheet.get_values(i, 6, correct=True),
                header = self.header,
            )

            self.data[damage_row.code] = damage_row

    # Here the importers are registered.
    importers = {
        XLSX_TYPE: _import_from_xlsx,
    }
