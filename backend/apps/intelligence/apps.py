from django.apps import AppConfig


class IntelligenceConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.intelligence"
    verbose_name = "Competitive Intelligence"

    def ready(self):
        # Inngest 替代 BackgroundScheduler，无需在 ready 中启动调度器
        # 调度由 Inngest Cloud 通过 webhook 触发
        pass
