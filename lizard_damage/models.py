# -*- coding: utf-8 -*-
# (c) Nelen & Schuurmans.  GPL licensed, see LICENSE.rst.
from __future__ import (
    print_function,
    unicode_literals,
    absolute_import,
    division,
)

import collections
import datetime
import json
import logging
import os
import random
import re
import shutil
import string
import subprocess
import tempfile
import zipfile

from PIL import Image
from osgeo import gdal
from pyproj import Proj
import matplotlib as mpl
import numpy as np

from django.contrib.gis.db import models
from django.core.urlresolvers import reverse
from django.core.files import File
from django.core.files.uploadedfile import UploadedFile

from lizard_damage import raster
from lizard_damage import results
from lizard_damage import tools
from lizard_damage import utils
from lizard_damage.conf import settings
from lizard_damage_calculation import calculation
from lizard_damage_calculation import table

logger = logging.getLogger(__name__)

# from django.utils.translation import ugettext_lazy as _

RD = str(
    "+proj=sterea +lat_0=52.15616055555555 +lon_0=5.38763888888889 +k=0.999908"
    " +x_0=155000 +y_0=463000 +ellps=bessel +units=m +towgs84=565.2369,"
    "50.0087,465.658,-0.406857330322398,0.350732676542563,-1.8703473836068,"
    "4.0812 +no_defs <>"
)

WGS84 = str('+proj=latlong +datum=WGS84')

rd_proj = Proj(RD)
wgs84_proj = Proj(WGS84)


def gdal_open(path):
    """Make sure path is a bytestring"""
    if isinstance(path, unicode):
        path = path.encode('utf-8')
    return gdal.Open(path)


def extent_from_geotiff(filename):
    ds = gdal_open(filename)
    return extent_from_dataset(ds)


def extent_from_dataset(ds):
    width = ds.RasterXSize
    height = ds.RasterYSize
    gt = ds.GetGeoTransform()
    minx = gt[0]
    miny = gt[3] + width * gt[4] + height * gt[5]
    maxx = gt[0] + width * gt[1] + height * gt[2]
    maxy = gt[3]
    return (minx, miny, maxx, maxy)


def write_geotransform_pgw(name, geotransform):
    """Write PGW based on geotransform"""
    f = open(name, 'w')
    x0, dxx, dxy, y0, dyx, dyy = geotransform
    for gt in dxx, dxy, dyx, dyy, x0, y0:
        f.write("{0}\n".format(gt))
    f.close()


def friendly_filesize(size):
    if size > 1024 * 1024 * 1024 * 1024 * 1024:
        # Just for fun
        return '%0.1fPB' % (float(size) / (1024 * 1024 * 1024 * 1024 * 1024))
    if size > 1024 * 1024 * 1024 * 1024:
        return '%0.1fTB' % (float(size) / (1024 * 1024 * 1024 * 1024))
    if size > 1024 * 1024 * 1024:
        return '%0.1fGB' % (float(size) / (1024 * 1024 * 1024))
    if size > 1024 * 1024:
        return '%0.1fMB' % (float(size) / (1024 * 1024))
    if size > 1024:
        return '%0.1fKB' % (float(size) / (1024))
    return str(size)


def copy(uploadedfile, targetdir):
    """Copy the file given by uploadedfile to targetdir, with the same name.
    Creates targetdir and parent dirs if they don't already exist.

    If uploadedfile is a path to a file, copy it. If it is an UploadedFile
    object, save its chunks.

    Returns new path."""
    if not os.path.exists(targetdir):
        os.makedirs(targetdir)

    if isinstance(uploadedfile, UploadedFile):
        target = os.path.join(targetdir, uploadedfile.name)
        with open(target, 'wb') as f:
            for chunk in uploadedfile.chunks():
                f.write(chunk)
    else:
        # Assume it's a string
        target = os.path.join(targetdir, os.path.basename(uploadedfile))
        shutil.copyfile(uploadedfile, target)

    return target


