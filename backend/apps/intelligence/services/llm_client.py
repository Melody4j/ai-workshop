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
        description="竞品整体定位与背景概述，基于补充文档和 diff 综合分析",
    )
    change_summary: str = Field(
        ...,
        description="竞品变化的简要摘要，1-3句话，说明发生了什么变化",
    )
    strategic_intent: str = Field(
        ...,
        description="竞品此举的战略意图分析，对我方和行业的影响",
    )
    action_suggestion: str = Field(
        ...,
        description="结合我方产品定位的具体可执行行动建议",
    )
    evidence_diff: str = Field(
        ...,
        description="支撑分析的实际变化片段引用",
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
