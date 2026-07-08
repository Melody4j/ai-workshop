import logging
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from django.conf import settings

logger = logging.getLogger(__name__)


def save_raw_html(project_id: int, url: str, content: str, fetch_time: datetime) -> str:
    """将原始 HTML 保存到文件，返回绝对路径。内容为空时返回空字符串。"""
    return _save_content(project_id, url, content, fetch_time, "html")


def save_clean_md(project_id: int, url: str, content: str, fetch_time: datetime) -> str:
    """将清洗后的 Markdown 保存到文件，返回绝对路径。内容为空时返回空字符串。"""
    return _save_content(project_id, url, content, fetch_time, "md")


def _save_content(
    project_id: int,
    url: str,
    content: str,
    fetch_time: datetime,
    ext: str,
) -> str:
    if not content:
        return ""

    storage_dir = Path(settings.SNAPSHOT_STORAGE_DIR)
    date_str = fetch_time.strftime("%Y%m%d")
    time_str = fetch_time.strftime("%H%M%S")
    slug = _url_to_slug(url)

    dir_path = storage_dir / "snapshots" / str(project_id) / date_str
    dir_path.mkdir(parents=True, exist_ok=True)

    filename = f"{time_str}_{slug}.{ext}"
    file_path = dir_path / filename

    # 同秒冲突时追加序号
    counter = 1
    while file_path.exists():
        filename = f"{time_str}_{slug}_{counter}.{ext}"
        file_path = dir_path / filename
        counter += 1

    file_path.write_text(content, encoding="utf-8")
    abs_path = str(file_path.resolve())
    logger.info(f"[文件存储] 已保存 {ext.upper()} 文件: {abs_path} ({len(content)} chars)")
    return abs_path


def _url_to_slug(url: str) -> str:
    """从 URL 提取域名，转为安全的文件名片段。"""
    parsed = urlparse(url)
    domain = parsed.netloc.replace("www.", "")
    slug = re.sub(r"[^a-zA-Z0-9.-]", "-", domain)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug or "unknown"