class Roads(models.Model):
    """
    Generated with bin/django inspectdb after executing:

    shp2pgsql -s 28992 wegen_indirect public.lizard_damage_roads |\
    sed s/geom/the_geom/g | psql schademodule --username buildout

    When using postgis2, shp2pgsql must take care of the table creation
    since django doesn't handle postgis2 very well currently.
    """
    # {landuse-code: gridcode} mapping for roads
    ROAD_GRIDCODE = {32: 20, 22: 21, 23: 22}

    gid = models.IntegerField(primary_key=True)
    typeinfr_1 = models.CharField(max_length=25, blank=True)
    typeweg = models.CharField(max_length=120, blank=True)
    gridcode = models.SmallIntegerField(null=True, blank=True)
    the_geom = models.MultiPolygonField(srid=28992, null=True, blank=True)
    objects = models.GeoManager()

    class Meta:
        db_table = 'data_roads'

    @classmethod
    def get_by_geo(cls, gridcode, geo, shape):
        """ Return roads contained by dataset with gridcode gridcode. """
        polygon = raster.get_polygon_from_geo_and_shape(geo, shape)

        return cls.objects.filter(
            the_geom__intersects=polygon, gridcode=gridcode)

    @classmethod
    def get_roads_flooded_for_tile_and_code(cls, code, depth, geo):
        """ Return dict {road-pk: flooded_m2}. """
        area_per_pixel = raster.geo2cellsize(geo)
        roads_flooded_for_tile_and_code = {}

        roads = cls.get_by_geo(cls.ROAD_GRIDCODE[code], geo, depth.shape)
        for road in roads:
            mask = raster.get_mask([road], depth.shape, geo)
            flooded_m2 = (mask * area_per_pixel * np.greater(depth, 0)).sum()
            if flooded_m2:
                roads_flooded_for_tile_and_code[road.pk] = flooded_m2

        return roads_flooded_for_tile_and_code

    def __unicode__(self):
        return 'road({}): {} {}'.format(self.gid, self.typeweg, self.gridcode)


class Unit(models.Model):
    name = models.CharField(
        max_length=64,
        blank=True, null=True,
    )
    factor = models.FloatField(
        blank=True, null=True,
    )

    def __unicode__(self):
        return self.name

    def to_si(self, value):
        return value * self.factor

    def from_si(self, value):
        return value / self.factor

    @classmethod
    def fill_units_table(cls):
        """For use in testing..."""
        from lizard_damage_calculation.unit import DEFAULT_UNITS
        for unit in DEFAULT_UNITS:
            cls.objects.create(
                name=unit.name, factor=unit.factor)


