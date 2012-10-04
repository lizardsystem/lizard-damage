# (c) Nelen & Schuurmans.  GPL licensed, see LICENSE.rst.
from __future__ import unicode_literals

from django.contrib import admin
from lizard_damage import models
from lizard_task.models import SecuredPeriodicTask

from lizard_damage import tasks

class DamageEventInline(admin.TabularInline):
    model = models.DamageEvent


class DamageEventWaterlevelInline(admin.TabularInline):
    model = models.DamageEventWaterlevel


class DamageEventResultInline(admin.TabularInline):
    model = models.DamageEventResult


class BenefitScenarioResultInline(admin.TabularInline):
    model = models.BenefitScenarioResult


class DamageEventAdmin(admin.ModelAdmin):
    list_display = ['__unicode__']
    actions = ['process']
    inlines = [DamageEventResultInline, DamageEventWaterlevelInline]

    def process(self, request, queryset):
        for damage_event in queryset:
            damage_event.process()
        return self.message_user(
            request,
            'DamageEvents calculated.'
        )
    process.short_description = 'Bereken schade voor geselecteerde events'


class DamageScenarioAdmin(admin.ModelAdmin):
    list_display = ['__unicode__', 'email', 'datetime_created']
    inlines = [DamageEventInline]
    actions = ['process', 'send_received_email', 'send_finished_email', ]

    class Meta:
        ordering = ('-datetime_created', )

    def process(self, request, queryset):
        sent = 0
        for damage_scenario in queryset:
            tasks.damage_scenario_to_task(damage_scenario, username="admin")
            sent += 1
        return self.message_user(
            request,
            '%d DamageScenarios sent to message queue.' % sent,
        )
    process.short_description = 'Bereken schade voor geselecteerde scenarios'

    def send_received_email(self, request, queryset):
        """Create a send mail task and put it on the queue."""
        sent = 0
        for damage_scenario in queryset:
            subject = 'Schademodule: Scenario %s ontvangen' % damage_scenario.name
            tasks.send_email_to_task(
                damage_scenario.id, 'email_received', subject, username='admin')
            sent += 1
        return self.message_user(
            request,
            '%d mail tasks are sent (the mails themselves are sent by the task).' % sent)
    send_received_email.short_description = 'Zend e-mail dat het scenario is ontvangen'

    def send_finished_email(self, request, queryset):
        """Create a send mail task and put it on the queue."""
        sent = 0
        for damage_scenario in queryset:
            subject = 'Schademodule: Resultaten beschikbaar voor scenario %s ' % damage_scenario.name
            tasks.send_email_to_task(
                damage_scenario.id, 'email_ready', subject, username='admin')
            sent += 1
        return self.message_user(
            request,
            '%d mail tasks are sent (the mails themselves are sent by the task).' % sent)
    send_finished_email.short_description = 'Zend e-mail dat het scenario is uitgerekend'


class UnitAdmin(admin.ModelAdmin):
    list_display = ['name', 'factor']


class BenefitScenarioAdmin(admin.ModelAdmin):
    list_display = ['__unicode__', 'email', 'datetime_created']
    inlines = [BenefitScenarioResultInline]


admin.site.register(models.AhnIndex)
admin.site.register(models.BenefitScenario, BenefitScenarioAdmin)
admin.site.register(models.Unit, UnitAdmin)
admin.site.register(models.DamageEvent, DamageEventAdmin)
admin.site.register(models.DamageEventResult)
admin.site.register(models.DamageScenario, DamageScenarioAdmin)
