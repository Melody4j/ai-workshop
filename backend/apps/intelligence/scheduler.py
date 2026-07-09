"""调度模块（已迁移到 Inngest）。

原 BackgroundScheduler + django-apscheduler 已移除。
调度逻辑由 Inngest Cron 函数 + 事件函数接管，定义在 inngest_client.py 中。

run_scan / run_scan_for_project 的实际实现位于 scheduler_service.py，由 Inngest 函数调用。
"""

# 此模块保留为空，避免历史导入引用报错。
# 调度入口已迁移至 apps.intelligence.inngest_client
