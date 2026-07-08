"""Prompt 模板加载与变量注入工具。

从 backend/prompts/{name}.md 读取模板文件，用 str.replace 逐个替换变量占位符。
使用 replace 而非 str.format，避免模板中的 JSON 花括号被误解析。
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# prompts 目录路径：backend/prompts/
PROMPTS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "prompts"


def load_prompt(name: str, **kwargs) -> str:
    """加载 Prompt 模板并替换变量占位符。

    Args:
        name: 模板名称（不含扩展名），如 "denoise" → prompts/denoise.md
        **kwargs: 变量占位符及对应值，如 bs_clean_md="内容"

    Returns:
        渲染后的 Prompt 字符串（占位符已替换为实际值）

    Raises:
        FileNotFoundError: 模板文件不存在
    """
    file_path = PROMPTS_DIR / f"{name}.md"
    if not file_path.exists():
        raise FileNotFoundError(f"Prompt 模板文件不存在: {file_path}")

    rendered = file_path.read_text(encoding="utf-8")

    # 用 replace 逐个替换占位符，避免 JSON 花括号冲突
    for key, value in kwargs.items():
        placeholder = "{" + key + "}"
        rendered = rendered.replace(placeholder, str(value))

    logger.debug(f"[Prompt] 已加载模板 {name}，变量: {list(kwargs.keys())}")
    return rendered


def save_prompt(name: str, content: str) -> None:
    """将内容写回 Prompt 模板文件（UTF-8 编码）。

    Args:
        name: 模板名称（不含扩展名），如 "intel_system" → prompts/intel_system.md
        content: 要写入的完整 prompt 内容
    """
    file_path = PROMPTS_DIR / f"{name}.md"
    file_path.write_text(content, encoding="utf-8")
    logger.info(f"[Prompt] 已保存模板 {name}，{len(content)} 字符")
