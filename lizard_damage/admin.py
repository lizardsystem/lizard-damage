# (c) Nelen & Schuurmans.  GPL licensed, see LICENSE.rst.
from __future__ import unicode_literals

from django.contrib import admin
from lizard_damage import models

class UnitAdmin(admin.ModelAdmin):
    list_display = ['name', 'factor']

admin.site.register(models.Unit, UnitAdmin)

