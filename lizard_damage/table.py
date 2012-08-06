# -*- coding: utf-8 -*-
# (c) Nelen & Schuurmans.  GPL licensed, see LICENSE.rst.
from __future__ import (
  print_function,
  unicode_literals,
  absolute_import,
  division,
)

import openpyxl
from lizard_damage.models import Unit

class DepthGamma(object):
    def __init__(self, depth, gamma):

        self.depth = depth
        self.gamma = gamma

    def to_gamma(self, depth):
        """ Return gamma array for depth array. """
        return numpy.interp(array, self.duration, self.gamma)


class DurationGamma(object):
    def __init__(self, duration, gamma):
        self.duration = duration
        self.gamma = gamma

    def to_gamma(self, duration):
        """ Return gamma for duration. """
        return numpy.interp(duration, self.duration, self.gamma)
  

class PeriodGamma(object):
    def __init__(self, month, gamma):
        self.month = month
        self.gamma = gamma
        self.lookup = dict(zip(month,gamma))

    def to_gamma(self, period):
        """ Return gamma for period. """
        return self.lookup.get(period)
        numpy.interp(array, self.duration, self.gamma)


class DirectDamage(object):
    """ Everything per square meter. """
    def __init__(self, dmg_avg, dmg_min, dmg_max, dmg_unit):
        self.unit = Unit.objects.get(name=dmg_unit)
        self.dmg_avg, self.dmg_min, self.dmg_max = self.unit.to_si(
            (dmg_avg, dmg_min, dmg_max),
        )

class IndirectDamage(object):
    pass


class DamageRanges(object):
    """ Store header ranges, added from table importer."""
    def __init__(self, depth, duration, period):
        self.depth = depth
        self.duration = duration
        self.period = period


class DamageWorksheet(object):
    """ Container for worksheet and handy methods. """

    def __init__(self, worksheet):
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
        if isinstance(value, (float, int)):
            return value
        if value == '-':
            return 0.
        if ',' in value:
            return float(value.replace(',', '.'))
        else:
            raise ValueError('Unsupported value!')
    
    def get_values(self, row, block, correct=False):
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


        duration_with_units = worksheet.get_values(1,5)



        
        
        self.ranges = DamageRanges(
            depth=worksheet.get_values(1, 4, True),
            duration=worksheet.get_values(1, 5),
            period=worksheet.get_values(1, 6),

        )

        import ipdb; ipdb.set_trace() 
        print(worksheet.get_values(3,5))


        # eenheden ombouwen, zie models.
        # interpolation of g(depth)
        

    importers = {
        XLSX_TYPE: _import_from_xlsx,
    }



    

