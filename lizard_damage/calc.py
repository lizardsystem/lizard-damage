# -*- coding: utf-8 -*-
# (c) Nelen & Schuurmans.  GPL licensed, see LICENSE.rst.
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import absolute_import
from __future__ import division

"""What is left in here is a pretty random collection of helper functions."""

import numpy as np

import logging
import os
import tempfile
import traceback

from matplotlib import colors
from PIL import Image
import json
import subprocess

from django.core.files import File
from django.template.defaultfilters import slugify

from lizard_damage import raster
from lizard_damage.models import DamageEventResult
from lizard_damage.models import RD
from lizard_damage.models import extent_from_geotiff

logger = logging.getLogger(__name__)


def convert_tif_to_png(filename_tif, filename_png):
    im = Image.open(filename_tif)
    im.save(filename_png, 'PNG')


def process_result(
        logger, damage_event, damage_event_index, result, scenario_name):
    errors = 0
    # result[0] is the result zip file name in temp dir.
    with open(result[0], 'rb') as doc_file:
        try:
            if damage_event.result:
                logger.warning('Deleting existing results...')
                damage_event.result.delete()  # Delete old results
            logger.info('Saving results...')
            damage_event.result.save(
                '%s%i.zip' % (
                    slugify(scenario_name),
                    damage_event_index + 1),
                File(doc_file), save=True)
            damage_event.save()
        except:
            logger.error('Exception saving zipfile. Too big?')
            for exception_line in traceback.format_exc().split('\n'):
                logger.error(exception_line)
            errors = 1
        os.remove(result[0])  # remove temp file, whether it was saved
                              # or not

        # result[2] is the table in a data structure
        damage_event.table = json.dumps(result[2])

        # Store references to GeoImage objects
        damage_event.set_slugs(
            landuse_slugs=','.join(result[3]),
            height_slugs=','.join(result[4]),
            depth_slugs=','.join(result[5]))

        damage_event.save()

        # result[1] is a list of png files to be uploaded to the django db.
        if damage_event.damageeventresult_set.count() >= 0:
            logger.warning("Removing old images...")
            for damage_event_result in (
                    damage_event.damageeventresult_set.all()):
                damage_event_result.image.delete()
                damage_event_result.delete()
        for img in result[1]:
            # convert filename_png to geotiff,
            #import pdb; pdb.set_trace()

            logger.info('Warping png to tif... %s' % img['filename_png'])
            command = (
                'gdalwarp %s %s -t_srs "+proj=latlong '
                '+datum=WGS83" -s_srs "%s"' % (
                    img['filename_png'], img['filename_tif'], RD.strip()))
            logger.info(command)
            # Warp png file, output is tif.
            subprocess.call([
                'gdalwarp', img['filename_png'], img['filename_tif'],
                '-t_srs', "+proj=latlong +datum=WGS84",
                '-s_srs', RD.strip()])

            img['extent'] = extent_from_geotiff(img['filename_tif'])
            # Convert it back to png
            convert_tif_to_png(img['filename_tif'], img['filename_png'])

            damage_event_result = DamageEventResult(
                damage_event=damage_event,
                west=img['extent'][0],
                south=img['extent'][1],
                east=img['extent'][2],
                north=img['extent'][3])
            logger.info('Uploading %s...' % img['filename_png'])
            with open(img['filename_png'], 'rb') as img_file:
                damage_event_result.image.save(
                    img['dstname'] % damage_event.slug,
                    File(img_file), save=True)
            damage_event_result.save()
            os.remove(img['filename_png'])
            os.remove(img['filename_pgw'])
            os.remove(img['filename_tif'])
        logger.info('Result has %d images' % len(result[1]))
    return errors


def mkstemp_and_close():
    """
    Make a tempfile and close it. It can be reopened later on.

    Return filename.

    Use this instead of tempfile.mktemp(), because there is a
    racecondition going on there.
    """
    handle, filename = tempfile.mkstemp()
    os.close(handle)
    return filename


def landuse_legend():
    # defaults
    result = ['#dddddd'] * 100

    # specifics
    result[2] = '#cc0000'  # Woonfunctie
    result[3] = result[2]
    result[4] = result[2]
    result[5] = result[2]
    result[6] = result[2]
    result[7] = result[2]  # Kassen
    result[8] = result[2]
    result[9] = result[2]
    result[10] = result[2]
    result[11] = result[2]
    result[12] = result[2]
    result[13] = result[2]
    result[14] = result[2]

    result[21] = '#5555ee'  # Water

    result[22] = '#888888'  # Primaire Wegen
    result[23] = result[22]
    result[24] = result[22]

    result[25] = '#007000'  # Bos/Natuur
    result[26] = '#00bb00'  # bebouwd gebied
    result[27] = result[25]
    result[28] = result[25]

    result[29] = result[26]  # Begraafplaats, medium groen
    result[30] = '#33ff33'  # Gras
    result[31] = result[30]

    result[32] = result[22]  # Spoorbaanlichaam

    result[41] = result[30]

    result[42] = '#ffff00'  # Mais

    result[43] = '#db5800'  # Aardappelen
    result[44] = result[43]

    result[45] = result[42]  # Granen

    result[46] = result[43]  # Overige akkerbouw

    #result[48] = result[42]  # Braakliggend terrein tussen kassen Glastuinbouw

    result[49] = result[43]  # Boomgaard

    result[50] = result[43]  # Bloembollen

    result[52] = result[30]  # Gras overig

    result[53] = result[25]  # Bos/Natuur

    result[56] = result[21]  # Water (LGN)

    #result[58] = result[25]  # Bebouwd gebied

    result[61] = result[22]  # Spoorwegen terrein
    result[62] = result[22]  # Primaire wegen
    result[63] = result[22]
    result[64] = result[22]
    result[65] = result[22]

    result[66] = result[29]  # Sportterrein
    result[67] = result[29]  # Volkstuinen

    result[68] = result[22]  # Recreatief terrein
    result[69] = result[22]  # Glastuinbouwterrein

    result[70] = result[25]  # Bos/Natuur
    result[71] = result[25]

    result[72] = result[21]  # Zee
    result[73] = result[21]  # Zoet water

    #result[98] = result[2]  # erf

    #result[99] = result[2]  # Overig/Geen landgebruik

    return result


