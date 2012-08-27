# -*- coding: utf-8 -*-
# (c) Nelen & Schuurmans.  GPL licensed, see LICENSE.rst.
from __future__ import (
  print_function,
  # unicode_literals,
  absolute_import,
  division,
)

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

from lizard_damage import (
    raster,
    calc,
    table,
)

import logging
import numpy
import os

logger = logging.getLogger(__name__) 


def show(arr):
        """ Visualize an array with PIL """
        import Image
        tmp = numpy.ma.copy(arr)
        tmp = (tmp - tmp.min()) * 255. / (tmp.max() - tmp.min())
        tmp[tmp.mask] = 0
        Image.fromarray(tmp[::4,::4]).show()

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
           

def main():
    ds_wl_filename = os.path.join(
        settings.DATA_ROOT, 'waterlevel', 'ws_test1.asc',
    )
    ds_wl_original = raster.import_dataset(ds_wl_filename, 'AAIGrid')
    dt_path = os.path.join(settings.BUILDOUT_DIR, 'data/damagetable/dt.cfg')
    with open(dt_path) as cfg:
        dt = table.DamageTable.read_cfg(cfg)


    overall_area = {}
    overall_damage = {}
    for ahn_name in raster.get_ahn_names(ds_wl_original):
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
        
        damage, count, area, result = calc.calculate(
            use=lgn, depth=depth,
            area_per_pixel=area_per_pixel,
            table=dt, month=6,
            floodtime=20 * 3600, repairtime=None
        )
        print(result.sum())
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



class Command(BaseCommand):
    args = 'Command args'
    help = 'Command help'

    def handle(self, *args, **options):
        main()
