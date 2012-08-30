# (c) Nelen & Schuurmans.  GPL licensed, see LICENSE.rst.
from __future__ import unicode_literals

from django.contrib import admin
from lizard_damage import models
from lizard_task.models import SecuredPeriodicTask


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
    list_display = ['__unicode__', 'email']
    inlines = [DamageEventInline]
    actions = ['process', 'send_received_email', 'send_finished_email', ]

    def process(self, request, queryset):
        for damage_scenario in queryset:
            damage_scenario.process()
        return self.message_user(
            request,
            'DamageScenarios calculated.',
        )
    process.short_description = 'Bereken schade voor geselecteerde scenarios'

    def create_send_email_task(self, damage_scenario, mail_template, subject):
        task_name = 'Send %s mail for scenario %d' % (mail_template, damage_scenario.id)
        task_kwargs = '{"username": "admin", "taskname": "%s", "damage_scenario_id": "%d", "mail_template": "%s", "subject": "%s"}' % (task_name, damage_scenario.id, mail_template, subject)
        email_task, created = SecuredPeriodicTask.objects.get_or_create(
            name=task_name, defaults={
                'kwargs': task_kwargs,
                'task' : 'lizard_damage.tasks.send_email'}
            )
        email_task.kwargs = task_kwargs
        email_task.task = 'lizard_damage.tasks.send_email'
        email_task.save()
        email_task.send_task(username='admin')

    def send_received_email(self, request, queryset):
        """Create a send mail task and put it on the queue."""
        sent = 0
        for damage_scenario in queryset:
            subject = 'Schademodule: Scenario %s ontvangen' % damage_scenario.name
            self.create_send_email_task(damage_scenario, 'email_received', subject)
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
            self.create_send_email_task(damage_scenario, 'email_ready', subject)
            sent += 1
        return self.message_user(
            request,
            '%d mail tasks are sent (the mails themselves are sent by the task).' % sent)
    send_finished_email.short_description = 'Zend e-mail dat het scenario is uitgerekend'


class UnitAdmin(admin.ModelAdmin):
    list_display = ['name', 'factor']

admin.site.register(models.Unit, UnitAdmin)
admin.site.register(models.DamageEvent, DamageEventAdmin)
admin.site.register(models.DamageScenario, DamageScenarioAdmin)
