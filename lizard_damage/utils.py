# -*- coding: utf-8 -*-
# (c) Nelen & Schuurmans.  GPL licensed, see LICENSE.rst.
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import logging

logger = logging.getLogger(__name__) 


class DamageWorksheet(object):
    """ Container for worksheet and handy methods. """

    def __init__(self, worksheet):
        self.worksheet = worksheet
        self.blocks = self._block_indices()

    def _block_indices(self):
        """ Return block indices based on top row headers. """
        block_starts = [i for i, c in enumerate(self.worksheet.rows[0])
                        if c.value is not None] + [len(self.worksheet.rows[0])]
        block_ends = [i - 1 for i in block_starts]
        blocks = zip(block_starts[:-1], block_ends[1:])

        # Append single column blocks for headerless columns
        blocks = [(i, i) for i in range(blocks[0][0])] + blocks

        return blocks

    def _to_float(self, value):
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
        return float(value)

    def _sequence(self, row, block):
        row = self.worksheet.rows[row]
        blockslice = slice(
            self.blocks[block][0],
            self.blocks[block][1] + 1,
        )
        return [cell.value for cell in row[blockslice]]

    def _float_sequence(self, row, block):
        return map(self._to_float, self._sequence(row, block))

    def get_header(self):
        depth = self._float_sequence(1, 5)
        time = self._sequence(1, 6)

        return {
            'time': time,
            'depth': depth,
        }

    def get_rows(self):
        source = ''
        for i in range(2, len(self.worksheet.rows)):

            # Source is only in table if it changes.
            row_source = self._sequence(i, 0)[0]
            if row_source:
                source = row_source
                
            code = self._sequence(i, 1)[0]
            description = self._sequence(i, 2)[0]

            damage_keys = ('avg', 'min', 'max', 'unit')

            direct_damage_seq = self._sequence(i, 3)
            indirect_damage_seq = self._sequence(i, 4)
            #  first three values have to be floats, the last one is the unit.
            for j in range(3):
                direct_damage_seq[j] = self._to_float(direct_damage_seq[j])
                indirect_damage_seq[j] = self._to_float(indirect_damage_seq[j])
            direct_damage = dict(zip(damage_keys, direct_damage_seq))
            indirect_damage = dict(zip(damage_keys, indirect_damage_seq))
            
            gamma_depth = self._float_sequence(i, 5)
            gamma_time = self._float_sequence(i, 6)
            gamma_month = self._float_sequence(i, 7)

            yield {
                'source': source,
                'code': code,
                'description': description,
                'direct_damage': direct_damage,
                'indirect_damage': direct_damage,
                'gamma_depth': gamma_depth,
                'gamma_time': gamma_time,
                'gamma_month': gamma_month,
            }
