import os
import shutil
import tempfile

import mock

from django.conf import settings
from django.test import TestCase

from lizard_damage import models
from lizard_damage import calc

import numpy as np

from . import factories


class TestDamageScenario(TestCase):
    def setUp(self):
        pass

    def test_factory(self):
        factories.DamageScenarioFactory.create()

    def test_that_setup_creates_a_scenario(self):
        self.assertEquals(
            models.DamageScenario.objects.filter(
                name="Testscenario").count(),
            0)
        models.DamageScenario.setup(
            "Testscenario", "info@nelen-schuurmans.nl", 0,
            models.DamageScenario.CALC_TYPE_AVG, None, None, None, [])
        self.assertEquals(
            models.DamageScenario.objects.filter(
                name="Testscenario").count(),
            1)


class TestDamageEvent(TestCase):
    def test_factory(self):
        factories.DamageEventFactory.create()


class TestDamageEventWaterlevel(TestCase):
    def test_setup_moves_file_correctly(self):
        source_dir = tempfile.mkdtemp()
        target_dir = tempfile.mkdtemp()

        oldproperty = models.DamageEvent.workdir
        try:
            testfile = os.path.join(source_dir, 'testfile.txt')
            open(testfile, 'w').write("Whee")

            event = factories.DamageEventFactory.create()
            models.DamageEvent.workdir = property(lambda self: target_dir)

            waterlevel = models.DamageEventWaterlevel.setup(
                damage_event=event, waterlevel=testfile)

            result_path = os.path.join(
                target_dir, 'waterlevels',
                str(waterlevel.id), 'testfile.txt')
            self.assertEquals(
                open(result_path).read(),
                "Whee")

        finally:
            # Cleanup
            models.DamageEvent.workdir = oldproperty
            shutil.rmtree(source_dir)
            shutil.rmtree(target_dir)


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
