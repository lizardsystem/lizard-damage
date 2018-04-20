# (c) Nelen & Schuurmans.  GPL licensed, see LICENSE.rst.
from __future__ import unicode_literals

from django.core.urlresolvers import reverse
from django.http import HttpResponse
from django.views.generic import TemplateView
from django.views.generic import View
from django.shortcuts import get_object_or_404
from django.core.files.storage import FileSystemStorage
from django.contrib.sites.models import Site

from lizard_damage import tasks
from lizard_damage.conf import settings
from lizard_damage.models import BenefitScenario
from lizard_damage.models import DamageScenario
from lizard_damage.models import DamageEvent
from lizard_damage.models import GeoImage
from lizard_ui.views import ViewContextMixin
from lizard_damage import tools

from zipfile import ZipFile
import csv
import shutil
import os
import re
import tempfile
from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont
import logging

# Do not generate directoryname, because for each worker the directory
# will be different and that loads to errors.
temp_storage_location = '/tmp/django_uploads'
temp_storage = FileSystemStorage(location=temp_storage_location)


logger = logging.getLogger(__name__)
# from lizard_damage import models


from django.http import HttpResponseRedirect
from django.contrib.formtools.wizard.views import SessionWizardView


def show_form_condition(condition):
    """Determine for a specific wizard step if it should be shown.

    condition is [] with ints which indicate a scenario_type
    """
    def show_form_fun(wizard):
        cleaned_data = wizard.get_cleaned_data_for_step('0') or {}
        scenario_type = int(cleaned_data.get('scenario_type', 0))
        return scenario_type in condition
    return show_form_fun


"""
DamageScenario types:
0, '1 Kaart met de max waterstand van 1 gebeurtenis'),
1, '1 Kaart met de waterstand voor een zekere herhalingstijd'),
2, 'Kaarten met per tijdstip de waterstand van 1 gebeurtenis'),
3, 'Kaarten met de max. waterstand van afzonderlijke gebeurtenissen.'),
4, 'Kaarten met voor verschillende herhalingstijden de waterstanden'),
5, 'Tijdserie aan kaarten met per tijdstip de '
   'waterstand van meerdere gebeurtenissen'),
6, 'Batenkaart',
"""


def damage_scenario_from_type_0(all_form_data):
    return DamageScenario.setup(
        name=all_form_data['name'],
        email=all_form_data['email'],
        scenario_type=all_form_data['scenario_type'],
        calc_type=all_form_data['calc_type'],
        ahn_version=all_form_data['ahn_version'],
        customheights=all_form_data.get('customheights_file'),
        customlanduse=all_form_data.get('customlanduse_file'),
        damagetable=all_form_data.get('damagetable'),
        damage_events=[dict(
            floodtime_hours=all_form_data['floodtime'],
            repairtime_roads_days=all_form_data['repairtime_roads'],
            repairtime_buildings_days=all_form_data['repairtime_buildings'],
            floodmonth=all_form_data['floodmonth'],
            repetition_time=all_form_data.get('repetition_time'),
            waterlevels=[dict(
                waterlevel=all_form_data['waterlevel'],
                index=1)])])


def damage_scenario_from_uniform_levels_batch_type(all_form_data):
    events = []
    tempdir = tempfile.mkdtemp()
    base_waterlevel_file = all_form_data['waterlevel_file']
    increment = all_form_data['increment']
    start_level = all_form_data['start_level']
    for index in range(all_form_data['number_of_increments']):
        desired_level = start_level + index * increment
        level_filename = os.path.join(tempdir, 'waterlevel_%s.tif' % desired_level)
        # ^^^ 'waterlevel_' should be retained as prefix, this is needed for
        # re-assembling the output afterwards.
        # gdal_calc.py -A in.asc --calc 2.2 --NoDataValue=-9999 --outfile out.tif
        cmd = ("gdal_calc.py -A %s --calc %s "
               "--NoDataValue=-9999 --outfile %s")
        logger.debug("Generating water level file (at %s) for batch: %s",
                     desired_level, level_filename)
        os.system(cmd % (base_waterlevel_file, desired_level, level_filename))
        event = dict(
            floodtime_hours=all_form_data['floodtime'],
            repairtime_roads_days=all_form_data['repairtime_roads'],
            repairtime_buildings_days=all_form_data['repairtime_buildings'],
            floodmonth=all_form_data['floodmonth'],
            repetition_time=all_form_data.get('repetition_time'),
            waterlevels=[{'waterlevel': level_filename,
                          'index': index + 1}])
        events.append(event)

    return DamageScenario.setup(
        name=all_form_data['name'],
        email=all_form_data['email'],
        scenario_type=all_form_data['scenario_type'],
        calc_type=all_form_data['calc_type'],
        ahn_version=all_form_data['ahn_version'],
        customheights=all_form_data.get('customheights_file'),
        customlanduse=all_form_data.get('customlanduse_file'),
        damagetable=all_form_data.get('damagetable'),
        damage_events=events)


