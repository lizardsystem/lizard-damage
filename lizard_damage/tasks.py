import datetime
import logging
import sys
import StringIO
import traceback

from celery.task import task

from lizard_damage import models
from lizard_damage import risk
from lizard_damage import emails
from lizard_damage.conf import settings
from lizard_damage.models import BenefitScenario
from lizard_task.models import SecuredPeriodicTask
from lizard_task.task import task_logging


def damage_scenario_to_task(damage_scenario, username="admin"):
    """
    Send provided damage scenario as task
    """
    task_name = 'Scenario (%05d) calculate damage' % damage_scenario.id
    task_kwargs = (
        '{"username": "%s", "taskname": "%s", "damage_scenario_id": "%d"}' % (
            username, task_name, damage_scenario.id))
    calc_damage_task, created = SecuredPeriodicTask.objects.get_or_create(
        name=task_name, defaults={
            'kwargs': task_kwargs,
            'task': 'lizard_damage.tasks.calculate_damage'
            })
    calc_damage_task.task = 'lizard_damage.tasks.calculate_damage'
    calc_damage_task.save()
    calc_damage_task.send_task(username=username)


def benefit_scenario_to_task(benefit_scenario, username="admin"):
    """
    Send provided benefit scenario as task
    """
    task_name = 'Scenario ({}) calculate benefit'.format(benefit_scenario.id)
    task_kwargs = (
        '{"username": "%s", "taskname": "%s", "benefit_scenario_id": "%d"}' % (
            username, task_name, benefit_scenario.id))
    calc_damage_task, created = SecuredPeriodicTask.objects.get_or_create(
        name=task_name, defaults={
            'kwargs': task_kwargs,
            'task': 'lizard_damage.tasks.calculate_benefit'
            })
    calc_damage_task.task = 'lizard_damage.tasks.calculate_benefit'
    calc_damage_task.save()
    calc_damage_task.send_task(username=username)


@task
#@task_logging
def send_email(scenario_id, username=None, taskname=None, loglevel=20,
               mail_template='email_received', subject='Onderwerp', email='',
               scenario_type='damage', extra_context={}):
    return emails.do_send_email(
        scenario_id, username, taskname, loglevel,
        mail_template, subject, email, scenario_type, extra_context)


@task
#@task_logging
def calculate_damage(
        damage_scenario_id, username=None, taskname=None, loglevel=20):
    """Call real_calculate_damage, send emails if an uncaught
    exception occurs.  Uncaught exceptions are usually problems in the
    code, not the input."""
    try:
        logger = logging.getLogger(taskname)
        damage_scenario = models.DamageScenario.objects.get(
            pk=damage_scenario_id)
        logger.info(
            "Starting scenario {} calculation...".format(damage_scenario))
        logger.info("BBBBBBBBBBBBBBBBBBBBB")
        damage_scenario.calculate(logger)
        logger.info("WWWWWWWWWWWWWWWWWWWWW")
    except:
        logger.info("AAAAAAAAAAAAAAAAAAAAA")
        exc_info = sys.exc_info()
        tracebackbuf = StringIO.StringIO()
        traceback.print_exception(*exc_info, limit=None, file=tracebackbuf)
        logger.info(tracebackbuf.getvalue())

        emails.send_email_to_task(
            damage_scenario_id, 'email_exception',
            "WaterSchadeSchatter: berekening mislukt")

        emails.send_email_to_task(
            damage_scenario_id, 'email_exception_traceback',
            "WaterSchadeSchatter: berekening gecrasht",
            email=settings.LIZARD_DAMAGE_EXCEPTION_EMAIL, extra_context={
                'exception': "{}: {}".format(exc_info[0], exc_info[1]),
                'traceback': tracebackbuf.getvalue()
                })


@task
#@task_logging
def calculate_benefit(
        benefit_scenario_id, username=None, taskname=None, loglevel=20):
    start_dt = datetime.datetime.now()
    logger = logging.getLogger(taskname)
    logger.info("calculate benefit")
    benefit_scenario = BenefitScenario.objects.get(pk=benefit_scenario_id)
    logger.info(
        "scenario: %d, %s" % (benefit_scenario.id, str(benefit_scenario)))

    errors = 0
    try:
        risk.create_benefit_map(
            benefit_scenario=benefit_scenario, logger=logger,
        )
    except:
        # For some reason logger.exception does not reach task logging.
        logger.error('Error creating benefit map.')
        for exception_line in traceback.format_exc().split('\n'):
            logger.error(exception_line)
        errors += 1

    # add BenefitScenarioResult objects for display on the map.

    if errors == 0:
        logger.info('STATS benefit van %s is klaar in %r' % (
            benefit_scenario.email,
            str(datetime.datetime.now() - start_dt)))
        logger.info(
            "creating email task for scenario %d" % benefit_scenario.id)
        subject = (
            'WaterSchadeSchatter: Resultaten beschikbaar voor scenario %s '
            % benefit_scenario.name)
        emails.send_email_to_task(
            benefit_scenario.id, 'email_ready_benefit',
            subject, username=username,
            scenario_type='benefit',
        )
        logger.info("finished")
    else:
        logger.info('STATS benefit van %s is mislukt in %r' % (
            benefit_scenario.email,
            str(datetime.datetime.now() - start_dt)))
        logger.info("there were errors in scenario %d" % benefit_scenario.id)
        logger.info("creating email task for error")
        subject = 'WaterSchadeSchatter: scenario %s heeft fouten' % (
            benefit_scenario.name,
        )
        emails.send_email_to_task(
            benefit_scenario.id, 'email_error', subject, username=username,
            scenario_type='benefit',
        )
        logger.info("finished with errors")
        return 'failure'
