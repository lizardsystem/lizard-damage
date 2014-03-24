# -*- coding: utf-8 -*-
# (c) Nelen & Schuurmans.  GPL licensed, see LICENSE.rst.
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import absolute_import
from __future__ import division

from osgeo import gdal
from osgeo import gdalconst
from osgeo import ogr
from osgeo import osr

import numpy as np
import logging
import re

logger = logging.getLogger(__name__)


class DamageWorksheet(object):
    """ Container for worksheet and handy methods. """

    def __init__(self, worksheet):
        self.worksheet = worksheet
        self.blocks = self._block_indices()

    def _block_indices(self):
        """ Return block indices based on top row headers. """
        block_starts = [i for i, c in enumerate(self.worksheet.rows[0])
                        if c.value is not None] + [len(self.worksheet.rows[0])]
        block_ends = [i - 1 for i in block_starts]
        blocks = zip(block_starts[:-1], block_ends[1:])

        # Append single column blocks for headerless columns
        blocks = [(i, i) for i in range(blocks[0][0])] + blocks

        return blocks

    def _to_float(self, value):
        """
        Return corrected values for common oddities.
        """
        if isinstance(value, float):
            return value
        if isinstance(value, int):
            return float(value)
        if value == '-':
            return 0.
        if ',' in value:
            return float(value.replace(',', '.'))
        return float(value)

    def _sequence(self, row, block):
        row = self.worksheet.rows[row]
        blockslice = slice(
            self.blocks[block][0],
            self.blocks[block][1] + 1,
        )
        return [cell.value for cell in row[blockslice]]

    def _float_sequence(self, row, block):
        return map(self._to_float, self._sequence(row, block))

    def get_header(self):
        depth = self._float_sequence(1, 5)
        floodtime = self._sequence(1, 6)
        repairtime = self._sequence(1, 7)

        return {
            'depth': depth,
            'floodtime': floodtime,
            'repairtime': repairtime,
        }

    def get_rows(self):
        source = ''
        for i in range(2, len(self.worksheet.rows)):

            # Source is only in table if it changes.
            row_source = self._sequence(i, 0)[0]
            if row_source:
                source = row_source

            code = self._sequence(i, 1)[0]
            description = self._sequence(i, 2)[0]

            damage_keys = ('avg', 'min', 'max', 'unit')

            direct_damage_seq = self._sequence(i, 3)
            indirect_damage_seq = self._sequence(i, 4)
            #  first three values have to be floats, the last one is the unit.
            for j in range(3):
                direct_damage_seq[j] = self._to_float(direct_damage_seq[j])
                indirect_damage_seq[j] = self._to_float(indirect_damage_seq[j])
            direct_damage = dict(zip(damage_keys, direct_damage_seq))
            indirect_damage = dict(zip(damage_keys, indirect_damage_seq))

            gamma_depth = self._float_sequence(i, 5)
            gamma_floodtime = self._float_sequence(i, 6)
            gamma_repairtime = self._float_sequence(i, 7)
            gamma_month = self._float_sequence(i, 8)

            yield {
                'source': source,
                'code': code,
                'description': description,
                'direct_damage': direct_damage,
                'indirect_damage': indirect_damage,
                'gamma_depth': gamma_depth,
                'gamma_floodtime': gamma_floodtime,
                'gamma_repairtime': gamma_repairtime,
                'gamma_month': gamma_month,
            }


NODATAVALUE = -9999

# Some projections
RD = 28992
UTM = 3405
WGS84 = 4326
GOOGLE = 900913

AEQD_PROJ4 = ('+proj=aeqd +a=6378.137 +b=6356.752 +R_A'
              ' +lat_0={lat} +lon_0={lon} +x_0=0 +y_0=0')


def projection_aeqd(lat=None, lon=None):
    sr = osr.SpatialReference()
    sr.ImportFromProj4(str(AEQD_PROJ4.format(lat=lat, lon=lon)))
    return sr.ExportToWkt()


