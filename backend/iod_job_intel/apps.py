from django.apps import AppConfig


class IodJobIntelConfig(AppConfig):
    name = "iod_job_intel"
    verbose_name = "IOD Job Intelligence"

    def ready(self):
        import iod_job_intel.signals  # noqa: F401
