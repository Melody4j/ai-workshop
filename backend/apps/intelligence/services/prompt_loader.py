"""Prompt 模板加载与变量注入工具（已迁移到 Vercel Blob）。

从 Vercel Blob 读取模板内容（pathname: prompts/{name}.md），用 str.replace 逐个替换变量占位符。
使用 replace 而非 str.format，避免模板中的 JSON 花括号被误解析。

本地 prompts/ 目录仅用于初始化脚本上传到 Blob。
"""

import logging
from pathlib import Path

from apps.intelligence.services import blob_storage

logger = logging.getLogger(__name__)

# prompts 本地目录路径：backend/prompts/（仅用于初始化脚本）
PROMPTS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "prompts"


def load_prompt(name: str, **kwargs) -> str:
    """从 Vercel Blob 加载 Prompt 模板并替换变量占位符。

    Args:
        name: 模板名称（不含扩展名），如 "denoise" → prompts/denoise.md
        **kwargs: 变量占位符及对应值，如 bs_clean_md="内容"

    Returns:
        渲染后的 Prompt 字符串（占位符已替换为实际值）

    Raises:
        Exception: Blob 读取失败
    """
    pathname = f"prompts/{name}.md"
    rendered = blob_storage.read_content(
        _get_blob_url(pathname)
    )

    # 用 replace 逐个替换占位符，避免 JSON 花括号冲突
    for key, value in kwargs.items():
        placeholder = "{" + key + "}"
        rendered = rendered.replace(placeholder, str(value))

    logger.debug(f"[Prompt] 已加载模板 {name}，变量: {list(kwargs.keys())}")
    return rendered


def save_prompt(name: str, content: str) -> None:
    """将内容写入 Vercel Blob（pathname: prompts/{name}.md）。

    Args:
        name: 模板名称（不含扩展名），如 "intel_system" → prompts/intel_system.md
        content: 要写入的完整 prompt 内容
    """
    pathname = f"prompts/{name}.md"
    blob_storage.upload(pathname, content, content_type="text/markdown")
    logger.info(f"[Prompt] 已保存模板 {name} 到 Blob，{len(content)} 字符")


# 缓存 Blob URL 映射，避免每次 load_prompt 都调用 list
_blob_url_cache: dict[str, str] = {}


def _get_blob_url(pathname: str) -> str:
    """通过 pathname 查找对应的 Blob URL。

    使用缓存避免重复请求。首次调用时从 Blob list 获取。
    """
    if pathname in _blob_url_cache:
        return _blob_url_cache[pathname]

    # 尝试直接构建 Blob URL（公共 store 的 URL 格式可预测）
    # 但最可靠的方式是通过 list API 查找
    import os
    import vercel_blob

    token = os.environ.get("BLOB_READ_WRITE_TOKEN", "")
    if not token:
        raise RuntimeError("BLOB_READ_WRITE_TOKEN 未配置")

    result = vercel_blob.list(options={"token": token})
    blobs = result.get("blobs", [])
    for blob in blobs:
        blob_path = blob.get("pathname", "")
        _blob_url_cache[blob_path] = blob.get("url", "")

    if pathname not in _blob_url_cache:
        raise FileNotFoundError(f"Prompt 模板不存在于 Blob: {pathname}")

    return _blob_url_cache[pathname]
