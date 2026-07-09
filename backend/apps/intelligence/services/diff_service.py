"""diff_service：文本 diff 生成与截断控制。

使用 difflib.unified_diff 生成文本 diff，超长时截断保留头尾核心变化。

核心设计：
1. text_diff()：段落级对比。diff 前先将 markdown 按段落（双换行分隔）切分，
   段落内的单换行合并为空格，减少换行漂移噪声。
2. canonical_text_diff()：先做确定性规则归一化，再复用 text_diff()，
   用于稳定化竞品页面正文 diff。
"""

import difflib
import logging
import re
import unicodedata

logger = logging.getLogger(__name__)

# diff 输出截断阈值（字符数）
DIFF_TRUNCATE_THRESHOLD = 8000


def _is_decorative_only_line(line: str) -> bool:
    """判断一行是否仅由 emoji / 装饰符号 / 标点组成。"""
    compact = re.sub(r"\s+", "", line)
    if not compact:
        return False

    for ch in compact:
        category = unicodedata.category(ch)
        if category and category[0] in {"L", "N"}:
            return False

    return all(unicodedata.category(ch)[0] in {"P", "S", "M", "C"} for ch in compact)


def canonicalize_markdown(md: str) -> str:
    """对 markdown 做确定性规则归一化，用于稳定生成 diff。

    规则：
    - 统一换行符
    - 去掉首尾空白行
    - 若整文由独立的 ``` 包裹，则移除该 code fence
    - 每行去掉首尾空白，并将连续空格/Tab 折叠为单个空格
    - 删除仅由 emoji / 装饰符号 / 项目符号组成的行
    - 连续空行折叠为单个空行
    """
    if not md or not md.strip():
        return ""

    normalized_md = md.replace("\r\n", "\n").replace("\r", "\n").strip()
    lines = normalized_md.split("\n")

    if len(lines) >= 2 and lines[0].strip() == "```" and lines[-1].strip() == "```":
        lines = lines[1:-1]

    canonical_lines: list[str] = []
    last_blank = False

    for raw_line in lines:
        collapsed = re.sub(r"[ \t]+", " ", raw_line.strip())

        if not collapsed:
            if canonical_lines and not last_blank:
                canonical_lines.append("")
            last_blank = True
            continue

        if _is_decorative_only_line(collapsed):
            continue

        canonical_lines.append(collapsed)
        last_blank = False

    while canonical_lines and canonical_lines[0] == "":
        canonical_lines.pop(0)
    while canonical_lines and canonical_lines[-1] == "":
        canonical_lines.pop()

    return "\n".join(canonical_lines)


def _normalize_to_paragraphs(md: str) -> list[str]:
    """将 markdown 按段落切分，段落内单换行合并为空格。

    markdown 的段落以双换行（含空行）分隔。在段落内部，单换行
    通常只是排版差异，不代表内容变化。

    Args:
        md: markdown 文本

    Returns:
        段落列表，每个段落为一行文本（单换行已合并为空格）

    Examples:
        >>> _normalize_to_paragraphs("hello\\nworld\\n\\nfoo")
        ['hello world', 'foo']
    """
    if not md or not md.strip():
        return []

    # 按双换行（空行）切分段落
    raw_paragraphs = re.split(r"\n\s*\n", md.strip())

    # 段落内单换行合并为空格，去除首尾空白
    paragraphs = []
    for para in raw_paragraphs:
        normalized = para.strip()
        if normalized:
            # 合并段落内的换行为空格
            normalized = re.sub(r"\n+", " ", normalized)
            # 合并多余空格
            normalized = re.sub(r" +", " ", normalized)
            # 去除 CJK 字符之间的空格（中日韩文本不使用空格分词，
            # 换行合并产生的空格在 CJK 间是噪声）
            normalized = re.sub(
                r"(?<=[\u3000-\u9fff\uff00-\uffef])\s+(?=[\u3000-\u9fff\uff00-\uffef])",
                "",
                normalized,
            )
            paragraphs.append(normalized)

    return paragraphs


def text_diff(new_md: str, prev_md: str) -> str:
    """生成文本 diff。

    用 difflib.unified_diff 对比新旧 markdown，返回 unified diff 格式字符串。
    内容完全相同返回空字符串。

    对比前先将 markdown 规范化为段落（段落内单换行合并为空格），
    避免同一段落内换行位置漂移产生 diff 噪声。

    Args:
        new_md: 当前 markdown
        prev_md: 上一条 markdown

    Returns:
        unified diff 字符串（空字符串 = 无变化）
    """
    if new_md == prev_md:
        return ""

    # 规范化为段落，避免换行漂移噪声
    new_lines = _normalize_to_paragraphs(new_md)
    prev_lines = _normalize_to_paragraphs(prev_md)

    diff_lines = list(difflib.unified_diff(prev_lines, new_lines, lineterm=""))
    diff_text = "\n".join(diff_lines)

    if not diff_text.strip():
        return ""

    # 截断处理
    diff_text = _truncate_diff(diff_text)

    logger.info(f"[Diff] 生成 {len(diff_text)} 字符的 diff")
    return diff_text


def canonical_text_diff(new_md: str, prev_md: str) -> str:
    """先做规则归一化，再生成稳定 diff。"""
    canonical_new = canonicalize_markdown(new_md)
    canonical_prev = canonicalize_markdown(prev_md)
    return text_diff(canonical_new, canonical_prev)


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
