from django.core.mail import EmailMultiAlternatives
from django.template import Context
#from django.template import Template
from django.template.loader import get_template

from lizard_damage.models import DamageScenario
from lizard_damage import calc
from lizard_task.task import task_logging
from lizard_task.models import SecuredPeriodicTask

from celery.task import task
from django.contrib.sites.models import Site

import logging


def damage_scenario_to_task(damage_scenario, username="admin"):
    """
    Send provided damage scenario as task
    """
    task_name = 'Calculate damage scenario %d' % damage_scenario.id
    task_kwargs = '{"username": "%s", "taskname": "%s", "damage_scenario_id": "%d"}' % (
        username, task_name, damage_scenario.id)
    calc_damage_task, created = SecuredPeriodicTask.objects.get_or_create(
        name=task_name, defaults={
            'kwargs': task_kwargs,
            'task': 'lizard_damage.tasks.calculate_damage'
            })
    calc_damage_task.task = 'lizard_damage.tasks.calculate_damage'
    calc_damage_task.save()
    calc_damage_task.send_task(username=username)


def send_email_to_task(damage_scenario_id, mail_template, subject, username='admin'):
    """
    Create a task for sending email
    """
    task_name = 'Send %s mail for scenario %d' % (mail_template, damage_scenario_id)
    task_kwargs = '{"username": "admin", "taskname": "%s", "damage_scenario_id": "%d", "mail_template": "%s", "subject": "%s"}' % (task_name, damage_scenario_id, mail_template, subject)
    email_task, created = SecuredPeriodicTask.objects.get_or_create(
        name=task_name, defaults={
            'kwargs': task_kwargs,
            'task' : 'lizard_damage.tasks.send_email'}
        )
    email_task.kwargs = task_kwargs
    email_task.task = 'lizard_damage.tasks.send_email'
    email_task.save()
    email_task.send_task(username=username)


@task
@task_logging
def send_email(damage_scenario_id, username=None, taskname=None, loglevel=20,
               mail_template='email_received', subject='Onderwerp'):
    logger = logging.getLogger(taskname)
    # Do your thing
    logger.info("send_mail: %s" % mail_template)
    damage_scenario = DamageScenario.objects.get(pk=damage_scenario_id)

    #subject = 'Schademodule: Scenario "%s" ontvangen' % damage_scenario.name
    try:
        root_url = 'http://%s' % Site.objects.all()[0].domain
    except:
        root_url = 'http://damage.lizard.net'
        logger.error('Error fetching Site... defaulting to damage.lizard.net')
    context = Context({"damage_scenario": damage_scenario, 'ROOT_URL': root_url})
    template_text = get_template("lizard_damage/%s.txt" % mail_template)
    template_html = get_template("lizard_damage/%s.html" % mail_template)

    from_email = 'no-reply@nelen-schuurmans.nl'
    to = damage_scenario.email

    logger.info("scenario: %s" % damage_scenario)
    logger.info("sending e-mail to: %s" % to)
    msg = EmailMultiAlternatives(subject, template_text.render(context), from_email, [to])
    msg.attach_alternative(template_html.render(context), 'text/html')
    msg.send()

    logger.info("e-mail has been successfully sent")


@task
@task_logging
def calculate_damage(damage_scenario_id, username=None, taskname=None, loglevel=20):
    """
    Main calculation task.
    """
    logger = logging.getLogger(taskname)
    logger.info("calculate damage")
    damage_scenario = DamageScenario.objects.get(pk=damage_scenario_id)
    logger.info("scenario: %d, %s" % (damage_scenario.id, str(damage_scenario)))

    logger.info("calculating...")

    import os
    from django.conf import settings
    ds_wl_filename = os.path.join(
        settings.DATA_ROOT, 'waterlevel', 'ws_test1.asc',
        )
    logger.info("scenario %s" % (damage_scenario.name))
    for damage_event in damage_scenario.damageevent_set.all():
        logger.info("event %s" % (damage_event))
        #logger.info(" - waterlevel: %s" % (damage_event.waterlevel))
        logger.info(" - month %s, floodtime %s, repairtime %s" % (
                damage_event.floodmonth, damage_event.floodtime, damage_event.repairtime))
        calc.calc_damage_for_waterlevel(
            ds_wl_filename=ds_wl_filename,
            damage_table_path='data/damagetable/dt.cfg',
            month=damage_event.floodmonth,
            floodtime=damage_event.floodtime,
            repairtime=damage_event.repairtime,
            logger=logger)

    logger.info("creating email task")
    subject = 'Schademodule: Resultaten beschikbaar voor scenario %s ' % damage_scenario.name
    send_email_to_task(damage_scenario.id, 'email_ready', subject, username=username)

    logger.info("finished")
