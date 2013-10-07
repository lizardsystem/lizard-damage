# -*- coding: utf-8 -*-
# (c) Nelen & Schuurmans.  GPL licensed, see LICENSE.rst.

from __future__ import print_function
from __future__ import unicode_literals
from __future__ import absolute_import
from __future__ import division

from django.template.defaultfilters import slugify
from django.core.files import File

from osgeo import gdal
from osgeo import gdalconst

import collections
import numpy as np
import os
import re
import shutil
import tempfile
import zipfile


"""
from second zip, check if names unchanged.
for each tile, for each event, calculate.
"""
PATTERN = re.compile(
    'schade_([a-z][0-9][0-9][a-z][a-z][0-9]_[0-9][0-9])_T(.*)\.asc$'
)

RISK_PATTERN = re.compile(
    'risk_([a-z][0-9][0-9][a-z][a-z][0-9]_[0-9][0-9])\.asc$'
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

    Iterable consists of {'geotransform':geotransform,
                          'damage':damage,
                          'time': time} elements.

        >>> damage = [1000,500,200,100,10,2]
        >>> time = [250,100,50,25,10,5]
        >>> iterable = [dict(damage=d, time=t, geotransform=None)
        ...             for d, t in zip(damage, time)]
        >>> calculate_risk(iterable)['risk']
        18.9

    """
    risk = None
    previous_time = None
    previous_damage = None

    for element in iterable:
        current_damage = element['damage']
        current_time = element['time']
        if risk is None:
            risk = current_damage / current_time
        else:
            risk_increment = (
                (1 / current_time - 1 / previous_time) *
                ((current_damage + previous_damage) / 2)
            )
            risk = np.ma.sum([risk, risk_increment], 0)

        previous_time = current_time
        previous_damage = current_damage

    # Note the geotransform from the last element is returned.
    return dict(geotransform=element['geotransform'], risk=risk)


def iter_risk_and_damage(jobs):
    """
    generator of dicts with data for each job.
    """
    for element in jobs:
        event = element['event']
        filename = element['filename']
        geotransform, damage = event.get_data(filename)
        yield dict(
            geotransform=geotransform,
            damage=damage,
            time=event.repetition_time,
        )


def create_risk_map(damage_scenario, logger):
    """
    """
    logger.info('Calculating risk maps for {}'.format(damage_scenario))
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

        logger.debug('calculating risk for {} ({} rasters)'.format(
            index, len(jobs)),
        )

        calc_dict = calculate_risk(iter_risk_and_damage(jobs))
        risk = calc_dict['risk']
        geotransform = calc_dict['geotransform']

        # Create dataset
        logger.debug('Writing to zipfile.')
        dataset = gdal.GetDriverByName(b'mem').Create(
            b'', risk.shape[1], risk.shape[0], 1, gdalconst.GDT_Float64,
        )
        dataset.SetGeoTransform(geotransform)
        band = dataset.GetRasterBand(1)
        band.SetNoDataValue(float(risk.fill_value))
        band.WriteArray(risk.filled())

        # Write to asc and add to zip
        ascpath = os.path.join(tempdir, str('risk_' + index + '.asc'))
        gdal.GetDriverByName(b'aaigrid').CreateCopy(ascpath, dataset)
        with zipfile.ZipFile(zipriskpath,
                             'a', zipfile.ZIP_DEFLATED) as archive:
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


def create_benefit_map(benefit_scenario, logger):
    logger.info('Calculating benefit map for {}'.format(benefit_scenario))

    # Delete earlier results
    logger.debug('removing earlier benefit results.')
    if benefit_scenario.zip_result:
        benefit_scenario.zip_result.delete()
    benefit_scenario.zip_result = None

    # Create tempdir
    tempdir = tempfile.mkdtemp()
    zipbenefitpath = os.path.join(
        tempdir,
        'benefit_' + slugify(benefit_scenario.name) + '.zip',
    )

    # Get the names of the zipfiles from the first zip
    with zipfile.ZipFile(benefit_scenario.zip_risk_a) as archive:
        jobs = []
        for info in archive.filelist:
            match = re.match(RISK_PATTERN, info.filename)
            if match:
                jobs.append((match.group(1), match.string))

    for index, filename in jobs:
        logger.debug(
            'calculating benefit for {}'.format(index, len(jobs))
        )
        before = benefit_scenario.get_data_before(filename)
        after = benefit_scenario.get_data_after(filename)
        benefit = np.ma.array([before['data'],
                               -after['data']]).sum(0) / 0.055

        # Create dataset
        logger.debug('Writing to zipfile.')
        dataset = gdal.GetDriverByName(b'mem').Create(
            b'', benefit.shape[1], benefit.shape[0], 1, gdalconst.GDT_Float64,
        )
        dataset.SetGeoTransform(after['geotransform'])
        band = dataset.GetRasterBand(1)
        band.SetNoDataValue(float(benefit.fill_value))
        band.WriteArray(benefit.filled())

        # Write to asc and add to zip
        ascpath = os.path.join(tempdir, str('benefit_' + index + '.asc'))
        gdal.GetDriverByName(b'aaigrid').CreateCopy(ascpath, dataset)
        with zipfile.ZipFile(
            zipbenefitpath, 'a', zipfile.ZIP_DEFLATED,
        ) as archive:
            archive.write(ascpath, os.path.basename(ascpath))
        os.remove(ascpath)

    logger.debug('Adding zip to result dir')
    with open(zipbenefitpath, 'rb') as zipbenefitfile:
        benefit_scenario.zip_result.save(
            os.path.basename(zipbenefitpath),
            File(zipbenefitfile),
        )
    benefit_scenario.save()

    shutil.rmtree(tempdir)
