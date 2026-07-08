import logging

from django.utils import timezone

from apps.intelligence.models import MonitorProject, DataSnapshot
from apps.intelligence.services import crawler_service
from apps.intelligence.services.cron_matcher import get_next_run

logger = logging.getLogger(__name__)


def run_scan():
    """全局扫描：检查所有 active 项目是否到期，到期则逐 URL 采集入库。"""
    now = timezone.now()
    active_projects = MonitorProject.objects.filter(is_active=True)
    for project in active_projects:
        if project.next_run_at is not None and project.next_run_at > now:
            logger.debug(f"项目未到期: {project.project_name} (next: {project.next_run_at})")
            continue
        logger.info(f"开始执行项目: {project.project_name}")
        urls = project.competitor_urls or []
        for item in urls:
            url = (item or {}).get("url", "")
            if not url:
                logger.warning(f"跳过空 URL: {project.project_name}")
                continue
            title = (item or {}).get("title", "")
            try:
                raw_md, clean_md = crawler_service.fetch_and_clean(url)
            except Exception as e:
                logger.error(f"采集异常: {url} - {e}")
                raw_md, clean_md = "", ""
            DataSnapshot.objects.create(
                project=project,
                source_url=url,
                source_title=title,
                raw_markdown=raw_md,
                clean_markdown=clean_md,
                fetch_time=now,
            )
        # 更新 next_run_at
        project.next_run_at = get_next_run(project.cron, now)
        project.save(update_fields=["next_run_at"])
        logger.info(f"项目执行完成: {project.project_name} (next: {project.next_run_at})")
