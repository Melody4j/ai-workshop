import os

from django.apps import AppConfig


class IntelligenceConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.intelligence"
    verbose_name = "Competitive Intelligence"

    def ready(self):
        # runserver autoreload 下仅在 worker 进程启动 scheduler
        if os.environ.get("RUN_MAIN") == "true":
            from apps.intelligence.scheduler import start_scheduler
            start_scheduler()
