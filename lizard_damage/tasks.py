import datetime
import json
import logging
import os
import subprocess
import sys
import StringIO
import traceback

from PIL import Image
from celery.task import task

from django.core.files import File
from django.template.defaultfilters import slugify

from lizard_damage import calc
from lizard_damage import risk
from lizard_damage import emails
from lizard_damage.conf import settings
from lizard_damage.models import BenefitScenario
from lizard_damage.models import DamageEventResult
from lizard_damage.models import DamageScenario
from lizard_damage.models import RD
from lizard_damage.models import extent_from_geotiff
from lizard_task.models import SecuredPeriodicTask
from lizard_task.task import task_logging


def convert_tif_to_png(filename_tif, filename_png):
    im = Image.open(filename_tif)
    im.save(filename_png, 'PNG')


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
@task_logging
def send_email(scenario_id, username=None, taskname=None, loglevel=20,
               mail_template='email_received', subject='Onderwerp', email='',
               scenario_type='damage', extra_context={}):
    return emails.do_send_email(
        scenario_id, username, taskname, loglevel,
        mail_template, subject, email, scenario_type, extra_context)


def call_calc_damage_for_waterlevel(
    logger, damage_event, damagetable, calc_type,
    alternative_heights_dataset, alternative_landuse_dataset):
    waterlevel_ascfiles = [dewl.waterlevel.path for dewl in
                       damage_event.damageeventwaterlevel_set.all()]
    logger.info("event %s" % (damage_event))
    logger.info(" - month %s, floodtime %s" % (
            damage_event.floodmonth, damage_event.floodtime))
    if damagetable:
        dt_path = damagetable.path
    else:
        # Default
        dt_path = os.path.join(
            settings.BUILDOUT_DIR, 'data/damagetable/dt.cfg')

    return calc.calc_damage_for_waterlevel(
        repetition_time=damage_event.repetition_time,
        waterlevel_ascfiles=waterlevel_ascfiles,
        dt_path=dt_path,
        month=damage_event.floodmonth,
        floodtime=damage_event.floodtime,
        repairtime_roads=damage_event.repairtime_roads,
        repairtime_buildings=damage_event.repairtime_buildings,
        calc_type=calc_type,
        alternative_landuse_dataset=alternative_landuse_dataset,
        alternative_heights_dataset=alternative_heights_dataset,
        logger=logger)


def process_result(
    logger, damage_event, damage_event_index, result, scenario_name):
    errors = 0
    # result[0] is the result zip file name in temp dir.
    with open(result[0], 'rb') as doc_file:
        try:
            if damage_event.result:
                logger.warning('Deleting existing results...')
                damage_event.result.delete()  # Delete old results
            logger.info('Saving results...')
            damage_event.result.save(
                '%s%i.zip' % (
                    slugify(scenario_name),
                    damage_event_index + 1),
                File(doc_file), save=True)
            damage_event.save()
        except:
            logger.error('Exception saving zipfile. Too big?')
            for exception_line in traceback.format_exc().split('\n'):
                logger.error(exception_line)
            errors = 1
        os.remove(result[0])  # remove temp file, whether it was saved
                              # or not

        # result[2] is the table in a data structure
        damage_event.table = json.dumps(result[2])

        # Store references to GeoImage objects
        damage_event.set_slugs(
            landuse_slugs=','.join(result[3]),
            height_slugs=','.join(result[4]),
            depth_slugs=','.join(result[5]))

        damage_event.save()

        # result[1] is a list of png files to be uploaded to the django db.
        if damage_event.damageeventresult_set.count() >= 0:
            logger.warning("Removing old images...")
            for damage_event_result in (
                damage_event.damageeventresult_set.all()):
                damage_event_result.image.delete()
                damage_event_result.delete()
        for img in result[1]:
            # convert filename_png to geotiff,
            #import pdb; pdb.set_trace()

            logger.info('Warping png to tif... %s' % img['filename_png'])
            command = (
                'gdalwarp %s %s -t_srs "+proj=latlong '
                '+datum=WGS83" -s_srs "%s"' % (
                    img['filename_png'], img['filename_tif'], RD.strip()))
            logger.info(command)
            # Warp png file, output is tif.
            subprocess.call([
                    'gdalwarp', img['filename_png'], img['filename_tif'],
                    '-t_srs', "+proj=latlong +datum=WGS84",
                    '-s_srs', RD.strip()])

            img['extent'] = extent_from_geotiff(img['filename_tif'])
            # Convert it back to png
            convert_tif_to_png(img['filename_tif'], img['filename_png'])

            damage_event_result = DamageEventResult(
                damage_event=damage_event,
                west=img['extent'][0],
                south=img['extent'][1],
                east=img['extent'][2],
                north=img['extent'][3])
            logger.info('Uploading %s...' % img['filename_png'])
            with open(img['filename_png'], 'rb') as img_file:
                damage_event_result.image.save(
                    img['dstname'] % damage_event.slug,
                    File(img_file), save=True)
            damage_event_result.save()
            os.remove(img['filename_png'])
            os.remove(img['filename_pgw'])
            os.remove(img['filename_tif'])
        logger.info('Result has %d images' % len(result[1]))
    return errors


