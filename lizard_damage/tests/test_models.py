import os

from django.conf import settings
from django.test import TestCase

from lizard_damage import models
from lizard_damage import calc

import numpy as np


class TestGeoImage(TestCase):
    def test_from_data_with_legend_creates_wgs84_png(self):
        landuse_legend = calc.landuse_legend()
        data = np.zeros((4, 4))

        # Some random RD-ish numbers
        extent = (100000.0, 500000.0, 120000.0, 520000.0)

        slug = 'some_random_slug'

        geo_image = models.GeoImage.from_data_with_legend(
            slug, data, landuse_legend, extent=extent)

        image_path = os.path.join(
            settings.BUILDOUT_DIR, 'var', 'media',
            geo_image.image.name)

        self.assertTrue(os.path.exists(image_path))

        # Check coordinates are WGS84 and > 0
        self.assertTrue(0 < geo_image.north < 90)
        self.assertTrue(0 < geo_image.south < 90)
        self.assertTrue(0 < geo_image.east < 90)
        self.assertTrue(0 < geo_image.west < 90)

        # Cleanup
        os.remove(image_path)
