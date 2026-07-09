"""文件存储服务（已迁移到 Vercel Blob）。

原本地文件系统存储已替换为 Vercel Blob。
返回值从本地路径变为 Blob URL。

保留 _url_to_slug 供 blob_storage.upload_snapshot 调用。
"""

import logging
import re
from datetime import datetime
from urllib.parse import urlparse

from apps.intelligence.services import blob_storage

logger = logging.getLogger(__name__)


def save_raw_html(project_id: int, url: str, content: str, fetch_time: datetime) -> str:
    """将原始 HTML 上传到 Vercel Blob，返回 Blob URL。内容为空时返回空字符串。"""
    if not content:
        return ""
    return blob_storage.upload_snapshot(project_id, url, content, fetch_time, "html")


def save_clean_md(project_id: int, url: str, content: str, fetch_time: datetime) -> str:
    """将 BS 清洗后的 Markdown 上传到 Vercel Blob，返回 Blob URL。内容为空时返回空字符串。"""
    if not content:
        return ""
    return blob_storage.upload_snapshot(project_id, url, content, fetch_time, "md")


def save_llm_clean_md(project_id: int, url: str, content: str, fetch_time: datetime) -> str:
    """将 LLM 降噪后的 Markdown 上传到 Vercel Blob，返回 Blob URL。

    pathname 加 llm_ 前缀以区分 BS 清洗版本，用于旧格式兼容检测。
    """
    if not content:
        return ""
    return blob_storage.upload_snapshot(project_id, url, content, fetch_time, "md", prefix="llm_")


def _url_to_slug(url: str) -> str:
    """从 URL 提取域名，转为安全的文件名片段。"""
    parsed = urlparse(url)
    domain = parsed.netloc.replace("www.", "")
    slug = re.sub(r"[^a-zA-Z0-9.-]", "-", domain)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug or "unknown"
