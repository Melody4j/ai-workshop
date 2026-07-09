"""Inngest 客户端与函数定义。

替代 django-apscheduler 的 BackgroundScheduler：
- Cron 函数：每分钟检查到期项目并执行扫描
- 事件函数 app/scan.project：手动触发单个项目扫描
- 事件函数 app/optimize.prompt：评分=-1 时触发 Prompt 优化
"""

import logging

import inngest

logger = logging.getLogger(__name__)

# 创建 Inngest 客户端
inngest_client = inngest.Inngest(
    app_id="ai_workshop",
    event_key=__import__("os").environ.get("INNGEST_EVENT_KEY", ""),
    signing_key=__import__("os").environ.get("INNGEST_SIGNING_KEY", ""),
)


@inngest_client.create_function(
    fn_id="scheduled-scan",
    trigger=inngest.TriggerCron(cron="* * * * *"),
)
def scheduled_scan(ctx: inngest.ContextSync) -> None:
    """定时扫描：每分钟检查所有 active 项目是否到期，到期则执行扫描链路。"""
    ctx.step.run(
        "run_scan",
        lambda: _run_scan_wrapper(),
    )


def _run_scan_wrapper():
    """包装 run_scan，供 Inngest step 调用。"""
    from apps.intelligence.services.scheduler_service import run_scan
    run_scan()


@inngest_client.create_function(
    fn_id="scan-project",
    trigger=inngest.TriggerEvent(event="app/scan.project"),
)
def scan_project(ctx: inngest.ContextSync) -> None:
    """手动触发单个项目扫描。

    事件 data: {"project_id": int}
    """
    project_id = ctx.event.data.get("project_id")
    if not project_id:
        logger.warning("[Inngest] scan-project 事件缺少 project_id")
        return

    ctx.step.run(
        f"scan-project-{project_id}",
        lambda: _run_scan_for_project_wrapper(project_id),
    )


def _run_scan_for_project_wrapper(project_id: int):
    """包装 run_scan_for_project，供 Inngest step 调用。"""
    from apps.intelligence.services.scheduler_service import run_scan_for_project
    run_scan_for_project(project_id)


@inngest_client.create_function(
    fn_id="optimize-prompt",
    trigger=inngest.TriggerEvent(event="app/optimize.prompt"),
)
def optimize_prompt(ctx: inngest.ContextSync) -> None:
    """评分=-1 时触发 Prompt 优化。

    事件 data: {"feed_id": int}
    """
    feed_id = ctx.event.data.get("feed_id")
    if not feed_id:
        logger.warning("[Inngest] optimize-prompt 事件缺少 feed_id")
        return

    ctx.step.run(
        f"optimize-prompt-{feed_id}",
        lambda: _optimize_prompts_wrapper(feed_id),
    )


def _optimize_prompts_wrapper(feed_id: int):
    """包装 optimize_prompts，供 Inngest step 调用。"""
    from apps.intelligence.services.prompt_optimizer_service import optimize_prompts
    optimize_prompts(feed_id)


# 导出所有函数列表（供 serve 注册）
all_functions = [scheduled_scan, scan_project, optimize_prompt]
