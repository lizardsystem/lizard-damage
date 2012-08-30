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
    list_display = ['__unicode__']
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

    def send_received_email(self, request, queryset):
        """Create a send mail task and put it on the queue."""
        sent = 0
        for damage_scenario in queryset:
            task_name = 'Send received mail for scenario %d' % damage_scenario.id
            task_kwargs = '{"username": "admin", "taskname": "%s", "damage_scenario_id": "%d"}' % (
                        task_name, damage_scenario.id)
            email_task, created = SecuredPeriodicTask.objects.get_or_create(
                name=task_name,
                task='lizard_damage.tasks.send_received_email',
                defaults={'kwargs':task_kwargs},
                )
            email_task.kwargs = task_kwargs
            email_task.save()
            email_task.send_task(username='admin')
            sent += 1
        return self.message_user(
            request,
            '%d mail tasks are sent (the mails themselves are sent by the task).' % sent)
    send_received_email.short_description = 'Zend e-mail dat het scenario is ontvangen'

    def send_finished_email(self, request, queryset):
        return self.message_user(request, 'TODO')
    send_finished_email.short_description = 'Zend e-mail dat het scenario is uitgerekend'


class UnitAdmin(admin.ModelAdmin):
    list_display = ['name', 'factor']

admin.site.register(models.Unit, UnitAdmin)
admin.site.register(models.DamageEvent, DamageEventAdmin)
admin.site.register(models.DamageScenario, DamageScenarioAdmin)
