"""report_service：Jinja2 HTML/MD 报告渲染与落盘。

渲染 IntelligenceFeed（仅 CHANGED）为 HTML 网页报告和 MD 表格，
落盘到 SNAPSHOT_STORAGE_DIR/reports/{project_id}/{date}/{feed_id}.html|md
"""

import logging
from datetime import datetime
from pathlib import Path

from django.conf import settings
from jinja2 import Environment, FileSystemLoader

from apps.intelligence.models import IntelligenceFeed

logger = logging.getLogger(__name__)

# Jinja2 模板目录
TEMPLATES_DIR = Path(__file__).resolve().parent.parent.parent.parent / "templates" / "reports"


def _get_env() -> Environment:
    """获取 Jinja2 Environment 实例。"""
    return Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=True,
    )


def _get_report_dir(project_id: int, feed_id: int) -> Path:
    """获取报告落盘目录，自动创建。"""
    storage_dir = Path(settings.SNAPSHOT_STORAGE_DIR)
    date_str = datetime.now().strftime("%Y%m%d")
    report_dir = storage_dir / "reports" / str(project_id) / date_str
    report_dir.mkdir(parents=True, exist_ok=True)
    return report_dir


def render_html(feed: IntelligenceFeed) -> str:
    """渲染 HTML 网页报告并落盘。

    Args:
        feed: IntelligenceFeed 实例（仅 CHANGED 状态才渲染）

    Returns:
        HTML 文件绝对路径；非 CHANGED 返回空字符串
    """
    if feed.job_status != IntelligenceFeed.JobStatus.CHANGED:
        logger.info(f"[报告] feed {feed.id} 状态={feed.job_status}，跳过 HTML 渲染")
        return ""

    env = _get_env()
    template = env.get_template("report.html.j2")
    html_content = template.render(feed=feed)

    report_dir = _get_report_dir(feed.project_id, feed.id)
    file_path = report_dir / f"{feed.id}.html"
    file_path.write_text(html_content, encoding="utf-8")

    abs_path = str(file_path.resolve())
    logger.info(f"[报告] HTML 已渲染: {abs_path}")
    return abs_path


def render_md(feed: IntelligenceFeed) -> str:
    """渲染 MD 表格报告并落盘。

    Args:
        feed: IntelligenceFeed 实例（仅 CHANGED 状态才渲染）

    Returns:
        MD 文件绝对路径；非 CHANGED 返回空字符串
    """
    if feed.job_status != IntelligenceFeed.JobStatus.CHANGED:
        logger.info(f"[报告] feed {feed.id} 状态={feed.job_status}，跳过 MD 渲染")
        return ""

    env = _get_env()
    template = env.get_template("report.md.j2")
    md_content = template.render(feed=feed)

    report_dir = _get_report_dir(feed.project_id, feed.id)
    file_path = report_dir / f"{feed.id}.md"
    file_path.write_text(md_content, encoding="utf-8")

    abs_path = str(file_path.resolve())
    logger.info(f"[报告] MD 已渲染: {abs_path}")
    return abs_path