@task
@task_logging
def calculate_damage(
    damage_scenario_id, username=None, taskname=None, loglevel=20):
    """Call real_calculate_damage, send emails if an uncaught
    exception occurs.  Uncaught exceptions are usually problems in the
    code, not the input."""
    try:
        return real_calculate_damage(
            damage_scenario_id, username, taskname, loglevel)
    except:
        exc_info = sys.exc_info()
        tracebackbuf = StringIO.StringIO()
        traceback.print_exception(*exc_info, limit=None, file=tracebackbuf)

        emails.send_email_to_task(
            damage_scenario_id, 'email_exception',
            "WaterSchadeSchatter: berekening mislukt", username=username)

        emails.send_email_to_task(
            damage_scenario_id, 'email_exception_traceback',
            "WaterSchadeSchatter: berekening gecrasht", username=username,
            email=settings.LIZARD_DAMAGE_EXCEPTION_EMAIL, extra_context={
                'exception': "{}: {}".format(exc_info[0], exc_info[1]),
                'traceback': tracebackbuf.getvalue()
                })


def real_calculate_damage(
    damage_scenario_id, username=None, taskname=None, loglevel=20):
    """
    Main calculation task.
    """
    start_dt = datetime.datetime.now()
    logger = logging.getLogger(taskname)
    logger.info("calculate damage")
    damage_scenario = DamageScenario.objects.get(pk=damage_scenario_id)
    logger.info(
        "scenario: %d, %s" % (damage_scenario.id, str(damage_scenario)))

    logger.info("calculating...")

    logger.info("scenario %s" % (damage_scenario.name))
    damage_scenario.status = damage_scenario.SCENARIO_STATUS_INPROGRESS
    damage_scenario.save()

    errors = 0
    for damage_event_index, damage_event in enumerate(
        damage_scenario.damageevent_set.all(),
    ):
        result = call_calc_damage_for_waterlevel(
            logger, damage_event,
            damage_scenario.damagetable,
            damage_scenario.calc_type,
            damage_scenario.alternative_heights_dataset,
            damage_scenario.alternative_landuse_dataset)
        if result:
            errors += process_result(
                logger, damage_event, damage_event_index,
                result, damage_scenario.name)
        else:
            errors += 1

    # Calculate risk maps
    if damage_scenario.scenario_type == 4:
        risk.create_risk_map(damage_scenario=damage_scenario, logger=logger)

    # Roundup
    damage_scenario.status = damage_scenario.SCENARIO_STATUS_DONE
    damage_scenario.save()

    if errors == 0:
        emails.send_damage_success_mail(
            damage_scenario, username, logger, start_dt)
        logger.info("finished successfully")
    else:
        emails.send_damage_error_mail(
            damage_scenario, username, logger, start_dt)
        logger.info("finished with errors")
        return 'failure'


@task
@task_logging
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