class DamageScenario(models.Model):
    """
    Has all information to calculate damage for one waterlevel grid.
    """
    SCENARIO_STATUS_RECEIVED = 1
    SCENARIO_STATUS_INPROGRESS = 2
    SCENARIO_STATUS_DONE = 3
    SCENARIO_STATUS_SENT = 4
    SCENARIO_STATUS_CLEANED = 5

    SCENARIO_STATUS_CHOICES = (
        (SCENARIO_STATUS_RECEIVED, 'Ontvangen'),
        (SCENARIO_STATUS_INPROGRESS, 'Bezig'),
        (SCENARIO_STATUS_DONE, 'Gereed'),
        (SCENARIO_STATUS_SENT, 'Verzonden'),
        (SCENARIO_STATUS_CLEANED, 'Opgeschoond'),
    )

    SCENARIO_STATUS_DICT = dict(SCENARIO_STATUS_CHOICES)

    CALC_TYPE_MIN = 1
    CALC_TYPE_MAX = 2
    CALC_TYPE_AVG = 3

    CALC_TYPE_CHOICES = (
        (CALC_TYPE_MIN, 'Minimale schadebedragen en schadefuncties'),
        (CALC_TYPE_MAX, 'Maximale schadebedragen en schadefuncties'),
        (CALC_TYPE_AVG, 'Gemiddelde schadebedragen en schadefuncties'),
        )

    SCENARIO_TYPES = (
        (0, '1 Kaart met de max waterstand van 1 gebeurtenis'),
        (1, '1 Kaart met de waterstand voor een zekere herhalingstijd'),
        (2, 'Kaarten met per tijdstip de waterstand van 1 gebeurtenis'),
        (3, 'Kaarten met de max. waterstand van afzonderlijke gebeurtenissen'),
        (4, 'Kaarten met voor verschillende herhalingstijden de '
         'waterstanden (voor risicokaart)'),
        (5, 'Tijdserie aan kaarten met per tijdstip de '
            'waterstand van meerdere gebeurtenissen'),
        (6, 'Batenkaart maken met resultaten uit twee risicokaarten'),
    )
    SCENARIO_TYPES_DICT = dict(SCENARIO_TYPES)

    status = models.IntegerField(
        choices=SCENARIO_STATUS_CHOICES,
        default=SCENARIO_STATUS_RECEIVED,
    )
    name = models.CharField(max_length=64)
    slug = models.SlugField(
        null=True, blank=True,
        help_text='auto generated on save; used for url')
    email = models.EmailField(max_length=128)

    datetime_created = models.DateTimeField(auto_now=True)
    expiration_date = models.DateTimeField()

    calc_type = models.IntegerField(
        choices=CALC_TYPE_CHOICES, default=CALC_TYPE_MAX)

    scenario_type = models.IntegerField(
        choices=SCENARIO_TYPES, default=0)

    customheights = models.FilePathField(
        max_length=200, null=True, blank=True)
    customlanduse = models.FilePathField(
        max_length=200, null=True, blank=True)
    damagetable_file = models.FilePathField(
        max_length=200, null=True, blank=True,
        help_text='Optionele schadetabel, indien niet ingevuld '
        'wordt de default gebruikt')
    customlandusegeoimage = models.ForeignKey(
        'GeoImage', null=True, blank=True)

    @classmethod
    def setup(
            cls, name, email, scenario_type, calc_type, customheights,
            customlanduse, damagetable, damage_events):
        """Create and setup a DamageScenario. Handles all types."""

        scenario = cls.objects.create(
            name=name, email=email, scenario_type=scenario_type,
            calc_type=calc_type)

        files_to_move = dict()
        if customheights:
            files_to_move['customheights'] = customheights
        if customlanduse:
            files_to_move['customlanduse'] = customlanduse
        if damagetable:
            files_to_move['damagetable_file'] = damagetable

        scenario.move_files(files_to_move)
        scenario.save()

        for damage_event_data in damage_events:
            DamageEvent.setup(scenario, **damage_event_data)

        return scenario

    def __unicode__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = ''.join(random.sample(string.letters, 20))
        if not self.expiration_date:
            self.expiration_date = (
                datetime.datetime.now() + datetime.timedelta(days=7))
        return super(DamageScenario, self).save(*args, **kwargs)

    @property
    def workdir(self):
        """The workdir must be located inside MEDIA_ROOT, because
        that's the directory that's mounted on both the webserver and
        the taskserver."""
        workdir = os.path.join(
            settings.MEDIA_ROOT, 'damagescenario', str(self.id))
        if not os.path.isdir(workdir):
            os.makedirs(workdir)
        return workdir

    def delete(self):
        """Also remove the workdir."""
        shutil.rmtree(self.workdir)
        return super(DamageScenario, self).delete()

    @property
    def directory_url(self):
        """URL to the workdir."""
        return "{}{}/{}".format(
            settings.MEDIA_URL, 'damagescenario', str(self.id))

    def read_damage_table(self):
        """Returns damage table from dt_path, or data/damagetable/dt.cfg
        if not given."""

        dt_path = self.damagetable_file or os.path.join(
            settings.BUILDOUT_DIR, table.DEFAULT_DAMAGE_TABLE)

        with open(dt_path) as cfg:
            return dt_path, table.DamageTable.read_cfg(
                cfg, units=Unit.objects.all())

    @property
    def display_status(self):
        return self.SCENARIO_STATUS_DICT.get(self.status, 'Onbekend')

    def get_absolute_url(self):
        return reverse('lizard_damage_result', kwargs=dict(slug=self.slug))

    @property
    def scenario_type_str(self):
        return self.SCENARIO_TYPES_DICT[self.scenario_type]

    @property
    def alternative_heights_dataset(self):
        if self.customheights:
            logger.info("Opening {}".format(self.customheights))
            return gdal_open(
                os.path.join(
                    settings.MEDIA_ROOT, self.customheights))

    @property
    def alternative_landuse_dataset(self):
        if self.customlanduse:
            logger.info("Opening {}".format(self.customlanduse))
            return gdal_open(
                os.path.join(
                    settings.MEDIA_ROOT, self.customlanduse))

    def move_files(self, file_dict):
        """file_dict has keys like 'customheights', and paths to
        these files as values. The files are moved to
        var/wss/damagescenario/<id>/filename and those new paths are saved
        to this object. Instead of a path, actual UploadedFile instances
        are also acceptable."""
        for field, path in file_dict.items():
            if path is None:
                continue
            setattr(self, field, copy(path, self.workdir))

    @property
    def landuse_slugs(self):
        """If this scenario has a custom landuse raster, it is saved as
        a GeoImage and its slug is used for KMLs. Otherwise, return None
        (use the slugs generated by the calculation task)."""
        if self.customlanduse is None:
            return None

        if self.customlandusegeoimage is None:
            self.customlandusegeoimage = GeoImage.from_landuse_dataset(
                gdal_open(self.customlanduse),
                slug="customlanduse_{}".format(self.id))
            self.save()

        # Return a comma-separated list of a single slug, aka the slug itself
        return self.customlandusegeoimage.slug

    def calculate(self, logger):
        """
        Calculate this DamageScenario. Called from task.
        """
        start_dt = datetime.datetime.now()
        logger.info("calculate damage")

        logger.info("scenario: %d, %s" % (self.id, str(self)))
        logger.info("calculating...")

        logger.info("scenario %s" % (self.name))

        self.status = self.SCENARIO_STATUS_INPROGRESS
        self.save()

        errors = 0

        # Use local imports while we are refactoring
        from lizard_damage import risk
        from lizard_damage import emails

        all_riskmap_data = []

        for damage_event_index, damage_event in enumerate(
                self.damageevent_set.all()):
            result, riskmap_data = damage_event.calculate(logger)
            if result:
                all_riskmap_data += riskmap_data
            else:
                errors += 1

        # Calculate risk maps
        if self.scenario_type == 4:
            risk.create_risk_map(damage_scenario=self, logger=logger)

        # Roundup
        self.status = self.SCENARIO_STATUS_DONE
        self.save()

        if errors == 0:
            emails.send_damage_success_mail(self, logger, start_dt)
            logger.info("finished successfully")
        else:
            emails.send_damage_error_mail(self, logger, start_dt)
            logger.info("finished with errors")


