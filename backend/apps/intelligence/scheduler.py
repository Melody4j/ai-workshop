import atexit
import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from django_apscheduler.jobstores import DjangoJobStore

logger = logging.getLogger(__name__)
_scheduler = None


def start_scheduler():
    global _scheduler
    if _scheduler is not None:
        return  # 防止重复启动
    _scheduler = BackgroundScheduler()
    _scheduler.add_jobstore(DjangoJobStore(), "default")
    _scheduler.add_job(
        run_scan_job,
        trigger=CronTrigger(second="*/5"),
        id="scan_all_projects",
        name="Scan all active projects",
        replace_existing=True,
    )
    _scheduler.start()
    atexit.register(lambda: _scheduler.shutdown(wait=False))
    logger.info("APScheduler 已启动，全局扫描 Job 已注册 (每 5 秒)")


def run_scan_job():
    from apps.intelligence.services import scheduler_service
    scheduler_service.run_scan()
