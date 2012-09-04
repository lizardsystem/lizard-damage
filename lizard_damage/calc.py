# -*- coding: utf-8 -*-
# (c) Nelen & Schuurmans.  GPL licensed, see LICENSE.rst.
from __future__ import (
  print_function,
  unicode_literals,
  absolute_import,
  division,
)

import numpy
import logging
import os

from django.conf import settings
from lizard_damage import raster
from lizard_damage import table

logger = logging.getLogger(__name__)


def calculate(use, depth,
              area_per_pixel, table,
              month, floodtime, repairtime):
    """
    Calculate damage for an area.

    Input: land use, water depth, area_per_pixel, damage table, month
    of flooding, flood time and repair time.
    """
    result = numpy.ma.zeros(depth.shape)
    result.mask = depth.mask

    count = {}
    damage = {}
    damage_area = {}

    for code, dr in table.data.items():

        index = (numpy.ma.equal(use, code))
        count[code] = numpy.count_nonzero(index)

        result[index] = (
            area_per_pixel *
            dr.to_direct_damage('max') *
            dr.to_gamma_depth(depth[index]) *
            dr.to_gamma_floodtime(floodtime) *
            dr.to_gamma_month(month)
        )

        damage_area[code] = numpy.count_nonzero(
            numpy.greater(result[index], 0)
        ) * area_per_pixel

        # The sum of an empty masked array is 'masked', so check that.
        if count[code] > 0:
            damage[code] = result[index].sum()
        else:
            damage[code] = 0.

        logger.debug(dr.source + ' - ' +
                     dr.description + ': ' + unicode(damage[code]))

    return damage, count, damage_area, result


def write_result(name, ma_result, ds_template):
    ds_result = raster.init_dataset(ds_template, nodatavalue=-1234)
    raster.fill_dataset(ds_result, ma_result)
    raster.export_dataset(
        filepath=name,
        ds=ds_result,
    )

def write_table(name, damage, area, dt):
    with open(name, 'w') as resultfile:
        resultfile.write(
            '"%s","%s","%s","%s","%s"\r\n' %
            (
                'bron',
                'code',
                'omschrijving',
                'oppervlakte met schade [ha]',
                'schade',
            )
        )
        for code, dr in dt.data.items():
            resultfile.write(
                '%s,%s,%s,%s,%s\r\n' %
                (
                    dr.source,
                    dr.code,
                    dr.description,
                    area[dr.code] / 10000.,
                    damage[dr.code],
                )
            )

def calc_damage_for_waterlevel(
    ds_wl_filename,
    damage_table_path=None,
    month=9, floodtime=20*3600, repairtime=None, logger=logger):
    """
    Calculate damage for provided waterlevel file.

    in:
    - waterlevel file (provided by user)
    - damage table (optionally provided by user, else default)
    - AHN: models.AhnIndex refer to ahn tiles available on <settings.DATA_ROOT>/...
    - month, floodtime (s), repairtime (s): provided by user, used by calc.calculate

    out:
    - per ahn tile an .asc and .csv (see write_result and write_table)
    - schade_totaal.csv (see write_table)
    """
    ds_wl_original = raster.import_dataset(ds_wl_filename, 'AAIGrid')

    if damage_table_path is None:
        damage_table_path = 'data/damagetable/dt.cfg'
    dt_path = os.path.join(settings.BUILDOUT_DIR, damage_table_path)
    with open(dt_path) as cfg:
        dt = table.DamageTable.read_cfg(cfg)

    overall_area = {}
    overall_damage = {}
    for ahn_name in raster.get_ahn_names(ds_wl_original):
        logger.info("calculating damage for tile %s..." % ahn_name)
        ds_wl, ds_ahn, ds_lgn = raster.get_ds_for_tile(
            ahn_name=ahn_name,
            ds_wl_original=ds_wl_original,
            method='filesystem',
        )

        # Prepare data for calculation
        wl = raster.to_masked_array(ds_wl)
        try:
            ahn = raster.to_masked_array(ds_ahn, mask=wl.mask)
            lgn = raster.to_masked_array(ds_lgn, mask=wl.mask)
        except ValueError as e:
            raise CommandError(e)
        depth = wl - ahn
        area_per_pixel = raster.get_area_per_pixel(ds_wl)

        damage, count, area, result = calculate(
            use=lgn, depth=depth,
            area_per_pixel=area_per_pixel,
            table=dt, month=month,
            floodtime=floodtime, repairtime=repairtime
        )
        #print(result.sum())
        logger.debug("result sum: %f" % result.sum())
        write_result(
            name='schade_' + ahn_name + '.asc',
            ma_result=result,
            ds_template=ds_ahn,
        )
        write_table(
            name='schade_' + ahn_name + '.csv',
            damage=damage,
            area=area,
            dt=dt,
        )
        for k in damage.keys():
            if k in overall_damage:
                overall_damage[k] += damage[k]
            else:
                overall_damage[k] = damage[k]

        for k in area.keys():
            if k in overall_area:
                overall_area[k] += area[k]
            else:
                overall_area[k] = area[k]

        del ds_wl, ds_ahn, ds_lgn
        del lgn, depth, wl
        del result

    write_table(
        name='schade_totaal.csv',
        damage=overall_damage,
        area=overall_area,
        dt=dt,
    )
