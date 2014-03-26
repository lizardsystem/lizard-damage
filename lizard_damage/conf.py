# (c) Nelen & Schuurmans.  GPL licensed, see LICENSE.rst.
# -*- coding: utf-8 -*-

"""Use AppConf to store sensible defaults for settings. This also documents the
settings that lizard_damage defines. Each setting name automatically has
"LIZARD_DAMGE_" prepended to it.

By puttng the AppConf in this module and importing the Django settings
here, it is possible to import Django's settings with `from
lizard_damage.conf import settings` and be certain that the AppConf
stuff has also been loaded."""

# Python 3 is coming
from __future__ import unicode_literals
from __future__ import print_function
from __future__ import absolute_import
from __future__ import division

import os

from django.conf import settings
settings  # Pyflakes...

from appconf import AppConf


class MyAppConf(AppConf):

    # This is the email address that tracebacks are sent to if a task
    # raises an exception.
    EXCEPTION_EMAIL = "servicedesk@nelen-schuurmans.nl"

    # Where to find land use and height tiles on the local filesystem
    DATA_ROOT = os.path.join(settings.BUILDOUT_DIR, 'var', 'data')

    MAX_WATERLEVEL_SIZE = 20000000  # 20 km2

# Note that lizard_damage's emails also need settings for
# EMAIL_USE_TLS, EMAIL_HOST, EMAIL_HOST_USER, EMAIL_HOST_PASSWORD and
# EMAIL_PORT, but we don't give defaults for them here.
