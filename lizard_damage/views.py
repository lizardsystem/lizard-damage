# (c) Nelen & Schuurmans.  GPL licensed, see LICENSE.rst.
from __future__ import unicode_literals

from django.utils.translation import ugettext as _
from django.core.files import File
from django.core.urlresolvers import reverse
from django.http import HttpResponse
# from lizard_map.views import MapView
from django.views.generic import TemplateView
from django.views.generic import View
from django.shortcuts import get_object_or_404
from django.shortcuts import render_to_response
from django.template import RequestContext
from django.core.files.storage import FileSystemStorage
from django.contrib.sites.models import Site
from django.conf import settings

from lizard_damage import tasks
from lizard_damage.models import BenefitScenario
from lizard_damage.models import DamageScenario
from lizard_damage.models import DamageEvent
from lizard_damage.models import DamageEventWaterlevel
from lizard_damage.models import GeoImage
from lizard_ui.views import ViewContextMixin
from lizard_damage import tools
from lizard_damage import forms

from zipfile import ZipFile
import datetime
import tempfile
import os
import re
from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont

temp_storage_location = tempfile.mkdtemp()
temp_storage = FileSystemStorage(location=temp_storage_location)

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
    damage_scenario = DamageScenario(
        name=all_form_data['name'], email=all_form_data['email'],
        scenario_type=all_form_data['scenario_type'],
        calc_type=all_form_data['calc_type'])
    if all_form_data['damagetable']:
        damage_scenario.damagetable=all_form_data['damagetable']
    damage_scenario.save()
    repairtime_roads = float(all_form_data['repairtime_roads']) * 3600 * 24
    repairtime_buildings = float(all_form_data['repairtime_buildings']) * 3600 * 24
    damage_event = damage_scenario.damageevent_set.create(
        floodtime=all_form_data['floodtime'] * 3600,
        repairtime_roads=repairtime_roads,
        repairtime_buildings=repairtime_buildings,
        floodmonth=all_form_data['floodmonth'])
    damage_event.damageeventwaterlevel_set.create(
        waterlevel=all_form_data['waterlevel'],
        index=1
        )
    return damage_scenario


def damage_scenario_from_type_1(all_form_data):
    damage_scenario = DamageScenario(
        name=all_form_data['name'], email=all_form_data['email'],
        scenario_type=all_form_data['scenario_type'],
        calc_type=all_form_data['calc_type'])
    if all_form_data['damagetable']:
        damage_scenario.damagetable=all_form_data['damagetable']
    damage_scenario.save()
    repairtime_roads = float(all_form_data['repairtime_roads']) * 3600 * 24
    repairtime_buildings = float(all_form_data['repairtime_buildings']) * 3600 * 24
    damage_event = damage_scenario.damageevent_set.create(
        repetition_time=all_form_data['repetition_time'],  # Difference is here
        floodtime=all_form_data['floodtime'] * 3600,
        repairtime_roads=repairtime_roads,
        repairtime_buildings=repairtime_buildings,
        floodmonth=all_form_data['floodmonth'])
    damage_event.damageeventwaterlevel_set.create(
        waterlevel=all_form_data['waterlevel'],
        index=1
        )
    return damage_scenario


def unpack_zipfile_into_scenario(zipfile, scenario_name='', scenario_email=''):
    """
    Create scenario structure from (user uploaded) zip file

    TODO: make a class for index.csv
    (so we can use it in analyze_zip_file as well)
    """
    with ZipFile(zipfile, 'r') as myzip:
        index = myzip.read('index.csv')
        index_data = [line.strip().split(',') for line in index.split('\n') if line.strip()]

        scenario_data = {}
        if scenario_name:
            scenario_data['name'] = scenario_name
        if scenario_email:
            scenario_data['email'] = scenario_email
        damage_table = None
        for line in index_data:
            print '%r' % line[0]
            if line[0] == 'scenario_name':
                if not scenario_data['name']:
                    scenario_data['name'] = line[1]
            elif line[0] == 'scenario_email':
                if not scenario_data['email']:
                    scenario_data['email'] = line[1]
            elif line[0] == 'scenario_type':
                scenario_data['scenario_type'] = int(line[1])
            elif line[0] == 'scenario_calc_type':
                scenario_data['calc_type'] = {'min': 1, 'max': 2, 'avg': 3}.get(line[1].lower(), 'max')
            elif line[0] == 'scenario_damage_table':
                if line[1]:
                    zip_temp = tempfile.mkdtemp()
                    myzip.extract(line[1], zip_temp)  # extract to temp dir
                    damage_table = os.path.join(zip_temp, line[1])
            elif line[0] == 'event_name':
                # Header for second part: create damage_scenario object
                print 'Create a damage scenario using %r' % scenario_data
                damage_scenario = DamageScenario(**scenario_data)
                damage_scenario.save()
                if damage_table:
                    print 'adding damage table...'
                    with open(damage_table) as damage_table_file:
                        damage_scenario.damagetable.save(
                            os.path.basename(damage_table),
                            File(damage_table_file), save=True)
            else:
                # This is an event
                damage_event = DamageEvent(
                    name=line[0],
                    scenario=damage_scenario,
                    floodtime=float(line[2]) * 3600,
                    repairtime_roads=float(line[3]) * 3600 * 24,
                    repairtime_buildings=float(line[4]) * 3600 * 24,
                    floodmonth=line[5]
                    )
                if line[6]:
                    damage_event.repetition_time = line[6]
                damage_event.save()

                if scenario_data['scenario_type'] == 2:
                    zip_file_names = myzip.namelist()
                    re_match = re.match(
                        '(.*[^0-9])([0-9]+)(\.asc)$', line[1]).groups()  # i.e. ('ws', '324', '.asc')

                    re_pattern = re.compile('%s[0-9]+%s' % (re_match[0], re_match[2]))
                    water_level_filenames = [
                        fn for fn in zip_file_names if re.match(re_pattern, fn)]
                    water_level_filenames.sort()
                else:
                    water_level_filenames = [line[1], ]

                for index, water_level_filename in enumerate(water_level_filenames):
                    water_level_tempdir = tempfile.mkdtemp()
                    myzip.extract(water_level_filename, water_level_tempdir)
                    tempfilename = os.path.join(water_level_tempdir, water_level_filename)
                    with open(tempfilename) as water_level_tempfile:
                        damage_event_waterlevel = DamageEventWaterlevel(event=damage_event, index=index)
                        damage_event_waterlevel.waterlevel.save(
                            water_level_filename, File(water_level_tempfile), save=True)
                        damage_event_waterlevel.save()
                    os.remove(tempfilename)
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

    return damage_scenario


