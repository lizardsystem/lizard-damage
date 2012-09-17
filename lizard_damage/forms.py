# -*- coding: utf-8 -*-
# (c) Nelen & Schuurmans.  GPL licensed, see LICENSE.rst.
from __future__ import (
  print_function,
  unicode_literals,
  absolute_import,
  division,
)

from django import forms
from django.utils.safestring import SafeUnicode
from xml.etree import ElementTree
import logging
from lizard_damage.models import DamageScenario
from django.utils.safestring import mark_safe
from django.utils.encoding import force_unicode

logger = logging.getLogger(__name__)


SCENARIO_TYPES = DamageScenario.SCENARIO_TYPES
SCENARIO_TYPES_DICT = DamageScenario.SCENARIO_TYPES_DICT


class CustomRadioSelectRenderer(forms.RadioSelect.renderer):
    """ Modifies some of the Radio buttons to be disabled in HTML,
    based on an externally-appended Actives list. """
    def render(self):
        if not hasattr(self, "actives"): # oops, forgot to add an Actives list
            return self.original_render()
        print('my render')
        return self.my_render()

    def original_render(self):
        return mark_safe(u'<ul>\n%s\n</ul>' % u'\n'.join([u'<li>%s</li>'
            % force_unicode(w) for w in self]))

    def my_render(self):
        midList = []
        for x, wid in enumerate(self):
            if self.actives[x] == False:
                wid.attrs['disabled'] = True
            midList.append(u'<li>%s</li>' % force_unicode(wid))
        finalList = mark_safe(u'<ul>\n%s\n</ul>' % u'\n'.join([u'<li>%s</li>'
            % w for w in midList]))
        return finalList


class FormStep0(forms.Form):
    """
    Name and e-mail
    """
    display_title = 'Lizard Schademodule'

    name = forms.CharField(
        max_length=100,
        label='Hoe wilt u het scenario noemen?',
    )
    email = forms.EmailField(
        label='Emailadres',
    )

    scenario_type = forms.ChoiceField(
        label='Kies het type gegevens waarmee u '
              'een schadeberekening wilt uitvoeren',
        choices=SCENARIO_TYPES,
        widget=forms.widgets.RadioSelect(renderer=CustomRadioSelectRenderer),
    )
    scenario_type.widget.renderer.actives = [True, True, True, True, True, False]


class FormStep1(forms.Form):
    """
    Scenario info (based on 1 kaart, 1 gebeurtenis)
    """
    display_title = 'Invoer voor "%s"' % SCENARIO_TYPES_DICT[0]

    MONTH_CHOICES = (
        (1, 'januari'),
        (2, 'februari'),
        (3, 'maart'),
        (4, 'april'),
        (5, 'mei'),
        (6, 'juni'),
        (7, 'juli'),
        (8, 'augustus'),
        (9, 'september'),
        (10, 'oktober'),
        (11, 'november'),
        (12, 'december'),
        )

    waterlevel = forms.FileField(label="Ascii bestand maximale waterstand", required=True)
    damagetable = forms.FileField(label="Optioneel: eigen schadetabel", required=False)
    floodtime = forms.FloatField(label="Duur overlast (uur)", help_text="")
    repairtime_roads = forms.ChoiceField(
        label="Hersteltijd wegen", help_text="", required=True,
        choices=(("1", "1 dag"), ("2", "2 dagen"), ("5", "5 dagen"), ("10", "10 dagen"))
        )
    repairtime_buildings = forms.ChoiceField(
        label="Hersteltijd bebouwing", help_text="", required=True,
        choices=(("1", "1 dag"), ("2", "2 dagen"), ("5", "5 dagen"), ("10", "10 dagen"))
        )
    floodmonth = forms.ChoiceField(
        label="Wat is de maand van de gebeurtenis?",
        choices=MONTH_CHOICES)
    calc_type = forms.ChoiceField(
        label="Gemiddelde, minimale of maximale schadebedragen en schadefuncties",
        choices=DamageScenario.CALC_TYPE_CHOICES,
        initial=DamageScenario.CALC_TYPE_MAX)


class FormStep2(FormStep1):
    """
    Scenario_type 1
    """
    display_title = 'Invoer voor "%s"' % SCENARIO_TYPES_DICT[1]
    repetition_time = forms.FloatField(label="Herhalingstijd (jaar)", help_text="")


class FormStep3(forms.Form):
    """
    """
    display_title = 'Invoer voor "%s"' % SCENARIO_TYPES_DICT[2]

    zipfile = forms.FileField(label="Zipbestand scenario", required=True)


class FormStep4(forms.Form):
    """
    """
    display_title = 'Invoer voor "%s"' % SCENARIO_TYPES_DICT[3]

    zipfile = forms.FileField(label="Zipbestand scenario", required=True)


class FormStep5(forms.Form):
    """
    """
    display_title = 'Invoer voor "%s"' % SCENARIO_TYPES_DICT[4]

    zipfile = forms.FileField(label="Zipbestand scenario", required=True)


class FormStep6(forms.Form):
    """
    """
    display_title = 'Invoer voor "%s"' % SCENARIO_TYPES_DICT[5]

    zipfile = forms.FileField(label="Zipbestand scenario", required=True)


class FormStep7(forms.Form):
    """
    """
    display_title = 'Controle invoer'

    test_title = forms.CharField(max_length=100)


class FormZipResult(forms.Form):
    """
    """
    display_title = 'Controle invoer'

    zip_content = forms.CharField(
        max_length=100,
        label="zipfile analyse",
        widget=forms.Textarea(attrs={'readonly':'readonly'}))

    # def __init__(self, *args, **kwargs):
    #     super(FormZipResult, self).__init__(*args, **kwargs)
    #     instance = getattr(self, 'instance', None)
    #     if instance and instance.id:
    #         self.fields['zip_content'].widget.attrs['readonly'] = True

    #test = forms.CharField(max_length=100, label="")
    # test2 = forms.CharField(max_length=100, label="")


    # def __init__(self, *args, **kwargs):
    #     extra = kwargs.pop('extra')
    #     super(FormZipResult, self).__init__(*args, **kwargs)

    #     for i, question in extra:
    #         self.fields['custom_%s' % i] = forms.CharField(label=question)
