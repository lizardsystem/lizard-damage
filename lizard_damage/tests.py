# (c) Nelen & Schuurmans.  GPL licensed, see LICENSE.txt.

from django.test import TestCase

from lizard_damage import (
    table,
    calc,
)

import numpy


class ExampleTest(TestCase):
    fixtures = ['unit.json']

    def setUp(self):
        with open('testdata/damagetable_test1.cfg') as cfg:
            self.dt = table.DamageTable.read_cfg(cfg)
        depth = numpy.ones((4, 4)) / 2.
        use = numpy.zeros((4, 4))
        use[:, 2:4] = 1
        mask = numpy.equal(depth, 1)
        mask[2:4, :] = True

        self.depth = numpy.ma.array(depth, mask=mask)
        self.use = numpy.ma.array(use, mask=mask)

    def test_calculation(self):
        self.damage, self.count, self.area, self.result = calc.calculate(
            use=self.use, depth=self.depth, area_per_pixel=1,
            table=self.dt, month=7,
            floodtime=20 * 3600, repairtime=None,
        )
        self.assertEquals(1, 1)
