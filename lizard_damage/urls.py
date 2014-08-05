# (c) Nelen & Schuurmans.  GPL licensed, see LICENSE.rst.
from django.conf.urls import include
from django.conf.urls import patterns
from django.conf.urls import url
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
             forms.FormZipResult,  # '8' for batch zip (single file)
             forms.FormZipResult,  # '9' for baten kaart (2 files)
             ],
            initial_dict={
                '0': {
                    'name': 'Nieuw scenario',
                    },
                '1': {
                    'floodtime': 1,
                    'flooddate': 9,
                    'repairtime_roads': "0.25",
                    'repairtime_buildings': "1",
                    },
                '2': {
                    'floodtime': 1,
                    'flooddate': 9,
                    'repairtime_roads': "0.25",
                    'repairtime_buildings': "1",
                    }
                },
            condition_dict={
                # Step 1, enable for calc_type 0
                '1': views.show_form_condition([0]),
                # Step 2, enable for calc_type 1, etc
                '2': views.show_form_condition([1]),
                '3': views.show_form_condition([2]),
                '4': views.show_form_condition([3]),
                '5': views.show_form_condition([4]),
                '6': views.show_form_condition([5]),
                '7': views.show_form_condition([6]),
                # Check zipfile and show results
                '8': views.show_form_condition([2, 3, 4, 5]),
                '9': views.show_form_condition([6]),  # Batenkaart files
                }
            ),
        name='lizard_damage_form'
    ),
    url(r'^disclaimer$',
        views.Disclaimer.as_view(
            template_name="lizard_damage/disclaimer.html"),
        name='lizard_damage_disclaimer'),
    url(
        r'^result/(?P<slug>.*)/$',
        views.DamageScenarioResult.as_view(),
        name='lizard_damage_result'
    ),
    url(
        r'^benefit_result/(?P<slug>.*)/$',
        views.BenefitScenarioResult.as_view(),
        name='lizard_damage_benefit_result'
    ),
    url(
        r'^benefit_result/(?P<slug>.*)/$',
        views.BenefitScenarioResult.as_view(),
        name='lizard_damage_benefit_result'
    ),
    url(
        r'^benefit_result/(?P<slug>.*)/kml$',
        views.BenefitScenarioKML.as_view(),
        name='lizard_damage_benefit_kml'
    ),
    url(
        r'^event/(?P<slug>.*)/kml/$',
        views.DamageEventKML.as_view(),
        name='lizard_damage_event_kml'
    ),
    url(
        r'^geoimage/(?P<scenario_type>[db])/(?P<scenario_id>\d+)/' +
        '(?P<slugs>.*)/',
        views.GeoImageKML.as_view(),
        name='lizard_damage_geo_image_kml'
    ),
    url(
        r'^geoimage_nolegend/(?P<scenario_type>[db])/(?P<scenario_id>\d+)/' +
        '(?P<slugs>.*)/',
        views.GeoImageNoLegendKML.as_view(),
        name='lizard_damage_geo_image_no_legend_kml'
    ),
    url(
        r'^geoimage_landuse/(?P<scenario_type>[db])/(?P<scenario_id>\d+)/' +
        '(?P<slugs>.*)/',
        views.GeoImageLandUseKML.as_view(),
        name='lizard_damage_geo_image_landuse_kml'
    ),
    url(
        r'^geoimage_height/(?P<scenario_type>[db])/(?P<scenario_id>\d+)/' +
        '(?P<slugs>.*)/',
        views.GeoImageHeightKML.as_view(),
        name='lizard_damage_geo_image_height_kml'
    ),
    url(
        r'^legend_height_(?P<min_height>.*)_(?P<max_height>.*).png$',
        views.LegendHeight.as_view(),
        name='lizard_damage_legend_height'
    ),
    url(
        r'^thank_you/$',
        views.ThankYou.as_view(),
        name='lizard_damage_thank_you'
        ),
    url(r'^test$',
        TemplateView.as_view(template_name="lizard_damage/openlayers.html"),
        name='lizard_damage_test'),
)
urlpatterns += debugmode_urlpatterns()
