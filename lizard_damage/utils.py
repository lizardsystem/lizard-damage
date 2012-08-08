# -*- coding: utf-8 -*-
# (c) Nelen & Schuurmans.  GPL licensed, see LICENSE.rst.
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from lizard_damage.models import Unit


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

    def _convert(self, )
        """
        Convert a field of the form '5,2 /uur' to a valid number in
        si units.
        """
        value, unit = text.split()
        return self.units[unit].to_si(self._to_number(value))

    def _get_sequence(self, row, block):
        row = self.worksheet.rows[row]
        blockslice = slice(
            self.blocks[block][0],
            self.blocks[block][1] + 1,
        )
        return [cell.value for cell in row[blockslice]]

    def get_text_values(self, row, block):
        return map(unicode, self._get_sequence(row, block))

    def get_numeric_values(self, row, block):
        return map(self._to_number, self._get_sequence(row, block))


        
