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
    # url(r'^map/', include('lizard_map.urls')),
    url(r'^admin/', include(admin.site.urls)),
    # url(r'^something/',
    #     views.some_method,
    #     name="name_it"),
    # url(r'^something_else/$',
    #     views.SomeClassBasedView.as_view(),
    #     name='name_it_too'),
    url(
        r'^$',
        views.Wizard.as_view([
            forms.Form1,
            #forms.Form2,
            forms.Form3,
        ], initial_dict={
                '0': {
                    'name': 'Jack',
                    'email': 'jack.ha@nelen-schuurmans.nl',
                    },
                '1': {
                    'floodtime': 1,
                    'repairtime': 1,
                    'flooddate': 9,
                    }}),
        name='lizard_damage_form'
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
        )
)
urlpatterns += debugmode_urlpatterns()
