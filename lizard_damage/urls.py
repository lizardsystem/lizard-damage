# (c) Nelen & Schuurmans.  GPL licensed, see LICENSE.rst.
from django.conf.urls.defaults import include
from django.conf.urls.defaults import patterns
from django.conf.urls.defaults import url
from django.contrib import admin
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
        views.ContactWizard.as_view([
            forms.ContactForm1,
            forms.ContactForm2,
        ]),
        name='lizard_damage_form'
    ),
    url(
        r'^result/(?P<slug>.*)/$',
        views.DamageScenarioResult.as_view(),
        name='lizard_damage_result'
    ),
)
urlpatterns += debugmode_urlpatterns()
