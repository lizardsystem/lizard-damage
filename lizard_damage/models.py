# -*- coding: utf-8 -*-
# (c) Nelen & Schuurmans.  GPL licensed, see LICENSE.rst.
from __future__ import (
  print_function,
  unicode_literals,
  absolute_import,
  division,
)
from django.contrib.gis.db import models
from django.core.urlresolvers import reverse
from django.core.files import File
from lizard_map import coordinates
from lizard_task.models import SecuredPeriodicTask
from pyproj import transform
from pyproj import Proj
import matplotlib as mpl
import numpy as np

import datetime
import os
import random
import string
import json
import tempfile
import Image
import subprocess
from osgeo import gdal

# from django.utils.translation import ugettext_lazy as _

RD = str("""
+proj=sterea +lat_0=52.15616055555555 +lon_0=5.38763888888889 +k=0.999908 +x_0=155000 +y_0=463000 +ellps=bessel +units=m +towgs84=565.2369,50.0087,465.658,-0.406857330322398,0.350732676542563,-1.8703473836068,4.0812 +no_defs <>
""")

WGS84 = str('+proj=latlong +datum=WGS84')

rd_proj = Proj(RD)
wgs84_proj = Proj(WGS84)


def extent_from_geotiff(filename):
    ds = gdal.Open(filename)
    width = ds.RasterXSize
    height = ds.RasterYSize
    gt = ds.GetGeoTransform()
    minx = gt[0]
    miny = gt[3] + width*gt[4] + height*gt[5]
    maxx = gt[0] + width*gt[1] + height*gt[2]
    maxy = gt[3]
    return (minx, miny, maxx, maxy)


def write_pgw(name, extent):
    """write pgw file:

    0.5
    0.000
    0.000
    0.5
    <x ul corner>
    <y ul corner>

    extent is a 4-tuple
    """
    f = open(name, 'w')
    f.write('0.5\n0.000\n0.000\n-0.5\n')
    f.write('%f\n%f' % (min(extent[0], extent[2]), max(extent[1], extent[3])))
    f.close()
    return


def friendly_filesize(size):
    if size > 1024*1024*1024*1024*1024:
        # Just for fun
        return '%0.1fPB' % (float(size) / (1024*1024*1024*1024*1024))
    if size > 1024*1024*1024*1024:
        return '%0.1fTB' % (float(size) / (1024*1024*1024*1024))
    if size > 1024*1024*1024:
        return '%0.1fGB' % (float(size) / (1024*1024*1024))
    if size > 1024*1024:
        return '%0.1fMB' % (float(size) / (1024*1024))
    if size > 1024:
        return '%0.1fKB' % (float(size) / (1024))
    return str(size)


class AhnIndex(models.Model):
    """
    Sql for this table can be generated using:

    shp2pgsql -s 28992 ahn2_05_int_index public.data_index | sed\
    s/geom/the_geom/g > index.sql

    Table definition can be obtained by executing this sql and using
    bin/django inspectdb, and then replace DecimalFields by FloatFields
    """
    gid = models.IntegerField(primary_key=True)
    x = models.FloatField(null=True, blank=True)  # In RD
    y = models.FloatField(null=True, blank=True)
    cellsize = models.CharField(max_length=2, blank=True)
    lo_x = models.CharField(max_length=6, blank=True)
    lo_y = models.CharField(max_length=6, blank=True)
    bladnr = models.CharField(max_length=24, blank=True)
    update = models.DateField(null=True, blank=True)
    datum = models.DateField(null=True, blank=True)
    min_datum = models.DateField(null=True, blank=True)
    max_datum = models.DateField(null=True, blank=True)
    ar = models.FloatField(null=True, blank=True)
    the_geom = models.MultiPolygonField(srid=28992, null=True, blank=True)  # All squares?
    objects = models.GeoManager()

    class Meta:
        db_table = 'data_index'

    def __unicode__(self):
        return '%s %f %f %r' % (self.gid, self.x, self.y, self.extent_wgs84)

    def extent_wgs84(self, e=None):
        if e is None:
            e = self.the_geom.extent
        #x0, y0 = coordinates.rd_to_wgs84(e[0], e[1])
        #x1, y1 = coordinates.rd_to_wgs84(e[2], e[3])
        x0, y0 = transform(rd_proj, wgs84_proj, e[0], e[1])
        x1, y1 = transform(rd_proj, wgs84_proj, e[2], e[3])
        #print ('Converting RD %r to WGS84 %s' % (e, '%f %f %f %f' % (x0, y0, x1, y1)))
        # we're using it for google maps and it does not project exactly on the correct spot.. try to fix it ugly
        # add rotation = 0.9 too for the kml
        #x0 = x0 - 0.00012
        #y0 = y0 + 0.000057
        #x1 = x1 + 0.000154
        #y1 = y1 - 0.000051
        return (x0, y0, x1, y1)


