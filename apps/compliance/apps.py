from django.apps import AppConfig

class ComplianceConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.compliance'
    verbose_name = 'Compliance & GDPR'

    def ready(self):
        import apps.compliance.signals