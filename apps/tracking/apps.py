from django.apps import AppConfig

class TrackingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.tracking'
    verbose_name = 'Real-Time Flight Tracking'

    def ready(self):
        import apps.tracking.signals