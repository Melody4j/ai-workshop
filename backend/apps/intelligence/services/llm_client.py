"""LLM Client 封装：OpenAI 兼容 client + instructor + Pydantic schema。

提供：
- IntelResult: Pydantic model，约束情报生成 4 字段输出
- get_openai_client(): 返回 OpenAI client（普通文本补全用）
- get_instructor_client(): 返回 instructor-wrapped client（结构化输出用）
"""

import logging

from django.conf import settings
from openai import OpenAI
import instructor
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class IntelResult(BaseModel):
    """情报生成结果 Pydantic schema（5 字段，instructor 约束）。"""

    competitor_overview: str = Field(
        ...,
        description="竞品的实际业务定位、核心产品、目标用户概述。基于页面内容和补充文档，不从 diff 推断。2-4 段。",
    )
    change_summary: str = Field(
        ...,
        description="严格基于 diff 描述发生了什么变化，点明变化类型。3-5 句话。",
    )
    strategic_intent: str = Field(
        ...,
        description="基于实际变化推断竞品战略目的。如变化不实质，直接说明。标注事实推断与假设。",
    )
    action_suggestion: str = Field(
        ...,
        description="结合我方产品定位，给出具体可执行的行动建议，包含优先级（高/中/低）。",
    )
    evidence_diff: str = Field(
        ...,
        description="从 diff 中选取关键变化原文片段，格式为引用 + 标注支撑的分析结论。不得编造引文。",
    )


class DiffJudgeResult(BaseModel):
    """diff 判断结果 Pydantic schema（instructor 约束）。"""

    has_meaningful_change: bool = Field(
        ...,
        description="diff 是否有竞争分析价值",
    )
    reason: str = Field(
        ...,
        description="详细判断理由",
    )


class OptimizedPrompts(BaseModel):
    """LLM prompt 优化结果 schema（2 字段，instructor 约束）。"""

    intel_system: str = Field(
        ...,
        description="优化后的情报生成 system prompt 全文",
    )
    intel_user: str = Field(
        ...,
        description="优化后的情报生成 user prompt 全文",
    )


def get_openai_client() -> OpenAI:
    """返回 OpenAI 兼容 client 实例（用于普通文本补全）。

    配置从 Django settings 读取（LLM_API_KEY / LLM_BASE_URL）。
    """
    return OpenAI(
        api_key=settings.LLM_API_KEY,
        base_url=settings.LLM_BASE_URL,
    )


def get_instructor_client():
    """返回 instructor-wrapped OpenAI client（用于结构化输出）。

    通过 instructor + Pydantic schema 约束 LLM 输出格式。
    """
    client = get_openai_client()
    return instructor.from_openai(client)
