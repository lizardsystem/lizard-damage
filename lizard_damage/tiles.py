# (c) Nelen & Schuurmans.  GPL licensed, see LICENSE.rst.
# -*- coding: utf-8 -*-

"""Helper functions for opening tiles of the AHN and LGN."""

# Python 3 is coming
from __future__ import unicode_literals
from __future__ import print_function
from __future__ import absolute_import
from __future__ import division

import os

import gdal

from django.conf import settings

from . import utils


def get_tile_filename(datadir, ahn_name):
    """Return bytestring path to the needed tile. datadir is
    'data_ahn' or 'data_lgn'."""
    return os.path.join(
        settings.DATA_ROOT, datadir, ahn_name[1:4],
        ahn_name + '.tif').encode('utf8')


def get_tile_dataset(datadir, ahn_name):
    return gdal.Open(get_tile_filename(datadir, ahn_name))


def get_ahn_dataset(ahn_name, logger=None):
    ds = get_tile_dataset('data_ahn', ahn_name)
    if ds is None and logger:
        logger.warning('No height data for {}'.format(ahn_name))
    return ds


def get_lgn_dataset(ahn_name, logger=None):
    ds = get_tile_dataset('data_lgn', ahn_name)
    if ds is None and logger:
        logger.warning('No landuse data for {}'.format(ahn_name))
    return ds


def get_datasets_for_tile(
    ahn_name,
    alternative_heights_dataset=None,
    alternative_landuse_dataset=None,
    logger=None):
    """
    Return datasets (waterlevel, height, landuse).

    Input:
        ahn_name: ahn subunit name

        If an alternative_heights_dataset or
        alternative_landuse_dataset is given, use that. But first we
        do retrieve the standard ahn/lgn datasets, and reproject the
        alternatives to have the same dimensions.

    Output:
        ds_ahn, ds_lgn, orig_ds_lgn

        Of these, the first two should be used for computations (they
        may contain data from custom uploaded height/landuse
        datasets), the last is guaranteed to be from the normal
        AHN/LGN (to be used for caching purposes, don't put custom
        stuff in the tile cache).

        This is less relevant for the height dataset as the cache slug
        for that has min and max value in it, so different datasets
        are likely (but not certain) to miss each other in the cache.
    """
    ds_ahn = get_ahn_dataset(ahn_name)
    orig_ds_lgn = ds_lgn = get_lgn_dataset(ahn_name)

    if ds_lgn and alternative_landuse_dataset is not None:
        logger.info('Reproject alternative dataset to same dimensions as LGN')
        ds_lgn = utils.reproject(alternative_landuse_dataset, ds_lgn)

    if ds_ahn and alternative_heights_dataset is not None:
        logger.info('Reproject alternative dataset to same dimensions as AHN')
        ds_ahn = utils.reproject(alternative_heights_dataset, ds_ahn)

    return ds_ahn, ds_lgn, orig_ds_lgn
