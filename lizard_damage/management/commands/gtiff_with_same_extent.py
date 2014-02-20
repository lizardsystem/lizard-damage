# -*- coding: utf-8 -*-
# (c) Nelen & Schuurmans.  GPL licensed, see LICENSE.rst.

from __future__ import print_function
from __future__ import unicode_literals
from __future__ import absolute_import
from __future__ import division

from django.core.management.base import BaseCommand
from django.core.management.base import CommandError

import gdal
import numpy as np
import os


class Command(BaseCommand):
    args = '<input dataset filename> <output dataset filename> <value>'
    help = ('Create a geotiff with the same extent as the input '
            'dataset, and one value everywhere.')

    def handle(self, *args, **options):
        if len(args) != 3:
            raise CommandError("Wrong amount of arguments.")

        dataset_in_fn, dataset_out_fn, value = args
        dataset_in_fn = str(dataset_in_fn)
        dataset_out_fn = str(dataset_out_fn)

        if not os.path.exists(dataset_in_fn):
            raise CommandError("{} does not exist.".format(dataset_in_fn))

        dataset_in = gdal.Open(dataset_in_fn)

        if not dataset_in:
            raise CommandError("Couldn't open {}.".format(dataset_in_fn))

        driver = gdal.GetDriverByName(b"GTiff")

        dataset_out = driver.Create(
            dataset_out_fn, dataset_in.RasterXSize, dataset_in.RasterYSize,
            1, gdal.GDT_Float32)

        dataset_out.SetGeoTransform(dataset_in.GetGeoTransform())

        raster = np.zeros((dataset_in.RasterYSize, dataset_in.RasterXSize),
                          dtype=np.float)

        raster += float(value.replace('m', '-'))

        dataset_out.GetRasterBand(1).WriteArray(raster)
