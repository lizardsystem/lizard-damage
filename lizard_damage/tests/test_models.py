import logging
import os
import shutil
import tempfile

from django.conf import settings
from django.test import TestCase

from lizard_damage import models
from lizard_damage import calc

import numpy as np

from . import factories


logger = logging.getLogger(__name__)

TESTDATA_DIR = os.path.join(settings.BUILDOUT_DIR, 'testdata')


class TestDamageScenario(TestCase):
    def test_directory_url(self):
        scenario = factories.DamageScenarioFactory.create()
        self.assertEquals(
            scenario.directory_url,
            '/media/damagescenario/{}'.format(scenario.id))

    def test_that_setup_creates_a_scenario(self):
        self.assertEquals(
            models.DamageScenario.objects.filter(
                name="Testscenario").count(),
            0)
        models.DamageScenario.setup(
            "Testscenario", "info@nelen-schuurmans.nl", 0,
            models.DamageScenario.CALC_TYPE_AVG, 2, None, None, None, [])
        self.assertEquals(
            models.DamageScenario.objects.filter(
                name="Testscenario").count(),
            1)

    def test_delete_deletes_files(self):
        scenario = factories.DamageScenarioFactory.create()

        workdir = scenario.workdir

        testfile = os.path.join(workdir, 'test.txt')
        f = open(testfile, 'w')
        f.write("Test!")
        f.close()

        self.assertTrue(os.path.exists(testfile))
        scenario.delete()
        self.assertFalse(os.path.exists(testfile))

    def test_delete_deletes_damage_events(self):
        scenario = factories.DamageScenarioFactory.create()
        event = factories.DamageEventFactory.create(scenario=scenario)

        event_id = event.id

        self.assertTrue(
            models.DamageEvent.objects.filter(pk=event_id).exists())
        scenario.delete()
        self.assertFalse(
            models.DamageEvent.objects.filter(pk=event_id).exists())


class TestDamageEvent(TestCase):

    def setUp(self):
        models.Unit.fill_units_table()

    def test_calculation_doesnt_crash(self):
        scenario = factories.DamageScenarioFactory(
            damagetable_file=os.path.join(
                TESTDATA_DIR, 'dt.cfg'))

        event = factories.DamageEventFactory.create(scenario=scenario)

        models.DamageEventWaterlevel.objects.create(
            event=event, waterlevel_path=os.path.join(
                TESTDATA_DIR, 'wl.asc'))

        with self.settings(LIZARD_DAMAGE_DATA_ROOT=TESTDATA_DIR):
            event.calculate(logger)

    def test_calculation_creates_results(self):
        scenario = factories.DamageScenarioFactory(
            damagetable_file=os.path.join(
                TESTDATA_DIR, 'dt.cfg'))

        event = factories.DamageEventFactory.create(scenario=scenario)

        models.DamageEventWaterlevel.objects.create(
            event=event, waterlevel_path=os.path.join(
                TESTDATA_DIR, 'wl.asc'))

        with self.settings(LIZARD_DAMAGE_DATA_ROOT=TESTDATA_DIR):
            event.calculate(logger)

        # Re-get from database to get saved version
        event = models.DamageEvent.objects.get(pk=event.id)

        # Check if a table has been saved
        self.assertTrue(event.parsed_table)

        # Check if a zipfile exists and is greater than size 0
        zippath = os.path.join(event.workdir, 'result.zip')
        self.assertTrue(os.path.exists(zippath))
        self.assertTrue(os.stat(zippath).st_size > 0)


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
