"""report_service：Jinja2 HTML/MD 报告渲染与上传到 Vercel Blob。

渲染 IntelligenceFeed（仅 CHANGED）为 HTML 网页报告和 MD 表格，
上传到 Vercel Blob，返回 Blob URL。
"""

import logging
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from apps.intelligence.models import IntelligenceFeed
from apps.intelligence.services import blob_storage

logger = logging.getLogger(__name__)

# Jinja2 模板目录
TEMPLATES_DIR = Path(__file__).resolve().parent.parent.parent.parent / "templates" / "reports"


def _get_env() -> Environment:
    """获取 Jinja2 Environment 实例。"""
    return Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=True,
    )


def render_html(feed: IntelligenceFeed) -> str:
    """渲染 HTML 网页报告并上传到 Vercel Blob。

    Args:
        feed: IntelligenceFeed 实例（仅 CHANGED 状态才渲染）

    Returns:
        Blob URL；非 CHANGED 返回空字符串
    """
    if feed.job_status != IntelligenceFeed.JobStatus.CHANGED:
        logger.info(f"[报告] feed {feed.id} 状态={feed.job_status}，跳过 HTML 渲染")
        return ""

    env = _get_env()
    template = env.get_template("report.html.j2")
    html_content = template.render(feed=feed)

    blob_url = blob_storage.upload_report(feed.project_id, feed.id, html_content, "html")
    logger.info(f"[报告] HTML 已渲染并上传: {blob_url}")
    return blob_url


def render_md(feed: IntelligenceFeed) -> str:
    """渲染 MD 表格报告并上传到 Vercel Blob。

    Args:
        feed: IntelligenceFeed 实例（仅 CHANGED 状态才渲染）

    Returns:
        Blob URL；非 CHANGED 返回空字符串
    """
    if feed.job_status != IntelligenceFeed.JobStatus.CHANGED:
        logger.info(f"[报告] feed {feed.id} 状态={feed.job_status}，跳过 MD 渲染")
        return ""

    env = _get_env()
    template = env.get_template("report.md.j2")
    md_content = template.render(feed=feed)

    blob_url = blob_storage.upload_report(feed.project_id, feed.id, md_content, "md")
    logger.info(f"[报告] MD 已渲染并上传: {blob_url}")
    return blob_url
