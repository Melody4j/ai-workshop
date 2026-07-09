"""测试 LLM Client 封装与 IntelResult Pydantic schema。"""
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from apps.intelligence.services.llm_client import (
    IntelResult,
    get_openai_client,
    get_instructor_client,
)


class IntelResultTest(SimpleTestCase):
    """测试 IntelResult Pydantic model。"""

    def test_intel_result_5_fields_all_str(self):
        """IntelResult 5 个字段类型均为 str，可实例化。"""
        result = IntelResult(
            competitor_overview="竞品概述",
            change_summary="变化摘要",
            strategic_intent="战略意图",
            action_suggestion="行动建议",
            evidence_diff="证据diff",
        )
        self.assertEqual(result.competitor_overview, "竞品概述")
        self.assertEqual(result.change_summary, "变化摘要")
        self.assertEqual(result.strategic_intent, "战略意图")
        self.assertEqual(result.action_suggestion, "行动建议")
        self.assertEqual(result.evidence_diff, "证据diff")

    def test_intel_result_field_count(self):
        """IntelResult 只有 5 个字段。"""
        result = IntelResult(
            competitor_overview="a",
            change_summary="b",
            strategic_intent="c",
            action_suggestion="d",
            evidence_diff="e",
        )
        # Pydantic v2 model_dump
        dumped = result.model_dump()
        self.assertEqual(len(dumped), 5)
        self.assertIn("competitor_overview", dumped)
        self.assertIn("change_summary", dumped)
        self.assertIn("strategic_intent", dumped)
        self.assertIn("action_suggestion", dumped)
        self.assertIn("evidence_diff", dumped)


@override_settings(LLM_API_KEY="test-key", LLM_BASE_URL="https://test.example.com/v1")
class LLMClientTest(SimpleTestCase):
    """测试 LLM Client 工厂函数。"""

    def test_get_openai_client_returns_client(self):
        """get_openai_client 返回 OpenAI 实例。"""
        client = get_openai_client()
        self.assertIsNotNone(client)

    def test_get_instructor_client_returns_client(self):
        """get_instructor_client 返回 instructor-wrapped client。"""
        client = get_instructor_client()
        self.assertIsNotNone(client)