class DamageEvent(models.Model):
    """
    Has all information to calculate damage for one waterlevel grid.
    """
    EVENT_STATUS_RECEIVED = 1
    EVENT_STATUS_INPROGRESS = 2
    EVENT_STATUS_DONE = 3
    EVENT_STATUS_CLEANED = 5

    EVENT_STATUS_CHOICES = (
        (EVENT_STATUS_RECEIVED, 'Ontvangen'),
        (EVENT_STATUS_INPROGRESS, 'Bezig'),
        (EVENT_STATUS_DONE, 'Gereed'),
        (EVENT_STATUS_CLEANED, 'Opgeschoond'),
    )

    name = models.CharField(max_length=100, null=True, blank=True)
    status = models.IntegerField(
        choices=EVENT_STATUS_CHOICES,
        default=EVENT_STATUS_RECEIVED,
    )
    scenario = models.ForeignKey(DamageScenario)
    slug = models.SlugField(
        null=True, blank=True,
        help_text='auto generated on save; used for url')
    floodtime = models.FloatField(
        help_text='How long was it flooded, in seconds')
    repairtime_roads = models.FloatField(
        help_text='In seconds', default=5 * 3600 * 24)
    repairtime_buildings = models.FloatField(
        help_text='In seconds', default=5 * 3600 * 24)
    floodmonth = models.IntegerField(default=9)

    repetition_time = models.FloatField(blank=True, null=True,
                                        help_text='In years!')

    # Result
    table = models.TextField(null=True, blank=True, help_text='in json format')

    # Used for the legend
    min_height = models.FloatField(null=True, blank=True)
    max_height = models.FloatField(null=True, blank=True)

    @classmethod
    def setup(cls, scenario, floodtime_hours, repairtime_roads_days,
              repairtime_buildings_days, floodmonth, repetition_time,
              waterlevels, name=None):
        damage_event = cls.objects.create(
            scenario=scenario,
            floodtime=float(floodtime_hours) * 3600,
            repairtime_roads=float(repairtime_roads_days) * 3600 * 24,
            repairtime_buildings=float(repairtime_buildings_days) * 3600 * 24,
            floodmonth=floodmonth)

        if repetition_time is not None:
            damage_event.repetition_time = float(repetition_time)
            damage_event.save()

        for waterlevel_data in waterlevels:
            DamageEventWaterlevel.setup(damage_event, **waterlevel_data)

        return damage_event

    def __unicode__(self):
        if self.name:
            return self.name
        dew = self.damageeventwaterlevel_set.all()
        if dew:
            return ', '.join([str(d) for d in dew])
        return 'id: %d' % self.id

    @property
    def workdir(self):
        """The workdir is below this scenario's workdir, and has
        the DamageEvent's primary key in its name. So this doesn't
        work on unsaved DamageEvents."""
        workdir = os.path.join(
            self.scenario.workdir, 'damage_events', str(self.id))
        if not os.path.isdir(workdir):
            os.makedirs(workdir)
        return workdir

    @property
    def directory_url(self):
        return '/'.join((self.scenario.directory_url,
                         'damage_events', str(self.id)))

    @property
    def result_url(self):
        """Return URL to result.zip in the workdir."""
        path = os.path.join(self.workdir, results.ZIP_FILENAME)
        if os.path.exists(path):
            return '/'.join((self.directory_url, results.ZIP_FILENAME))
        else:
            return None

    @property
    def result(self):
        """Path to result zipfile."""
        return os.path.join(self.workdir, results.ZIP_FILENAME)

    @property
    def result_display(self):
        """display name of result"""
        return 'zipfile (%s)' % friendly_filesize(
            os.stat(self.result).st_size)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = ''.join(random.sample(string.letters, 20))
        return super(DamageEvent, self).save(*args, **kwargs)

    @property
    def parsed_table(self):
        return json.loads(self.table)

    @parsed_table.setter
    def parsed_table(self, value):
        self.table = json.dumps(value)

    def get_filenames(self, pattern=None):
        """
        Return list of filenames in the result zip file.

        If a pattern is supplied, only returns files matching pattern.
        """
        with zipfile.ZipFile(self.result) as archive:
            filenames = [info.filename for info in archive.filelist]

        if pattern is None:
            return filenames
        else:
            return [filename
                    for filename in filenames
                    if re.match(pattern, filename)]

    def get_data(self, filename):
        """
        Return geotransform, numpy masked array corresponding to damage result.

        The file named filename is extracted from the result to a
        temporary directory and read via gdal. Filename must be the name
        of a gdal readable dataset inside the result zip file.
        """
        with zipfile.ZipFile(self.result) as archive:
            tempdir = tempfile.mkdtemp()
            archive.extract(filename, tempdir)
            filepath = os.path.join(tempdir, filename)
            dataset = gdal_open(filepath)
            data = utils.ds2ma(dataset)
            geotransform = dataset.GetGeoTransform()
            dataset = None  # Should closes the file
            os.remove(filepath)
            os.rmdir(tempdir)
            return geotransform, data

    def calculate(self, logger):
        """
        Calculate this damage event.
        """
        from lizard_damage import calc

        logger.info("event %s" % (self,))
        logger.info(" - month %s, floodtime %s" % (
            self.floodmonth, self.floodtime))

        # Read damage table
        dt_path, damage_table = self.scenario.read_damage_table()
        logger.info('damage table: %s' % dt_path)

        calc_type = self.scenario.calc_type or calculation.CALC_TYPE_MAX
        # Use the calculator from lizard-damage-calculation for the
        # actual calculation.
        calculator = calculation.DamageCalculator(
            ahn_data_dir=os.path.join(
                settings.LIZARD_DAMAGE_DATA_ROOT, 'data_ahn'),
            lgn_data_dir=os.path.join(
                settings.LIZARD_DAMAGE_DATA_ROOT, 'data_lgn'),
            alternative_heights_dataset=(
                self.scenario.alternative_heights_dataset),
            alternative_landuse_dataset=(
                self.scenario.alternative_landuse_dataset),
            table=damage_table,
            get_roads_flooded_for_tile_and_code=
            Roads.get_roads_flooded_for_tile_and_code,
            calc_type=calc_type,
            road_grid_codes=Roads.ROAD_GRIDCODE,
            logger=logger)

        waterlevel_ascfiles = [
            dewl.waterlevel_path for dewl in
            self.damageeventwaterlevel_set.all()]
        calculator.set_waterlevel_datafiles(waterlevel_ascfiles)

        # Track global results
        overall_area = collections.defaultdict(float)
        overall_damage = collections.defaultdict(float)
        roads_flooded_global = {i: collections.defaultdict(float)
                                for i in Roads.ROAD_GRIDCODE}

        all_leaves = calculator.get_ahn_leaves()

        result_collector = results.ResultCollector(
            self.workdir, all_leaves, logger)
        result_collector.save_file_for_zipfile(dt_path, 'dt.cfg')

        for (ahn_name, extent, ds_height, landuse_ma, depth_ma, damage,
             area, result, roads_flooded_for_tile) in (
                calculator.calculate_for_all_leaves(
                    month=self.floodmonth,
                    floodtime=self.floodtime,
                    repairtime_roads=self.repairtime_roads,
                    repairtime_buildings=self.repairtime_buildings)):
            logger.info("Recording results for tile {}...".format(ahn_name))

            # Keep track of flooded roads
            for code, roads_flooded in roads_flooded_for_tile.iteritems():
                for road, flooded_m2 in roads_flooded.iteritems():
                    roads_flooded_global[code][road] += flooded_m2

            logger.debug("result sum: %f" % result.sum())
            arcname = 'schade_{}'.format(ahn_name)
            if self.repetition_time:
                arcname += '_T%.1f' % self.repetition_time
            result_collector.save_ma(
                ahn_name, result, result_type='damage', ds_template=ds_height,
                repetition_time=self.repetition_time)

            result_collector.save_csv_data_for_zipfile(
                'schade_{}.csv'.format(ahn_name), dict(
                    damage=damage, area=area, damage_table=damage_table,
                    meta=[
                        ['schade module versie', tools.version()],
                        ['waterlevel', waterlevel_ascfiles[0]],
                        ['damage table', dt_path],
                        ['maand', str(self.floodmonth)],
                        ['duur overstroming (s)', str(self.floodtime)],
                        ['hersteltijd wegen (s)', str(self.repairtime_roads)],
                        ['hersteltijd bebouwing (s)',
                         str(self.repairtime_buildings)],
                        ['berekening',
                         {1: 'Minimum', 2: 'Maximum',
                          3: 'Gemiddelde'}[calc_type]],
                        ['ahn_name', ahn_name],
                    ]))

            for k in damage.keys():
                overall_damage[k] += damage[k]

            for k in area.keys():
                overall_area[k] += area[k]

        # Generate vrt + geotiff out of the .asc files.
        result_collector.build_damage_geotiff()

        # Only after all tiles have been processed, calculate overall indirect
        # Road damage. This is not visible in the per-tile-damagetable.
        roads_flooded_over_threshold = []
        for code, roads_flooded in roads_flooded_global.iteritems():
            damage_data = damage_table.data[code]
            for road, area in roads_flooded.iteritems():
                if area >= 100:
                    roads_flooded_over_threshold.append(road)
                    indirect_road_damage = (
                        damage_data.to_indirect_damage(
                            calculation.CALC_TYPES[calc_type]) *
                        damage_data.to_gamma_repairtime(self.repairtime_roads))

                    logger.info(
                        '%s - %s - %s: %.2f ind' %
                        (
                            damage_data.code,
                            damage_data.source,
                            damage_data.description,
                            indirect_road_damage,
                            ),
                        )
                    logger.info(
                        ('track indirect road damage: scenario slug {}, ' +
                         'roadid {}, damage {}').format(
                            self.scenario.slug, road, indirect_road_damage,
                        ))
                    overall_damage[code] += indirect_road_damage

        result_collector.save_csv_data_for_zipfile(
            'schade_totaal.csv', dict(
                damage=overall_damage,
                area=overall_area,
                damage_table=damage_table,
                meta=[
                    ['schade module versie', tools.version()],
                    ['waterlevel', waterlevel_ascfiles[0]],
                    ['damage table', dt_path],
                    ['maand', str(self.floodmonth)],
                    ['duur overstroming (s)', str(self.floodtime)],
                    ['hersteltijd wegen (s)', str(self.repairtime_roads)],
                    ['hersteltijd bebouwing (s)',
                     str(self.repairtime_buildings)],
                    ['berekening',
                     {1: 'Minimum', 2: 'Maximum', 3: 'Gemiddelde'}[calc_type]],
                ],
                include_total=True))

        result_collector.finalize()
        DamageEventResult.create_from_result_collector(self, result_collector)

        # Save a table in a JSON string to show in the interface
        self.parsed_table = calc.result_as_dict(
            damage=overall_damage,
            area=overall_area,
            damage_table=damage_table)

        # Save min and max height, for legend
        self.min_height = result_collector.mins.get('height')
        self.max_height = result_collector.maxes.get('height')
        self.save()

        return True, result_collector.riskmap_data  # success


