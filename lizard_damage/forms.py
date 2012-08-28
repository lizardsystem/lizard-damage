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


class ContactForm1(forms.Form):
    name = forms.CharField(
        max_length=100,
        label='Hoe wilt u het scenario noemen?',
    )
    email = forms.EmailField(
        label='Emailadres',
    )


class ContactForm2(forms.Form):
    message = forms.ChoiceField(
        label='Kies het type gegevens waarmee u '
              'een schadeberekening wilt uitvoeren',
        choices = CALCULATION_TYPES,
        widget = forms.widgets.RadioSelect,
    )



