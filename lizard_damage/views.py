# (c) Nelen & Schuurmans.  GPL licensed, see LICENSE.rst.
from __future__ import unicode_literals

from django.utils.translation import ugettext as _
# from django.core.urlresolvers import reverse
# from lizard_map.views import MapView
# from lizard_ui.views import UiView

# from lizard_damage import models


# class TodoView(UiView):
#     """Simple view without a map."""
#     template_name = 'lizard_damage/todo.html'
#     page_title = _('TODO view')


# class Todo2View(MapView):
#     """Simple view with a map."""
#     template_name = 'lizard_damage/todo2.html'
#     page_title = _('TODO 2 view')

from django.shortcuts import render_to_response
from django.contrib.formtools.wizard.views import SessionWizardView

class ContactWizard(SessionWizardView):
    template_name = 'lizard_damage/base_form.html'
    def done(self, form_list, **kwargs):
        return render_to_response('done.html', {
            'form_data': [form.cleaned_data for form in form_list],
        })

from django.http import HttpResponseRedirect
from django.contrib.formtools.wizard.views import SessionWizardView

class ContactWizard(SessionWizardView):
    template_name = 'lizard_damage/base_form.html'
    def done(self, form_list, **kwargs):
        do_something_with_the_form_data(form_list)
        return HttpResponseRedirect('/page-to-redirect-to-when-done/')
