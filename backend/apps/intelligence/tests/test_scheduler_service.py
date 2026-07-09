"""测试 scheduler_service：全局扫描 + LLM 全链路集成。"""
import shutil
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.intelligence.models import MonitorProject, DataSnapshot, IntelligenceFeed
from apps.intelligence.services import scheduler_service, file_storage
from apps.intelligence.services.llm_client import IntelResult


@override_settings(SNAPSHOT_STORAGE_DIR="/tmp/ai-workshop-test-scheduler")
class SchedulerServiceTest(TestCase):
    """测试 scheduler_service 全链路。"""

    def setUp(self):
        """创建测试目录 + mock LLM 链路。"""
        self.storage_dir = Path("/tmp/ai-workshop-test-scheduler")
        if self.storage_dir.exists():
            shutil.rmtree(self.storage_dir)

        # Mock LLM 服务（默认返回"全链路成功"）
        self.mock_denoise = patch(
            "apps.intelligence.services.scheduler_service.llm_service.denoise"
        ).start()
        self.mock_denoise.return_value = "llm_clean_md_content"

        self.mock_judge = patch(
            "apps.intelligence.services.scheduler_service.llm_service.judge_diff"
        ).start()
        self.mock_judge.return_value = {"has_meaningful_change": True, "reason": "有变化"}

        self.mock_generate = patch(
            "apps.intelligence.services.scheduler_service.llm_service.generate_intel"
        ).start()
        self.mock_generate.return_value = IntelResult(
            competitor_overview="竞品A是AI设计工具",
            change_summary="竞品新增AI绘图功能",
            strategic_intent="拓展AI创作赛道",
            action_suggestion="评估我方是否跟进",
            evidence_diff="+ 新增AI绘图模块",
        )

        self.mock_few_shots = patch(
            "apps.intelligence.services.scheduler_service.llm_service.get_negative_few_shots"
        ).start()
        self.mock_few_shots.return_value = []

        self.mock_render_html = patch(
            "apps.intelligence.services.scheduler_service.report_service.render_html"
        ).start()
        self.mock_render_html.return_value = "/tmp/test_report.html"

        self.mock_render_md = patch(
            "apps.intelligence.services.scheduler_service.report_service.render_md"
        ).start()
        self.mock_render_md.return_value = "/tmp/test_report.md"

        # Mock 飞书推送
        self.mock_push = patch(
            "apps.intelligence.services.scheduler_service.feishu_service.push_intelligence"
        ).start()
        self.mock_push.return_value = "pushed"

    def tearDown(self):
        patch.stopall()
        if self.storage_dir.exists():
            shutil.rmtree(self.storage_dir)

    def _create_project(self, **kwargs):
        """创建项目后用 update 绕过 save() 覆盖 next_run_at。"""
        defaults = {
            "project_name": "Test Project",
            "competitor_urls": [
                {"url": "https://example.com", "title": "Example"},
                {"url": "https://test.com", "title": "Test"},
            ],
            "cron": "*/5 * * * *",
            "is_active": True,
        }
        defaults.update(kwargs)
        project = MonitorProject.objects.create(**defaults)
        if "next_run_at" in kwargs:
            MonitorProject.objects.filter(pk=project.pk).update(
                next_run_at=kwargs["next_run_at"]
            )
            project.refresh_from_db()
        return project

    def _create_prev_snapshot(
        self,
        project,
        *,
        raw_md="line1\nline2\nline3",
        llm_md="llm_clean_md_content",
        url="https://example.com",
        title="Example",
        fetch_time=None,
        legacy=False,
        include_raw_md=True,
    ):
        """创建上一条快照，支持稳定 diff 所需字段和旧格式兼容场景。"""
        fetch_time = fetch_time or timezone.now()
        raw_md_path = (
            file_storage.save_clean_md(project.id, url, raw_md, fetch_time)
            if include_raw_md
            else ""
        )
        if legacy:
            clean_md_path = file_storage.save_clean_md(project.id, url, llm_md, fetch_time)
        else:
            clean_md_path = file_storage.save_llm_clean_md(project.id, url, llm_md, fetch_time)

        return DataSnapshot.objects.create(
            project=project,
            source_url=url,
            source_title=title,
            raw_html_path="/tmp/prev.html",
            clean_md_path=clean_md_path,
            raw_md_path=raw_md_path,
            fetch_time=fetch_time,
        )

    # === 基础调度测试 ===

    @patch("apps.intelligence.services.scheduler_service.crawler_service.fetch_and_clean")
    def test_run_scan_active_project_due(self, mock_fetch):
        """到期项目 → 采集 + LLM 链路 → 快照 + CHANGED feed。"""
        mock_fetch.return_value = ("<html></html>", "line1\nline2\nline3")
        project = self._create_project(next_run_at=timezone.now() - timedelta(minutes=1))
        scheduler_service.run_scan()
        self.assertEqual(DataSnapshot.objects.filter(project=project).count(), 2)
        self.assertEqual(
            IntelligenceFeed.objects.filter(
                project=project, job_status=IntelligenceFeed.JobStatus.CHANGED
            ).count(),
            2,
        )
        project.refresh_from_db()
        self.assertGreater(project.next_run_at, timezone.now())

    @patch("apps.intelligence.services.scheduler_service.crawler_service.fetch_and_clean")
    def test_run_scan_active_project_not_due(self, mock_fetch):
        """未到期项目 → 跳过。"""
        project = self._create_project(next_run_at=timezone.now() + timedelta(hours=1))
        scheduler_service.run_scan()
        mock_fetch.assert_not_called()
        self.assertEqual(DataSnapshot.objects.filter(project=project).count(), 0)

    @patch("apps.intelligence.services.scheduler_service.crawler_service.fetch_and_clean")
    def test_run_scan_inactive_project_skipped(self, mock_fetch):
        """未激活项目 → 跳过。"""
        project = self._create_project(
            is_active=False,
            next_run_at=timezone.now() - timedelta(minutes=1),
        )
        scheduler_service.run_scan()
        mock_fetch.assert_not_called()
        self.assertEqual(DataSnapshot.objects.filter(project=project).count(), 0)

    @patch("apps.intelligence.services.scheduler_service.crawler_service.fetch_and_clean")
    def test_run_scan_next_run_at_none_triggers(self, mock_fetch):
        """next_run_at=None → 立即触发。"""
        mock_fetch.return_value = ("<html></html>", "line1\nline2\nline3")
        project = self._create_project(next_run_at=None)
        MonitorProject.objects.filter(pk=project.pk).update(next_run_at=None)
        project.refresh_from_db()
        scheduler_service.run_scan()
        self.assertEqual(DataSnapshot.objects.filter(project=project).count(), 2)
        project.refresh_from_db()
        self.assertGreater(project.next_run_at, timezone.now())

    @patch("apps.intelligence.services.scheduler_service.crawler_service.fetch_and_clean")
    def test_run_scan_updates_next_run_at(self, mock_fetch):
        """执行后 next_run_at 更新。"""
        mock_fetch.return_value = ("<html></html>", "line1\nline2\nline3")
        project = self._create_project(next_run_at=timezone.now() - timedelta(minutes=1))
        old_next = project.next_run_at
        scheduler_service.run_scan()
        project.refresh_from_db()
        self.assertGreater(project.next_run_at, old_next)
        self.assertGreater(project.next_run_at, timezone.now())

    @patch("apps.intelligence.services.scheduler_service.crawler_service.fetch_and_clean")
    def test_run_scan_empty_url_skipped(self, mock_fetch):
        """空 URL 跳过。"""
        mock_fetch.return_value = ("<html></html>", "line1\nline2\nline3")
        project = self._create_project(
            competitor_urls=[
                {"url": "", "title": "Empty"},
                {"url": "https://example.com", "title": "Example"},
            ],
            next_run_at=timezone.now() - timedelta(minutes=1),
        )
        scheduler_service.run_scan()
        self.assertEqual(DataSnapshot.objects.filter(project=project).count(), 1)

    # === 采集失败测试 ===

    @patch("apps.intelligence.services.scheduler_service.crawler_service.fetch_and_clean")
    def test_run_scan_fetch_failure_writes_error_crawl(self, mock_fetch):
        """采集失败 → ERROR_CRAWL feed，无快照。"""
        mock_fetch.return_value = ("", "")
        project = self._create_project(next_run_at=timezone.now() - timedelta(minutes=1))
        scheduler_service.run_scan()
        # 不创建快照
        self.assertEqual(DataSnapshot.objects.filter(project=project).count(), 0)
        # 写 ERROR_CRAWL feed
        error_feeds = IntelligenceFeed.objects.filter(
            project=project, job_status=IntelligenceFeed.JobStatus.ERROR_CRAWL
        )
        self.assertEqual(error_feeds.count(), 2)
        for feed in error_feeds:
            self.assertIn("采集失败", feed.change_summary)

    @patch("apps.intelligence.services.scheduler_service.crawler_service.fetch_and_clean")
    def test_run_scan_partial_failure_continues(self, mock_fetch):
        """第 1 个 URL 采集失败、第 2 个成功 → 第 1 个 ERROR_CRAWL、第 2 个 CHANGED。"""
        mock_fetch.side_effect = [
            ("", ""),  # 第 1 个失败
            ("<html></html>", "line1\nline2\nline3"),  # 第 2 个成功
        ]
        project = self._create_project(
            competitor_urls=[
                {"url": "https://a.com", "title": "A"},
                {"url": "https://b.com", "title": "B"},
            ],
            next_run_at=timezone.now() - timedelta(minutes=1),
        )
        scheduler_service.run_scan()
        # 1 个快照（成功的 URL）
        self.assertEqual(DataSnapshot.objects.filter(project=project).count(), 1)
        # 1 个 ERROR_CRAWL + 1 个 CHANGED
        self.assertEqual(
            IntelligenceFeed.objects.filter(
                project=project, job_status=IntelligenceFeed.JobStatus.ERROR_CRAWL
            ).count(),
            1,
        )
        self.assertEqual(
            IntelligenceFeed.objects.filter(
                project=project, job_status=IntelligenceFeed.JobStatus.CHANGED
            ).count(),
            1,
        )

    # === LLM 链路测试 ===

    @patch("apps.intelligence.services.scheduler_service.crawler_service.fetch_and_clean")
    def test_run_scan_writes_intelligence_feed(self, mock_fetch):
        """首次爬取（无历史快照）→ 跳过 diff → 情报生成 → CHANGED。"""
        mock_fetch.return_value = ("<html></html>", "line1\nline2\nline3")
        project = self._create_project(next_run_at=timezone.now() - timedelta(minutes=1))
        scheduler_service.run_scan()
        feeds = IntelligenceFeed.objects.filter(project=project)
        self.assertEqual(feeds.count(), 2)
        for feed in feeds:
            self.assertEqual(feed.job_status, IntelligenceFeed.JobStatus.CHANGED)
            self.assertTrue(feed.change_summary)
            self.assertTrue(feed.strategic_intent)
            self.assertTrue(feed.action_suggestion)
            self.assertTrue(feed.evidence_diff)

    @patch("apps.intelligence.services.scheduler_service.crawler_service.fetch_and_clean")
    def test_run_scan_clean_md_path_points_to_llm_version(self, mock_fetch):
        """DataSnapshot.clean_md_path 指向 LLM 降噪后 MD（含 llm_ 前缀）。"""
        mock_fetch.return_value = ("<html></html>", "line1\nline2\nline3")
        project = self._create_project(next_run_at=timezone.now() - timedelta(minutes=1))
        scheduler_service.run_scan()
        for snap in DataSnapshot.objects.filter(project=project):
            self.assertIn("llm_", Path(snap.clean_md_path).name)

    @patch("apps.intelligence.services.scheduler_service.crawler_service.fetch_and_clean")
    def test_run_scan_first_crawl_skips_diff(self, mock_fetch):
        """首次爬取 → 不调用 judge_diff（跳过 diff 判断）。"""
        mock_fetch.return_value = ("<html></html>", "line1\nline2\nline3")
        project = self._create_project(next_run_at=timezone.now() - timedelta(minutes=1))
        scheduler_service.run_scan()
        # judge_diff 不应被调用（首次爬取跳过 diff）
        self.mock_judge.assert_not_called()
        # 但 generate_intel 应被调用
        self.mock_generate.assert_called()

    @patch("apps.intelligence.services.scheduler_service.crawler_service.fetch_and_clean")
    def test_run_scan_denoise_failure_writes_error_crawl(self, mock_fetch):
        """LLM 降噪失败 → ERROR_CRAWL。"""
        mock_fetch.return_value = ("<html></html>", "line1\nline2\nline3")
        self.mock_denoise.side_effect = Exception("LLM 降噪超时")
        project = self._create_project(next_run_at=timezone.now() - timedelta(minutes=1))
        scheduler_service.run_scan()
        # 无快照（降噪失败在快照创建之前）
        self.assertEqual(DataSnapshot.objects.filter(project=project).count(), 0)
        # ERROR_CRAWL feed
        error_feeds = IntelligenceFeed.objects.filter(
            project=project, job_status=IntelligenceFeed.JobStatus.ERROR_CRAWL
        )
        self.assertEqual(error_feeds.count(), 2)
        for feed in error_feeds:
            self.assertIn("LLM 降噪失败", feed.change_summary)

    @patch("apps.intelligence.services.scheduler_service.crawler_service.fetch_and_clean")
    def test_run_scan_generate_intel_failure_writes_error_crawl(self, mock_fetch):
        """LLM 情报生成失败 → ERROR_CRAWL。"""
        mock_fetch.return_value = ("<html></html>", "line1\nline2\nline3")
        self.mock_generate.side_effect = Exception("LLM 情报生成失败")
        project = self._create_project(next_run_at=timezone.now() - timedelta(minutes=1))
        scheduler_service.run_scan()
        # 有快照（情报生成在快照之后）
        self.assertEqual(DataSnapshot.objects.filter(project=project).count(), 2)
        # ERROR_CRAWL feed
        error_feeds = IntelligenceFeed.objects.filter(
            project=project, job_status=IntelligenceFeed.JobStatus.ERROR_CRAWL
        )
        self.assertEqual(error_feeds.count(), 2)

    @patch("apps.intelligence.services.scheduler_service.crawler_service.fetch_and_clean")
    def test_run_scan_report_paths_updated(self, mock_fetch):
        """CHANGED feed 的 html_report_path / md_table_path 被更新。"""
        mock_fetch.return_value = ("<html></html>", "line1\nline2\nline3")
        project = self._create_project(next_run_at=timezone.now() - timedelta(minutes=1))
        scheduler_service.run_scan()
        for feed in IntelligenceFeed.objects.filter(project=project):
            self.assertEqual(feed.html_report_path, "/tmp/test_report.html")
            self.assertEqual(feed.md_table_path, "/tmp/test_report.md")

    @patch("apps.intelligence.services.scheduler_service.crawler_service.fetch_and_clean")
    def test_run_scan_raw_diff_empty_no_change(self, mock_fetch):
        """有历史快照 + raw_diff_text 为空 → NO_CHANGE（零后续 LLM 调用）。"""
        mock_fetch.return_value = ("<html></html>", "line1\nline2\nline3")
        self.mock_denoise.return_value = "new_llm_md_content_different"
        project = self._create_project(
            competitor_urls=[{"url": "https://example.com", "title": "Example"}],
            next_run_at=timezone.now() - timedelta(minutes=1),
        )

        # 创建上一条快照（原始 Markdown 相同，但 LLM 输出不同）
        now = timezone.now()
        self._create_prev_snapshot(
            project,
            raw_md="line1\nline2\nline3",
            llm_md="old_llm_md_content",
            fetch_time=now - timedelta(hours=1),
        )

        scheduler_service.run_scan()

        # judge_diff / generate_intel 都不应被调用（raw diff 为空直接熔断）
        self.mock_judge.assert_not_called()
        self.mock_generate.assert_not_called()

        feed = IntelligenceFeed.objects.get(
            project=project,
            job_status=IntelligenceFeed.JobStatus.NO_CHANGE,
        )
        self.assertEqual(feed.diff_text, "")
        self.assertEqual(feed.raw_diff_text, "")
        self.assertIn("原始页面内容无变化", feed.change_summary)

    @patch("apps.intelligence.services.scheduler_service.crawler_service.fetch_and_clean")
    def test_run_scan_canonical_diff_empty_no_change(self, mock_fetch):
        """raw diff 非空但规则归一化后为空 → NO_CHANGE，并保留 raw_diff_text。"""
        mock_fetch.return_value = ("<html></html>", "## 功能介绍\n\n🎨\n\n$29/月")
        project = self._create_project(
            competitor_urls=[{"url": "https://example.com", "title": "Example"}],
            next_run_at=timezone.now() - timedelta(minutes=1),
        )

        now = timezone.now()
        self._create_prev_snapshot(
            project,
            raw_md="## 功能介绍\n\n$29/月",
            llm_md="old_llm_md_content",
            fetch_time=now - timedelta(hours=1),
        )

        scheduler_service.run_scan()

        self.mock_judge.assert_not_called()
        self.mock_generate.assert_not_called()

        feed = IntelligenceFeed.objects.get(
            project=project,
            job_status=IntelligenceFeed.JobStatus.NO_CHANGE,
        )
        self.assertEqual(feed.diff_text, "")
        self.assertTrue(feed.raw_diff_text)
        self.assertIn("规则归一化后内容无变化", feed.change_summary)

    @patch("apps.intelligence.services.scheduler_service.crawler_service.fetch_and_clean")
    def test_run_scan_judge_no_meaningful_change(self, mock_fetch):
        """有历史快照 + canonical diff 非空 + LLM 判断无意义 → NO_CHANGE。"""
        mock_fetch.return_value = ("<html></html>", "new raw content")
        self.mock_judge.return_value = {"has_meaningful_change": False, "reason": "只是排版变化"}

        project = self._create_project(
            competitor_urls=[{"url": "https://example.com", "title": "Example"}],
            next_run_at=timezone.now() - timedelta(minutes=1),
        )

        # 创建上一条快照（原始 Markdown 不同 → canonical diff 非空）
        now = timezone.now()
        self._create_prev_snapshot(
            project,
            raw_md="old raw content",
            llm_md="old_llm_md_content",
            fetch_time=now - timedelta(hours=1),
        )

        scheduler_service.run_scan()

        # judge_diff 被调用
        self.mock_judge.assert_called_once()
        # generate_intel 不应被调用
        self.mock_generate.assert_not_called()
        # NO_CHANGE feed
        no_change_feeds = IntelligenceFeed.objects.filter(
            project=project, job_status=IntelligenceFeed.JobStatus.NO_CHANGE
        )
        self.assertEqual(no_change_feeds.count(), 1)
        self.assertIn("排版变化", no_change_feeds.first().change_summary)
        self.assertTrue(no_change_feeds.first().raw_diff_text)

    @patch("apps.intelligence.services.scheduler_service.crawler_service.fetch_and_clean")
    def test_run_scan_judge_has_meaningful_change(self, mock_fetch):
        """有历史快照 + canonical diff 非空 + LLM 判断有意义 → CHANGED。"""
        mock_fetch.return_value = ("<html></html>", "### Starter\n\n$39/月")
        self.mock_denoise.return_value = "new_llm_md_content_different"

        project = self._create_project(
            competitor_urls=[{"url": "https://example.com", "title": "Example"}],
            next_run_at=timezone.now() - timedelta(minutes=1),
        )

        # 创建上一条快照（原始 Markdown 不同，LLM 文本只是辅料）
        now = timezone.now()
        self._create_prev_snapshot(
            project,
            raw_md="### Starter\n\n$29/月",
            llm_md="old_llm_md_content",
            fetch_time=now - timedelta(hours=1),
        )

        scheduler_service.run_scan()

        # judge_diff 被调用
        self.mock_judge.assert_called_once()
        # generate_intel 被调用
        self.mock_generate.assert_called_once()
        # CHANGED feed
        changed_feeds = IntelligenceFeed.objects.filter(
            project=project, job_status=IntelligenceFeed.JobStatus.CHANGED
        )
        self.assertEqual(changed_feeds.count(), 1)
        feed = changed_feeds.first()
        self.assertIn("+$39/月", feed.diff_text)
        self.assertIn("-$29/月", feed.diff_text)
        self.assertNotIn("new_llm_md_content_different", feed.diff_text)

    @patch("apps.intelligence.services.scheduler_service.crawler_service.fetch_and_clean")
    def test_run_scan_old_format_compatibility(self, mock_fetch):
        """旧格式快照（缺少 raw_md_path / clean_md_path 无 llm_）→ 跳过 diff → CHANGED。"""
        mock_fetch.return_value = ("<html></html>", "line1\nline2\nline3")

        project = self._create_project(
            competitor_urls=[{"url": "https://example.com", "title": "Example"}],
            next_run_at=timezone.now() - timedelta(minutes=1),
        )

        # 创建旧格式快照（使用 save_clean_md 而非 save_llm_clean_md → 无 llm_ 前缀）
        now = timezone.now()
        self._create_prev_snapshot(
            project,
            raw_md="old_bs_clean_md",
            llm_md="old_bs_clean_md",
            fetch_time=now - timedelta(hours=1),
            legacy=True,
            include_raw_md=False,
        )

        scheduler_service.run_scan()

        # judge_diff 不应被调用（旧格式跳过 diff）
        self.mock_judge.assert_not_called()
        # generate_intel 被调用（跳过 diff 后直接情报生成）
        self.mock_generate.assert_called_once()
        # CHANGED feed
        changed_feeds = IntelligenceFeed.objects.filter(
            project=project, job_status=IntelligenceFeed.JobStatus.CHANGED
        )
        self.assertEqual(changed_feeds.count(), 1)

    @patch("apps.intelligence.services.scheduler_service.crawler_service.fetch_and_clean")
    def test_run_scan_judge_diff_failure_writes_error_crawl(self, mock_fetch):
        """LLM diff 判断失败 → ERROR_CRAWL。"""
        mock_fetch.return_value = ("<html></html>", "new raw content")
        self.mock_judge.side_effect = Exception("LLM diff 判断超时")

        project = self._create_project(
            competitor_urls=[{"url": "https://example.com", "title": "Example"}],
            next_run_at=timezone.now() - timedelta(minutes=1),
        )

        # 创建上一条快照
        now = timezone.now()
        self._create_prev_snapshot(
            project,
            raw_md="old raw content",
            llm_md="old_llm_md_content",
            fetch_time=now - timedelta(hours=1),
        )

        scheduler_service.run_scan()

        # 2 条快照（上一条 + 本次新建，diff 判断在快照之后）
        self.assertEqual(DataSnapshot.objects.filter(project=project).count(), 2)
        # ERROR_CRAWL feed
        error_feeds = IntelligenceFeed.objects.filter(
            project=project, job_status=IntelligenceFeed.JobStatus.ERROR_CRAWL
        )
        self.assertEqual(error_feeds.count(), 1)
        self.assertIn("LLM diff 判断失败", error_feeds.first().change_summary)

    # === 飞书推送集成测试 ===

    @patch("apps.intelligence.services.scheduler_service.crawler_service.fetch_and_clean")
    def test_run_scan_changed_feed_triggers_feishu_push(self, mock_fetch):
        """CHANGED feed → 飞书推送被调用。"""
        mock_fetch.return_value = ("<html></html>", "line1\nline2\nline3")
        project = self._create_project(next_run_at=timezone.now() - timedelta(minutes=1))
        scheduler_service.run_scan()
        # 2 个 CHANGED feed → 飞书推送调用 2 次
        self.assertEqual(self.mock_push.call_count, 2)

    @patch("apps.intelligence.services.scheduler_service.crawler_service.fetch_and_clean")
    def test_run_scan_no_change_feed_does_not_push(self, mock_fetch):
        """NO_CHANGE feed → 飞书推送不被调用。"""
        mock_fetch.return_value = ("<html></html>", "line1\nline2\nline3")
        self.mock_denoise.return_value = "new_llm_md_content_different"
        project = self._create_project(
            competitor_urls=[{"url": "https://example.com", "title": "Example"}],
            next_run_at=timezone.now() - timedelta(minutes=1),
        )

        # 创建上一条快照（原始 Markdown 相同 → raw diff 为空 → NO_CHANGE）
        now = timezone.now()
        self._create_prev_snapshot(
            project,
            raw_md="line1\nline2\nline3",
            llm_md="old_llm_md_content",
            fetch_time=now - timedelta(hours=1),
        )

        scheduler_service.run_scan()
        # NO_CHANGE → 飞书推送不被调用
        self.mock_push.assert_not_called()

    @patch("apps.intelligence.services.scheduler_service.crawler_service.fetch_and_clean")
    def test_run_scan_error_crawl_feed_does_not_push(self, mock_fetch):
        """ERROR_CRAWL feed → 飞书推送不被调用。"""
        mock_fetch.return_value = ("", "")
        project = self._create_project(next_run_at=timezone.now() - timedelta(minutes=1))
        scheduler_service.run_scan()
        # 采集失败 → ERROR_CRAWL → 飞书推送不被调用
        self.mock_push.assert_not_called()

    @patch("apps.intelligence.services.scheduler_service.crawler_service.fetch_and_clean")
    def test_run_scan_feishu_push_failure_does_not_break_flow(self, mock_fetch):
        """飞书推送异常不中断主流程。"""
        mock_fetch.return_value = ("<html></html>", "line1\nline2\nline3")
        self.mock_push.side_effect = Exception("飞书 API 超时")
        project = self._create_project(next_run_at=timezone.now() - timedelta(minutes=1))
        scheduler_service.run_scan()
        # 推送异常不影响 feed 创建
        feeds = IntelligenceFeed.objects.filter(project=project)
        self.assertEqual(feeds.count(), 2)
        for feed in feeds:
            self.assertEqual(feed.job_status, IntelligenceFeed.JobStatus.CHANGED)

    @patch("apps.intelligence.services.scheduler_service.crawler_service.fetch_and_clean")
    def test_run_scan_passes_crawl_hint_to_fetch_and_clean(self, mock_fetch):
        """competitor_urls 含 crawl_hint 时传递给 fetch_and_clean。"""
        mock_fetch.return_value = ("<html></html>", "line1\nline2\nline3")
        project = self._create_project(
            next_run_at=timezone.now() - timedelta(minutes=1),
            competitor_urls=[
                {"url": "https://example.com", "title": "Example", "crawl_hint": "爬取定价页"},
                {"url": "https://test.com", "title": "Test"},  # 无 crawl_hint
            ],
        )
        scheduler_service.run_scan()

        # fetch_and_clean 被调用 2 次
        self.assertEqual(mock_fetch.call_count, 2)
        # 第一次调用带 crawl_hint
        first_call = mock_fetch.call_args_list[0]
        self.assertEqual(first_call[0][0], "https://example.com")
        self.assertEqual(first_call[0][1], "爬取定价页")
        # 第二次调用 crawl_hint 为空字符串
        second_call = mock_fetch.call_args_list[1]
        self.assertEqual(second_call[0][0], "https://test.com")
        self.assertEqual(second_call[0][1], "")
