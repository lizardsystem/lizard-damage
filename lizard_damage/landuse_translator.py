# Users can optionally upload their own land use maps. If they do,
# they can also optionally upload an Excel file that translates their
# IDs to our IDs. This module checks, reads, and uses that Excel file.

import logging
import os

import numpy as np
import xlrd

from django.conf import settings

from lizard_damage.models import Unit
from lizard_damage_calculation import table

logger = logging.getLogger(__name__)


class TranslatorException(Exception):
    def __init__(self, description):
        self.description = description
        return super(TranslatorException, self).__init__()


class LanduseTranslator(object):
    NODATA_VALUE = 255

    def __init__(self, path):
        """Only sets path."""
        self.path = path

    def check(self):
        """Checks the Excel file. Needs to check the following:
        - Can the Excel file be opened
        - Are the values readable in the right way
        - Are there no values in the A column that occur more than once
        """

        try:
            excel = xlrd.open_workbook(self.path)
            sheet = excel.sheet_by_index(0)  # First sheet
        except xlrd.XLRDError:
            raise TranslatorException(
                "Kan Excelfile niet openen.")

        if sheet.ncols < 2:
            raise TranslatorException(
                "Eerste sheet van de Excelfile moet minstens 2 kolommen "
                "bevatten.")
        if sheet.nrows <= 1:
            raise TranslatorException(
                "Eerste sheet van de Excelfile moet meer dan 1 " +
                "regel bevatten.")

        translate_dict = {}

        for row in xrange(1, sheet.nrows):
            if any(sheet.cell_type(row, col) != xlrd.XL_CELL_NUMBER
                   for col in (0, 1)):
                raise TranslatorException(
                    "Waarde in {} of {} is geen getal."
                    .format(xlrd.cellname(row, 0),
                            xlrd.cellname(row, 1)))
            from_value = int(sheet.cell_value(row, 0))
            to_value = int(sheet.cell_value(row, 1))

            if from_value in translate_dict:
                raise TranslatorException(
                    "Waarde {} komt meer dan eens voor in kolom A."
                    .format(from_value))
            translate_dict[from_value] = to_value

        self.translate_dict = translate_dict

    def check_with_dataset(self, dataset):
        """Checks the Excel file in combination with a dataset.
        Needs to check the following
        - Is there actually an uploaded landuse dataset
        - Are all the values in that dataset accounted for
        - Are all the values they are translated to known in the damage table

        In case of any errors, TranslatorError with an appropriate
        description is raised."""
        if not hasattr(self, 'translate_dict'):
            # Something else failed before now.
            return

        if not dataset:
            # Shouldn't happen, checked before calling this.
            raise TranslatorException(
                "De landgebruiksdata is niet beschikbaar.")

        band = dataset.GetRasterBand(1)

        # self.nodatavalue is used while translating
        self.nodatavalue = int(band.GetNoDataValue())

        grid = band.ReadAsArray()

        uniques = np.unique(grid)

        for value in uniques:
            if value == self.nodatavalue:
                continue
            if int(value) not in self.translate_dict:
                raise TranslatorException(
                    "De vertaaltabel bevat geen waarde voor '{}'. "
                    "Die waarde komt wel voor op de landgebruikskaart."
                    .format(value))

        # Check if all values are in the default damage table
        default_damage_table_path = os.path.join(settings.BUILDOUT_DIR,
                                                 table.DEFAULT_DAMAGE_TABLE)
        damage_table = table.DamageTable.read_cfg(
            open(default_damage_table_path), units=Unit.objects.all()
        )

        codes = set(damage_table.data)
        for value in sorted(self.translate_dict.values()):
            if value not in codes:
                raise TranslatorException(
                    "De vertaaltabel heeft waarde {} in kolom B, "
                    "maar die waarde komt niet voor de in de schadetabel."
                    .format(value))

    def translate_grid(self, grid):
        """Translates the values in grid so that they are known."""
        grid = grid.astype(np.int)

        # Build a numpy translation array
        maxvalue = max(self.translate_dict)

        if self.nodatavalue is not None:
            # Set all points where the grid is nodata
            # to the first unused value; then put that in
            # the translate dict, so that it will be
            # translated to our NODATA. The reason is
            # that the numpy magic we use below doesn't
            # work with negative numbers.
            grid[grid == self.nodatavalue] = maxvalue + 1
            self.translate_dict[maxvalue + 1] = self.NODATA_VALUE

            # Increment maxvalue because the max value is
            # higher now.
            maxvalue += 1

        translation = np.array([
            # Translate each index to its to_value from
            # the translate dict, or 0 if it's not
            # in there (shouldn't happen).
            self.translate_dict.get(i, 0)
            for i in range(maxvalue + 1)])

        # Numpy magic
        return translation[grid]