class BatchConfig(object):
    def __init__(self, content):
        # Set default headers:
        self.scenario_type = '3'
        self.calc_type = 'max'
        self.scenario_damage_table = ''
        self.ahn_version = '2'

        head, body = [], []
        for line in content:
            if line.count(',') == 1:
                head.append(line)
            else:
                body.append(line)

        for rec in csv.reader(head):
            setattr(self, rec[0], rec[1])

        self.events = list(csv.DictReader(body))


def unpack_zipfile_into_scenario(zipfile, scenario_name='', scenario_email=''):
    """
    Create scenario structure from (user uploaded) zip file
    """
    zip_temp = tempfile.mkdtemp()
    with ZipFile(zipfile, 'r') as myzip:
        config = BatchConfig(myzip.open('index.csv').readlines())

        scenario_data = {
            'name': getattr(config, 'scenario_name', scenario_name),
            'email': getattr(config, 'scenario_email', scenario_email),
            'scenario_type': int(config.scenario_type),
            'ahn_version': getattr(config, 'ahn_version', '2'),
            'customheights': None,
            'customlanduse': None,
            'damagetable': None,
            'damage_events': []
        }
        scenario_data['calc_type'] = {
            'min': 1, 'max': 2, 'avg': 3,
        }.get(config.scenario_calc_type.lower(), 2)

        if config.scenario_damage_table:
            # extract to temp dir
            myzip.extract(config.scenario_damage_table, zip_temp)
            scenario_data['damagetable'] = os.path.join(
                zip_temp, config.scenario_damage_table)

        for event in config.events:
            # This is an event
            damage_event = {
                'name': event['event_name'],
                'floodtime_hours': event['floodtime'],
                'repairtime_roads_days': event['repairtime_roads'],
                'repairtime_buildings_days': event['repairtime_buildings'],
                'floodmonth': event['floodmonth'],
                'waterlevels': [],
                'repetition_time': event.get('repetition_time', None) or None
            }
            scenario_data['damage_events'].append(damage_event)

            if scenario_data['scenario_type'] == 2:
                # guess the waterlevel names from the zip
                zip_file_names = myzip.namelist()
                re_match = re.match(
                    '(.*[^0-9])([0-9]+)(\.asc)$',
                    event['waterlevel']).groups()  # i.e. ('ws', '324', '.asc')

                re_pattern = re.compile(
                    '%s[0-9]+%s' % (re_match[0], re_match[2]))
                water_level_filenames = [
                    fn for fn in zip_file_names
                    if re.match(re_pattern, fn)]
                water_level_filenames.sort()
            else:
                water_level_filenames = [event['waterlevel']]

            for index, water_level_filename in enumerate(
                    water_level_filenames):
                myzip.extract(water_level_filename, zip_temp)
                tempfilename = os.path.join(
                    zip_temp, water_level_filename)
                damage_event['waterlevels'].append({
                    'waterlevel': tempfilename,
                    'index': index
                })
        damage_scenario = DamageScenario.setup(**scenario_data)

    shutil.rmtree(zip_temp)
    return damage_scenario


def damage_scenario_from_zip_type(all_form_data):
    """
    Unpack zipfile, make scenario with events
    """
    zipfile = all_form_data['zipfile']
    scenario_name = all_form_data['name']
    scenario_email = all_form_data['email']

    damage_scenario = unpack_zipfile_into_scenario(
        zipfile, scenario_name=scenario_name,
        scenario_email=scenario_email)

    # And delete the zipfile
    try:
        logger.info('Deleting temp zipfile %s' % (zipfile.file.name))
        os.remove(zipfile.file.name)
    except:
        logger.error(
            'Error deleting temp zipfile %s (but what the heck...)' % (
                zipfile.file.name))

    return damage_scenario


