# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding field 'DamageScenario.ahn_version'
        db.add_column(u'lizard_damage_damagescenario', 'ahn_version',
                      self.gf('django.db.models.fields.CharField')(default=2, max_length=2),
                      keep_default=False)


    def backwards(self, orm):
        # Deleting field 'DamageScenario.ahn_version'
        db.delete_column(u'lizard_damage_damagescenario', 'ahn_version')


    models = {
        u'lizard_damage.benefitscenario': {
            'Meta': {'object_name': 'BenefitScenario'},
            'datetime_created': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'blank': 'True'}),
            'email': ('django.db.models.fields.EmailField', [], {'max_length': '128'}),
            'expiration_date': ('django.db.models.fields.DateTimeField', [], {}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '64'}),
            'slug': ('django.db.models.fields.SlugField', [], {'max_length': '50', 'null': 'True', 'blank': 'True'}),
            'status': ('django.db.models.fields.IntegerField', [], {'default': '1'}),
            'zip_result': ('django.db.models.fields.files.FileField', [], {'max_length': '100', 'null': 'True', 'blank': 'True'}),
            'zip_risk_a': ('django.db.models.fields.files.FileField', [], {'max_length': '100'}),
            'zip_risk_b': ('django.db.models.fields.files.FileField', [], {'max_length': '100'})
        },
        u'lizard_damage.benefitscenarioresult': {
            'Meta': {'object_name': 'BenefitScenarioResult'},
            'benefit_scenario': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['lizard_damage.BenefitScenario']"}),
            'east': ('django.db.models.fields.FloatField', [], {}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'image': ('django.db.models.fields.files.FileField', [], {'max_length': '100'}),
            'north': ('django.db.models.fields.FloatField', [], {}),
            'south': ('django.db.models.fields.FloatField', [], {}),
            'west': ('django.db.models.fields.FloatField', [], {})
        },
        u'lizard_damage.damageevent': {
            'Meta': {'object_name': 'DamageEvent'},
            'floodmonth': ('django.db.models.fields.IntegerField', [], {'default': '9'}),
            'floodtime': ('django.db.models.fields.FloatField', [], {}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'max_height': ('django.db.models.fields.FloatField', [], {'null': 'True', 'blank': 'True'}),
            'min_height': ('django.db.models.fields.FloatField', [], {'null': 'True', 'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100', 'null': 'True', 'blank': 'True'}),
            'repairtime_buildings': ('django.db.models.fields.FloatField', [], {'default': '432000'}),
            'repairtime_roads': ('django.db.models.fields.FloatField', [], {'default': '432000'}),
            'repetition_time': ('django.db.models.fields.FloatField', [], {'null': 'True', 'blank': 'True'}),
            'scenario': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['lizard_damage.DamageScenario']"}),
            'slug': ('django.db.models.fields.SlugField', [], {'max_length': '50', 'null': 'True', 'blank': 'True'}),
            'status': ('django.db.models.fields.IntegerField', [], {'default': '1'}),
            'table': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'})
        },
        u'lizard_damage.damageeventresult': {
            'Meta': {'object_name': 'DamageEventResult'},
            'damage_event': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['lizard_damage.DamageEvent']"}),
            'east': ('django.db.models.fields.FloatField', [], {}),
            'geotransform_json': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'north': ('django.db.models.fields.FloatField', [], {}),
            'relative_path': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'result_type': ('django.db.models.fields.CharField', [], {'max_length': '10'}),
            'south': ('django.db.models.fields.FloatField', [], {}),
            'west': ('django.db.models.fields.FloatField', [], {})
        },
        u'lizard_damage.damageeventwaterlevel': {
            'Meta': {'ordering': "(u'index',)", 'object_name': 'DamageEventWaterlevel'},
            'event': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['lizard_damage.DamageEvent']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'index': ('django.db.models.fields.IntegerField', [], {'default': '100'}),
            'waterlevel_path': ('django.db.models.fields.FilePathField', [], {'max_length': '200', 'null': 'True', 'blank': 'True'})
        },
        u'lizard_damage.damagescenario': {
            'Meta': {'object_name': 'DamageScenario'},
            'ahn_version': ('django.db.models.fields.CharField', [], {'default': '2', 'max_length': '2'}),
            'calc_type': ('django.db.models.fields.IntegerField', [], {'default': '2'}),
            'customheights': ('django.db.models.fields.FilePathField', [], {'max_length': '200', 'null': 'True', 'blank': 'True'}),
            'customlanduse': ('django.db.models.fields.FilePathField', [], {'max_length': '200', 'null': 'True', 'blank': 'True'}),
            'customlandusegeoimage': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['lizard_damage.GeoImage']", 'null': 'True', 'blank': 'True'}),
            'damagetable_file': ('django.db.models.fields.FilePathField', [], {'max_length': '200', 'null': 'True', 'blank': 'True'}),
            'datetime_created': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'blank': 'True'}),
            'email': ('django.db.models.fields.EmailField', [], {'max_length': '128'}),
            'expiration_date': ('django.db.models.fields.DateTimeField', [], {}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '64'}),
            'scenario_type': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'slug': ('django.db.models.fields.SlugField', [], {'max_length': '50', 'null': 'True', 'blank': 'True'}),
            'status': ('django.db.models.fields.IntegerField', [], {'default': '1'})
        },
        u'lizard_damage.geoimage': {
            'Meta': {'object_name': 'GeoImage'},
            'east': ('django.db.models.fields.FloatField', [], {}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'image': ('django.db.models.fields.files.FileField', [], {'max_length': '100'}),
            'north': ('django.db.models.fields.FloatField', [], {}),
            'slug': ('django.db.models.fields.SlugField', [], {'max_length': '50'}),
            'south': ('django.db.models.fields.FloatField', [], {}),
            'west': ('django.db.models.fields.FloatField', [], {})
        },
        u'lizard_damage.riskresult': {
            'Meta': {'object_name': 'RiskResult'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'scenario': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['lizard_damage.DamageScenario']"}),
            'zip_risk': ('django.db.models.fields.files.FileField', [], {'max_length': '100'})
        },
        u'lizard_damage.roads': {
            'Meta': {'object_name': 'Roads', 'db_table': "u'data_roads'"},
            'gid': ('django.db.models.fields.IntegerField', [], {'primary_key': 'True'}),
            'gridcode': ('django.db.models.fields.SmallIntegerField', [], {'null': 'True', 'blank': 'True'}),
            'the_geom': ('django.contrib.gis.db.models.fields.MultiPolygonField', [], {'srid': '28992', 'null': 'True', 'blank': 'True'}),
            'typeinfr_1': ('django.db.models.fields.CharField', [], {'max_length': '25', 'blank': 'True'}),
            'typeweg': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'})
        },
        u'lizard_damage.unit': {
            'Meta': {'object_name': 'Unit'},
            'factor': ('django.db.models.fields.FloatField', [], {'null': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '64', 'null': 'True', 'blank': 'True'})
        }
    }

    complete_apps = ['lizard_damage']