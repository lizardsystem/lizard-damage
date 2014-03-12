# (c) Nelen & Schuurmans.  GPL licensed, see LICENSE.rst.
# -*- coding: utf-8 -*-

"""In order to make calc.calc_damage_for_waterlevel shorter, small
subroutines of it were factored out and placed here."""

from __future__ import unicode_literals
from __future__ import print_function
from __future__ import absolute_import
from __future__ import division

import logging
import os
import shutil
import tempfile

from lizard_damage import raster

logger = logging.getLogger(__name__)


def correct_single_ascfile(ascpath):
    """ Remove non-native headers in ascfile. """
    asc_headers = [
        'ncols', 'nrows', 'xllcorner', 'yllcorner', 'cellsize', 'nodata_value',
    ]
    ascfile = open(ascpath)
    for i, line in enumerate(ascfile):
        if line.split()[0].lower() in asc_headers:
            if i == 0:
            # File ok, nothing to do.
                return
            break

    # Write the last (correct) line and remaining lines to tempfile
    logger.warning('Correcting file: %s' % ascpath)
    tempfd, temppath = tempfile.mkstemp()

    with os.fdopen(tempfd, 'w') as asctempfile:
        asctempfile.write(line)  # First good line
        asctempfile.writelines(ascfile)  # Remaining lines
    ascfile.close()

    shutil.move(temppath, ascpath)


def correct_ascfiles(input_list):
    """
    test ascfiles for known faulty behaviour and correct them if needed
    """
    for filename in input_list:
        # Skip anything non-asc
        if not os.path.splitext(filename)[-1].lower() == '.asc':
            continue
        correct_single_ascfile(ascpath=filename)


def read_ascfiles(ascfiles, logger=logger):
    correct_ascfiles(ascfiles)  # TODO: do it elsewhere
    datasets = [raster.import_dataset(ascfile, 'AAIGrid')
                for ascfile in ascfiles]
    logger.info('waterlevel_ascfiles: %r' % ascfiles)
    logger.info('waterlevel_datasets: %r' % datasets)
    for fn, ds in zip(ascfiles, datasets):
        if ds is None:
            logger.error('data source is not available,'
                         ' please check %s' % fn)
            return None

    return datasets
