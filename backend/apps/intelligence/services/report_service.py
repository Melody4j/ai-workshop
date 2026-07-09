"""report_service：Jinja2 HTML/MD 报告渲染与上传到 Vercel Blob。

渲染 IntelligenceFeed（仅 CHANGED）为 HTML 网页报告和 MD 表格，
上传到 Vercel Blob，返回 Blob URL。
"""

import logging
import re
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from apps.intelligence.models import IntelligenceFeed
from apps.intelligence.services import blob_storage

logger = logging.getLogger(__name__)

# Jinja2 模板目录
TEMPLATES_DIR = Path(__file__).resolve().parent.parent.parent.parent / "templates" / "reports"


def parse_diff_lines(diff_text: str) -> list[dict]:
    """将 unified diff 文本解析为结构化行列表，供模板渲染红绿对比。

    解析 difflib.unified_diff 输出格式：
    - `---` / `+++` 文件头行 → 跳过
    - `@@ ... @@` hunk 头 → type=“hunk”
    - `+...` → type=“add”
    - `-...` → type=“del”
    - ` ...` → type=“ctx”
    - 其他 → type=“ctx”

    对连续的 del+add 行进行配对，生成 type=“pair”（左右对比）。
    未配对的 del 或 add 保留原样。

    Returns:
        [{"type": "hunk", "content": "@@ ... @@"},
         {"type": "pair", "old": "...", "new": "..."},
         {"type": "add", "content": "..."},
         {"type": "del", "content": "..."},
         {"type": "ctx", "content": "..."}]
    """
    if not diff_text or not diff_text.strip():
        return []

    lines = diff_text.splitlines()
    result: list[dict] = []

    # 先分类所有行
    classified: list[dict] = []
    for line in lines:
        if line.startswith("---") or line.startswith("+++"):
            continue
        elif line.startswith("@@"):
            classified.append({"type": "hunk", "content": line})
        elif line.startswith("+"):
            classified.append({"type": "add", "content": line[1:]})
        elif line.startswith("-"):
            classified.append({"type": "del", "content": line[1:]})
        elif line.startswith(" "):
            classified.append({"type": "ctx", "content": line[1:]})
        else:
            classified.append({"type": "ctx", "content": line})

    # 配对连续 del+add 行
    i = 0
    while i < len(classified):
        item = classified[i]
        if item["type"] == "del":
            # 收集连续 del 行
            dels = [item]
            j = i + 1
            while j < len(classified) and classified[j]["type"] == "del":
                dels.append(classified[j])
                j += 1
            # 检查后面是否有连续 add 行
            adds = []
            k = j
            while k < len(classified) and classified[k]["type"] == "add":
                adds.append(classified[k])
                k += 1
            if adds:
                # 配对
                for idx in range(max(len(dels), len(adds))):
                    old = dels[idx]["content"] if idx < len(dels) else ""
                    new = adds[idx]["content"] if idx < len(adds) else ""
                    if old and new:
                        result.append({"type": "pair", "old": old, "new": new})
                    elif new:
                        result.append({"type": "add", "content": new})
                    elif old:
                        result.append({"type": "del", "content": old})
                i = k
            else:
                # 无配对 add，直接输出 del
                for d in dels:
                    result.append(d)
                i = j
        elif item["type"] == "add":
            # 前面没有 del 配对的 add
            result.append(item)
            i += 1
        else:
            # hunk / ctx
            result.append(item)
            i += 1

    return result


def _get_env() -> Environment:
    """获取 Jinja2 Environment 实例。"""
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=True,
    )
    env.filters["parse_diff"] = parse_diff_lines
    return env


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
