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
    project_count = active_projects.count()
    logger.info(f"[扫描开始] 当前 {project_count} 个活跃项目, 时间 {now:%Y-%m-%d %H:%M:%S}")

    for project in active_projects:
        if project.next_run_at is not None and project.next_run_at > now:
            logger.info(f"[跳过] 项目 {project.project_name} 未到期, 下次执行 {project.next_run_at:%Y-%m-%d %H:%M:%S}")
            continue

        logger.info(f"[到期] 项目 {project.project_name} (id={project.id}) 开始执行, cron={project.cron}")
        urls = project.competitor_urls or []
        logger.info(f"[采集] 项目 {project.project_name} 共 {len(urls)} 个竞品 URL")

        for idx, item in enumerate(urls, 1):
            url = (item or {}).get("url", "")
            if not url:
                logger.warning(f"[采集] 项目 {project.project_name} 第 {idx} 个 URL 为空, 跳过")
                continue
            title = (item or {}).get("title", "")
            logger.info(f"[采集] ({idx}/{len(urls)}) {title} - {url}")
            try:
                raw_md, clean_md = crawler_service.fetch_and_clean(url)
                logger.info(
                    f"[采集完成] {url} raw={len(raw_md)} chars, clean={len(clean_md)} chars"
                )
            except Exception as e:
                logger.error(f"[采集异常] {url} - {e}", exc_info=True)
                raw_md, clean_md = "", ""
            DataSnapshot.objects.create(
                project=project,
                source_url=url,
                source_title=title,
                raw_markdown=raw_md,
                clean_markdown=clean_md,
                fetch_time=now,
            )
            logger.info(f"[入库] 快照已保存: {url}")

        # 更新 next_run_at
        project.next_run_at = get_next_run(project.cron, now)
        project.save(update_fields=["next_run_at"])
        logger.info(
            f"[项目完成] {project.project_name} 执行结束, 下次执行 {project.next_run_at:%Y-%m-%d %H:%M:%S}"
        )

    logger.info(f"[扫描结束] 本次扫描完成")