def slug_for_landuse(ahn_name):
    """Name as slug in GeoImage"""
    return 'landuse_%s' % ahn_name


def slug_for_height(ahn_name, min_value, max_value):
    """Name as slug in GeoImage"""
    return 'height_%s_%d_%d' % (
        ahn_name, int(min_value * 1000), int(max_value * 1000))


def slug_for_depth(ahn_name, min_value, max_value):
    """Name as slug in GeoImage

    min_value and max_values are depths
    """
    return 'depth_%s_%d_%d' % (
        ahn_name, int(min_value * 1000), int(max_value * 1000))


def get_colorizer(max_damage):
    """ Return colormap and normalizer. """
    # Note the hardcoded area_per_pixel
    area_per_pixel = 0.25
    f = 1 / max_damage * area_per_pixel

    cdict = {
        'red': (
            (0.0,       0, 0),
            (00.01 * f, 0, 1),
            (1.0,       1, 1),
        ),
        'green': (
            (0.,        0.00, 0.00),
            (00.01 * f, 0.00, 1.00),
            (00.50 * f, 1.00, 0.65),
            (10.00 * f, 0.65, 0.00),
            (1.,        0.00, 0.00),
        ),
        'blue': (
            (0., 0, 0),
            (1., 0, 0),
        ),
    }

    # Beware of the amount of quantization levels, it DOES matter
    colormap = colors.LinearSegmentedColormap('damage', cdict, N=1024)
    normalize = colors.Normalize(vmin=0, vmax=max_damage)

    def colorize(data):
        return colormap(normalize(data), bytes=True)

    return colorize


def write_result(name, ma_result, ds_template):
    ds_result = raster.init_dataset(ds_template, nodatavalue=-9999)
    raster.fill_dataset(ds_result, ma_result)
    raster.export_dataset(
        filepath=name,
        ds=ds_result,
    )


def write_table(
        name, damage, area, damage_table, meta=[], include_total=False):
    """
    Write results in a csv table on disk.

    Optionally provide meta in a list and they are on top.

    i.e. [['name', 'amahoela'], ['description','moehaha']]
    """
    with open(name, 'w') as resultfile:
        # Some meta data
        for l in meta:
            resultfile.write('%s\r\n' % (','.join(l)))

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
        if include_total:
            resultfile.write(
                '%s,%s,%s,%s,%s\r\n' %
                (
                    '-',
                    '-',
                    'Totaal',
                    sum(area.values()) / 10000.,
                    sum(damage.values()),
                )
            )
        for code, dr in damage_table.data.items():
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


def result_as_dict(damage, area, damage_table):
    """
    return data structure of result which can be stored and looped
    """

    head = [{'display': 'bron', 'key': 'source'},
            {'display': 'code', 'key': 'code'},
            {'display': 'omschrijving', 'key': 'description'},
            {'display': 'oppervlakte met schade [ha]', 'key': 'area_ha'},
            {'display': 'schade', 'key': 'damage'}]

    data = [{
        'source': None,
        'code': None,
        'description': 'Totaal',
        'area_ha': sum(area.values()) / 10000.,
        'damage': sum(damage.values()),
    }] + [{
        'source': dr.source,
        'code': dr.code,
        'description': dr.description,
        'area_ha': area[dr.code] / 10000.,
        'damage': damage[dr.code],
    } for code, dr in damage_table.data.items()]

    return (head, data)


def write_image(name, values):
    """
    Create png image from values.

    Values is a 2d np array
    """
    colorize = get_colorizer(max_damage=11)
    rgba = colorize(values)
    rgba[:, :, 3] = np.where(rgba[:, :, 0], 153, 0)
    Image.fromarray(rgba).save(name, 'PNG')


def add_roads_to_image(roads, image_path, extent):
    """Draw roads into an existing PNG."""

    # Get old image that needs indirect road damage visualized
    image = Image.open(image_path)

    # Rasterize all roads that have indirect damage
    size = image.size
    geotransform = [
        extent[0],
        (extent[2] - extent[0]) / size[0],
        0,
        extent[3],
        0,
        (extent[1] - extent[3]) / size[1],
        ]
    roadgrid = raster.get_mask(
        roads=roads,
        shape=image.size[::-1],
        geo=(b'', geotransform),
        )

    # Paste it into the old image and overwrite the image file
    rgba = np.uint8([[[0, 0, 0, 153]]]) * roadgrid.reshape(
        roadgrid.shape[0], roadgrid.shape[1], 1
        )
    image_roads_rgb = Image.fromstring(
        'RGB',
        (rgba.shape[1], rgba.shape[0]),
        rgba[:, :, 0:3].tostring(),
        )
    image_roads_mask = Image.fromstring(
        'L',
        (rgba.shape[1], rgba.shape[0]),
        rgba[:, :, 3].tostring(),
        )
    image.paste(image_roads_rgb, None, image_roads_mask)
    image.save(image_path)
