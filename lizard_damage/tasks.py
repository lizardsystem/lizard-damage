from django.core.mail import EmailMultiAlternatives
from django.core.mail import send_mail
from django.template import Context
#from django.template import Template
from django.template.loader import get_template

from lizard_damage.models import DamageScenario
from lizard_task.task import task_logging
from celery.task import task

import logging


@task
@task_logging
def damage_task(username=None, taskname=None, loglevel=20):
    logger = logging.getLogger(taskname)
    # Do your thing
    logger.info("Doing my thing")


@task
@task_logging
def send_email(damage_scenario_id, username=None, taskname=None, loglevel=20,
               mail_template='email_received'):
    logger = logging.getLogger(taskname)
    # Do your thing
    logger.info("send_mail: %s" % mail_template)
    damage_scenario = DamageScenario.objects.get(pk=damage_scenario_id)

    subject = 'Schademodule: Scenario "%s" ontvangen' % damage_scenario.name
    context = Context({"damage_scenario": damage_scenario})
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