class DamageEventResult(models.Model):
    """ Result of 1 tile of a Damage Event

    Normally a Damage Event has multiple tiles
    """

    RESULT_TYPE_CHOICES = ('damage', 'landuse', 'height', 'depth')
    result_type = models.CharField(max_length=10, choices=[
        (choice, choice) for choice in RESULT_TYPE_CHOICES])

    damage_event = models.ForeignKey(DamageEvent)

    # Relative to the damage event's workdir
    relative_path = models.CharField(max_length=100)

    north = models.FloatField()
    south = models.FloatField()
    east = models.FloatField()
    west = models.FloatField()

    geotransform_json = models.TextField(null=True, blank=True)

    def __unicode__(self):
        return '%s' % (self.damage_event)

    def url(self):
        return "{}{}".format(
            self.damage_event.directory_url,
            self.relative_path)

    def rotation(self):
        # somethings wrong with google maps projection, see also AhnIndex
        # test show that for north = 51.797214 -> rotation = 0.9
        # north = 52.835332 -> rotation = 0.3
        #fraction = (self.north - 51.797214) / (52.835332 - 51.797214)
        #return 0.9 - 0.6 * fraction
        return 0

    @property
    def name(self):
        return os.path.splitext(self.relative_path.split('/')[-1])[0]

    @classmethod
    def create_from_result_collector(cls, damage_event, result_collector):
        # Delete old results
        cls.objects.filter(damage_event=damage_event).delete()

        results = [
            cls(
                damage_event=damage_event, result_type=result_type,
                relative_path=relative_path,
                north=north, south=south, east=east, west=west,
            )
            for (result_type, relative_path, (west, south, east, north)) in
            result_collector.all_images()]

        cls.objects.bulk_create(results)


