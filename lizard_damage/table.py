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
import os

from django.conf import settings
from django.utils import simplejson as json
from lizard_damage import (
    models,
    utils,
)

CFG_HEADER_SECTION = 'algemeen'
CFG_HEADER_FLOODTIME = 'inundatieduur'
CFG_HEADER_REPAIRTIME = 'herstelperiode'
CFG_HEADER_DEPTH = 'inundatiediepte'
#CFG_HEADER_DEFAULT_FLOODTIME = 'standaard_inundatieduur'
#CFG_HEADER_DEFAULT_REPAIRTIME = 'standaard_herstelperiode'
#CFG_HEADER_DEFAULT_MONTH = 'standaard_maand'

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
CFG_ROW_G_FLOODTIME = 'gamma_inundatieduur'
CFG_ROW_G_REPAIRTIME = 'gamma_herstelperiode'
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
    def __init__(self, units, depth, floodtime, repairtime,
                 default_floodtime='12 uur',
                 default_repairtime='1 dag', default_month=9):
        self._units = units
        self.depth = depth

        self.floodtime = floodtime
        self._floodtime_in_seconds = [self._to_seconds(t)
                                      for t in self.floodtime]

        self.repairtime = repairtime
        self._repairtime_in_seconds = [self._to_seconds(t)
                                      for t in self.repairtime]

        self.default_floodtime = default_floodtime
        self._default_floodtime_in_seconds = self._to_seconds(
            self.default_floodtime,
        )

        self.default_repairtime = default_repairtime
        self._default_repairtime_in_seconds = self._to_seconds(
            self.default_repairtime,
        )

        self.default_month = default_month

    def _to_seconds(self, text):
        value, unit = text.split()
        seconds = self._units[unit].to_si(float(value))
        return seconds

    def get_depth(self):
        return self.depth

    def get_floodtime(self):
        """ Return list of time in seconds. """
        return self._floodtime_in_seconds

    def get_repairtime(self):
        """ Return list of time in seconds. """
        return self._repairtime_in_seconds

    def get_default_floodtime(self):
        """ Return list of time in seconds. """
        return self._default_floodtime_in_seconds

    def get_default_repairtime(self):
        """ Return list of time in seconds. """
        return self._default_repairtime_in_seconds


class DamageRow(object):
    """ Container for single land use data. """
    def __init__(self, units, header,
                 source, code, description,
                 direct_damage, indirect_damage, gamma_depth,
                 gamma_floodtime, gamma_repairtime, gamma_month):

        self._units = units
        self.header = header

        self.source = source
        self.code = code
        self.description = description
        self.direct_damage = Damage(**direct_damage)
        self.indirect_damage = Damage(**indirect_damage)

        self.gamma_depth = gamma_depth
        self.gamma_floodtime = gamma_floodtime
        self.gamma_repairtime = gamma_repairtime
        self.gamma_month = gamma_month

    def to_gamma_depth(self, depth):
        """ Return gamma array for depth array. """
        return numpy.interp(depth, self.header.depth, self.gamma_depth)

    def to_gamma_floodtime(self, floodtime):
        """ Return gamma for floodtime. """
        return numpy.interp(
            floodtime,
            self.header.get_floodtime(),
            self.gamma_floodtime
        )

    def to_gamma_repairtime(self, repairtime):
        """ Return gamma for repairtime. """
        return numpy.interp(
            repairtime,
            self.header.get_repairtime(),
            self.gamma_repairtime
        )

    def to_gamma_month(self, month):
        """ Return gamma for period. """
        return self.gamma_month[month - 1]

    def to_direct_damage(self, damage='max'):
        damage_unit = self._units[self.direct_damage.unit]
        return damage_unit.to_si(getattr(self.direct_damage, damage))

    def to_indirect_damage(self, damage='max'):
        damage_unit = self._units[self.indirect_damage.unit]
        return damage_unit.to_si(getattr(self.indirect_damage, damage))

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
        logger.debug('Writing damage table %s.', file_object.name)
        c = ConfigParser.ConfigParser()
        c.add_section(CFG_HEADER_SECTION)
        c.set(CFG_HEADER_SECTION, CFG_HEADER_DEPTH,
            json.dumps(self.header.depth),
        )
        c.set(CFG_HEADER_SECTION, CFG_HEADER_FLOODTIME,
            json.dumps(self.header.floodtime)
        )
        c.set(CFG_HEADER_SECTION, CFG_HEADER_REPAIRTIME,
            json.dumps(self.header.repairtime)
        )
        #c.set(CFG_HEADER_SECTION, CFG_HEADER_DEFAULT_FLOODTIME,
            #self.header.default_floodtime
        #)
        #c.set(CFG_HEADER_SECTION, CFG_HEADER_DEFAULT_REPAIRTIME,
            #self.header.default_repairtime
        #)
        #c.set(CFG_HEADER_SECTION, CFG_HEADER_DEFAULT_MONTH,
            #self.header.default_month
        #)

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
            c.set(section, CFG_ROW_G_FLOODTIME, json.dumps(dr.gamma_floodtime))
            c.set(section, CFG_ROW_G_REPAIRTIME, json.dumps(
                    dr.gamma_repairtime))
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
                    floodtime=json.loads(cp.get(section,
                                         CFG_HEADER_FLOODTIME)),
                    repairtime=json.loads(cp.get(section,
                                         CFG_HEADER_REPAIRTIME)),
                    #default_floodtime=(cp.get(section,
                                       #CFG_HEADER_DEFAULT_FLOODTIME)),
                    #default_repairtime=(cp.get(section,
                                       #CFG_HEADER_DEFAULT_REPAIRTIME)),
                    #default_month=(cp.get(section,
                                       #CFG_HEADER_DEFAULT_MONTH)),
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
                    gamma_depth=json.loads(cp.get(section,
                                                  CFG_ROW_G_DEPTH)),
                    gamma_floodtime=json.loads(cp.get(section,
                                                 CFG_ROW_G_FLOODTIME)),
                    gamma_repairtime=json.loads(cp.get(section,
                                                 CFG_ROW_G_REPAIRTIME)),
                    gamma_month=json.loads(cp.get(section,
                                                  CFG_ROW_G_MONTH)),
                )

    # Here the importers are registered.
    importers = {
        XLSX_TYPE: _import_from_xlsx,
        CFG_TYPE: _import_from_cfg,
    }


def read_damage_table(dt_path):
    """Returns possibly changed dt_path and damage table"""
    if dt_path is None:
        damage_table_path = 'data/damagetable/dt.cfg'
        dt_path = os.path.join(settings.BUILDOUT_DIR, damage_table_path)
    with open(dt_path) as cfg:
        dt = DamageTable.read_cfg(cfg)
        return dt_path, dt
