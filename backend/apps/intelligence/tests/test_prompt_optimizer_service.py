"""测试 prompt_optimizer_service 优化服务。"""
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock

from django.test import TestCase

from apps.intelligence.models import IntelligenceFeed, MonitorProject, PromptVersion, DataSnapshot
from apps.intelligence.services.llm_client import OptimizedPrompts
from apps.intelligence.services.prompt_loader import load_prompt, save_prompt, PROMPTS_DIR


OPTIMIZED_SYSTEM = """你是一位竞争情报分析师。

## 我方产品锚定文档
{self_product_doc}

## 优化后的分析要求
1. 必须引用具体变化内容
2. 行动建议必须包含优先级
3. 证据必须来自 diff 原文
"""

OPTIMIZED_USER = """请分析以下竞品变化，产出竞争情报。

## 竞品变化 diff
{diff_text}

## 历史反面案例
{negative_few_shots}

## 输出要求
请输出 4 个字段。
"""


class PromptOptimizerServiceTest(TestCase):
    """prompt_optimizer_service 测试。"""

    def setUp(self):
        self.project = MonitorProject.objects.create(
            project_name="Test Project",
            competitor_urls=[{"url": "https://example.com", "title": "Example"}],
            cron="*/5 * * * *",
            is_active=True,
            self_product_doc="我方产品文档",
        )
        self.feed = IntelligenceFeed.objects.create(
            project=self.project,
            job_status=IntelligenceFeed.JobStatus.CHANGED,
            change_summary="变化摘要",
            strategic_intent="战略意图",
            action_suggestion="行动建议",
            evidence_diff="证据diff",
            diff_text="diff内容",
            user_feedback=-1,
            user_comment="分析太笼统",
        )
        # 备份原始 prompt 文件
        self._backup_prompt("intel_system")
        self._backup_prompt("intel_user")

    def tearDown(self):
        # 恢复原始 prompt 文件
        self._restore_prompt("intel_system")
        self._restore_prompt("intel_user")
        patch.stopall()

    def _backup_prompt(self, name):
        src = PROMPTS_DIR / f"{name}.md"
        bak = PROMPTS_DIR / f"{name}.md.bak"
        if src.exists():
            bak.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

    def _restore_prompt(self, name):
        src = PROMPTS_DIR / f"{name}.md"
        bak = PROMPTS_DIR / f"{name}.md.bak"
        if bak.exists():
            src.write_text(bak.read_text(encoding="utf-8"), encoding="utf-8")
            bak.unlink()

    @patch("apps.intelligence.services.prompt_optimizer_service.get_instructor_client")
    def test_optimize_prompts_creates_version_records(self, mock_client_fn):
        """优化后创建 2 条 PromptVersion 记录，version 自增。"""
        mock_client = MagicMock()
        mock_client_fn.return_value = mock_client
        mock_client.chat.completions.create.return_value = OptimizedPrompts(
            intel_system=OPTIMIZED_SYSTEM,
            intel_user=OPTIMIZED_USER,
        )

        from apps.intelligence.services.prompt_optimizer_service import optimize_prompts
        result = optimize_prompts(self.feed.id)

        # 2 条版本记录
        versions = PromptVersion.objects.filter(feed=self.feed)
        self.assertEqual(versions.count(), 2)
        self.assertTrue(versions.filter(prompt_name="intel_system").exists())
        self.assertTrue(versions.filter(prompt_name="intel_user").exists())

        # version 自增
        sys_ver = versions.get(prompt_name="intel_system").version
        user_ver = versions.get(prompt_name="intel_user").version
        self.assertEqual(sys_ver, 1)
        self.assertEqual(user_ver, 1)

        # 返回值
        self.assertEqual(result["intel_system_version"], 1)
        self.assertEqual(result["intel_user_version"], 1)

    @patch("apps.intelligence.services.prompt_optimizer_service.get_instructor_client")
    def test_optimize_prompts_overwrites_files(self, mock_client_fn):
        """优化后 prompts/ 文件被覆盖为新内容。"""
        mock_client = MagicMock()
        mock_client_fn.return_value = mock_client
        mock_client.chat.completions.create.return_value = OptimizedPrompts(
            intel_system=OPTIMIZED_SYSTEM,
            intel_user=OPTIMIZED_USER,
        )

        from apps.intelligence.services.prompt_optimizer_service import optimize_prompts
        optimize_prompts(self.feed.id)

        # 验证文件被覆盖
        sys_content = load_prompt("intel_system")
        user_content = load_prompt("intel_user")
        self.assertIn("优化后的分析要求", sys_content)
        self.assertIn("必须包含优先级", sys_content)

    @patch("apps.intelligence.services.prompt_optimizer_service.get_instructor_client")
    def test_optimize_prompts_preserves_placeholders(self, mock_client_fn):
        """优化后的 prompt 保留占位符。"""
        mock_client = MagicMock()
        mock_client_fn.return_value = mock_client
        mock_client.chat.completions.create.return_value = OptimizedPrompts(
            intel_system=OPTIMIZED_SYSTEM,
            intel_user=OPTIMIZED_USER,
        )

        from apps.intelligence.services.prompt_optimizer_service import optimize_prompts
        optimize_prompts(self.feed.id)

        sys_content = load_prompt("intel_system")
        user_content = load_prompt("intel_user")
        self.assertIn("{self_product_doc}", sys_content)
        self.assertIn("{diff_text}", user_content)
        self.assertIn("{negative_few_shots}", user_content)

    @patch("apps.intelligence.services.prompt_optimizer_service.get_instructor_client")
    def test_optimize_prompts_reads_feed_context(self, mock_client_fn):
        """LLM 调用参数包含 diff_text / clean_md / ai_report / user_comment。"""
        mock_client = MagicMock()
        mock_client_fn.return_value = mock_client
        mock_client.chat.completions.create.return_value = OptimizedPrompts(
            intel_system=OPTIMIZED_SYSTEM,
            intel_user=OPTIMIZED_USER,
        )

        from apps.intelligence.services.prompt_optimizer_service import optimize_prompts
        optimize_prompts(self.feed.id)

        # 验证 LLM 被调用
        mock_client.chat.completions.create.assert_called_once()

        # 验证 prompt 内容包含 feed 上下文
        call_args = mock_client.chat.completions.create.call_args
        prompt_content = call_args.kwargs["messages"][0]["content"]
        self.assertIn("diff内容", prompt_content)
        self.assertIn("分析太笼统", prompt_content)
        self.assertIn("变化摘要", prompt_content)

    @patch("apps.intelligence.services.prompt_optimizer_service.get_instructor_client")
    def test_optimize_prompts_llm_failure_raises(self, mock_client_fn):
        """LLM 调用失败抛出异常（由 @retry 处理后抛 LLMError）。"""
        mock_client = MagicMock()
        mock_client_fn.return_value = mock_client
        mock_client.chat.completions.create.side_effect = Exception("LLM timeout")

        from apps.intelligence.services.prompt_optimizer_service import optimize_prompts
        from apps.intelligence.services.retry import LLMError

        with self.assertRaises(LLMError):
            optimize_prompts(self.feed.id)

        # 没有创建版本记录
        self.assertEqual(PromptVersion.objects.filter(feed=self.feed).count(), 0)