class Roads(models.Model):
    """
    Generated with bin/django inspectdb after executing:

    shp2pgsql -s 28992 wegen_indirect public.lizard_damage_roads |\
    sed s/geom/the_geom/g | psql schademodule --username buildout

    When using postgis2, shp2pgsql must take care of the table creation
    since django doesn't handle postgis2 very well currently.
    """
    gid = models.IntegerField(primary_key=True)
    typeinfr_1 = models.CharField(max_length=25, blank=True)
    typeweg = models.CharField(max_length=120, blank=True)
    gridcode = models.SmallIntegerField(null=True, blank=True)
    the_geom = models.MultiPolygonField(srid=28992, null=True, blank=True)
    objects = models.GeoManager()

    class Meta:
        db_table = 'data_roads'


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

SCENARIO_STATUS_CHOICES = (
    (1, 'Ontvangen'),
    (2, 'Bezig'),
    (3, 'Gereed'),
    (4, 'Verzonden'),
    (5, 'Opgeschoond'),
)


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
        (4, 'Kaarten met voor verschillende herhalingstijden de waterstanden (voor risicokaart)'),
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
    slug = models.SlugField(null=True, blank=True, help_text='auto generated on save; used for url')
    email = models.EmailField(max_length=128)

    datetime_created = models.DateTimeField(auto_now=True)
    expiration_date = models.DateTimeField()
    # For cleaning up
    #task = models.ForeignKey(SecuredPeriodicTask, null=True, blank=True)

    damagetable = models.FileField(
        upload_to='scenario/damage_table',
        null=True, blank=True,
        help_text='Optionele schadetabel, indien niet ingevuld wordt de default gebruikt'
        )

    calc_type = models.IntegerField(
        choices=CALC_TYPE_CHOICES, default=CALC_TYPE_MAX)

    scenario_type = models.IntegerField(
        choices=SCENARIO_TYPES, default=0)

    def __unicode__(self):
        return self.name

    # def process(self):
    #     pass

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = ''.join(random.sample(string.letters, 20))
        if not self.expiration_date:
            self.expiration_date = datetime.datetime.now() + datetime.timedelta(days=7)
        return super(DamageScenario, self).save(*args, **kwargs)

    @property
    def display_status(self):
        return self.SCENARIO_STATUS_DICT.get(self.status, 'Onbekend')

    def get_absolute_url(self):
        return reverse('lizard_damage_result', kwargs=dict(slug=self.slug))

    @property
    def scenario_type_str(self):
        return self.SCENARIO_TYPES_DICT[self.scenario_type]


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
    slug = models.SlugField(null=True, blank=True, help_text='auto generated on save; used for url')
    floodtime = models.FloatField(help_text='How long was it flooded, in seconds')
    repairtime_roads = models.FloatField(help_text='In seconds', default=5*3600*24)
    repairtime_buildings = models.FloatField(help_text='In seconds', default=5*3600*24)
    # waterlevel = models.FileField(upload_to='scenario/waterlevel',
    #     blank=True, null=True)
    # flooddate = models.DateTimeField()
    floodmonth = models.IntegerField(default=9)

    repetition_time = models.FloatField(blank=True, null=True,
        help_text='In years!')

    # Result
    table = models.TextField(null=True, blank=True, help_text='in json format')
    result = models.FileField(
        upload_to='scenario/result',
        null=True, blank=True,
        help_text='Will be filled once the calculation has been done')
    landuse_slugs = models.TextField(
        null=True, blank=True,
        help_text='comma separated landuse slugs for GeoImage')
    height_slugs = models.TextField(
        null=True, blank=True,
        help_text='comma separated height slugs for GeoImage')
    min_height = models.FloatField(null=True, blank=True)
    max_height = models.FloatField(null=True, blank=True)

    def __unicode__(self):
        if self.name: return self.name
        dew = self.damageeventwaterlevel_set.all()
        if dew:
            return ', '.join([str(d) for d in dew])
        return 'id: %d' % self.id

    @property
    def result_display(self):
        """display name of result"""
        return 'zipfile (%s)' % friendly_filesize(self.result.size)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = ''.join(random.sample(string.letters, 20))
        return super(DamageEvent, self).save(*args, **kwargs)

    @property
    def parsed_table(self):
        return json.loads(self.table)


