"""diff_service：文本 diff 生成与截断控制。

使用 difflib.unified_diff 生成文本 diff，超长时截断保留头尾核心变化。
"""

import difflib
import logging

logger = logging.getLogger(__name__)

# diff 输出截断阈值（字符数）
DIFF_TRUNCATE_THRESHOLD = 8000


def text_diff(new_md: str, prev_md: str) -> str:
    """生成文本 diff。

    用 difflib.unified_diff 对比新旧 markdown，返回 unified diff 格式字符串。
    内容完全相同返回空字符串。

    Args:
        new_md: 当前 LLM 降噪后 markdown
        prev_md: 上一条快照的 LLM 降噪后 markdown

    Returns:
        unified diff 字符串（空字符串 = 无变化）
    """
    if new_md == prev_md:
        return ""

    new_lines = new_md.splitlines(keepends=True)
    prev_lines = prev_md.splitlines(keepends=True)

    diff_lines = list(difflib.unified_diff(prev_lines, new_lines, lineterm=""))
    diff_text = "\n".join(diff_lines)

    if not diff_text.strip():
        return ""

    # 截断处理
    diff_text = _truncate_diff(diff_text)

    logger.info(f"[Diff] 生成 {len(diff_text)} 字符的 diff")
    return diff_text


def _truncate_diff(diff_text: str) -> str:
    """截断 diff 输出，保留头部和尾部核心变化。

    超过 DIFF_TRUNCATE_THRESHOLD 字符时：
    - 保留头部前 4000 字符
    - 保留尾部后 4000 字符
    - 中间用截断标记替换

    Args:
        diff_text: 原始 diff 文本

    Returns:
        截断后的 diff 文本（可能等于原文）
    """
    if len(diff_text) <= DIFF_TRUNCATE_THRESHOLD:
        return diff_text

    half = DIFF_TRUNCATE_THRESHOLD // 2
    head = diff_text[:half]
    tail = diff_text[-half:]
    truncation_marker = f"\n\n...截断（省略 {len(diff_text) - DIFF_TRUNCATE_THRESHOLD} 字符）...\n\n"

    logger.info(
        f"[Diff] 截断：{len(diff_text)} → {len(head) + len(tail) + len(truncation_marker)} 字符"
    )
    return head + truncation_marker + tail
