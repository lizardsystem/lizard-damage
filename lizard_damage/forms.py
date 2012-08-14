# -*- coding: utf-8 -*-
# (c) Nelen & Schuurmans.  GPL licensed, see LICENSE.rst.
from __future__ import (
  print_function,
  unicode_literals,
  absolute_import,
  division,
)

from django import forms

class ContactForm1(forms.Form):
    name = forms.CharField(
        max_length=100,
        label='Hoe wilt u het scenario noemen?',
    )
    sender = forms.EmailField(
        label='Emailadres',
    )


class ContactForm2(forms.Form):
    message = forms.CharField(widget=forms.Textarea)
