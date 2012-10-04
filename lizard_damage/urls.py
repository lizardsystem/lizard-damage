# (c) Nelen & Schuurmans.  GPL licensed, see LICENSE.rst.
from django.conf.urls.defaults import include
from django.conf.urls.defaults import patterns
from django.conf.urls.defaults import url
from django.contrib import admin
from django.views.generic import TemplateView

from lizard_ui.urls import debugmode_urlpatterns

from lizard_damage import (
    views,
    forms,
)

admin.autodiscover()

urlpatterns = patterns(
    '',
    url(r'^ui/', include('lizard_ui.urls')),
    url(r'^admin/', include(admin.site.urls)),

    url(
        r'^$',
        views.Wizard.as_view(
            [forms.FormStep0,
             forms.FormStep1,
             forms.FormStep2,
             forms.FormStep3,
             forms.FormStep4,
             forms.FormStep5,
             forms.FormStep6,
             forms.FormBatenKaart,  # '7'
             forms.FormZipResult, # '8' for batch zip (single file)
             forms.FormZipResult, # '9' for baten kaart (2 files)
             ],
            initial_dict={
                '0': {
                    'name': 'Nieuw scenario',
                    },
                '1': {
                    'floodtime': 1,
                    'flooddate': 9,
                    }
                },
            condition_dict={
                # '0': views.show_form_condition,
                '1': views.show_form_condition([0]),  # Step 1, enable for calc_type 0
                '2': views.show_form_condition([1]),  # Step 2, enable for calc_type 1, etc
                '3': views.show_form_condition([2]),
                '4': views.show_form_condition([3]),
                '5': views.show_form_condition([4]),
                '6': views.show_form_condition([5]),
                '7': views.show_form_condition([6]),
                '8': views.show_form_condition([2,3,4,5]),  # Check zipfile and show results
                '9': views.show_form_condition([6]),  # Batenkaart files 
                }
            ),
        name='lizard_damage_form'
    ),
    url(r'^disclaimer$',
        views.Disclaimer.as_view(template_name="lizard_damage/disclaimer.html"),
        name='lizard_damage_disclaimer'
    ),
    url(
        r'^result/(?P<slug>.*)/$',
        views.DamageScenarioResult.as_view(),
        name='lizard_damage_result'
    ),
    url(
        r'^event/(?P<slug>.*)/kml/$',
        views.DamageEventKML.as_view(),
        name='lizard_damage_event_kml'
    ),
    url(
        r'^thank_you/$',
        TemplateView.as_view(template_name="lizard_damage/thank_you.html"),
        name='lizard_damage_thank_you'
        ),
    url(r'^test$',
        TemplateView.as_view(template_name="lizard_damage/openlayers.html"),
        name='lizard_damage_test'
    ),
)
urlpatterns += debugmode_urlpatterns()