class DamageEventResult(models.Model):
    """ Result of 1 tile of a Damage Event

    Normally a Damage Event has multiple tiles
    """

    #table = models.TextField()
    #raster = models.FileField(upload_to='scenario/result')

    damage_event = models.ForeignKey(DamageEvent)
    image = models.FileField(upload_to='scenario/image')

    north = models.FloatField()
    south = models.FloatField()
    east = models.FloatField()
    west = models.FloatField()

    def __unicode__(self):
        return '%s - %s' % (self.damage_event, self.image)

    def rotation(self):
        # somethings wrong with google maps projection, see also AhnIndex
        # test show that for north = 51.797214 -> rotation = 0.9
        # north = 52.835332 -> rotation = 0.3
        #fraction = (self.north - 51.797214) / (52.835332 - 51.797214)
        #return 0.9 - 0.6 * fraction
        return 0

    """
     with open('/tmp/test', 'rb') as testfile:
         ds.waterlevel.save('blabla', File(testfile), save=True)
    """


class DamageEventWaterlevel(models.Model):
    """
    One waterlevel file to be used for a timeseries of waterlevels.
    """
    waterlevel = models.FileField(upload_to='scenario/waterlevel')
    event = models.ForeignKey(DamageEvent)
    index = models.IntegerField(default=100)

    class Meta:
        ordering = ('index', )

    def __unicode__(self):
        return os.path.basename(self.waterlevel.path)


class BenefitScenario(models.Model):
    """Baten berekening.

    Results will be in result_zip and
    in BenefitScenarioResult.
    """
    name = models.CharField(max_length=64)
    slug = models.SlugField(null=True, blank=True, help_text='auto generated on save; used for url')
    email = models.EmailField(max_length=128)

    datetime_created = models.DateTimeField(auto_now=True)
    expiration_date = models.DateTimeField()

    zip_risk_a = models.FileField(upload_to='benefit/risk')
    zip_risk_b = models.FileField(upload_to='benefit/risk')

    zip_result = models.FileField(
        upload_to='benefit/result',
        null=True, blank=True,
        help_text='Will be filled when results are available')

    def __unicode__(self):
        return '%s' % (self.name)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = ''.join(random.sample(string.letters, 20))
        if not self.expiration_date:
            self.expiration_date = datetime.datetime.now() + datetime.timedelta(days=7)
        return super(BenefitScenario, self).save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('lizard_damage_benefit_result', kwargs=dict(slug=self.slug))

    def result_display(self):
        try:
            return 'zipfile (%s)' % friendly_filesize(self.zip_result.size)
        except:
            return 'geen zipfile'


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
    def from_data_with_legend(cls, slug, data, extent, legend):
        """
        Create GeoImage from slug and data.

        Data is numpy array.
        """
        tmp_base = tempfile.mktemp()
        #print('tmp_base: %s' % tmp_base)
        #print('step 1')
        # Step 1: save png + pgw in RD

        colormap = mpl.colors.ListedColormap(legend, 'indexed')
        rgba = colormap(data, bytes=True)
        #rgba[:,:,3] = np.where(rgba[:,:,0], 153 , 0)
        Image.fromarray(rgba).save(tmp_base + '.png', 'PNG')
        write_pgw(tmp_base + '.pgw', extent)

        return cls.from_rd_png(tmp_base, slug, extent)


    @classmethod
    def from_data_with_min_max(cls, slug, data, extent, min_value, max_value):
        """
        Create GeoImage from slug and data.
        """
        tmp_base = tempfile.mktemp()
        #print('tmp_base: %s' % tmp_base)
        #print('step 1')
        # Step 1: save png + pgw in RD

        cdict = {
            'red': ((0.0, 51./256, 51./256),
                    (0.5, 237./256, 237./256),
                    (1.0, 83./256, 83./256)),
            'green': ((0.0, 114./256, 114./256),
                      (0.5, 245./256, 245./256),
                      (1.0, 83./256, 83./256)),
            'blue': ((0.0, 54./256, 54./256),
                     (0.5, 170./256, 170./256),
                     (1.0, 83./256, 83./256)),
            }
        colormap = mpl.colors.LinearSegmentedColormap('something', cdict, N=1024)
        normalize = mpl.colors.Normalize(vmin=min_value, vmax=max_value)
        rgba = colormap(normalize(data), bytes=True)
        #rgba[:,:,3] = np.where(rgba[:,:,0], 153 , 0)
        Image.fromarray(rgba).save(tmp_base + '.png', 'PNG')

        write_pgw(tmp_base + '.pgw', extent)

        return cls.from_rd_png(tmp_base, slug, extent)


    @classmethod
    def from_rd_png(cls, tmp_base, slug, extent):
        """
        Input: <tmp_base>.png
        Output: geo_image object
        """

        # Step 2: warp using gdalwarp to lon/lat in .tif
        #logger.info('Warping png to tif... %s' % img['filename_png'])
        command = 'gdalwarp %s %s -t_srs "+proj=latlong +datum=WGS83" -s_srs "%s"' % (
            tmp_base + '.png', tmp_base + '.tif', RD.strip())
        #logger.info(command)
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