def projection(epsg):
    sr = osr.SpatialReference()
    sr.ImportFromEPSG(epsg)
    return sr.ExportToWkt()


def to_dataset(masked_array,
               geotransform=None,
               projection=None,
               dtype=gdalconst.GDT_Float64):
    """
    Return gdal dataset.
    """

    # Create in memory array
    ds = gdal.GetDriverByName('MEM').Create(
        b'',  # No filename
        masked_array.shape[1],
        masked_array.shape[0],
        1,  # number of bands
        dtype
    )

    # Coordinates
    ds.SetGeoTransform(geotransform)
    ds.SetProjection(projection)

    # Write data
    ds.GetRasterBand(1).WriteArray(masked_array.filled())
    ds.GetRasterBand(1).SetNoDataValue(masked_array.fill_value)
    return ds


def ds2ma(ds, bandnumber=1):
    """
    Return np masked array.
    """
    band = ds.GetRasterBand(bandnumber)
    fill_value = band.GetNoDataValue()
    array = band.ReadAsArray()
    mask = np.equal(array, fill_value)
    masked_array = np.ma.array(array, mask=mask, fill_value=fill_value)
    return masked_array


def reproject(ds_source, ds_match):
    """
    Accepts and returns gdal datasets. Creates a copy of ds_match.
    """
    ds_dest = gdal.GetDriverByName(b'MEM').CreateCopy(b'', ds_match)

    # Fill dest with NoData so that cells where no data is projected
    # to are handled correctly
    ds_dest.GetRasterBand(1).Fill(ds_dest.GetRasterBand(1).GetNoDataValue())

    gdal.ReprojectImage(
        ds_source,
        ds_dest,
        ds_source.GetProjection(),
        ds_dest.GetProjection(),
        gdalconst.GRA_Cubic,  # Not sure if this is a good idea.
    )

    return ds_dest


def geotransform(x, y):
    """ Return geotransform for an x, y grid """
    x0, x1 = x[(0, 0), (0, 1)]
    y0, y1 = y[(0, 1), (0, 0)]
    return (
        x0 - (x1 - x0) / 2.,
        x1 - x0,
        0.,
        y0 - (y1 - y0) / 2.,
        0.,
        y1 - y0,
    )


def rasterize(ds, shapepath):
    """ Return copy of ds with shape rasterized into it. """
    gdal_ds = gdal.GetDriverByName(b'MEM').CreateCopy(b'', ds)
    ogr_ds = ogr.Open(shapepath)
    # shp_copy = ogr.GetDriverByName(b'Memory').CopyDataSource(shp, b'')
    gdal.RasterizeLayer(gdal_ds, (1,), ogr_ds.GetLayer(0), burn_values=(1,))
    return gdal_ds


def dms2dec(dms):
    d, e, f, a, b, c = re.match(
        '''( *[0-9]+)d( *[0-9]+)'( *[0-9]+\.[0-9]+)"E,''' +
        '''( *[0-9]+)d( *[0-9]+)'( *[0-9]+\.[0-9]+)"N''',
        dms).groups()
    return (
        int(a) + int(b) / 60 + float(c) / 3600,
        int(d) + int(e) / 60 + float(f) / 3600,
        )


def ds_empty_copy(ds, bands=1, datatype=gdalconst.GDT_Float64):
    empty = gdal.GetDriverByName(b'MEM').Create(
        b'',
        ds.RasterXSize,
        ds.RasterYSize,
        bands,
        datatype,
    )
    empty.SetProjection(ds.GetProjection())
    empty.SetGeoTransform(ds.GetGeoTransform())
    return empty


def get_geo(ds):
    """ Return tuple (projection, geotransform) """
    return  ds.GetProjection(), ds.GetGeoTransform()


def set_geo(ds, geo):
    """ Put geo in ds """
    ds.SetProjection(geo[0])
    ds.SetGeoTransform(geo[1])
