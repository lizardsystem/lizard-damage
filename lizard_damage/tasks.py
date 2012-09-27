from django.core.files import File
from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from django.template import Context
#from django.template import Template
from django.template.loader import get_template

from lizard_damage.models import DamageScenario
from lizard_damage.models import DamageEventResult
from lizard_damage.models import RD
from lizard_damage import calc
from lizard_task.task import task_logging
from lizard_task.models import SecuredPeriodicTask

from celery.task import task
from django.contrib.sites.models import Site
from django.template.defaultfilters import slugify

import logging
import os
import random
import string
import json
import subprocess
from osgeo import gdal
from PIL import Image


def extent_from_geotiff(filename):
    ds = gdal.Open(filename)
    width = ds.RasterXSize
    height = ds.RasterYSize
    gt = ds.GetGeoTransform()
    minx = gt[0]
    miny = gt[3] + width*gt[4] + height*gt[5] 
    maxx = gt[0] + width*gt[1] + height*gt[2]
    maxy = gt[3] 
    return (minx, miny, maxx, maxy)


def convert_tif_to_png(filename_tif, filename_png):
    im = Image.open(filename_tif)
    im.save(filename_png, 'PNG')


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


def send_email_to_task(damage_scenario_id, mail_template, subject, username='admin', email=""):
    """
    Create a task for sending email
    """
    task_name = 'Send %s mail for scenario %d' % (mail_template, damage_scenario_id)
    task_kwargs = '{"username": "admin", "taskname": "%s", "damage_scenario_id": "%d", "mail_template": "%s", "subject": "%s", "email": "%s"}' % (task_name, damage_scenario_id, mail_template, subject, email)
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
               mail_template='email_received', subject='Onderwerp', email=''):
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
    if not email:
        # Default
        to = damage_scenario.email
    else:
        # In case of user provided email (errors)
        to = email

    logger.info("scenario: %s" % damage_scenario)
    logger.info("sending e-mail to: %s" % to)
    msg = EmailMultiAlternatives(subject, template_text.render(context), from_email, [to])
    msg.attach_alternative(template_html.render(context), 'text/html')
    msg.send()

    damage_scenario.status = damage_scenario.SCENARIO_STATUS_SENT
    damage_scenario.save()

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

    logger.info("scenario %s" % (damage_scenario.name))
    damage_scenario.status = damage_scenario.SCENARIO_STATUS_INPROGRESS
    damage_scenario.save()

    errors = 0
    for damage_event_index, damage_event in enumerate(
        damage_scenario.damageevent_set.all(),
    ):
        # ds_wl_filename = os.path.join(
        #     settings.DATA_ROOT, 'waterlevel', 'ws_test1.asc',
        #     )

        # damage_event.waterlevel.path
        ds_wl_filenames = [dewl.waterlevel.path for dewl in
                          damage_event.damageeventwaterlevel_set.all()]
        logger.info("event %s" % (damage_event))
        #logger.info(" - waterlevel: %s" % (damage_event.waterlevel))
        logger.info(" - month %s, floodtime %s" % (
                damage_event.floodmonth, damage_event.floodtime))
        if damage_scenario.damagetable:
            dt_path = damage_scenario.damagetable.path
        else:
            # Default
            dt_path = os.path.join(settings.BUILDOUT_DIR, 'data/damagetable/dt.cfg')
        result = calc.calc_damage_for_waterlevel(
            repetition_time=damage_event.repetition_time,
            ds_wl_filenames=ds_wl_filenames,
            dt_path=dt_path,
            month=damage_event.floodmonth,
            floodtime=damage_event.floodtime,
            repairtime_roads=damage_event.repairtime_roads,
            repairtime_buildings=damage_event.repairtime_buildings,
            calc_type=damage_scenario.calc_type,
            logger=logger)
        if result:
            # result[0] is the result zip file name in temp dir.
            with open(result[0], 'rb') as doc_file:
                try:
                    if damage_event.result:
                        logger.warning('Deleting existing results...')
                        damage_event.result.delete()  # Delete old results
                    logger.info('Saving results...')
                    damage_event.result.save('%s%i.zip' % (
                            slugify(damage_scenario.name), damage_event_index + 1),
                        File(doc_file),save=True)
                    damage_event.save()
                except:
                    logger.error('Exception saving zipfile. Too big?')
                    for exception_line in traceback.format_exc().split('\n'):
                        logger.error(exception_line)
                    errors += 1
            os.remove(result[0])  # remove temp file, whether it was saved or not

            # result[2] is the table in a data structure
            damage_event.table = json.dumps(result[2])
            damage_event.save()

            # result[1] is a list of png files to be uploaded to the django db.
            if damage_event.damageeventresult_set.count() >= 0:
                logger.warning("Removing old images...")
                for damage_event_result in damage_event.damageeventresult_set.all():
                    damage_event_result.image.delete()
                    damage_event_result.delete()
            for img in result[1]:
                # convert filename_png to geotiff,
                #import pdb; pdb.set_trace()

                logger.info('Warping png to tif... %s' % img['filename_png'])
                command = 'gdalwarp %s %s -t_srs "+proj=latlong +datum=WGS84" -s_srs "%s"' % (
                    img['filename_png'], img['filename_tif'], RD.strip())
                logger.info(command)
                # Warp png file, output is tif.
                subprocess.call([
                    'gdalwarp', img['filename_png'], img['filename_tif'], 
                    '-t_srs', "+proj=latlong +datum=WGS84", '-s_srs', RD.strip()])

                img['extent'] = extent_from_geotiff(img['filename_tif'])
                # Convert it back to png
                #subprocess.call([
                #    'convert', img['filename_tif'], img['filename_png']]) 
                convert_tif_to_png(img['filename_tif'], img['filename_png'])

            #logger.info('Creating damage event results...')
            #for img in result[1]:
                damage_event_result = DamageEventResult(
                    damage_event=damage_event,
                    west=img['extent'][0],
                    south=img['extent'][1],
                    east=img['extent'][2],
                    north=img['extent'][3])
                logger.info('Uploading %s...' % img['filename_png'])
                with open(img['filename_png'], 'rb') as img_file:
                    damage_event_result.image.save(img['dstname'] % damage_event.slug,
                                                   File(img_file), save=True)
                damage_event_result.save()
                os.remove(img['filename_png'])
                os.remove(img['filename_pgw'])
                os.remove(img['filename_tif'])
        else:
            errors += 1

    damage_scenario.status = damage_scenario.SCENARIO_STATUS_DONE
    damage_scenario.save()

    if errors == 0:
        logger.info("creating email task for scenario %d" % damage_scenario.id)
        subject = 'STOWA Schade Calculator: Resultaten beschikbaar voor scenario %s ' % damage_scenario.name
        send_email_to_task(damage_scenario.id, 'email_ready', subject, username=username)
        logger.info("finished")
    else:
        logger.info("there were errors in scenario %d" % damage_scenario.id)
        logger.info("creating email task for error")
        subject = 'STOWA Schade Calculator: scenario %s heeft fouten' % damage_scenario.name
        send_email_to_task(damage_scenario.id, 'email_error', subject, username=username,
                           email='jack.ha@nelen-schuurmans.nl')
        logger.info("finished with errors")
        return 'failure'
