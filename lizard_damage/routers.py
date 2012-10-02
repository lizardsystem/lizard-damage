class LizardDamageRouter(object):

    def db_for_read(self, model, **hints):
        if model._meta.app_label == 'lizard_damage':
            if model._meta.object_name in ['Roads', 'AhnIndex']:
                return 'raster'
        return None  # Use default database

    def allow_syncdb(self, db, model):
        """
        """
        if db == 'raster':
            return False
        if model._meta.app_label == 'lizard_damage':
            if model._meta.object_name in ['Roads', 'AhnIndex']:
                return False
        return None  # None means 'no opinion'.
