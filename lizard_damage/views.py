# (c) Nelen & Schuurmans.  GPL licensed, see LICENSE.rst.
from __future__ import unicode_literals

from django.utils.translation import ugettext as _
from django.core.urlresolvers import reverse
# from lizard_map.views import MapView
from django.views.generic import TemplateView
from django.shortcuts import get_object_or_404
from django.core.files.storage import FileSystemStorage

from lizard_damage import tasks
from lizard_damage.models import DamageScenario
from lizard_ui.views import ViewContextMixin

import datetime
import tempfile

temp_storage_location = tempfile.mkdtemp()
temp_storage = FileSystemStorage(location=temp_storage_location)

# from lizard_damage import models


from django.http import HttpResponseRedirect
from django.contrib.formtools.wizard.views import SessionWizardView

class Wizard(SessionWizardView):
    template_name = 'lizard_damage/base_form.html'
    file_storage = temp_storage

    # def get_form_step_files(self, form):
    #     return form.files

    def done(self, form_list, **kwargs):
        #import ipdb; ipdb.set_trace()
        #do_something_with_the_form_data(form_list)

        # TODO: validate that everything is correct
        #print self.file_storage
        all_form_data = self.get_all_cleaned_data()
        damage_scenario = DamageScenario(
            name=all_form_data['name'], email=all_form_data['email'])
        damage_scenario.save()
        damage_scenario.damageevent_set.create(
            floodtime=all_form_data['floodtime'] * 3600,
            repairtime=all_form_data['repairtime'] * 3600,
            waterlevel=all_form_data['waterlevel'],
            floodmonth=all_form_data['floodmonth'])

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

    @property
    def damage_scenario(self):
        return get_object_or_404(DamageScenario, slug=self.kwargs['slug'])