class DamageEventWaterlevel(models.Model):
    """
    One waterlevel file to be used for a timeseries of waterlevels.
    """
    event = models.ForeignKey(DamageEvent)
    index = models.IntegerField(default=100)
    waterlevel_path = models.FilePathField(
        max_length=200, null=True, blank=True)

    class Meta:
        ordering = ('index', )

    @classmethod
    def setup(cls, damage_event, waterlevel, index=None):
        # Create damageeventwaterlevel instance
        damageeventwaterlevel = cls.objects.create(event=damage_event)

        # Set index if given
        if index is not None:
            damageeventwaterlevel.index = index

        # Move provided file to workdir
        damageeventwaterlevel.waterlevel_path = copy(
            waterlevel, damageeventwaterlevel.workdir)

        # Save and return
        damageeventwaterlevel.save()
        return damageeventwaterlevel

    @property
    def workdir(self):
        """The workdir is below this event's workdir, and has the
        DamageEventWaterlevel's primary key in its name. So this
        doesn't work on unsaved DamageEventsWaterlevels.
        """
        workdir = os.path.join(
            self.event.workdir, 'waterlevels', str(self.id))
        if not os.path.isdir(workdir):
            os.makedirs(workdir)
        return workdir

    def __unicode__(self):
        return os.path.basename(self.waterlevel_path)


