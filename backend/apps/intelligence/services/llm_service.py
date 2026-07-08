"""LLM 服务层：封装 3 次独立 LLM 调用。

1. denoise(): LLM 语义降噪（普通文本补全）
2. judge_diff(): LLM diff 判断（普通文本补全，JSON 输出）
3. generate_intel(): LLM 情报生成（instructor + Pydantic 结构化输出）
"""

import json
import logging
import re
import time

from django.conf import settings

from .llm_client import get_openai_client, get_instructor_client, IntelResult
from .prompt_loader import load_prompt
from .retry import retry, LLMError

logger = logging.getLogger(__name__)

# 极短输入阈值（字符数），低于此值不调用 LLM
MIN_INPUT_LENGTH = 10


@retry(max_retries=3, delay=30)
def denoise(bs_clean_md: str) -> str:
    """LLM 语义降噪：输入 BS 去噪后 MD，输出 LLM 语义降噪后 MD。

    Args:
        bs_clean_md: BeautifulSoup 去噪后的 markdown 文本

    Returns:
        LLM 语义降噪后的 markdown 文本

    Raises:
        LLMError: 重试耗尽后抛出
    """
    # 空输入或极短输入不调用 LLM
    if not bs_clean_md or len(bs_clean_md.strip()) < MIN_INPUT_LENGTH:
        logger.info("[LLM降噪] 输入为空或过短，跳过 LLM 调用")
        return bs_clean_md

    prompt = load_prompt("denoise", bs_clean_md=bs_clean_md)

    client = get_openai_client()
    response = client.chat.completions.create(
        model=settings.LLM_MODEL,
        messages=[
            {"role": "user", "content": prompt},
        ],
        temperature=settings.LLM_TEMPERATURE,
        max_tokens=settings.LLM_MAX_TOKENS,
    )

    result = response.choices[0].message.content.strip()
    logger.info(f"[LLM降噪] 完成，输入 {len(bs_clean_md)} 字符 → 输出 {len(result)} 字符")
    return result


@retry(max_retries=3, delay=30)
def judge_diff(diff_text: str, self_product_doc: str) -> dict:
    """LLM diff 判断：判断文本 diff 是否有分析价值。

    Args:
        diff_text: 文本 diff 片段（difflib 输出）
        self_product_doc: 我方产品锚定文档

    Returns:
        {"has_meaningful_change": bool, "reason": str}

    Raises:
        LLMError: 重试耗尽后抛出（含 LLM 返回非 JSON 的情况）
    """
    # 空 diff 直接返回无意义
    if not diff_text or not diff_text.strip():
        logger.info("[LLM diff判断] diff 为空，直接返回无意义")
        return {"has_meaningful_change": False, "reason": "无变化"}

    # self_product_doc 为空时标注
    doc_context = self_product_doc if self_product_doc and self_product_doc.strip() else "（暂无产品锚定文档）"

    prompt = load_prompt(
        "diff_judge",
        self_product_doc=doc_context,
        diff_text=diff_text,
    )

    client = get_openai_client()
    response = client.chat.completions.create(
        model=settings.LLM_MODEL,
        messages=[
            {"role": "user", "content": prompt},
        ],
        temperature=settings.LLM_TEMPERATURE,
        max_tokens=settings.LLM_MAX_TOKENS,
    )

    raw_output = response.choices[0].message.content.strip()

    # 尝试从返回中提取 JSON
    result = _extract_json(raw_output)
    if result is None:
        raise ValueError(f"LLM 返回非 JSON 格式: {raw_output[:200]}")

    logger.info(f"[LLM diff判断] 结果: has_meaningful_change={result.get('has_meaningful_change')}")
    return result


def _extract_json(text: str) -> dict | None:
    """从文本中提取 JSON 对象。

    LLM 可能在 JSON 前后添加 markdown 代码块标记，需要容错提取。

    Args:
        text: LLM 返回的文本

    Returns:
        解析后的 dict，解析失败返回 None
    """
    # 尝试直接解析
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 尝试提取 ```json ... ``` 代码块
    match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # 尝试提取第一个 { ... } 块
    match = re.search(r'\{[^{}]*\}', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    return None


def get_negative_few_shots(project_id: int, limit: int = 5) -> list:
    """查询最近 N 条被标记为"毫无意义"的历史情报（Negative Few-Shot）。

    Args:
        project_id: 项目 ID
        limit: 最多返回条数（默认 5）

    Returns:
        IntelligenceFeed 列表（按 published_at 倒序），无记录返回空列表
    """
    from apps.intelligence.models import IntelligenceFeed

    return list(
        IntelligenceFeed.objects.filter(
            project_id=project_id,
            user_feedback=-1,
        )
        .order_by("-published_at")[:limit]
    )


def _format_few_shots(few_shots: list) -> str:
    """将 Negative Few-Shot 列表格式化为 prompt 文本。

    Args:
        few_shots: IntelligenceFeed 列表

    Returns:
        格式化后的文本；空列表返回"暂无反面案例"
    """
    if not few_shots:
        return "暂无反面案例"

    parts = []
    for idx, feed in enumerate(few_shots, 1):
        parts.append(f"### 反面案例 {idx}")
        parts.append(f"- 摘要：{feed.change_summary}")
        parts.append(f"- 用户评语（为何无意义）：{feed.user_comment or '无评语'}")
        parts.append("")

    return "\n".join(parts).strip()


@retry(max_retries=3, delay=30)
def generate_intel(
    diff_text: str,
    self_product_doc: str,
    few_shots: list,
) -> IntelResult:
    """LLM 情报生成：instructor + Pydantic 结构化输出 4 字段。

    Args:
        diff_text: 有意义的 diff 片段
        self_product_doc: 我方产品锚定文档
        few_shots: Negative Few-Shot 列表（IntelligenceFeed 对象列表）

    Returns:
        IntelResult 实例（4 字段：change_summary / strategic_intent / action_suggestion / evidence_diff）

    Raises:
        LLMError: 重试耗尽后抛出
    """
    doc_context = self_product_doc if self_product_doc and self_product_doc.strip() else "（暂无产品锚定文档）"
    few_shots_text = _format_few_shots(few_shots)

    system_prompt = load_prompt("intel_system", self_product_doc=doc_context)
    user_prompt = load_prompt(
        "intel_user",
        diff_text=diff_text,
        negative_few_shots=few_shots_text,
    )

    client = get_instructor_client()
    result = client.chat.completions.create(
        model=settings.LLM_MODEL,
        response_model=IntelResult,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=settings.LLM_TEMPERATURE,
        max_tokens=settings.LLM_MAX_TOKENS,
    )

    logger.info(
        f"[LLM情报生成] 完成，"
        f"change_summary={len(result.change_summary)}字符, "
        f"strategic_intent={len(result.strategic_intent)}字符"
    )
    return result
