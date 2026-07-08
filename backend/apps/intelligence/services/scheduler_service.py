"""调度服务：全局扫描 → 采集 → LLM 降噪 → diff 熔断 → 情报生成 → 入库+报告。

核心链路（每 URL）：
1. 采集（httpx + BS 去噪）
2. LLM 语义降噪（第 1 次 LLM 调用）
3. 保存 LLM 降噪 MD，创建 DataSnapshot（clean_md_path 指向 LLM 版本）
4. 获取上一条快照 → 首次爬取/旧格式 → 跳过 diff；否则文本 diff
5. 文本 diff 为空 → 熔断 NO_CHANGE
6. LLM diff 判断（第 2 次 LLM 调用）→ 无意义 → 熔断 NO_CHANGE
7. LLM 情报生成（第 3 次 LLM 调用，instructor + Pydantic）
8. 写 IntelligenceFeed(CHANGED) + Jinja2 报告落盘
"""

import logging
from pathlib import Path

from django.utils import timezone

from apps.intelligence.models import MonitorProject, DataSnapshot, IntelligenceFeed
from apps.intelligence.services import crawler_service
from apps.intelligence.services import diff_service
from apps.intelligence.services import file_storage
from apps.intelligence.services import llm_service
from apps.intelligence.services import report_service
from apps.intelligence.services.cron_matcher import get_next_run

logger = logging.getLogger(__name__)


def run_scan():
    """全局扫描：检查所有 active 项目是否到期，到期则逐 URL 采集 → LLM 链路 → 入库。"""
    now = timezone.now()
    now_local = timezone.localtime(now)
    active_projects = MonitorProject.objects.filter(is_active=True)
    project_count = active_projects.count()
    logger.info(f"[扫描开始] 当前 {project_count} 个活跃项目, 时间 {now_local:%Y-%m-%d %H:%M:%S}")

    for project in active_projects:
        if project.next_run_at is not None and project.next_run_at > now:
            next_local = timezone.localtime(project.next_run_at)
            logger.info(f"[跳过] 项目 {project.project_name} 未到期, 下次执行 {next_local:%Y-%m-%d %H:%M:%S}")
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
                _process_url(project, url, title, now)
            except Exception as e:
                logger.error(f"[处理异常] {url} - {e}", exc_info=True)
                IntelligenceFeed.objects.create(
                    project=project,
                    job_status=IntelligenceFeed.JobStatus.ERROR_CRAWL,
                    change_summary=f"处理异常: {e}",
                    published_at=now,
                )

        # 更新 next_run_at
        project.next_run_at = get_next_run(project.cron, now)
        project.save(update_fields=["next_run_at"])
        next_local = timezone.localtime(project.next_run_at)
        logger.info(
            f"[项目完成] {project.project_name} 执行结束, 下次执行 {next_local:%Y-%m-%d %H:%M:%S}"
        )

    logger.info(f"[扫描结束] 本次扫描完成")


