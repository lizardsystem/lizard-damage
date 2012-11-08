# -*- coding: utf-8 -*-
# (c) Nelen & Schuurmans.  GPL licensed, see LICENSE.rst.

from __future__ import print_function
from __future__ import unicode_literals
from __future__ import absolute_import
from __future__ import division

from django.template.defaultfilters import slugify
from django.core.files import File

from lizard_damage import tasks
from lizard_damage import models

from osgeo import gdal
from osgeo import gdalconst

import collections
import numpy as np
import os
import re
import shutil
import sys
import tempfile
import zipfile


"""
from second zip, check if names unchanged.
for each tile, for each event, calculate.
"""
PATTERN = re.compile(
    'schade_([a-z][0-9][0-9][a-z][a-z][0-9]_[0-9][0-9])_T(.*)\.asc$'
)


def _index_and_filenames(event):
    """
    Return index, filename
    """
    filenames = event.get_filenames()
    result = []
    for filename in filenames:
        match = re.match(PATTERN, filename)
        if match:
            result.append((match.group(1), match.string))

    return result


def calculate_risk(iterable):
    """ 
    Return risk.

    Iterable consists of {'damage':damage, 'time': time} elements.

        >>> damage = [1000,500,200,100,10,2]
        >>> time = [250,100,50,25,10,5]
        >>> iterable = [dict(damage=d, time=t) for d, t in zip(damage, time)]
        >>> calculate_risk(iterable)
        18.9

    """
    risk = None
    for element in iterable:
        current_damage = element['damage']
        current_time = element['time']
        if risk is None:
            risk = current_damage / current_time
        else:
            risk += (
                (1 / current_time - 1 / previous_time) * 
                ((current_damage + previous_damage) / 2)
            )
        previous_time = current_time
        previous_damage = current_damage
    return risk


def iter_risk_and_damage(jobs):
    """ 
    """
    for element in jobs:
        event = element['event']
        filename = element['filename']
        yield dict(
            damage=event.get_data(filename),
            time=event.repetition_time,
        )


def create_risk_map(damage_scenario, logger):
    """
    """
    logger.debug('Calculating risk maps for {}'.format(damage_scenario))
    logger.debug('removing earlier risk results.')
    riskresults = damage_scenario.riskresult_set.all()
    for riskresult in riskresults:
        riskresult.zip_risk.delete()
        riskresult.delete()


    tempdir = tempfile.mkdtemp()
    zipriskpath = os.path.join(
        tempdir, 
        'risk_' + slugify(damage_scenario.name) + '.zip',
    )

    events = damage_scenario.damageevent_set.order_by('-repetition_time').all()

    jobdict = collections.defaultdict(list)
    for event in events:
        for index, filename in _index_and_filenames(event):
            jobdict[index].append(dict(event=event, filename=filename))

    for index, jobs in jobdict.items():
        logger.debug('calculating risk for {} ({} rasters)'.format(index, len(jobs)))
        risk = calculate_risk(iter_risk_and_damage(jobs))
        
        # Create dataset
        logger.debug('Writing to zipfile.')
        dataset = gdal.GetDriverByName(b'mem').Create(
            b'', risk.shape[1], risk.shape[0], 1, gdalconst.GDT_Float64,
        )
        band = dataset.GetRasterBand(1)
        band.SetNoDataValue(float(risk.fill_value))
        band.WriteArray(risk.filled())

        # Write to asc and add to zip
        ascpath = os.path.join(tempdir, str('risk_' + index + '.asc'))
        gdal.GetDriverByName(b'aaigrid').CreateCopy(ascpath, dataset)
        with zipfile.ZipFile(zipriskpath, 'a', zipfile.ZIP_DEFLATED) as archive:
            archive.write(ascpath, os.path.basename(ascpath))
        os.remove(ascpath)

    riskresult = damage_scenario.riskresult_set.create()

    logger.debug('Adding zip to result dir')
    with open(zipriskpath, 'rb') as zipriskfile:
        riskresult.zip_risk.save(
            os.path.basename(zipriskpath),
            File(zipriskfile),
        )
    riskresult.save()
    shutil.rmtree(tempdir)


