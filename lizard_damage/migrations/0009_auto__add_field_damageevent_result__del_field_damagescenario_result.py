# encoding: utf-8
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models

class Migration(SchemaMigration):

    def forwards(self, orm):
        
        # Adding field 'DamageEvent.result'
        db.add_column('lizard_damage_damageevent', 'result', self.gf('django.db.models.fields.files.FileField')(max_length=100, null=True, blank=True), keep_default=False)

        # Deleting field 'DamageScenario.result'
        db.delete_column('lizard_damage_damagescenario', 'result')


    def backwards(self, orm):
        
        # Deleting field 'DamageEvent.result'
        db.delete_column('lizard_damage_damageevent', 'result')

        # Adding field 'DamageScenario.result'
        db.add_column('lizard_damage_damagescenario', 'result', self.gf('django.db.models.fields.files.FileField')(max_length=100, null=True, blank=True), keep_default=False)


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
        'lizard_damage.damageevent': {
            'Meta': {'object_name': 'DamageEvent'},
            'floodmonth': ('django.db.models.fields.IntegerField', [], {'default': '9'}),
            'floodtime': ('django.db.models.fields.FloatField', [], {}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'repairtime': ('django.db.models.fields.FloatField', [], {}),
            'result': ('django.db.models.fields.files.FileField', [], {'max_length': '100', 'null': 'True', 'blank': 'True'}),
            'scenario': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['lizard_damage.DamageScenario']"}),
            'status': ('django.db.models.fields.IntegerField', [], {'default': '1'}),
            'table': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'waterlevel': ('django.db.models.fields.files.FileField', [], {'max_length': '100'})
        },
        'lizard_damage.damageeventresult': {
            'Meta': {'object_name': 'DamageEventResult'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'raster': ('django.db.models.fields.files.FileField', [], {'max_length': '100'}),
            'table': ('django.db.models.fields.TextField', [], {})
        },
        'lizard_damage.damagescenario': {
            'Meta': {'object_name': 'DamageScenario'},
            'datetime_created': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'blank': 'True'}),
            'email': ('django.db.models.fields.EmailField', [], {'max_length': '128'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '64'}),
            'slug': ('django.db.models.fields.SlugField', [], {'db_index': 'True', 'max_length': '50', 'null': 'True', 'blank': 'True'}),
            'status': ('django.db.models.fields.IntegerField', [], {'default': '1'})
        },
        'lizard_damage.unit': {
            'Meta': {'object_name': 'Unit'},
            'factor': ('django.db.models.fields.FloatField', [], {'null': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '64', 'null': 'True', 'blank': 'True'})
        }
    }

    complete_apps = ['lizard_damage']
