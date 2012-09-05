# -*- coding: utf-8 -*-
# (c) Nelen & Schuurmans.  GPL licensed, see LICENSE.rst.
from __future__ import (
  print_function,
  unicode_literals,
  absolute_import,
  division,
)
from django.contrib.gis.db import models

import os
import random
import string

# from django.utils.translation import ugettext_lazy as _

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
    Generated with bin/django inspectdb after executing, with
    DecimalFields replaced y FloatFields:

    shp2pgsql -s 28992 data/index/ahn2_05_int_index_gevuld\
    public.lizard_damage_ahnindex | sed s/geom/the_geom/g | psql schademodule\
    --username buildout

    When using postgis2, shp2pgsql must take care of the table creation
    since django doesn't handle postgis2 very well currently.
    """
    gid = models.IntegerField(primary_key=True)
    x = models.FloatField(null=True, blank=True)
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
    the_geom = models.MultiPolygonField(srid=28992, null=True, blank=True)
    objects = models.GeoManager()


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

    status = models.IntegerField(
        choices=SCENARIO_STATUS_CHOICES,
        default=SCENARIO_STATUS_RECEIVED,
    )
    name = models.CharField(max_length=64)
    slug = models.SlugField(null=True, blank=True, help_text='auto generated on save; used for url')
    email = models.EmailField(max_length=128)
    # token = models.CharField(max_length=32)

    datetime_created = models.DateTimeField(auto_now=True)

    def __unicode__(self):
        return self.name

    def process(self):
        pass

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = ''.join(random.sample(string.letters, 20))
        return super(DamageScenario, self).save(*args, **kwargs)


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

    status = models.IntegerField(
        choices=EVENT_STATUS_CHOICES,
        default=EVENT_STATUS_RECEIVED,
    )
    scenario = models.ForeignKey(DamageScenario)
    floodtime = models.FloatField(help_text='How long was it flooded, in seconds')
    repairtime = models.FloatField(help_text='In seconds')
    waterlevel = models.FileField(upload_to='scenario/waterlevel')
    # flooddate = models.DateTimeField()
    floodmonth = models.IntegerField(default=9)

    # calculationtype = models.IntegerField()
    # repetitiontime = models.FloatField(help_text='In years')

    # Result
    table = models.TextField(null=True, blank=True)
    result = models.FileField(
        upload_to='scenario/result',
        null=True, blank=True,
        help_text='Will be filled once the calculation has been done')

    def __unicode__(self):
        try:
            return '%s' % (os.path.basename(self.waterlevel.path))
        except:
            return '(no waterlevel)'

    @property
    def result_display(self):
        """display name of result"""
        return '%s (%s)' % (
            os.path.basename(self.result.name),
            friendly_filesize(self.result.size))

# class DamageEventResult(models.Model):
#     """ Partial damage grid with corresponding damage table."""
#     table = models.TextField()
#     raster = models.FileField(upload_to='scenario/result')
#     """
#      with open('/tmp/test', 'rb') as testfile:
#          ds.waterlevel.save('blabla', File(testfile), save=True)
#     """










