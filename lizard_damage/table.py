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
import logging
import numpy

from django.utils import simplejson as json
from lizard_damage import (
    models,
    utils,
)

CFG_HEADER_SECTION = 'algemeen'
CFG_HEADER_TIME = 'inundatieduur'
CFG_HEADER_DEPTH = 'inundatiediepte'

CFG_ROW_SOURCE = 'bron'
CFG_ROW_DESCRIPTION = 'omschrijving'
CFG_ROW_D_UNIT = 'direct_eenheid'
CFG_ROW_D_AVG = 'direct_gem'
CFG_ROW_D_MIN = 'direct_min'
CFG_ROW_D_MAX = 'direct_max'
CFG_ROW_I_UNIT = 'indirect_eenheid'
CFG_ROW_I_AVG = 'indirect_gem'
CFG_ROW_I_MIN = 'indirect_min'
CFG_ROW_I_MAX = 'indirect_max'
CFG_ROW_G_DEPTH = 'gamma_inundatiediepte'
CFG_ROW_G_TIME = 'gamma_periode'
CFG_ROW_G_MONTH = 'gamma_maand'

logger = logging.getLogger(__name__) 


class Damage(object):
    def __init__(self, avg, min, max, unit):
        self.avg = float(avg)
        self.min = float(min)
        self.max = float(max)
        self.unit = unit


class DamageHeader(object):
    """ Store header ranges, added from table importer."""
    def __init__(self, units, depth, time):
        self._units = units
        self.depth = depth
        self.time = time
        self._time_in_seconds = []
        for t in time:
            v, u = t.split()
            self._time_in_seconds.append(self._units[u].to_si(float(v)))

    def get_depth(self):
        return self.depth

    def get_time(self):
        return self._time_in_seconds


class DamageRow(object):
    """ Container for single land use data. """
    def __init__(
        self, units, header,
        source, code, description, direct_damage, indirect_damage,
        gamma_depth, gamma_time, gamma_month
    ):
        self._units = units
        self.header = header

        self.source = source
        self.code = code
        self.description = description
        self.direct_damage = Damage(**direct_damage)
        self.indirect_damage = Damage(**indirect_damage)

        self.gamma_depth = gamma_depth
        self.gamma_time = gamma_time
        self.gamma_month = gamma_month

    def to_gamma_depth(self, depth):
        """ Return gamma array for depth array. """
        return numpy.interp(depth, self.header.depth, self.gamma_depth)

    def to_gamma_time(self, time):
        """ Return gamma for time. """
        return numpy.interp(
            time,
            self.header.get_time(),
            self.gamma_time
        )

    def to_gamma_month(self, month):
        """ Return gamma for period. """
        return self.gamma_month[month - 1]

    def to_direct_damage(self, damage='max'):
        damage_unit = self._units[self.direct_damage.unit]
        return damage_unit.to_si(getattr(self.direct_damage, damage))

    def __repr__(self):
        return '<' + self.__class__.__name__ + ': ' + self.description + '>'


