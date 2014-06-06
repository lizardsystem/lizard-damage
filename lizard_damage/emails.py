# (c) Nelen & Schuurmans.  GPL licensed, see LICENSE.rst.
# -*- coding: utf-8 -*-

"""Send emails (using a Celery task)."""

# Python 3 is coming
from __future__ import unicode_literals
from __future__ import print_function
from __future__ import absolute_import
from __future__ import division

import datetime
import json
import logging

from django import template
from django.core import mail
from django.core import urlresolvers
from django.template import loader
from django.contrib.sites.models import Site

from lizard_task.models import SecuredPeriodicTask

from . import models


def send_email_to_task(
        scenario_id, mail_template, subject,
        email="", scenario_type='damage', extra_context=None):
    """
    Create a task for sending email
    """
    task_name = 'Scenario ({}) send mail {}'.format(scenario_id, mail_template)
    task_kwargs = (
        '{{'
        '"username": "admin", '
        '"taskname": "{}", '
        '"scenario_id": "{}", '
        '"mail_template": "{}", '
        '"subject": "{}", '
        '"email": "{}", '
        '"scenario_type": "{}", '
        '"extra_context": {} '
        '}}'
        ).format(task_name, scenario_id, mail_template,
                 subject, email, scenario_type,
                 "{}" if not extra_context else json.dumps(extra_context))
    email_task, created = SecuredPeriodicTask.objects.get_or_create(
        name=task_name, defaults={
            'kwargs': task_kwargs,
            'task': 'lizard_damage.tasks.send_email'}
        )
    email_task.kwargs = task_kwargs
    email_task.task = 'lizard_damage.tasks.send_email'
    email_task.save()
    email_task.send_task(username='mail')


def do_send_email(
        scenario_id, username=None, taskname=None, loglevel=20,
        mail_template='email_received', subject='Onderwerp', email='',
        scenario_type='damage', extra_context={}):
    """Called from the send_email task to actually send it."""

    logger = logging.getLogger(taskname)

    logger.info("send_mail: %s" % mail_template)
    scenario = dict(
        damage=models.DamageScenario, benefit=models.BenefitScenario,
    )[scenario_type].objects.get(pk=scenario_id)

    try:
        root_url = 'http://%s' % Site.objects.all()[0].domain
    except:
        root_url = 'http://damage.lizard.net'
        logger.error('Error fetching Site... defaulting to damage.lizard.net')
    context = template.Context(
        {"damage_scenario": scenario, 'ROOT_URL': root_url})
    context.update(extra_context)

    template_text = loader.get_template(
        "lizard_damage/%s.txt" % mail_template)
    template_html = loader.get_template(
        "lizard_damage/%s.html" % mail_template)

    from_email = 'no-reply@nelen-schuurmans.nl'
    to_email = email or scenario.email

    logger.info("scenario: %s" % scenario)
    logger.info("sending e-mail to: %s" % to_email)
    msg = mail.EmailMultiAlternatives(
        subject, template_text.render(context), from_email, [to_email])
    msg.attach_alternative(template_html.render(context), 'text/html')
    msg.send()

    scenario.status = scenario.SCENARIO_STATUS_SENT
    scenario.save()

    logger.info("e-mail has been successfully sent")
    logger.info("url was {}".format(
        urlresolvers.reverse(
            "lizard_damage_result", kwargs=dict(slug=scenario.slug))))


def send_damage_success_mail(damage_scenario, logger, start_dt):
    """Send success mail"""
    logger.info('STATS scenario type %s van %s is klaar in %r' % (
        damage_scenario.scenario_type_str,
        damage_scenario.email,
        str(datetime.datetime.now() - start_dt)))
    logger.info("creating email task for scenario %d" % damage_scenario.id)
    subject = (
        'WaterSchadeSchatter: Resultaten beschikbaar voor scenario %s '
        % damage_scenario.name)
    send_email_to_task(
        damage_scenario.id, 'email_ready', subject)


def send_damage_error_mail(damage_scenario, logger, start_dt):
    # Send error mail
    logger.info('STATS scenario type %s van %s is mislukt in %r' % (
        damage_scenario.scenario_type_str,
        damage_scenario.email,
        str(datetime.datetime.now() - start_dt)))
    logger.info("there were errors in scenario %d" % damage_scenario.id)
    logger.info("creating email task for error")
    subject = (
        'WaterSchadeSchatter: scenario %s heeft fouten'
        % damage_scenario.name)
    send_email_to_task(
        damage_scenario.id, 'email_error', subject)
    send_email_to_task(
        damage_scenario.id, 'email_error', subject,
        email='olivier.hoes@nelen-schuurmans.nl')
