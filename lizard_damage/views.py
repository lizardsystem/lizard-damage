# (c) Nelen & Schuurmans.  GPL licensed, see LICENSE.rst.
from __future__ import unicode_literals

from django.utils.translation import ugettext as _
from django.core.urlresolvers import reverse
# from lizard_map.views import MapView
from django.views.generic import TemplateView
from django.shortcuts import get_object_or_404
from django.shortcuts import render_to_response
from django.template import RequestContext
from django.core.files.storage import FileSystemStorage
from django.contrib.sites.models import Site

from lizard_damage import tasks
from lizard_damage.models import DamageScenario
from lizard_damage.models import DamageEvent
from lizard_ui.views import ViewContextMixin
from lizard_damage import tools

import datetime
import tempfile

temp_storage_location = tempfile.mkdtemp()
temp_storage = FileSystemStorage(location=temp_storage_location)

# from lizard_damage import models


from django.http import HttpResponseRedirect
from django.contrib.formtools.wizard.views import SessionWizardView


def show_form_condition(condition):
    """Determine for a specific wizard step if it should be shown."""
    def show_form_fun(wizard):
        cleaned_data = wizard.get_cleaned_data_for_step('0') or {}
        calc_type = int(cleaned_data.get('calculation_type', 0))
        return calc_type == condition
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
"""
def damage_scenario_from_type_0(all_form_data):
    damage_scenario = DamageScenario(
        name=all_form_data['name'], email=all_form_data['email'],
        calc_type=all_form_data['calc_type'])
    if all_form_data['damagetable']:
        damage_scenario.damagetable=all_form_data['damagetable']
    damage_scenario.save()
    repairtime_roads = float(all_form_data['repairtime_roads']) * 3600 * 24
    repairtime_buildings = float(all_form_data['repairtime_roads']) * 3600 * 24
    damage_scenario.damageevent_set.create(
        floodtime=all_form_data['floodtime'] * 3600,
        repairtime_roads=repairtime_roads,
        repairtime_buildings=repairtime_buildings,
        waterlevel=all_form_data['waterlevel'],
        floodmonth=all_form_data['floodmonth'])
    return damage_scenario

def damage_scenario_from_type_1(all_form_data):
    damage_scenario = damage_scenario_from_type_0(all_form_data)
    damage_scenario.repetition_time = all_form_data['repetition_time']
    damage_scenario.scenario_type = all_form_data['scenario_type']
    damage_scenario.save()
    return damage_scenario
    
    


class Wizard(SessionWizardView):
    template_name = 'lizard_damage/base_form.html'
    file_storage = temp_storage

    SCENARIO_TYPE_FUNCTIONS = {
        0: damage_scenario_from_type_0,
        1: damage_scenario_from_type_1,
        2: damage_scenario_from_type_2,
        3: damage_scenario_from_type_3,
        4: damage_scenario_from_type_4,
        5: damage_scenario_from_type_5,

    }

    def done(self, form_list, **kwargs):
        """
        The Wizard is finished: create a new DamageScenario object and
        launch the calculation task associated to it.
        """
        #import ipdb; ipdb.set_trace()
        #do_something_with_the_form_data(form_list)

        all_form_data = self.get_all_cleaned_data()

        scenario_type = int(all_form_data['scenario_type'])
        damage_scenario = SCENARIO_TYPE_FUNCTIONS[scenario_type](all_form_data)
        
        # launch task
        tasks.damage_scenario_to_task(damage_scenario, username="web")

        # e-mail received: let's not do this. Feedback is given directly
        # subject = 'Schademodule: Scenario %s ontvangen' % damage_scenario.name
        # tasks.send_email_to_task(
        #     damage_scenario.id, 'email_received', subject, username='web')

        return HttpResponseRedirect(reverse('lizard_damage_thank_you'))


class DamageScenarioResult(ViewContextMixin, TemplateView):
    template_name = 'lizard_damage/damage_scenario_result.html'

    def title(self):
        return 'Schademodule resultatenpagina %s' % str(self.damage_scenario)

    def version(self):
        return tools.version()

    @property
    def root_url(self):
        try:
            root_url = 'http://%s' % Site.objects.all()[0].domain
        except:
            root_url = 'http://damage.lizard.net'
        return root_url

    @property
    def damage_scenario(self):
        return get_object_or_404(DamageScenario, slug=self.kwargs['slug'])


class DamageEventKML(ViewContextMixin, TemplateView):
    template_name = 'lizard_damage/event_result.kml'

    @property
    def damage_event(self):
        return get_object_or_404(DamageEvent, slug=self.kwargs['slug'])

    @property
    def root_url(self):
        try:
            root_url = 'http://%s' % Site.objects.all()[0].domain
        except:
            root_url = 'http://damage.lizard.net'
        return root_url

    def get(self, request, *args, **kwargs):
        context = self.get_context_data(**kwargs)
        return self.render_to_response(context, mimetype='application/vnd.google-earth.kml+xml')
