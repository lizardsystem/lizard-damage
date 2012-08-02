# -*- coding: utf-8 -*-
# (c) Nelen & Schuurmans.  GPL licensed, see LICENSE.rst.
from __future__ import (
  print_function,
#  unicode_literals,
  absolute_import,
  division,
)

import openpyxl

class DamageTable(object):
    """
    Container for damagetable properties, including import and export methods
    """
    @classmethod
    def from_xlsx(cls, filename):
        workbook = openpyxl.reader.excel.load_workbook(filename)
        worksheet = workbook.get_active_sheet()

        damage_table = cls()
        damage_table.data = [c.value for r in worksheet.rows for c in r]
        
        return damage_table



    

