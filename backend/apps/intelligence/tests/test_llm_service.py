"""测试 LLM 降噪服务。"""
from unittest.mock import patch, MagicMock

from django.test import SimpleTestCase, override_settings

from apps.intelligence.services.retry import LLMError


@override_settings(LLM_API_KEY="test-key", LLM_BASE_URL="https://test.example.com/v1")
class DenoiseServiceTest(SimpleTestCase):
    """测试 llm_service.denoise()。"""

    @patch("apps.intelligence.services.llm_service.load_prompt")
    @patch("apps.intelligence.services.llm_service.get_openai_client")
    def test_denoise_success(self, mock_get_client, mock_load_prompt):
        """denoise 正常调用 LLM，返回降噪后 MD。"""
        mock_load_prompt.side_effect = lambda name, **kw: f"[prompt:{name}]" if name == "denoise_system" else f"[prompt:{name}]{kw.get('bs_clean_md','')}"
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="降噪后MD"))]
        mock_client.chat.completions.create.return_value = mock_response
        mock_get_client.return_value = mock_client

        from apps.intelligence.services.llm_service import denoise

        result = denoise("这是一段有噪音的MD内容用于测试降噪")
        self.assertEqual(result, "降噪后MD")
        mock_client.chat.completions.create.assert_called_once()

    @patch("apps.intelligence.services.llm_service.get_openai_client")
    def test_denoise_empty_input_returns_empty(self, mock_get_client):
        """空输入不调用 LLM，直接返回空字符串。"""
        from apps.intelligence.services.llm_service import denoise

        result = denoise("")
        self.assertEqual(result, "")
        mock_get_client.assert_not_called()

    @patch("apps.intelligence.services.llm_service.get_openai_client")
    def test_denoise_short_input_returns_original(self, mock_get_client):
        """极短输入（<10字符）不调用 LLM，返回原文。"""
        from apps.intelligence.services.llm_service import denoise

        result = denoise("极短")
        self.assertEqual(result, "极短")
        mock_get_client.assert_not_called()

    @patch("apps.intelligence.services.llm_service.load_prompt")
    @patch("apps.intelligence.services.llm_service.time.sleep")
    @patch("apps.intelligence.services.llm_service.get_openai_client")
    def test_denoise_retry_exhausted_raises_llm_error(self, mock_get_client, mock_sleep, mock_load_prompt):
        """LLM 3 次失败 → raise LLMError。"""
        mock_load_prompt.side_effect = lambda name, **kw: f"[prompt:{name}]"
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception("API Error")
        mock_get_client.return_value = mock_client

        from apps.intelligence.services.llm_service import denoise

        with self.assertRaises(LLMError):
            denoise("这是一段足够长的MD内容用于测试")

        self.assertEqual(mock_client.chat.completions.create.call_count, 3)


@override_settings(LLM_API_KEY="test-key", LLM_BASE_URL="https://test.example.com/v1")
class JudgeDiffServiceTest(SimpleTestCase):
    """测试 llm_service.judge_diff()。"""

    @patch("apps.intelligence.services.llm_service.load_prompt")
    @patch("apps.intelligence.services.llm_service.get_instructor_client")
    def test_judge_diff_meaningful_change(self, mock_get_client, mock_load_prompt):
        """LLM 判断有意义的变 → 返回 {has_meaningful_change: True}。"""
        mock_load_prompt.side_effect = lambda name, **kw: f"[prompt:{name}]"
        from apps.intelligence.services.llm_client import DiffJudgeResult
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = DiffJudgeResult(
            has_meaningful_change=True, reason="功能更新"
        )
        mock_get_client.return_value = mock_client

        from apps.intelligence.services.llm_service import judge_diff

        result = judge_diff("有变化的diff片段", "我方产品文档")
        self.assertTrue(result["has_meaningful_change"])
        self.assertEqual(result["reason"], "功能更新")

    @patch("apps.intelligence.services.llm_service.load_prompt")
    @patch("apps.intelligence.services.llm_service.get_instructor_client")
    def test_judge_diff_no_meaningful_change(self, mock_get_client, mock_load_prompt):
        """LLM 判断无意义的变 → 返回 {has_meaningful_change: False}。"""
        mock_load_prompt.side_effect = lambda name, **kw: f"[prompt:{name}]"
        from apps.intelligence.services.llm_client import DiffJudgeResult
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = DiffJudgeResult(
            has_meaningful_change=False, reason="仅排版调整"
        )
        mock_get_client.return_value = mock_client

        from apps.intelligence.services.llm_service import judge_diff

        result = judge_diff("排版变化的diff", "我方产品文档")
        self.assertFalse(result["has_meaningful_change"])
        self.assertEqual(result["reason"], "仅排版调整")

    @patch("apps.intelligence.services.llm_service.get_instructor_client")
    def test_judge_diff_empty_diff_returns_false(self, mock_get_client):
        """空 diff → 直接返回无意义，不调用 LLM。"""
        from apps.intelligence.services.llm_service import judge_diff

        result = judge_diff("", "我方产品文档")
        self.assertFalse(result["has_meaningful_change"])
        self.assertIn("无变化", result["reason"])
        mock_get_client.assert_not_called()

    @patch("apps.intelligence.services.llm_service.load_prompt")
    @patch("apps.intelligence.services.llm_service.time.sleep")
    @patch("apps.intelligence.services.llm_service.get_instructor_client")
    def test_judge_diff_retry_exhausted_raises_llm_error(self, mock_get_client, mock_sleep, mock_load_prompt):
        """LLM 3 次失败 → raise LLMError。"""
        mock_load_prompt.side_effect = lambda name, **kw: f"[prompt:{name}]"
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception("API Error")
        mock_get_client.return_value = mock_client

        from apps.intelligence.services.llm_service import judge_diff

        with self.assertRaises(LLMError):
            judge_diff("有变化的diff片段", "我方产品文档")

        self.assertEqual(mock_client.chat.completions.create.call_count, 3)


