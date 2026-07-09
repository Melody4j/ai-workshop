"""竞品补充文档链路打通集成测试。

验证点：
- V-001：load_prompt("intel_user", ...) 正确替换 {competitor_context} 占位符
- V-003：_get_competitor_context 空值返回占位文本
- V-004：generate_intel 返回 5 字段（mock LLM）
- V-005：报告模板渲染 competitor_overview 为空时不报错
"""

from datetime import datetime
from unittest.mock import patch, MagicMock

from django.test import TestCase

from apps.intelligence.services.prompt_loader import load_prompt


class TestPlaceholderReplacement(TestCase):
    """V-001：intel_user.md 占位符完整性"""

    def test_load_prompt_replaces_competitor_context(self):
        """load_prompt("intel_user", ...) 不残留 {competitor_context} 字面量"""
        result = load_prompt(
            "intel_user",
            diff_text="测试 diff",
            negative_few_shots="测试反面案例",
            competitor_context="测试竞品上下文",
        )
        self.assertNotIn("{competitor_context}", result)
        self.assertNotIn("{diff_text}", result)
        self.assertNotIn("{negative_few_shots}", result)
        self.assertIn("测试竞品上下文", result)

    def test_load_prompt_with_empty_competitor_context(self):
        """空 competitor_context 也应被替换为占位文本"""
        result = load_prompt(
            "intel_user",
            diff_text="测试 diff",
            negative_few_shots="测试反面案例",
            competitor_context="",
        )
        self.assertNotIn("{competitor_context}", result)


class TestGetCompetitorContext(TestCase):
    """V-003：_get_competitor_context 空值降级"""

    def test_empty_competitor_contexts_returns_placeholder(self):
        """competitor_contexts=[] 时返回占位文本"""
        from apps.intelligence.services.scheduler_service import _get_competitor_context

        class FakeProject:
            competitor_contexts = []

        result = _get_competitor_context(FakeProject(), 0)
        self.assertEqual(result, "暂无竞品补充文档")

    def test_index_out_of_range_returns_placeholder(self):
        """index 越界时返回占位文本"""
        from apps.intelligence.services.scheduler_service import _get_competitor_context

        class FakeProject:
            competitor_contexts = [
                {"title": "A", "url": "http://a.com", "supplement_doc_name": "doc", "supplement_doc_content": "content"},
            ]

        result = _get_competitor_context(FakeProject(), 5)
        self.assertEqual(result, "暂无竞品补充文档")

    def test_empty_supplement_content_returns_placeholder(self):
        """supplement_doc_content 为空字符串时返回占位文本"""
        from apps.intelligence.services.scheduler_service import _get_competitor_context

        class FakeProject:
            competitor_contexts = [
                {"title": "A", "url": "http://a.com", "supplement_doc_name": "doc", "supplement_doc_content": ""},
            ]

        result = _get_competitor_context(FakeProject(), 0)
        self.assertEqual(result, "暂无竞品补充文档")

    def test_valid_supplement_content_returns_formatted_text(self):
        """有补充文档时返回格式化文本"""
        from apps.intelligence.services.scheduler_service import _get_competitor_context

        class FakeProject:
            competitor_contexts = [
                {
                    "title": "A",
                    "url": "http://a.com",
                    "supplement_doc_name": "竞品A简介",
                    "supplement_doc_content": "竞品A是一个AI设计工具",
                },
            ]

        result = _get_competitor_context(FakeProject(), 0)
        self.assertIn("竞品A简介", result)
        self.assertIn("竞品A是一个AI设计工具", result)


class TestIntelResultFiveFields(TestCase):
    """V-004：generate_intel 返回 5 字段（mock LLM）"""

    @patch("apps.intelligence.services.llm_service.get_instructor_client")
    @patch("apps.intelligence.services.llm_service.load_prompt")
    def test_generate_intel_returns_5_fields(self, mock_load_prompt, mock_get_client):
        """generate_intel 返回含 competitor_overview 的 5 字段 IntelResult"""
        from apps.intelligence.services.llm_client import IntelResult
        from apps.intelligence.services import llm_service

        # mock load_prompt 返回非占位符文本
        mock_load_prompt.side_effect = lambda name, **kwargs: f"prompt_{name}"

        # mock instructor client
        mock_result = IntelResult(
            competitor_overview="竞品概述内容",
            change_summary="变化摘要内容",
            strategic_intent="战略意图内容",
            action_suggestion="行动建议内容",
            evidence_diff="证据diff内容",
        )
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_result
        mock_get_client.return_value = mock_client

        result = llm_service.generate_intel(
            diff_text="diff",
            self_product_doc="doc",
            few_shots=[],
            competitor_context="竞品背景",
        )

        self.assertEqual(result.competitor_overview, "竞品概述内容")
        self.assertEqual(result.change_summary, "变化摘要内容")
        self.assertEqual(result.strategic_intent, "战略意图内容")
        self.assertEqual(result.action_suggestion, "行动建议内容")
        self.assertEqual(result.evidence_diff, "证据diff内容")

        # 验证 load_prompt 被调用时传入了 competitor_context
        user_prompt_call = [c for c in mock_load_prompt.call_args_list if c.args[0] == "intel_user"]
        self.assertTrue(user_prompt_call)
        self.assertIn("competitor_context", user_prompt_call[0].kwargs)
        self.assertEqual(user_prompt_call[0].kwargs["competitor_context"], "竞品背景")


class TestReportTemplateRendering(TestCase):
    """V-005：报告模板渲染 competitor_overview 为空时不报错"""

    def test_html_template_renders_empty_competitor_overview(self):
        """HTML 模板渲染 competitor_overview 为空字符串时不报错"""
        from jinja2 import Environment, FileSystemLoader

        env = Environment(loader=FileSystemLoader("templates/reports"))
        template = env.get_template("report.html.j2")

        class FakeFeed:
            competitor_overview = ""
            change_summary = "test"
            strategic_intent = "test"
            action_suggestion = "test"
            evidence_diff = "test"
            published_at = datetime.now()

            class project:
                project_name = "test"
            job_status = "CHANGED"

        html = template.render(feed=FakeFeed())
        self.assertIn("竞品概述", html)
        self.assertIn("变化摘要", html)

    def test_md_template_renders_empty_competitor_overview(self):
        """MD 模板渲染 competitor_overview 为空字符串时不报错"""
        from jinja2 import Environment, FileSystemLoader

        env = Environment(loader=FileSystemLoader("templates/reports"))
        template = env.get_template("report.md.j2")

        class FakeFeed:
            competitor_overview = ""
            change_summary = "test"
            strategic_intent = "test"
            action_suggestion = "test"
            evidence_diff = "test"
            published_at = datetime.now()

            class project:
                project_name = "test"
            job_status = "CHANGED"

        md = template.render(feed=FakeFeed())
        self.assertIn("竞品概述", md)
        self.assertIn("变化摘要", md)
