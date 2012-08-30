# (c) Nelen & Schuurmans.  GPL licensed, see LICENSE.rst.
from __future__ import unicode_literals

from django.utils.translation import ugettext as _
# from django.core.urlresolvers import reverse
# from lizard_map.views import MapView
from lizard_ui.views import ViewContextMixin
from django.views.generic import TemplateView
from django.shortcuts import get_object_or_404
from lizard_damage.models import DamageScenario

# from lizard_damage import models


from django.http import HttpResponseRedirect
from django.contrib.formtools.wizard.views import SessionWizardView

class ContactWizard(SessionWizardView):
    template_name = 'lizard_damage/base_form.html'
    def done(self, form_list, **kwargs):
        import ipdb; ipdb.set_trace()
        do_something_with_the_form_data(form_list)
        return HttpResponseRedirect('/page-to-redirect-to-when-done/')


class DamageScenarioResult(ViewContextMixin, TemplateView):
    template_name = 'lizard_damage/damage_scenario_result.html'

    def damage_scenario(self):
        return get_object_or_404(DamageScenario, slug=self.kwargs['slug'])