def analyze_zip_file(zipfile):
    """
    Analyze zip file: generate kind of logging

    This function is kinda dirty, because parts are copied from
    unpack_zipfile_into_scenario.
    """
    result = []

    # read and parse
    with ZipFile(zipfile) as archive:
        namelist = archive.namelist()
        try:
            index_lines = archive.open('index.csv').readlines()
        except KeyError:
            return 'Zip-bestand bevat geen "index.csv".'
        try:
            config = BatchConfig(index_lines)
        except Exception as error:
            return '"fout bij lezen van index.csv:\n{}"'.format(error)

    # scenario type
    scenario = int(config.scenario_type)
    if scenario not in DamageScenario.SCENARIO_TYPES_DICT:
        message = 'Onbekend scenariotype ({}); kies uit 0 t/m 4.'
        result.append(message.format(scenario))

    # scenario calc type
    calc_type = config.scenario_calc_type
    if calc_type not in ('min', 'max', 'avg'):
        message = 'Onbekend berekeningstype ({}); kies min, max of avg.'
        result.append(message.format(calc_type))

    # scenario damage table
    damage_table = config.scenario_damage_table
    if damage_table and damage_table not in namelist:
        message = 'Schadetabel "{}" niet gevonden in zipfile.'
        result.append(message.format(damage_table))

    # waterlevel files
    for event in config.events:
        waterlevel = event['waterlevel']
        if waterlevel not in namelist:
            message = 'Waterstand "{}" niet gevonden in zipfile.'
            result.append(message.format(waterlevel))

    # repetition times
    rtimes = [event['repetition_time'] for event in config.events]
    if scenario in (1, 4) and not all(rtimes):
        message = ('Scenario type is {}, maar niet alle '
                   'waterstanden hebben een herhalingstijd.')
        result.append(message.format(scenario))

    if not result:
        # Everything seems to be ok
        result.append("zip bestand ok")

    return '\n'.join(result)


def create_benefit_scenario(all_form_data):
    """batenkaart"""
    benefit_scenario = BenefitScenario(
        name=all_form_data['name'],
        email=all_form_data['email'],
        zip_risk_a=all_form_data['zipfile_risk_before'],
        zip_risk_b=all_form_data['zipfile_risk_after'],)
    benefit_scenario.save()
    return benefit_scenario


def analyze_benefit_files(zipfile_before, zipfile_after):
    result = ['start analyse']
    return '\n'.join(result)


