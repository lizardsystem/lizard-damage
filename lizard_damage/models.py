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
from lizard_map import coordinates
from lizard_task.models import SecuredPeriodicTask
from pyproj import transform
from pyproj import Proj

import datetime
import os
import random
import string
import json

# from django.utils.translation import ugettext_lazy as _

RD = str("""
+proj=sterea +lat_0=52.15616055555555 +lon_0=5.38763888888889 +k=0.999908 +x_0=155000 +y_0=463000 +ellps=bessel +units=m +towgs84=565.2369,50.0087,465.658,-0.406857330322398,0.350732676542563,-1.8703473836068,4.0812 +no_defs <>
""")

WGS84 = str('+proj=latlong +datum=WGS84')

rd_proj = Proj(RD)
wgs84_proj = Proj(WGS84)


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
        (3, 'Kaarten met de max. waterstand van afzonderlijke gebeurtenissen.'),
        (4, 'Kaarten met voor verschillende herhalingstijden de waterstanden'),
        (5, 'Tijdserie aan kaarten met per tijdstip de '
            'waterstand van meerdere gebeurtenissen'),
        (6, 'Batenkaart maken met resultaten uit berekeningen'),
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
        return '%s %s' % (self.name, self.email)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = ''.join(random.sample(string.letters, 20))
        if not self.expiration_date:
            self.expiration_date = datetime.datetime.now() + datetime.timedelta(days=7)
        return super(BenefitScenario, self).save(*args, **kwargs)


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


