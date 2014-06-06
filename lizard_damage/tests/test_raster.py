from osgeo import gdal

from django.test import TestCase

from lizard_damage import raster


class TestGetAreaWithData(TestCase):
    def test_correct_area_all_data(self):
        driver = gdal.GetDriverByName('mem')
        dataset = driver.Create(
            '', 10, 10, 1, gdal.GDT_Byte,
            )
        dataset.SetGeoTransform([
            126000.0, 25.0, 0.0, 503749.0, 0.0, -25.0])

        dataset.GetRasterBand(1).Fill(1)
        self.assertEquals(
            raster.get_area_with_data(dataset),
            62500)  # 10 * 10 * 25 * 25

        dataset.GetRasterBand(1).SetNoDataValue(0)
        self.assertEquals(
            raster.get_area_with_data(dataset),
            62500)  # 10 * 10 * 25 * 25

        dataset.GetRasterBand(1).SetNoDataValue(1)
        self.assertEquals(
            raster.get_area_with_data(dataset),
            0)  # 10 * 10 * 25 * 25


class TestExtentWithinExtent(TestCase):
    def test_some_extent(self):
        waterextent = (126001.0, 502501.5, 126999.0, 503749.0)
        landuseextent = (126000.0, 502550.0, 127000.0, 503750.0)

        self.assertFalse(
            raster.extent_within_extent(
                inner_extent=waterextent, outer_extent=landuseextent))

    def test_some_other_extent(self):
        waterextent = (126001.0, 502501.5, 126999.0, 503749.0)
        landuseextent = (126000.0, 502500.0, 127000.0, 503750.0)

        self.assertTrue(
            raster.extent_within_extent(
                inner_extent=waterextent, outer_extent=landuseextent))