def analyze_zip_file(zipfile):
    """
    Analyze zip file: generate kind of logging

    This function is kinda dirty, because parts are copied from
    unpack_zipfile_into_scenario.
    """
    result = []

    with ZipFile(zipfile, 'r') as myzip:
        zip_file_names = myzip.namelist()

        try:
            index = myzip.read('index.csv')
            index_data = [line.strip().split(',') for line in index.split('\n') if line.strip()]
        except:
            result.append('index.csv is afwezig of is niet goed')

        for line in index_data:
            if line[0] == 'scenario_type':
                try:
                    DamageScenario.SCENARIO_TYPES_DICT[int(line[1])]
                except:
                    result.append('Scenario type "%s" niet goed (moet 0..4 zijn)' % line[1])
            elif line[0] == 'scenario_name':
                pass
            elif line[0] == 'scenario_email':
                pass
            elif line[0] == 'scenario_calc_type':
                if line[1].lower() not in ['min', 'max', 'avg']:
                    result.append('FOUT: scenario type "%s" moet min, max of avg zijn' % line[1].lower())
            elif line[0] == 'scenario_damage_table':
                if line[1] not in zip_file_names:
                    result.append('FOUT: schadetabel %s (NIET gevonden in zipfile)' % line[1])
            elif line[0] == 'event_name':
                pass
            else:
                # result.append('gebeurtenis (naam, waterlevel, overstromingsduur, reparatie wegen, rep. bebouwing, maand): %s' % ', '.join(line))
                if line[1] not in zip_file_names:
                    result.append('FOUT: waterlevel %s NIET gevonden' % line[1])
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

    SCENARIO_TYPE_FUNCTIONS = {
        0: damage_scenario_from_type_0,
        1: damage_scenario_from_type_1,
        2: damage_scenario_from_zip_type,
        3: damage_scenario_from_zip_type,
        4: damage_scenario_from_zip_type,
        # 5: damage_scenario_from_zip_type,
    }

    def get_form_initial(self, step):
        # For batch processing
        if step == '8':
            form_datas = {}
            for form_step in ('3', '4', '5'):
                form_data = self.get_cleaned_data_for_step(form_step)
                if form_data:
                    form_datas.update(form_data)
            # return {'zip_content': analyze_zip_file(form_datas['zipfile'])}
            try:
                return {'zip_content': analyze_zip_file(form_datas['zipfile'])}
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
                return {'zip_content': 'analyse gefaald, batenkaart bestanden zijn niet goed'}
        return super(Wizard, self).get_form_initial(step)

    # def get_form(self, step=None, data=None, files=None):
    #     if step == '7':
    #         #form = forms.FormStep7(initial={'test_title': 'asdf'})
    #         #from django.forms.models import inlineformset_factory
    #         from django.forms.formsets import formset_factory
    #         # FormSetScenario = formset_factory(forms.FormScenario)
    #         # FormSetEvent = formset_factory(forms.FormEvent, extra=2)
    #         # FormSet =
    #         #FormSet = inlineformset_factory(DamageScenario, DamageEvent)
    #         FormSet = formset_factory(forms.FormZipResult)
    #         form = FormSet(initial=[{'test': '1'}, {'test': 'event 2'}])
    #         #form = forms.FormZipResult(extra=(('extra', 'Extra veld'),))
    #     else:
    #         form = super(Wizard, self).get_form(step, data, files)
    #     return form

    def version(self):
        return tools.version()

    def done(self, form_list, **kwargs):
        """
        The Wizard is finished: create a new DamageScenario object and
        launch the calculation task associated to it.
        """
        #import ipdb; ipdb.set_trace()
        #do_something_with_the_form_data(form_list)

        all_form_data = self.get_all_cleaned_data()

        scenario_type = int(all_form_data['scenario_type'])
        if scenario_type in (0, 1, 2, 3, 4, 5):
            damage_scenario = self.SCENARIO_TYPE_FUNCTIONS[scenario_type](all_form_data)
            # launch task
            tasks.damage_scenario_to_task(damage_scenario, username="web")
        elif scenario_type == 6:
            # baten taak
            benefit_scenario = create_benefit_scenario(all_form_data)
            tasks.benefit_scenario_to_task(benefit_scenario, username="web")

        # e-mail received: let's not do this. Feedback is given directly
        # subject = 'Schademodule: Scenario %s ontvangen' % damage_scenario.name
        # tasks.send_email_to_task(
        #     damage_scenario.id, 'email_received', subject, username='web')

        return HttpResponseRedirect(reverse('lizard_damage_thank_you'))


