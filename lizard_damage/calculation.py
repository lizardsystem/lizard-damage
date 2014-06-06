"""The calculation happens here.

This module _can not_ import other modules from lizard_damage.
"""

import numpy as np
from . import raster

BUILDING_SOURCES = ('BAG', )

CALC_TYPE_MIN = 1
CALC_TYPE_MAX = 2
CALC_TYPE_AVG = 3

CALC_TYPES = {
    1: 'min',
    2: 'max',
    3: 'avg',
}


def calculate(
        landuse, depth, geo_transform, calc_type, table, month, floodtime,
        repairtime_roads, repairtime_buildings, road_grid_codes,
        get_roads_flooded_for_tile_and_code, logger):
    """
    Calculate damage for an area.

    Input: landuse, depth and floodtime are numpy arrays of the same shape.
    """
    logger.info('Calculating damage')

    # Initialize result array
    result = np.ma.zeros(depth.shape)
    result.mask = depth.mask

    # Track results so far
    roads_flooded_for_tile = {}  # {road-pk: flooded-m2}
    damage = {}                  # {landuse_code: damage}
    damage_area = {}             # {landuse_code: m2}

    area_per_pixel = raster.geo2cellsize(geo_transform)
    default_repairtime = table.header.get_default_repairtime()

    codes_in_use = np.unique(landuse.compressed())

    for code, damage_row in table.data.items():
        damage_area[code] = 0  # Defaults, in case we continue below
        damage[code] = 0

        if code not in codes_in_use:
            continue

        # Where in the landuse grid does this code occur?
        # Note: never empty, because code is in codes_in_use
        index = np.ma.where(landuse, code)

        # Compute direct damage.
        partial_result_direct = (
            area_per_pixel *
            damage_row.to_direct_damage(CALC_TYPES[calc_type]) *
            damage_row.to_gamma_depth(depth[index]) *
            damage_row.to_gamma_floodtime(floodtime[index]) *
            damage_row.to_gamma_month(month)
        )

        # Compute indirect damage, which is different for roads.
        if code in road_grid_codes:
            # Don't add indirect damage for the road yet, only record
            # how much of it is flooded in this tile. This is done so
            # that we don't count a road twice if it is flooded in
            # multiple tiles, and also so that we do count it once in
            # case it is only flooded enough when looking at multiple
            # tiles (there is a 100m2 threshold, if a road is flooded
            # less then there is no indirect damage).
            roads_flooded_for_tile[code] = (
                get_roads_flooded_for_tile_and_code(
                    code=code, depth=depth, geo=geo_transform))
            partial_result_indirect = np.array(0)
        else:
            if damage_row.source in BUILDING_SOURCES:
                repairtime = repairtime_buildings
            else:
                repairtime = default_repairtime

            # Compute normal indirect damage.
            partial_result_indirect = (
                area_per_pixel *
                damage_row.to_gamma_repairtime(repairtime) *
                damage_row.to_indirect_damage(CALC_TYPES[calc_type])
            ) * np.greater(depth[index], 0)  # True evaluates to 1

        # Set damage in the result grid. Indirect road damage not included!
        result[index] = partial_result_direct + partial_result_indirect

        damage_area[code] = np.where(
            np.greater(result[index], 0), area_per_pixel, 0,
        ).sum()
        damage[code] = result[index].sum()

        logger.debug(
            '%s - %s - %s: %.2f dir + %.2f ind = %.2f tot' %
            (
                damage_row.code,
                damage_row.source,
                damage_row.description,
                partial_result_direct.sum(),
                partial_result_indirect.sum(),
                damage[code],
            ),
        )

    return damage, damage_area, result, roads_flooded_for_tile
