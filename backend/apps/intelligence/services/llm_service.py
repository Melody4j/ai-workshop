"""LLM 服务层：封装 3 次独立 LLM 调用。

1. denoise(): LLM 语义降噪（普通文本补全）
2. judge_diff(): LLM diff 判断（普通文本补全，JSON 输出）
3. generate_intel(): LLM 情报生成（instructor + Pydantic 结构化输出）
"""

import logging
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