class Wizard(ViewContextMixin, SessionWizardView):
    template_name = 'lizard_damage/base_form.html'
    file_storage = temp_storage

    def get_form_initial(self, step):
        # For batch processing
        if step == '8':
            form_datas = {}
            for form_step in ('3', '4', '5'):
                form_data = self.get_cleaned_data_for_step(form_step)
                if form_data:
                    form_datas.update(form_data)
            try:
                zipfile = form_datas['zipfile']
                logger.info('zipfile.file.name %s' % zipfile.file.name)
                print 'zipfile.file.name %s' % zipfile.file.name
                return {'zip_content': analyze_zip_file(zipfile)}
            except:
                return {'zip_content': 'analyse gefaald, zipfile is niet goed'}
        # For batenkaart
        if step == '9':
            form_data = self.get_cleaned_data_for_step('7')
            try:
                return {'zip_content': analyze_benefit_files(
                    form_data['zipfile_risk_before'],
                    form_data['zipfile_risk_after'])}
            except:
                return {
                    'zip_content':
                    'analyse gefaald, batenkaart bestanden zijn niet goed'
                    }
        return super(Wizard, self).get_form_initial(step)

    def version(self):
        return tools.version()

    def done(self, form_list, **kwargs):
        """
        The Wizard is finished: create a new DamageScenario object and
        launch the calculation task associated to it.
        """
        scenario_type_name = {
            0: '1 Kaart met de max waterstand van 1 gebeurtenis',
            1: '1 Kaart met de waterstand voor een zekere herhalingstijd',
            2: 'Kaarten met per tijdstip de waterstand van 1 gebeurtenis',
            3: 'Kaarten met de max. waterstand van afzonderlijke '
            'gebeurtenissen.',
            7: 'Schadeberekening voor een reeks waterstanden voor 1 gebied',
            4: 'Kaarten met voor verschillende herhalingstijden de '
            'waterstanden',
            5: 'Tijdserie aan kaarten met per tijdstip de waterstand van '
            'meerdere gebeurtenissen',
            6: 'baten taak',
        }

        all_form_data = self.get_all_cleaned_data()

        logger.info('Scenario is being created: %r' % all_form_data)
        scenario_type = int(all_form_data['scenario_type'])
        logger.info(
            'STATS scenario aangemaakt door %s: %s, %r' % (
                all_form_data['email'],
                scenario_type_name[scenario_type], all_form_data))
        if scenario_type in (0, 1):
            damage_scenario = damage_scenario_from_type_0(all_form_data)
            self.clean_temporary_directory(all_form_data)
            # launch task
            tasks.damage_scenario_to_task(damage_scenario, username="web")
            return HttpResponseRedirect(
                reverse('lizard_damage_thank_you') +
                '?damage_scenario_id=%d' % damage_scenario.id)
        if scenario_type in (2, 3, 4):
            damage_scenario = damage_scenario_from_zip_type(all_form_data)
            self.clean_temporary_directory(all_form_data)
            # launch task
            tasks.damage_scenario_to_task(damage_scenario, username="web")
            return HttpResponseRedirect(
                reverse('lizard_damage_thank_you') +
                '?damage_scenario_id=%d' % damage_scenario.id)
        elif scenario_type == 6:
            # baten taak
            benefit_scenario = create_benefit_scenario(all_form_data)
            tasks.benefit_scenario_to_task(benefit_scenario, username="web")
            return HttpResponseRedirect(
                reverse('lizard_damage_thank_you') +
                '?benefit_scenario_id=%d' % benefit_scenario.id)
        if scenario_type == 7:
            damage_scenario = damage_scenario_from_uniform_levels_batch_type(
                all_form_data)
            self.clean_temporary_directory(all_form_data)
            # launch task
            tasks.damage_scenario_to_task(damage_scenario, username="web")
            return HttpResponseRedirect(
                reverse('lizard_damage_thank_you') +
                '?damage_scenario_id=%d' % damage_scenario.id)

    def clean_temporary_directory(self, all_form_data):
        """This must be called after processing the saved files."""
        if 'temporary_directory' in all_form_data:
            shutil.rmtree(all_form_data['temporary_directory'])


class DamageScenarioResult(ViewContextMixin, TemplateView):
    template_name = 'lizard_damage/damage_scenario_result.html'

    def title(self):
        return (
            'WaterSchadeSchatter resultatenpagina %s'
            % str(self.damage_scenario))

    def version(self):
        return tools.version()

    @property
    def root_url(self):
        try:
            root_url = 'http://%s' % Site.objects.all()[0].domain
        except:
            root_url = 'http://waterschadeschatter.nl'
        return root_url

    @property
    def damage_scenario(self):
        return get_object_or_404(DamageScenario, slug=self.kwargs['slug'])

    @property
    def table_for_uniform_levels_batch(self):
        # table for calculation #7, used in damage_scenario_result.html
        return self.damage_scenario.table_for_uniform_levels_batch()


class DamageEventKML(ViewContextMixin, TemplateView):
    template_name = 'lizard_damage/event_result.kml'

    @property
    def legend_url(self):
        if self.result_type == 'damage':
            return self.root_url + '/static_media/lizard_damage/legend.png'
        elif self.result_type == 'landuse':
            return (
                self.root_url +
                '/static_media/lizard_damage/legend_landuse.png')
        elif self.result_type == 'depth':
            return
        elif self.result_type == 'height':
            return self.root_url + reverse(
                'lizard_damage_legend_height', kwargs={
                    'min_height': self.damage_event.min_height * 1000,
                    'max_height': self.damage_event.max_height * 1000})

    @property
    def events(self):
        return self.damage_event.damageeventresult_set.filter(
            result_type=self.result_type)

    def get(self, request, slug, result_type):
        self.slug = slug
        self.damage_event = get_object_or_404(DamageEvent, slug=self.slug)
        self.result_type = result_type
        try:
            self.root_url = 'http://%s' % Site.objects.all()[0].domain
        except:
            self.root_url = 'http://schade.lizard.net'

        context = self.get_context_data()
        return self.render_to_response(
            context, mimetype='application/vnd.google-earth.kml+xml')


