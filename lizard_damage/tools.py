# (c) Nelen & Schuurmans.  GPL licensed, see LICENSE.rst.
from __future__ import unicode_literals


def version():
    """
    return version string
    """
    from pkginfo.installed import Installed
    import lizard_damage
    installed = Installed(lizard_damage)
    return 'versie %s' % (installed.version)