class DamageTable(object):
    """
    Container for damagetable properties, including import and export methods

    Instantiate it from a configuration file, such as:

        with open('data/damagetable/Schadetabel.xlsx', 'rb') as xlsx:
            dt = table.DamageTable.read_xlsx(xlsx)
        with open('data/damagetable/dt.cfg') as cfg:
            dt = table.DamageTable.read_cfg(cfg)
    """

    XLSX_TYPE = 1
    CFG_TYPE = 2

    def __init__(self, from_type, from_filename):
        self._units = dict((u.name, u) for u in models.Unit.objects.all())
        self.importers[from_type](self, from_filename)

    @classmethod
    def read_xlsx(cls, filename):
        return cls(from_type=cls.XLSX_TYPE, from_filename=filename)

    @classmethod
    def read_cfg(cls, filename):
        return cls(from_type=cls.CFG_TYPE, from_filename=filename)

    def write_cfg(self, file_object):
        logger.debug('Writeing damage table %s.', file_object.name)
        c = ConfigParser.ConfigParser()
        c.add_section(CFG_HEADER_SECTION)
        c.set(CFG_HEADER_SECTION, CFG_HEADER_DEPTH,
            json.dumps(self.header.depth),
        )
        c.set(CFG_HEADER_SECTION, CFG_HEADER_TIME,
            json.dumps(self.header.time)
        )

        for code, dr in self.data.items():
            section = unicode(code)
            c.add_section(section)
            c.set(section, CFG_ROW_SOURCE, dr.source)
            c.set(section, CFG_ROW_DESCRIPTION, dr.description)
            c.set(section, CFG_ROW_D_UNIT, dr.direct_damage.unit)
            c.set(section, CFG_ROW_D_AVG, dr.direct_damage.avg)
            c.set(section, CFG_ROW_D_MIN, dr.direct_damage.min)
            c.set(section, CFG_ROW_D_MAX, dr.direct_damage.max)
            c.set(section, CFG_ROW_I_UNIT, dr.indirect_damage.unit)
            c.set(section, CFG_ROW_I_AVG, dr.indirect_damage.avg)
            c.set(section, CFG_ROW_I_MIN, dr.indirect_damage.min)
            c.set(section, CFG_ROW_I_MAX, dr.indirect_damage.max)
            c.set(section, CFG_ROW_G_DEPTH, json.dumps(dr.gamma_depth))
            c.set(section, CFG_ROW_G_TIME, json.dumps(dr.gamma_time))
            c.set(section, CFG_ROW_G_MONTH, json.dumps(dr.gamma_month))

        c.write(file_object)

    def _import_from_xlsx(self, file_object):
        logger.debug('Reading damage table %s.', file_object.name)
        workbook = openpyxl.reader.excel.load_workbook(file_object)
        worksheet = utils.DamageWorksheet(workbook.get_active_sheet())

        self.data = {}
        self.header = DamageHeader(units=self._units, **worksheet.get_header())
        for row in worksheet.get_rows():
            damage_row = DamageRow(
                header=self.header, units=self._units, **row
            )
            self.data[damage_row.code] = damage_row

    def _import_from_cfg(self, file_object):
        logger.debug('Reading damage table %s.', file_object.name)
        self.data = {}
        cp = ConfigParser.ConfigParser()
        cp.readfp(file_object)
        for section in cp.sections():
            if section == CFG_HEADER_SECTION:
                self.header = DamageHeader(
                    units=self._units,
                    depth=json.loads(cp.get(section, CFG_HEADER_DEPTH)),
                    time=json.loads(cp.get(section, CFG_HEADER_TIME)),
                )
            else:
                code = int(section)
                self.data[code] = DamageRow(
                    header=self.header,
                    units=self._units,
                    source=cp.get(section, CFG_ROW_SOURCE),
                    code=code,
                    description=cp.get(section, CFG_ROW_DESCRIPTION),
                    direct_damage=dict(
                        unit=cp.get(section, CFG_ROW_D_UNIT),
                        avg=cp.get(section, CFG_ROW_D_AVG),
                        min=cp.get(section, CFG_ROW_D_MIN),
                        max=cp.get(section, CFG_ROW_D_MAX),
                    ),
                    indirect_damage=dict(
                        unit=cp.get(section, CFG_ROW_I_UNIT),
                        avg=cp.get(section, CFG_ROW_I_AVG),
                        min=cp.get(section, CFG_ROW_I_MIN),
                        max=cp.get(section, CFG_ROW_I_MAX),
                    ),
                    gamma_depth=json.loads(cp.get(section, CFG_ROW_G_DEPTH)),
                    gamma_time=json.loads(cp.get(section, CFG_ROW_G_TIME)),
                    gamma_month=json.loads(cp.get(section, CFG_ROW_G_MONTH)),
                )

    # Here the importers are registered.
    importers = {
        XLSX_TYPE: _import_from_xlsx,
        CFG_TYPE: _import_from_cfg,
    }