class RiskResult(models.Model):
    """
    Ascii file with risk map belonging to a type 4 scenario.
    """
    zip_risk = models.FileField(
        upload_to='scenario/result',
    )
    scenario = models.ForeignKey(DamageScenario)

    def __unicode__(self):
        return os.path.basename(self.zip_risk.path)


    @property
    def result_display(self):
        """display name of result"""
        return 'zipfile (%s)' % friendly_filesize(self.zip_risk.size)


class BenefitScenario(models.Model):
    """Baten berekening.

    Results will be in result_zip and
    in BenefitScenarioResult.
    """

    SCENARIO_STATUS_RECEIVED = 1
    SCENARIO_STATUS_INPROGRESS = 2
    SCENARIO_STATUS_DONE = 3
    SCENARIO_STATUS_SENT = 4
    SCENARIO_STATUS_CLEANED = 5

    SCENARIO_STATUS_CHOICES = (
        (SCENARIO_STATUS_RECEIVED, 'Ontvangen'),
        (SCENARIO_STATUS_INPROGRESS, 'Bezig'),
        (SCENARIO_STATUS_DONE, 'Gereed'),
        (SCENARIO_STATUS_SENT, 'Verzonden'),
        (SCENARIO_STATUS_CLEANED, 'Opgeschoond'),
    )

    SCENARIO_STATUS_DICT = dict(SCENARIO_STATUS_CHOICES)

    name = models.CharField(max_length=64)
    slug = models.SlugField(
        null=True, blank=True,
        help_text='auto generated on save; used for url')
    email = models.EmailField(max_length=128)

    datetime_created = models.DateTimeField(auto_now=True)
    expiration_date = models.DateTimeField()

    zip_risk_a = models.FileField(upload_to='benefit/risk')
    zip_risk_b = models.FileField(upload_to='benefit/risk')

    zip_result = models.FileField(
        upload_to='benefit/result',
        null=True, blank=True,
        help_text='Will be filled when results are available')

    status = models.IntegerField(
        choices=SCENARIO_STATUS_CHOICES,
        default=SCENARIO_STATUS_RECEIVED,
    )

    def __unicode__(self):
        return '%s' % (self.name)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = ''.join(random.sample(string.letters, 20))
        if not self.expiration_date:
            self.expiration_date = (
                datetime.datetime.now() + datetime.timedelta(days=7))
        return super(BenefitScenario, self).save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse(
            'lizard_damage_benefit_result', kwargs=dict(slug=self.slug))

    def result_display(self):
        try:
            return 'zipfile (%s)' % friendly_filesize(self.zip_result.size)
        except:
            return 'geen zipfile'

    def get_data_before(self, filename):
        return self._get_data(filename, 'before')

    def get_data_after(self, filename):
        return self._get_data(filename, 'after')

    def _get_data(self, filename, when):
        """
        Return numpy masked array corresponding to damage result.

        The file named filename is extracted from the result to a
        temporary directory and read via gdal. Filename must be the name
        of a gdal readable dataset inside the result zip file.
        """
        fieldmap = {
            'before': self.zip_risk_a,
            'after': self.zip_risk_b,
        }
        field = fieldmap[when]

        with zipfile.ZipFile(field) as archive:
            tempdir = tempfile.mkdtemp()
            archive.extract(filename, tempdir)
            filepath = os.path.join(tempdir, filename)
            dataset = gdal_open(filepath)
            geotransform = dataset.GetGeoTransform()
            data = utils.ds2ma(dataset)
            dataset = None  # Should closes the file
            os.remove(filepath)
            os.rmdir(tempdir)
            return dict(data=data, geotransform=geotransform)


class BenefitScenarioResult(models.Model):
    """ Result of 1 tile of a Benefit Scenario

    Used to create kml
    """
    benefit_scenario = models.ForeignKey(BenefitScenario)
    image = models.FileField(upload_to='scenario/image')

    north = models.FloatField()
    south = models.FloatField()
    east = models.FloatField()
    west = models.FloatField()

    def __unicode__(self):
        return '%s - %s' % (self.benefit_scenario, self.image)


