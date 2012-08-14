# -*- coding: utf-8 -*-
# (c) Nelen & Schuurmans.  GPL licensed, see LICENSE.rst.
from __future__ import (
  print_function,
  unicode_literals,
  absolute_import,
  division,
)

import numpy
import logging

logger = logging.getLogger(__name__)


def calculate(use, depth, area_per_pixel, table, month, time):
    """
    Calculate stuff. Note the hardcoded area_per_pixel!
    """
    result = numpy.ma.zeros(depth.shape)
    result.mask = depth.mask

    count = {}
    damage = {}
    damage_area = {}

    for code, dr in table.data.items():

        index = (numpy.ma.equal(use, code))
        count[code] = numpy.count_nonzero(index)

        result[index] = (
            area_per_pixel *
            dr.to_direct_damage('max') *
            dr.to_gamma_depth(depth[index]) *
            dr.to_gamma_time(time) *
            dr.to_gamma_month(month)
        )

        damage_area[code] = numpy.count_nonzero(
            numpy.greater(result[index], 0)
        ) * area_per_pixel

        # The sum of an empty masked array is 'masked', so check that.
        if count[code] > 0:
            damage[code] = result[index].sum()
        else:
            damage[code] = 0.

        logger.debug(dr.description + ': ' + unicode(damage[code]))

    return damage, count, damage_area, result
