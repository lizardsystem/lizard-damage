# (c) Nelen & Schuurmans.  GPL licensed, see LICENSE.rst.
from __future__ import unicode_literals

from django.contrib import admin
from lizard_damage import models


class DamageEventInline(admin.TabularInline):
    model = models.DamageEvent


class DamageEventAdmin(admin.ModelAdmin):
    list_display = ['__unicode__']
    actions = ['process']
    
    def process(self, request, queryset):
        for damage_event in queryset:
            damage_event.process()
        return self.message_user(
            request,
            'DamageEvents calculated.'
        )
    process.short_description = 'Bereken schade voor geselecteerde events'


class DamageScenarioAdmin(admin.ModelAdmin):
    list_display = ['__unicode__']
    inlines = [DamageEventInline]
    actions = ['process']

    def process(self, request, queryset):
        for damage_scenario in queryset:
            damage_scenario.process()
        return self.message_user(
            request,
            'DamageScenarios calculated.',
        )
    process.short_description = 'Bereken schade voor geselecteerde scenarios'

class UnitAdmin(admin.ModelAdmin):
    list_display = ['name', 'factor']

admin.site.register(models.Unit, UnitAdmin)
admin.site.register(models.DamageEvent, DamageEventAdmin)
admin.site.register(models.DamageScenario, DamageScenarioAdmin)
