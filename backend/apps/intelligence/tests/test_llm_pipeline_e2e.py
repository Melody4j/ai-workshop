"""端到端集成测试：LLM 全链路 E2E（S-001/S-002/S-003 + AC-013/AC-017）。

验证 run_scan() 串接 LLM 链路的完整流程，覆盖 prd.md 中的 3 个场景 + 2 个验收标准。
"""
import shutil
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.intelligence.models import MonitorProject, DataSnapshot, IntelligenceFeed
from apps.intelligence.services import scheduler_service, file_storage
from apps.intelligence.services.llm_client import IntelResult


@override_settings(SNAPSHOT_STORAGE_DIR="/tmp/ai-workshop-test-e2e")
class LLMPipelineE2ETest(TestCase):
    """LLM 全链路端到端测试。"""

    def setUp(self):
        self.storage_dir = Path("/tmp/ai-workshop-test-e2e")
        if self.storage_dir.exists():
            shutil.rmtree(self.storage_dir)

        # Mock LLM 服务（默认全链路成功）
        self.mock_denoise = patch("apps.intelligence.services.scheduler_service.llm_service.denoise").start()
        self.mock_denoise.return_value = "llm_clean_md_content"

        self.mock_judge = patch("apps.intelligence.services.scheduler_service.llm_service.judge_diff").start()
        self.mock_judge.return_value = {"has_meaningful_change": True, "reason": "有变化"}

        self.mock_generate = patch("apps.intelligence.services.scheduler_service.llm_service.generate_intel").start()
        self.mock_generate.return_value = IntelResult(
            competitor_overview="竞品A是AI设计工具",
            change_summary="竞品新增AI绘图功能",
            strategic_intent="拓展AI创作赛道",
            action_suggestion="评估我方是否跟进AI绘图",
            evidence_diff="+ 新增AI绘图模块",
        )

        self.mock_few_shots = patch("apps.intelligence.services.scheduler_service.llm_service.get_negative_few_shots").start()
        self.mock_few_shots.return_value = []

        self.mock_render_html = patch("apps.intelligence.services.scheduler_service.report_service.render_html").start()
        self.mock_render_html.return_value = "/tmp/e2e_report.html"

        self.mock_render_md = patch("apps.intelligence.services.scheduler_service.report_service.render_md").start()
        self.mock_render_md.return_value = "/tmp/e2e_report.md"

        # Mock 飞书推送
        self.mock_push = patch("apps.intelligence.services.scheduler_service.feishu_service.push_intelligence").start()
        self.mock_push.return_value = "pushed"

    def tearDown(self):
        patch.stopall()
        if self.storage_dir.exists():
            shutil.rmtree(self.storage_dir)

    def _create_project(self, **kwargs):
        defaults = {
            "project_name": "E2E Test Project",
            "competitor_urls": [{"url": "https://example.com", "title": "Example"}],
            "cron": "*/5 * * * *",
            "is_active": True,
            "self_product_doc": "我方产品是AI设计工具",
        }
        defaults.update(kwargs)
        project = MonitorProject.objects.create(**defaults)
        if "next_run_at" in kwargs:
            MonitorProject.objects.filter(pk=project.pk).update(next_run_at=kwargs["next_run_at"])
            project.refresh_from_db()
        return project

    @patch("apps.intelligence.services.scheduler_service.crawler_service.fetch_and_clean")
    def test_S001_full_chain_changed(self, mock_fetch):
        """S-001：有变化全链路 → CHANGED + clean_md_path 指向 LLM + 4 字段非空 + 报告路径。

        AC-001: clean_md_path 指向 LLM 降噪后 MD
        AC-002/003/004: 有变化全链路（CHANGED + 4 字段非空 + 报告落盘 + 3 次独立调用）
        """
        mock_fetch.return_value = ("<html><body>content</body></html>", "line1\nline2\nline3")
        project = self._create_project(next_run_at=timezone.now() - timedelta(minutes=1))

        scheduler_service.run_scan()

        # AC-001: clean_md_path 指向 LLM 版本
        snapshot = DataSnapshot.objects.get(project=project)
        self.assertIn("llm_", Path(snapshot.clean_md_path).name)

        # AC-002: CHANGED + 4 字段非空
        feed = IntelligenceFeed.objects.get(project=project)
        self.assertEqual(feed.job_status, IntelligenceFeed.JobStatus.CHANGED)
        self.assertTrue(feed.change_summary)
        self.assertTrue(feed.strategic_intent)
        self.assertTrue(feed.action_suggestion)
        self.assertTrue(feed.evidence_diff)

        # AC-003: 报告路径已设置
        self.assertEqual(feed.html_report_path, "/tmp/e2e_report.html")
        self.assertEqual(feed.md_table_path, "/tmp/e2e_report.md")

        # AC-004: 3 次独立 LLM 调用（denoise + generate_intel；首次爬取跳过 judge_diff）
        self.mock_denoise.assert_called_once()
        self.mock_generate.assert_called_once()

        # AC-001 (Spec 006): diff_text 非空（首次爬取 = llm_clean_md 全量）
        self.assertTrue(feed.diff_text)

    @patch("apps.intelligence.services.scheduler_service.crawler_service.fetch_and_clean")
    def test_S002_text_diff_empty_circuit_breaker(self, mock_fetch):
        """S-002：无变化熔断 → NO_CHANGE + 零 LLM diff 调用 + 4 字段空。

        AC-005/006/007: 无变化熔断（NO_CHANGE + 零 LLM diff 调用 + 4 字段空）
        """
        mock_fetch.return_value = ("<html><body>content</body></html>", "line1\nline2\nline3")
        project = self._create_project(next_run_at=timezone.now() - timedelta(minutes=1))

        # 创建上一条快照（内容相同 → diff 为空）
        now = timezone.now()
        prev_path = file_storage.save_llm_clean_md(project.id, "https://example.com", "llm_clean_md_content", now)
        DataSnapshot.objects.create(
            project=project,
            source_url="https://example.com",
            source_title="Example",
            raw_html_path="/tmp/prev.html",
            clean_md_path=prev_path,
            fetch_time=now - timedelta(hours=1),
        )

        scheduler_service.run_scan()

        # AC-005: NO_CHANGE
        feed = IntelligenceFeed.objects.get(project=project)
        self.assertEqual(feed.job_status, IntelligenceFeed.JobStatus.NO_CHANGE)

        # AC-006: 零 LLM diff 调用（judge_diff 未调用）
        self.mock_judge.assert_not_called()

        # AC-007: 4 字段空
        self.assertFalse(feed.change_summary)
        self.assertFalse(feed.strategic_intent)
        self.assertFalse(feed.action_suggestion)
        self.assertFalse(feed.evidence_diff)

        # generate_intel 也未调用
        self.mock_generate.assert_not_called()

        # AC-001 (Spec 006): NO_CHANGE 的 diff_text 为空字符串
        self.assertEqual(feed.diff_text, "")

    @patch("apps.intelligence.services.scheduler_service.crawler_service.fetch_and_clean")
    def test_S002b_judge_no_meaningful_change(self, mock_fetch):
        """S-002b：LLM 判断无意义 → NO_CHANGE。

        diff 非空但 LLM 判断为无意义变化（如排版调整），熔断。
        """
        mock_fetch.return_value = ("<html><body>content</body></html>", "line1\nline2\nline3")
        self.mock_denoise.return_value = "new_different_content"
        self.mock_judge.return_value = {"has_meaningful_change": False, "reason": "仅排版变化，无实质内容更新"}

        project = self._create_project(next_run_at=timezone.now() - timedelta(minutes=1))

        # 创建上一条快照（不同内容 → diff 非空）
        now = timezone.now()
        prev_path = file_storage.save_llm_clean_md(project.id, "https://example.com", "old_content", now)
        DataSnapshot.objects.create(
            project=project,
            source_url="https://example.com",
            source_title="Example",
            raw_html_path="/tmp/prev.html",
            clean_md_path=prev_path,
            fetch_time=now - timedelta(hours=1),
        )

        scheduler_service.run_scan()

        # NO_CHANGE
        feed = IntelligenceFeed.objects.get(project=project)
        self.assertEqual(feed.job_status, IntelligenceFeed.JobStatus.NO_CHANGE)
        self.assertIn("排版变化", feed.change_summary)

        # judge_diff 被调用，generate_intel 未调用
        self.mock_judge.assert_called_once()
        self.mock_generate.assert_not_called()

    @patch("apps.intelligence.services.scheduler_service.crawler_service.fetch_and_clean")
    def test_S003_first_crawl_skips_diff(self, mock_fetch):
        """S-003：首次爬取 → 跳过 diff + 直接情报生成 + CHANGED。

        AC-008/009: 首次爬取跳过 diff 直接情报生成
        """
        mock_fetch.return_value = ("<html><body>content</body></html>", "line1\nline2\nline3")
        project = self._create_project(next_run_at=timezone.now() - timedelta(minutes=1))

        scheduler_service.run_scan()

        # 无上一条快照 → 首次爬取
        self.assertEqual(DataSnapshot.objects.filter(project=project).count(), 1)

        # judge_diff 未调用（跳过 diff）
        self.mock_judge.assert_not_called()

        # generate_intel 被调用（直接情报生成）
        self.mock_generate.assert_called_once()

        # CHANGED
        feed = IntelligenceFeed.objects.get(project=project)
        self.assertEqual(feed.job_status, IntelligenceFeed.JobStatus.CHANGED)

    @patch("apps.intelligence.services.scheduler_service.crawler_service.fetch_and_clean")
    def test_AC013_single_url_failure_isolation(self, mock_fetch):
        """AC-013：单 URL 异常不中断其他 URL。

        第 1 个 URL LLM 降噪失败 → ERROR_CRAWL
        第 2 个 URL 正常 → CHANGED
        """
        mock_fetch.return_value = ("<html><body>content</body></html>", "line1\nline2\nline3")

        # denoise 第 1 次失败，第 2 次成功
        self.mock_denoise.side_effect = [Exception("LLM timeout"), "llm_clean_md_content"]

        project = self._create_project(
            competitor_urls=[
                {"url": "https://a.com", "title": "A"},
                {"url": "https://b.com", "title": "B"},
            ],
            next_run_at=timezone.now() - timedelta(minutes=1),
        )

        scheduler_service.run_scan()

        # 第 1 个 URL → ERROR_CRAWL
        error_feeds = IntelligenceFeed.objects.filter(
            project=project, job_status=IntelligenceFeed.JobStatus.ERROR_CRAWL
        )
        self.assertEqual(error_feeds.count(), 1)
        self.assertIn("LLM 降噪失败", error_feeds.first().change_summary)

        # 第 2 个 URL → CHANGED
        changed_feeds = IntelligenceFeed.objects.filter(
            project=project, job_status=IntelligenceFeed.JobStatus.CHANGED
        )
        self.assertEqual(changed_feeds.count(), 1)

        # 只有 1 个快照（第 2 个 URL）
        self.assertEqual(DataSnapshot.objects.filter(project=project).count(), 1)

    @patch("apps.intelligence.services.scheduler_service.crawler_service.fetch_and_clean")
    def test_AC017_old_format_compatibility(self, mock_fetch):
        """AC-017：旧格式快照兼容。

        上一条 clean_md_path 无 llm_ 前缀（pre-LLM 格式）→ 跳过 diff → CHANGED。
        """
        mock_fetch.return_value = ("<html><body>content</body></html>", "line1\nline2\nline3")

        project = self._create_project(next_run_at=timezone.now() - timedelta(minutes=1))

        # 创建旧格式快照（BS 版本，无 llm_ 前缀）
        now = timezone.now()
        prev_bs_path = file_storage.save_clean_md(project.id, "https://example.com", "old_bs_md", now)
        DataSnapshot.objects.create(
            project=project,
            source_url="https://example.com",
            source_title="Example",
            raw_html_path="/tmp/prev.html",
            clean_md_path=prev_bs_path,  # 无 llm_ 前缀
            fetch_time=now - timedelta(hours=1),
        )

        scheduler_service.run_scan()

        # judge_diff 未调用（旧格式跳过 diff）
        self.mock_judge.assert_not_called()

        # generate_intel 被调用（跳过 diff 后直接情报生成）
        self.mock_generate.assert_called_once()

        # CHANGED
        feed = IntelligenceFeed.objects.get(
            project=project, job_status=IntelligenceFeed.JobStatus.CHANGED
        )
        self.assertTrue(feed.change_summary)

    @patch("apps.intelligence.services.scheduler_service.crawler_service.fetch_and_clean")
    def test_three_independent_llm_calls(self, mock_fetch):
        """AC-002/003/004：3 次独立 LLM 调用验证。

        有历史快照 + diff 非空 + 有意义变化 → denoise + judge_diff + generate_intel 各调用 1 次。
        """
        mock_fetch.return_value = ("<html><body>content</body></html>", "line1\nline2\nline3")
        self.mock_denoise.return_value = "new_different_content"

        project = self._create_project(next_run_at=timezone.now() - timedelta(minutes=1))

        # 创建上一条快照
        now = timezone.now()
        prev_path = file_storage.save_llm_clean_md(project.id, "https://example.com", "old_content", now)
        DataSnapshot.objects.create(
            project=project,
            source_url="https://example.com",
            source_title="Example",
            raw_html_path="/tmp/prev.html",
            clean_md_path=prev_path,
            fetch_time=now - timedelta(hours=1),
        )

        scheduler_service.run_scan()

        # 3 次独立调用各 1 次
        self.mock_denoise.assert_called_once()
        self.mock_judge.assert_called_once()
        self.mock_generate.assert_called_once()

        # CHANGED + 4 字段非空
        feed = IntelligenceFeed.objects.get(project=project)
        self.assertEqual(feed.job_status, IntelligenceFeed.JobStatus.CHANGED)
        self.assertTrue(feed.change_summary)
        self.assertTrue(feed.strategic_intent)
        self.assertTrue(feed.action_suggestion)
        self.assertTrue(feed.evidence_diff)
