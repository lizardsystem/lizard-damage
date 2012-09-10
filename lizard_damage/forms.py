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

logger = logging.getLogger(__name__)

CALCULATION_TYPES = (
    (0, '1 Kaart met de max waterstand van 1 gebeurtenis'),
    (1, '1 Kaart met de waterstand voor een zekere herhalingstijd'),
    (2, 'Kaarten met per tijdstip de waterstand van 1 gebeurtenis'),
    (3, 'Kaarten met de max. waterstand van afzonderlijke gebeurtenissen.'),
    (4, 'Kaarten met voor verschillende herhalingstijden de waterstanden'),
    (5, 'Tijdserie aan kaarten met per tijdstip de '
        'waterstand van meerdere gebeurtenissen'),
)

CALCULATION_TYPES_DICT = dict(CALCULATION_TYPES)


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

    calculation_type = forms.ChoiceField(
        label='Kies het type gegevens waarmee u '
              'een schadeberekening wilt uitvoeren',
        choices = CALCULATION_TYPES,
        widget = forms.widgets.RadioSelect,
    )


class FormStep1(forms.Form):
    """
    Scenario info (based on 1 kaart, 1 gebeurtenis)
    """
    display_title = 'Invoer voor "%s"' % CALCULATION_TYPES_DICT[0]

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


class FormStep2(forms.Form):
    """
    """
    display_title = 'Invoer voor "%s"' % CALCULATION_TYPES_DICT[1]

    zipfile = forms.FileField(label="Zipbestand scenario", required=True)


class FormStep3(forms.Form):
    """
    """
    display_title = 'Invoer voor "%s"' % CALCULATION_TYPES_DICT[2]

    zipfile = forms.FileField(label="Zipbestand scenario", required=True)


class FormStep4(forms.Form):
    """
    """
    display_title = 'Invoer voor "%s"' % CALCULATION_TYPES_DICT[3]

    zipfile = forms.FileField(label="Zipbestand scenario", required=True)


class FormStep5(forms.Form):
    """
    """
    display_title = 'Invoer voor "%s"' % CALCULATION_TYPES_DICT[4]

    zipfile = forms.FileField(label="Zipbestand scenario", required=True)


class FormStep6(forms.Form):
    """
    """
    display_title = 'Invoer voor "%s"' % CALCULATION_TYPES_DICT[5]

    zipfile = forms.FileField(label="Zipbestand scenario", required=True)


class FormStep7(forms.Form):
    """
    """
    display_title = 'Controle invoer'

    zipfile = forms.FileField(label="Zipbestand scenario", required=True)
