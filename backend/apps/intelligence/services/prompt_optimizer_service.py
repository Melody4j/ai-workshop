"""Prompt 优化服务：收集上下文 → LLM 优化 → 版本存档 → 覆盖文件。

用户评分=-1 时触发，异步执行（threading）。
复用现有 @retry / instructor / prompt_loader 基础设施。
"""

import logging

from django.conf import settings

from apps.intelligence.models import IntelligenceFeed, PromptVersion, DataSnapshot
from .llm_client import get_instructor_client, OptimizedPrompts
from .prompt_loader import load_prompt, save_prompt
from .retry import retry, LLMError

logger = logging.getLogger(__name__)


@retry(max_retries=3, delay=30)
def optimize_prompts(feed_id: int) -> dict:
    """收集上下文 → LLM 优化 → 版本存档 → 覆盖文件。

    Args:
        feed_id: 触发优化的 IntelligenceFeed ID（user_feedback=-1 的记录）

    Returns:
        {"intel_system_version": N, "intel_user_version": M}

    Raises:
        LLMError: LLM 调用重试耗尽后抛出
    """
    # 1. 读取 feed
    feed = IntelligenceFeed.objects.get(pk=feed_id)

    # 2. 收集上下文
    diff_text = feed.diff_text or ""

    # 读取 clean_md（从最新快照的 Blob URL）
    clean_md = ""
    snapshot = DataSnapshot.objects.filter(
        project=feed.project_id,
    ).order_by("-fetch_time", "-id").first()
    if snapshot and snapshot.clean_md_path:
        try:
            from . import blob_storage
            clean_md = blob_storage.read_content(snapshot.clean_md_path)
        except Exception as e:
            logger.warning(f"[Prompt优化] 读取 clean_md 失败: {e}")

    # 拼接 AI 分析报告
    ai_report = f"""## 竞品概述
{feed.competitor_overview}

## 变化摘要
{feed.change_summary}

## 战略意图
{feed.strategic_intent}

## 行动建议
{feed.action_suggestion}

## 证据 diff
{feed.evidence_diff}
"""

    user_comment = feed.user_comment or "（无评语）"

    # 3. 读取当前 prompt 全文
    current_intel_system = _read_prompt_file("intel_system")
    current_intel_user = _read_prompt_file("intel_user")

    # 4. 注入 meta-prompt → 调用 LLM
    optimizer_prompt = load_prompt(
        "prompt_optimizer",
        diff_text=diff_text,
        clean_md=clean_md,
        ai_report=ai_report,
        user_comment=user_comment,
        current_intel_system=current_intel_system,
        current_intel_user=current_intel_user,
    )

    client = get_instructor_client()
    result = client.chat.completions.create(
        model=settings.LLM_MODEL,
        response_model=OptimizedPrompts,
        messages=[
            {"role": "user", "content": optimizer_prompt},
        ],
        temperature=settings.LLM_TEMPERATURE,
        max_tokens=settings.LLM_MAX_TOKENS,
    )

    # 5. 校验返回内容
    if not result.intel_system or len(result.intel_system.strip()) < 50:
        raise ValueError(f"LLM 返回 intel_system 过短或为空: {len(result.intel_system)} 字符")
    if not result.intel_user or len(result.intel_user.strip()) < 50:
        raise ValueError(f"LLM 返回 intel_user 过短或为空: {len(result.intel_user)} 字符")

    # 6. 写 PromptVersion 记录（存全文 + version 自增）
    sys_version = _create_version("intel_system", result.intel_system, feed, user_comment)
    user_version = _create_version("intel_user", result.intel_user, feed, user_comment)

    # 7. 覆盖 prompt 文件
    save_prompt("intel_system", result.intel_system)
    save_prompt("intel_user", result.intel_user)

    logger.info(
        f"[Prompt优化] feed={feed_id} 完成: "
        f"intel_system v{sys_version}, intel_user v{user_version}"
    )

    return {
        "intel_system_version": sys_version,
        "intel_user_version": user_version,
    }


def _read_prompt_file(name: str) -> str:
    """读取 prompt 模板文件原始内容（从 Blob 读取，不注入变量）。"""
    from .prompt_loader import _get_blob_url
    from . import blob_storage
    pathname = f"prompts/{name}.md"
    return blob_storage.read_content(_get_blob_url(pathname))


def _create_version(prompt_name: str, content: str, feed: IntelligenceFeed, reason: str) -> int:
    """创建 PromptVersion 记录，返回新 version 号。"""
    max_version = PromptVersion.objects.filter(prompt_name=prompt_name).aggregate(
        max_v=models_max("version")
    )["max_v"] or 0
    new_version = max_version + 1
    PromptVersion.objects.create(
        prompt_name=prompt_name,
        content=content,
        version=new_version,
        feed=feed,
        optimization_reason=reason,
    )
    return new_version


def models_max(field_name):
    """避免在模块顶层 import aggregate 函数。"""
    from django.db.models import Max
    return Max(field_name)
