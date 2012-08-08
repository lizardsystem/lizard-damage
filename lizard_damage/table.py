# -*- coding: utf-8 -*-
# (c) Nelen & Schuurmans.  GPL licensed, see LICENSE.rst.
from __future__ import (
  print_function,
  unicode_literals,
  absolute_import,
  division,
)

import ConfigParser
import openpyxl
import numpy

from lizard_damage import (
    models,
    utils,
)


class DirectDamage(object):
    def __init__(self, avg, min, max, unit):
        self.avg = avg
        self.min = min
        self.max = max
        self.unit = unit


class DamageHeader(object):
    """ Store header ranges, added from table importer."""
    def __init__(self, depth, time_value, time_unit):
        self.depth = depth
        self.time_value = time_value
        self.time_unit = time_unit


class DamageRow(object):
    """ Container for single land use data. """
    def __init__(
        self, code, description, direct_damage,
        gamma_depth, gamma_time, gamma_month, header
    ):
        self.header = header

        self.code = code
        self.description = description
        self.direct_damage = direct_damage

        self._gamma_depth = gamma_depth
        self._gamma_time = gamma_time
        self._gamma_month = gamma_month

    def gamma_depth(self, depth):
        """ Return gamma array for depth array. """
        return numpy.interp(depth, self.header.depth, self._gamma_depth)

    def gamma_time(self, time):
        """ Return gamma for time. """
            time_with_units = zip(self.header.time_value,
                                  self.header.time_unit)
            seconds = [u.to_si(t) for t, u in time_with_units]
        return numpy.interp(time, seconds, self._gamma_time)

    def gamma_month(self, month):
        """ Return gamma for period. """
        return self._gamma_month[month - 1]


class DamageTable(object):
    """
    Container for damagetable properties, including import and export methods
    """

    XLSX_TYPE = 1
    CFG_TYPE = 2

    def __init__(self, from_type, from_filename):
        self.importers[from_type](self, from_filename)
        self.units = dict((u.name, u) for u in models.Unit.objects.all())

    @classmethod
    def read_xlsx(cls, filename):
        return cls(from_type=cls.XLSX_TYPE, from_filename=filename)

    def write_cfg(self, file_object):
        c = ConfigParser.ConfigParser()
        c.add_section('algemeen')
        c.set('algemeen', 'inundatiediepte', self.header.depth)
        c.set('algemeen', 'inundatieduur', self.header.time)

        for code, dr in self.data.items():
            section = unicode(code)
            c.add_section(section)
            c.set(section, 'omschrijving', dr.description)
            direct_unit = dr.direct_damage.unit

            c.set(section, 'direct_eenheid', direct_unit)
            c.set(section, 'direct_gem',
                direct_unit.from_si(dr.direct_damage.avg))
            c.set(section, 'direct_min',
                direct_unit.from_si(dr.direct_damage.min))
            c.set(section, 'direct_max',
                direct_unit.from_si(dr.direct_damage.max))
            c.set(section, 'gamma_inundatie', 'bla')
                

        c.write(file_object)

    def _import_from_xlsx(self, filename):
        workbook = openpyxl.reader.excel.load_workbook(filename)
        worksheet = utils.DamageWorksheet(workbook.get_active_sheet())

        self.header = DamageHeader(
            depth=worksheet.get_values(1, 4, correct=True),
            time=worksheet.get_values(1, 5, convert=True),
            
            period=range(1, len(worksheet.get_values(1, 6)) + 1),
        )

        self.data = {}
        for i in range(2, len(worksheet.worksheet.rows)):
            damage_row = DamageRow(
                code=worksheet.get_values(i, 0)[0],
                description=worksheet.get_values(i, 1)[0],
                direct_damage=DirectDamage(
                    *worksheet.get_values(i, 2, correct=True)),
                gamma_depth=worksheet.get_values(i, 4, correct=True),
                gamma_time=worksheet.get_values(i, 5, correct=True),
                gamma_month=worksheet.get_values(i, 6, correct=True),
                header=self.header,
            )

            self.data[damage_row.code] = damage_row

    def _import_from_cfg(file_object):
        pass
        

    # Here the importers are registered.
    importers = {
        XLSX_TYPE: _import_from_xlsx,
        CFG_TYPE: _import_from_cfg,
    }
