import mock
import os

from django.test import TestCase

from lizard_damage.conf import settings
from lizard_damage import tiles


class TestTiles(TestCase):
    def test_get_tile_dataset_opens_correct(self):
        """Don't laugh at this test, it actually caught a bug -- I
        forgot to 'return' in get_tile_filename :-)"""
        mock_dataset = mock.MagicMock()

        with mock.patch('gdal.Open', return_value=mock_dataset) as mocked:
            dataset = tiles.get_ahn_dataset('testing')
            self.assertEquals(dataset, mock_dataset)

            expected_path = os.path.join(
                settings.BUILDOUT_DIR, 'var', 'data', 'data_ahn',
                'est', 'testing.tif').encode('utf8')

            mocked.assert_called_with(expected_path)