class GeoImageKML(DamageEventKML):
    @property
    def scenario(self):
        scenario_type = self.kwargs['scenario_type']

        if scenario_type == 'd':
            return DamageScenario.objects.get(
                pk=self.kwargs['scenario_id'])
        elif scenario_type == 'b':
            return BenefitScenario.objects.get(
                pk=self.kwargs['scenario_id'])
        return None

    @property
    def events(self):
        """HACK. Our superclass returns DamageEventResult instances,
        but we return GeoImage instances that just happen to have the
        same attributes so that they work in the template."""
        slugs = self.kwargs['slugs']
        # When multiple GeoImages have the same slug, just take first
        return GeoImage.objects.filter(slug__in=slugs.split(','))


class GeoImageNoLegendKML(GeoImageKML):
    @property
    def legend_url(self):
        return ''


class GeoImageLandUseKML(GeoImageKML):
    @property
    def legend_url(self):
        return self.root_url + '/static_media/lizard_damage/legend_landuse.png'


class GeoImageHeightKML(GeoImageKML):
    @property
    def legend_url(self):
        """Dirty way to get min/max"""
        try:
            # fn something like: height_i43bn2_09_-2230_3249
            fn = self.kwargs['slugs'].split(',')[0]
            fn_split = fn.split('_')
            min_height = fn_split[-2]
            max_height = fn_split[-1]
        except:
            min_height = 0
            max_height = 1000
        return self.root_url + reverse('lizard_damage_legend_height', kwargs={
            'min_height': min_height * 1000.0,
            'max_height': max_height * 1000.0})


class LegendHeight(View):
    """Use pil to take an existing image and add some text on top.

    Note that it uses the STATIC_ROOT folder, so you should run
    "collectstatic" (which is standard on servers).
    """
    def get(self, request, *args, **kwargs):
        f1 = float(kwargs.get('min_height', '0')) / 1000
        f2 = float(kwargs.get('max_height', '1000')) / 1000

        image = Image.open(
            os.path.join(
                settings.STATIC_ROOT, "lizard_damage/legend_height.png"))
        f = ImageFont.load_default()

        draw = ImageDraw.Draw(image)
        draw.text((45, 15), " %.1f mNAP" % f2, font=f, fill=(90, 90, 90))
        draw.text((45, 65), " %.1f mNAP" % f1, font=f, fill=(90, 90, 90))

        # serialize to HTTP response
        response = HttpResponse(mimetype="image/png")
        image.save(response, "PNG")
        return response


class BenefitScenarioResult(ViewContextMixin, TemplateView):
    template_name = 'lizard_damage/benefit_scenario_result.html'

    def title(self):
        return (
            'WaterSchadeSchatter resultatenpagina baten %s'
            % str(self.benefit_scenario))

    def version(self):
        return tools.version()

    @property
    def root_url(self):
        try:
            root_url = 'http://%s' % Site.objects.all()[0].domain
        except:
            root_url = 'http://waterschadeschatter.nl'
        return root_url

    @property
    def benefit_scenario(self):
        return get_object_or_404(BenefitScenario, slug=self.kwargs['slug'])


class BenefitScenarioKML(ViewContextMixin, TemplateView):
    template_name = 'lizard_damage/benefit_scenario.kml'

    @property
    def benefit_scenario(self):
        return get_object_or_404(BenefitScenario, slug=self.kwargs['slug'])

    @property
    def root_url(self):
        try:
            root_url = 'http://%s' % Site.objects.all()[0].domain
        except:
            root_url = 'http://schade.lizard.net'
        return root_url

    def get(self, request, *args, **kwargs):
        context = self.get_context_data(**kwargs)
        return self.render_to_response(
            context, mimetype='application/vnd.google-earth.kml+xml')


class Disclaimer(ViewContextMixin, TemplateView):
    template_name = 'lizard_damage/disclaimer.html'

    def version(self):
        return tools.version()


class ThankYou(ViewContextMixin, TemplateView):
    template_name = "lizard_damage/thank_you.html"

    @property
    def message(self):
        message = ''
        damage_scenario_id = self.request.GET.get('damage_scenario_id', None)
        if damage_scenario_id is not None:
            message += 'Uw referentie is scenario id s%s' % damage_scenario_id

        benefit_scenario_id = self.request.GET.get('benefit_scenario_id', None)
        if benefit_scenario_id is not None:
            message += 'Uw referentie is scenario id b%s' % benefit_scenario_id

        return message