def _process_url(project, url, title, now):
    """处理单个 URL 的完整链路：采集 → LLM降噪 → diff熔断 → 情报生成 → 入库+报告。

    异常由调用方捕获，单 URL 异常不中断其他 URL。
    """
    # === Step 1: 采集 ===
    try:
        raw_md, clean_md = crawler_service.fetch_and_clean(url)
        logger.info(f"[采集完成] {url} raw={len(raw_md)} chars, clean={len(clean_md)} chars")
    except Exception as e:
        logger.error(f"[采集异常] {url} - {e}", exc_info=True)
        raw_md, clean_md = "", ""

    if not raw_md or not clean_md:
        IntelligenceFeed.objects.create(
            project=project,
            job_status=IntelligenceFeed.JobStatus.ERROR_CRAWL,
            change_summary=f"采集失败: {url}",
            published_at=now,
        )
        logger.warning(f"[采集失败] {url} → ERROR_CRAWL")
        return

    # === Step 2: 保存原始 HTML 和 BS 清洗 MD（BS 版本仅存文件，不入 DB）===
    raw_html_path = file_storage.save_raw_html(project.id, url, raw_md, now)
    file_storage.save_clean_md(project.id, url, clean_md, now)

    # === Step 3: LLM 语义降噪（第 1 次 LLM 调用）===
    try:
        llm_clean_md = llm_service.denoise(clean_md)
    except Exception as e:
        logger.error(f"[LLM降噪失败] {url} - {e}", exc_info=True)
        IntelligenceFeed.objects.create(
            project=project,
            job_status=IntelligenceFeed.JobStatus.ERROR_CRAWL,
            change_summary=f"LLM 降噪失败: {e}",
            published_at=now,
        )
        return

    # === Step 4: 保存 LLM 降噪 MD，创建快照（clean_md_path 指向 LLM 版本）===
    llm_clean_md_path = file_storage.save_llm_clean_md(project.id, url, llm_clean_md, now)
    snapshot = DataSnapshot.objects.create(
        project=project,
        source_url=url,
        source_title=title,
        raw_html_path=raw_html_path,
        clean_md_path=llm_clean_md_path,
        fetch_time=now,
    )
    logger.info(f"[入库] 快照已保存: {url} (clean_md_path → LLM 版本)")

    # === Step 5: 获取上一条快照（排除当前条）===
    prev_snapshot = DataSnapshot.objects.filter(
        project=project,
        source_url=url,
    ).exclude(pk=snapshot.pk).first()

    diff_text = ""
    skip_diff = False

    if prev_snapshot is None:
        # 首次爬取：跳过 diff，直接情报生成
        logger.info(f"[首次爬取] {url} 无历史快照，跳过 diff")
        skip_diff = True
        diff_text = llm_clean_md
    elif not prev_snapshot.clean_md_path or "llm_" not in Path(prev_snapshot.clean_md_path).name:
        # 旧格式兼容：上一条是 pre-LLM 快照
        logger.info(f"[旧格式兼容] {url} 上一条快照为 pre-LLM 格式，跳过 diff")
        skip_diff = True
        diff_text = llm_clean_md
    else:
        # === Step 6: 读取上一条 LLM 降噪 MD，做文本 diff ===
        prev_md = ""
        try:
            prev_md = Path(prev_snapshot.clean_md_path).read_text(encoding="utf-8")
        except Exception as e:
            logger.warning(f"[读取上一条快照失败] {url} - {e}，跳过 diff")
            skip_diff = True
            diff_text = llm_clean_md

        if not skip_diff:
            diff_text = diff_service.text_diff(llm_clean_md, prev_md)
            if not diff_text:
                # 文本 diff 为空 → 熔断
                IntelligenceFeed.objects.create(
                    project=project,
                    job_status=IntelligenceFeed.JobStatus.NO_CHANGE,
                    published_at=now,
                )
                logger.info(f"[熔断] {url} 文本 diff 为空 → NO_CHANGE")
                return

    # === Step 7: LLM diff 判断（第 2 次 LLM 调用，仅非跳过时执行）===
    if not skip_diff:
        try:
            judge_result = llm_service.judge_diff(diff_text, project.self_product_doc)
        except Exception as e:
            logger.error(f"[LLM diff判断失败] {url} - {e}", exc_info=True)
            IntelligenceFeed.objects.create(
                project=project,
                job_status=IntelligenceFeed.JobStatus.ERROR_CRAWL,
                change_summary=f"LLM diff 判断失败: {e}",
                published_at=now,
            )
            return

        if not judge_result.get("has_meaningful_change"):
            IntelligenceFeed.objects.create(
                project=project,
                job_status=IntelligenceFeed.JobStatus.NO_CHANGE,
                change_summary=judge_result.get("reason", "LLM 判断无意义变化"),
                published_at=now,
            )
            logger.info(f"[熔断] {url} LLM 判断无意义变化 → NO_CHANGE")
            return

    # === Step 8: LLM 情报生成（第 3 次 LLM 调用，instructor + Pydantic）===
    try:
        few_shots = llm_service.get_negative_few_shots(project.id)
        intel_result = llm_service.generate_intel(
            diff_text=diff_text,
            self_product_doc=project.self_product_doc,
            few_shots=few_shots,
        )
    except Exception as e:
        logger.error(f"[LLM情报生成失败] {url} - {e}", exc_info=True)
        IntelligenceFeed.objects.create(
            project=project,
            job_status=IntelligenceFeed.JobStatus.ERROR_CRAWL,
            change_summary=f"LLM 情报生成失败: {e}",
            published_at=now,
        )
        return

    # === Step 9: 写 IntelligenceFeed(CHANGED, 4字段) ===
    feed = IntelligenceFeed.objects.create(
        project=project,
        job_status=IntelligenceFeed.JobStatus.CHANGED,
        change_summary=intel_result.change_summary,
        strategic_intent=intel_result.strategic_intent,
        action_suggestion=intel_result.action_suggestion,
        evidence_diff=intel_result.evidence_diff,
        published_at=now,
    )
    logger.info(f"[情报入库] {url} → feed {feed.id} CHANGED")

    # === Step 10: 报告渲染 ===
    try:
        html_path = report_service.render_html(feed)
        md_path = report_service.render_md(feed)
        feed.html_report_path = html_path
        feed.md_table_path = md_path
        feed.save(update_fields=["html_report_path", "md_table_path"])
        logger.info(f"[报告落盘] {url} → HTML: {html_path}, MD: {md_path}")
    except Exception as e:
        logger.error(f"[报告渲染失败] {url} - {e}", exc_info=True)
