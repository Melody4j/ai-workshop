"""Vercel Blob 存储服务。

封装 vercel_blob 库，提供文件上传、读取、删除功能。
替代本地文件系统存储（file_storage.py / report_service.py / prompt_loader.py）。

DB 字段（raw_html_path / clean_md_path / html_report_path / md_table_path）
语义从本地路径变为 Vercel Blob URL。
"""

import logging
import os

import requests
import vercel_blob

logger = logging.getLogger(__name__)

# 从环境变量读取 Blob token
_BLOB_TOKEN = os.environ.get("BLOB_READ_WRITE_TOKEN", "")


def _ensure_token():
    """确保 Blob token 已配置。"""
    if not _BLOB_TOKEN:
        raise RuntimeError("BLOB_READ_WRITE_TOKEN 未配置，无法操作 Vercel Blob")


def upload(pathname: str, content: str | bytes, content_type: str = "text/plain") -> str:
    """上传内容到 Vercel Blob，返回 Blob URL。

    Args:
        pathname: Blob 路径名（如 "snapshots/1/20240101_120000_example.html"）
        content: 文件内容（str 或 bytes）
        content_type: MIME 类型

    Returns:
        Blob URL 字符串（如 "https://xxx.public.blob.vercel-storage.com/..."）
    """
    _ensure_token()

    if isinstance(content, str):
        content_bytes = content.encode("utf-8")
    else:
        content_bytes = content

    result = vercel_blob.put(
        pathname,
        content_bytes,
        options={
            "token": _BLOB_TOKEN,
            "contentType": content_type,
        },
    )
    blob_url = result.get("url", "")
    logger.info(f"[Blob] 已上传 {pathname} → {blob_url} ({len(content_bytes)} bytes)")
    return blob_url


def upload_snapshot(project_id: int, url: str, content: str, fetch_time, ext: str, prefix: str = "") -> str:
    """上传快照文件到 Blob。

    Args:
        project_id: 项目 ID
        url: 采集的 URL（用于生成 pathname）
        content: 文件内容
        fetch_time: 采集时间
        ext: 文件扩展名（html / md）
        prefix: 文件名前缀（如 "llm_" 区分 LLM 降噪版本）

    Returns:
        Blob URL 字符串
    """
    from apps.intelligence.services.file_storage import _url_to_slug

    date_str = fetch_time.strftime("%Y%m%d")
    time_str = fetch_time.strftime("%H%M%S")
    slug = _url_to_slug(url)

    pathname = f"snapshots/{project_id}/{date_str}/{prefix}{time_str}_{slug}.{ext}"
    content_type = "text/html" if ext == "html" else "text/markdown"

    return upload(pathname, content, content_type)


def upload_report(project_id: int, feed_id: int, content: str, ext: str) -> str:
    """上传报告文件到 Blob。

    Args:
        project_id: 项目 ID
        feed_id: IntelligenceFeed ID
        content: 文件内容
        ext: 文件扩展名（html / md）

    Returns:
        Blob URL 字符串
    """
    from datetime import datetime

    date_str = datetime.now().strftime("%Y%m%d")
    pathname = f"reports/{project_id}/{date_str}/{feed_id}.{ext}"
    content_type = "text/html" if ext == "html" else "text/markdown"

    return upload(pathname, content, content_type)


def read_content(blob_url: str) -> str:
    """从 Blob URL 读取文件内容。

    公共 store 的 Blob URL 可直接通过 HTTP GET 访问，无需认证。

    Args:
        blob_url: Blob URL

    Returns:
        文件内容字符串
    """
    response = requests.get(blob_url, timeout=30)
    response.raise_for_status()
    return response.text


def delete(blob_url: str) -> None:
    """删除 Blob 文件。

    Args:
        blob_url: Blob URL
    """
    _ensure_token()
    vercel_blob.delete(blob_url, options={"token": _BLOB_TOKEN})
    logger.info(f"[Blob] 已删除 {blob_url}")