class GeoImage(models.Model):
    """
    Generic geo referenced image

    i.e. For use in kml files
    """
    slug = models.SlugField()
    image = models.FileField(upload_to='geoimage')

    north = models.FloatField()
    south = models.FloatField()
    east = models.FloatField()
    west = models.FloatField()

    def __unicode__(self):
        return self.slug

    @classmethod
    def check_existence(cls, slug):
        geoimages = cls.objects.filter(slug=slug)
        if geoimages.count() == 0:
            return False

        for geoimage in geoimages:
            if geoimage.image and os.path.exists(os.path.join(
                    settings.MEDIA_ROOT, geoimage.image.name)):
                return geoimage
            else:
                geoimage.delete()

        return False

    @classmethod
    def from_landuse_dataset(cls, dataset, slug):
        """Create GeoImage from a dataset containing landuse data."""
        geoimage = cls.check_existence(slug)
        if geoimage:
            return geoimage

        from .calc import landuse_legend
        legend = landuse_legend()

        data = dataset.GetRasterBand(1).ReadAsArray()

        return cls.from_data_with_legend(
            slug, data, legend, geotransform=dataset.GetGeoTransform())

    @classmethod
    def from_data_with_legend(
            cls, slug, data, legend, extent=None, geotransform=None):
        """
        Create GeoImage from slug and data.

        Data is numpy array.

        Extent is list/tuple of the form (west, south, east, north).
        """
        geoimage = cls.check_existence(slug)
        if geoimage:
            return geoimage

        tmp_base = tempfile.mktemp()
        colormap = mpl.colors.ListedColormap(legend, 'indexed')
        rgba = colormap(data, bytes=True)
        Image.fromarray(rgba).save(tmp_base + '.png', 'PNG')
        if extent is not None:
            results.write_extent_pgw(tmp_base + '.pgw', extent)
        if geotransform is not None:
            write_geotransform_pgw(tmp_base + '.pgw', geotransform)

        return cls._from_rd_png(tmp_base, slug, extent)

    @classmethod
    def from_data_with_min_max(
            cls, slug, data, extent, min_value, max_value, cdict=None):
        """
        Create GeoImage from slug and data.
        """
        geoimage = cls.check_existence(slug)
        if geoimage:
            return geoimage

        tmp_base = tempfile.mktemp()
        if cdict is None:
            cdict = {
                'red': ((0.0, 51. / 256, 51. / 256),
                        (0.5, 237. / 256, 237. / 256),
                        (1.0, 83. / 256, 83. / 256)),
                'green': ((0.0, 114. / 256, 114. / 256),
                          (0.5, 245. / 256, 245. / 256),
                          (1.0, 83. / 256, 83. / 256)),
                'blue': ((0.0, 54. / 256, 54. / 256),
                         (0.5, 170. / 256, 170. / 256),
                         (1.0, 83. / 256, 83. / 256)),
                }
        colormap = mpl.colors.LinearSegmentedColormap(
            'something', cdict, N=1024)
        normalize = mpl.colors.Normalize(vmin=min_value, vmax=max_value)
        rgba = colormap(normalize(data), bytes=True)

        if 'depth' in slug:
            # Make transparent where depth is zero or less
            rgba[:, :, 3] = np.where(np.greater(data, 0), 255, 0)

        Image.fromarray(rgba).save(tmp_base + '.png', 'PNG')

        results.write_extent_pgw(tmp_base + '.pgw', extent)

        return cls._from_rd_png(tmp_base, slug, extent)

    @classmethod
    def _from_rd_png(cls, tmp_base, slug, extent):
        """
        Input: <tmp_base>.png
        Output: geo_image object

        Takes a RD PNG, turns it into a WGS84 PNG and sets the extent of that
        on the GeoImage object. Also removes <tmp_base>.png and <tmp_base>.pgw
        that were made elsewhere.

        Does not save a .pgw for the new .png.
        """

        # Step 2: warp using gdalwarp to lon/lat in .tif
        # Warp png file, output is tif.
        subprocess.call([
            'gdalwarp', tmp_base + '.png', tmp_base + '.tif',
            '-t_srs', "+proj=latlong +datum=WGS84", '-s_srs', RD.strip()])

        result_extent = extent_from_geotiff(tmp_base + '.tif')

        # Step 3: convert .tif back to .png
        im = Image.open(tmp_base + '.tif')
        im.save(tmp_base + '_2.png', 'PNG')

        # Step 4: put .png in GeoObject, with new extent
        geo_image = cls(slug=slug)
        geo_image.north = result_extent[3]
        geo_image.south = result_extent[1]
        geo_image.east = result_extent[2]
        geo_image.west = result_extent[0]
        with open(tmp_base + '_2.png', 'rb') as img_file:
            geo_image.image.save(slug + '.png', File(img_file), save=True)
        geo_image.save()

        # Step 5: clean tempfiles.
        os.remove(tmp_base + '.png')
        os.remove(tmp_base + '.pgw')
        os.remove(tmp_base + '.tif')
        os.remove(tmp_base + '_2.png')

        return geo_image
