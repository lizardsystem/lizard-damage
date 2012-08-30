import logging
from celery.task import task
from lizard_task.task import task_logging
from django.core.mail import send_mail
from lizard_damage.models import DamageScenario


@task
@task_logging
def damage_task(username=None, taskname=None, loglevel=20):
    logger = logging.getLogger(taskname)
    # Do your thing
    logger.info("Doing my thing")


@task
@task_logging
def send_received_email(damage_scenario_id, username=None, taskname=None, loglevel=20):
    logger = logging.getLogger(taskname)
    # Do your thing
    logger.info("send_received_mail")
    damage_scenario = DamageScenario.objects.get(pk=damage_scenario_id)
    send_mail(
        'Schademodule: Scenario "%s" ontvangen' % damage_scenario.name,
        'Schademodule scenario "%s" ontvangen. Als de berekening klaar is krijgt U een nieuw bericht.' % (
            damage_scenario.name),
        'no-reply@nelen-schuurmans.nl',
        [damage_scenario.email], fail_silently=False)
    logger.info("e-mail has been successfully sent to %s for scenario %s" % (damage_scenario.email, damage_scenario.name))