@override_settings(LLM_API_KEY="test-key", LLM_BASE_URL="https://test.example.com/v1")
class GenerateIntelServiceTest(SimpleTestCase):
    """测试 llm_service.generate_intel()。"""

    @patch("apps.intelligence.services.llm_service.get_instructor_client")
    def test_generate_intel_success(self, mock_get_client):
        """generate_intel 正常调用，返回 IntelResult 实例。"""
        from apps.intelligence.services.llm_service import generate_intel
        from apps.intelligence.services.llm_client import IntelResult

        expected = IntelResult(
            competitor_overview="竞品A是AI设计工具",
            change_summary="竞品新增AI绘图功能",
            strategic_intent="拓展AI创作赛道",
            action_suggestion="评估我方是否跟进AI绘图",
            evidence_diff="+ 新增AI绘图模块",
        )
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = expected
        mock_get_client.return_value = mock_client

        result = generate_intel("diff片段", "产品文档", [])
        self.assertIsInstance(result, IntelResult)
        self.assertEqual(result.change_summary, "竞品新增AI绘图功能")
        self.assertEqual(result.strategic_intent, "拓展AI创作赛道")
        self.assertEqual(result.action_suggestion, "评估我方是否跟进AI绘图")
        self.assertEqual(result.evidence_diff, "+ 新增AI绘图模块")

    @patch("apps.intelligence.services.llm_service.time.sleep")
    @patch("apps.intelligence.services.llm_service.get_instructor_client")
    def test_generate_intel_retry_exhausted(self, mock_get_client, mock_sleep):
        """LLM 3 次失败 → raise LLMError。"""
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception("API Error")
        mock_get_client.return_value = mock_client

        from apps.intelligence.services.llm_service import generate_intel

        with self.assertRaises(LLMError):
            generate_intel("diff片段", "产品文档", [])

        self.assertEqual(mock_client.chat.completions.create.call_count, 3)


class FormatFewShotsTest(SimpleTestCase):
    """测试 _format_few_shots() 格式化。"""

    def test_empty_list_returns_default_text(self):
        """空列表 → '暂无反面案例'。"""
        from apps.intelligence.services.llm_service import _format_few_shots

        result = _format_few_shots([])
        self.assertEqual(result, "暂无反面案例")


@override_settings(LLM_API_KEY="test-key", LLM_BASE_URL="https://test.example.com/v1")
class GetNegativeFewShotsDBTest(SimpleTestCase):
    """测试 get_negative_few_shots() DB 查询。"""

    databases = "__all__"

    def test_query_returns_recent_5(self):
        """有 7 条记录 → 返回最近 5 条。"""
        from apps.intelligence.services.llm_service import get_negative_few_shots
        from apps.intelligence.models import MonitorProject, IntelligenceFeed
        from django.utils import timezone
        from datetime import timedelta

        project = MonitorProject.objects.create(
            project_name="Test",
            competitor_urls=[],
            cron="0 9 * * *",
        )

        for i in range(7):
            IntelligenceFeed.objects.create(
                project=project,
                job_status=IntelligenceFeed.JobStatus.CHANGED,
                change_summary=f"摘要{i}",
                user_feedback=-1,
                user_comment=f"评语{i}",
                published_at=timezone.now() - timedelta(hours=7 - i),
            )

        result = get_negative_few_shots(project.id)
        self.assertEqual(len(result), 5)
        summaries = [r.change_summary for r in result]
        self.assertIn("摘要6", summaries)
        self.assertIn("摘要2", summaries)
        self.assertNotIn("摘要0", summaries)
        self.assertNotIn("摘要1", summaries)

    def test_query_no_records_returns_empty(self):
        """无记录 → 返回空列表。"""
        from apps.intelligence.services.llm_service import get_negative_few_shots
        from apps.intelligence.models import MonitorProject

        project = MonitorProject.objects.create(
            project_name="Test2",
            competitor_urls=[],
            cron="0 9 * * *",
        )

        result = get_negative_few_shots(project.id)
        self.assertEqual(result, [])

