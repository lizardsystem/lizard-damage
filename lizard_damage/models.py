# -*- coding: utf-8 -*-
# (c) Nelen & Schuurmans.  GPL licensed, see LICENSE.rst.
from __future__ import (
  print_function,
  unicode_literals,
  absolute_import,
  division,
)

from django.contrib.gis.db import models

# from django.utils.translation import ugettext_lazy as _


class AhnIndex(models.Model):
    """
    Generated with bin/django inspectdb after executing, with
    DecimalFields replaced y FloatFields:

    shp2pgsql -s 28992 data/index/ahn2_05_int_index_gevuld\
    public.lizard_damage_ahnindex | psql schademodule\
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