class DamageScenarioResult(ViewContextMixin, TemplateView):
    template_name = 'lizard_damage/damage_scenario_result.html'

    def title(self):
        return 'STOWA Schade Calculator resultatenpagina %s' % str(self.damage_scenario)

    def version(self):
        return tools.version()

    @property
    def root_url(self):
        try:
            root_url = 'http://%s' % Site.objects.all()[0].domain
        except:
            root_url = 'http://schade.lizard.net'
        return root_url

    @property
    def damage_scenario(self):
        return get_object_or_404(DamageScenario, slug=self.kwargs['slug'])


class DamageEventKML(ViewContextMixin, TemplateView):
    template_name = 'lizard_damage/event_result.kml'

    # @property
    # def legend_url(self):
    #     # Url to an image, optional
    @property
    def legend_url(self):
        return self.root_url + '/static_media/lizard_damage/legend.png'

    @property
    def events(self):
        event = get_object_or_404(DamageEvent, slug=self.kwargs['slug'])
        return event.damageeventresult_set.all()

    @property
    def root_url(self):
        try:
            root_url = 'http://%s' % Site.objects.all()[0].domain
        except:
            root_url = 'http://schade.lizard.net'
        return root_url

    def get(self, request, *args, **kwargs):
        context = self.get_context_data(**kwargs)
        return self.render_to_response(context, mimetype='application/vnd.google-earth.kml+xml')


class GeoImageKML(DamageEventKML):
    @property
    def events(self):
        slugs = self.kwargs['slugs']
        return [get_object_or_404(GeoImage, slug=slug) for slug in slugs.split(',')]


class GeoImageLandUseKML(GeoImageKML):
    @property
    def legend_url(self):
        return self.root_url + '/static_media/lizard_damage/legend_landuse.png'


class GeoImageHeightKML(GeoImageKML):
    @property
    def legend_url(self):
        """Dirty way to get min/max"""
        try:
            #fn something like: height_i43bn2_09_-2230_3249
            fn = self.kwargs['slugs'].split(',')[0]
            fn_split = fn.split('_')
            min_height = fn_split[-2]
            max_height = fn_split[-1]
        except:
            min_height = 0
            max_height = 1000
        return self.root_url + reverse('lizard_damage_legend_height', kwargs={
                'min_height': min_height, 'max_height': max_height})


class LegendHeight(View):
    """Use pil to take an existing image and add some text on top.

    Note that it uses the STATIC_ROOT folder, so you should run
    "collectstatic" (which is standard on servers).
    """
    def get(self, request, *args, **kwargs):
        f1 = float(kwargs.get('min_height', '0')) / 1000
        f2 = float(kwargs.get('max_height', '1000')) / 1000

        image = Image.open(os.path.join(settings.STATIC_ROOT, "lizard_damage/legend_height.png"))
        f = ImageFont.load_default()

        draw = ImageDraw.Draw(image)
        draw.text( (45, 15), " %.1f mNAP" % f2, font=f, fill=(90, 90, 90))
        draw.text( (45, 65), " %.1f mNAP" % f1, font=f, fill=(90, 90, 90))

        # serialize to HTTP response
        response = HttpResponse(mimetype="image/png")
        image.save(response, "PNG")
        return response


class BenefitScenarioResult(ViewContextMixin, TemplateView):
    template_name = 'lizard_damage/benefit_scenario_result.html'

    def title(self):
        return 'STOWA Schade Calculator resultatenpagina baten %s' % str(self.benefit_scenario)

    def version(self):
        return tools.version()

    @property
    def root_url(self):
        try:
            root_url = 'http://%s' % Site.objects.all()[0].domain
        except:
            root_url = 'http://schade.lizard.net'
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
        return self.render_to_response(context, mimetype='application/vnd.google-earth.kml+xml')


class Disclaimer(ViewContextMixin, TemplateView):
    template_name = 'lizard_damage/disclaimer.html'

    def version(self):
        return tools.version()
