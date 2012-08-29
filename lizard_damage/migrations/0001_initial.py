# encoding: utf-8
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models

class Migration(SchemaMigration):

    def forwards(self, orm):
        
        # Adding model 'AhnIndex'
        db.create_table('lizard_damage_ahnindex', (
            ('gid', self.gf('django.db.models.fields.IntegerField')(primary_key=True)),
            ('x', self.gf('django.db.models.fields.FloatField')(null=True, blank=True)),
            ('y', self.gf('django.db.models.fields.FloatField')(null=True, blank=True)),
            ('cellsize', self.gf('django.db.models.fields.CharField')(max_length=2, blank=True)),
            ('lo_x', self.gf('django.db.models.fields.CharField')(max_length=6, blank=True)),
            ('lo_y', self.gf('django.db.models.fields.CharField')(max_length=6, blank=True)),
            ('bladnr', self.gf('django.db.models.fields.CharField')(max_length=24, blank=True)),
            ('update', self.gf('django.db.models.fields.DateField')(null=True, blank=True)),
            ('datum', self.gf('django.db.models.fields.DateField')(null=True, blank=True)),
            ('min_datum', self.gf('django.db.models.fields.DateField')(null=True, blank=True)),
            ('max_datum', self.gf('django.db.models.fields.DateField')(null=True, blank=True)),
            ('ar', self.gf('django.db.models.fields.FloatField')(null=True, blank=True)),
            ('the_geom', self.gf('django.contrib.gis.db.models.fields.MultiPolygonField')(srid=28992, null=True, blank=True)),
        ))
        db.send_create_signal('lizard_damage', ['AhnIndex'])

        # Adding model 'Unit'
        db.create_table('lizard_damage_unit', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=64, null=True, blank=True)),
            ('factor', self.gf('django.db.models.fields.FloatField')(null=True, blank=True)),
        ))
        db.send_create_signal('lizard_damage', ['Unit'])


    def backwards(self, orm):
        
        # Deleting model 'AhnIndex'
        db.delete_table('lizard_damage_ahnindex')

        # Deleting model 'Unit'
        db.delete_table('lizard_damage_unit')


    models = {
        'lizard_damage.ahnindex': {
            'Meta': {'object_name': 'AhnIndex'},
            'ar': ('django.db.models.fields.FloatField', [], {'null': 'True', 'blank': 'True'}),
            'bladnr': ('django.db.models.fields.CharField', [], {'max_length': '24', 'blank': 'True'}),
            'cellsize': ('django.db.models.fields.CharField', [], {'max_length': '2', 'blank': 'True'}),
            'datum': ('django.db.models.fields.DateField', [], {'null': 'True', 'blank': 'True'}),
            'gid': ('django.db.models.fields.IntegerField', [], {'primary_key': 'True'}),
            'lo_x': ('django.db.models.fields.CharField', [], {'max_length': '6', 'blank': 'True'}),
            'lo_y': ('django.db.models.fields.CharField', [], {'max_length': '6', 'blank': 'True'}),
            'max_datum': ('django.db.models.fields.DateField', [], {'null': 'True', 'blank': 'True'}),
            'min_datum': ('django.db.models.fields.DateField', [], {'null': 'True', 'blank': 'True'}),
            'the_geom': ('django.contrib.gis.db.models.fields.MultiPolygonField', [], {'srid': '28992', 'null': 'True', 'blank': 'True'}),
            'update': ('django.db.models.fields.DateField', [], {'null': 'True', 'blank': 'True'}),
            'x': ('django.db.models.fields.FloatField', [], {'null': 'True', 'blank': 'True'}),
            'y': ('django.db.models.fields.FloatField', [], {'null': 'True', 'blank': 'True'})
        },
        'lizard_damage.unit': {
            'Meta': {'object_name': 'Unit'},
            'factor': ('django.db.models.fields.FloatField', [], {'null': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '64', 'null': 'True', 'blank': 'True'})
        }
    }

    complete_apps = ['lizard_damage']
