"""测试 report_service：Jinja2 HTML/MD 报告渲染。"""
import os
from pathlib import Path

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.intelligence.models import MonitorProject, IntelligenceFeed
from apps.intelligence.services.report_service import render_html, render_md


@override_settings(SNAPSHOT_STORAGE_DIR="/tmp/ai-workshop-test-reports")
class ReportServiceTest(TestCase):
    """测试 report_service 渲染与落盘。"""

    def setUp(self):
        """创建测试数据和清理目录。"""
        self.storage_dir = Path("/tmp/ai-workshop-test-reports")
        if self.storage_dir.exists():
            import shutil
            shutil.rmtree(self.storage_dir)

        self.project = MonitorProject.objects.create(
            project_name="测试项目",
            competitor_urls=[{"url": "https://example.com", "title": "Example"}],
            cron="0 9 * * *",
        )

        self.feed = IntelligenceFeed.objects.create(
            project=self.project,
            job_status=IntelligenceFeed.JobStatus.CHANGED,
            change_summary="竞品新增AI绘图功能",
            strategic_intent="拓展AI创作赛道",
            action_suggestion="评估我方是否跟进AI绘图",
            evidence_diff="+ 新增AI绘图模块",
        )

    def test_render_html_changed_feed(self):
        """CHANGED feed → 渲染 HTML 报告，返回路径，文件存在。"""
        html_path = render_html(self.feed)
        self.assertTrue(html_path)
        self.assertTrue(Path(html_path).exists())
        content = Path(html_path).read_text(encoding="utf-8")
        self.assertIn("竞品新增AI绘图功能", content)
        self.assertIn("拓展AI创作赛道", content)
        self.assertIn("评估我方是否跟进AI绘图", content)
        self.assertIn("+ 新增AI绘图模块", content)

    def test_render_md_changed_feed(self):
        """CHANGED feed → 渲染 MD 表格，返回路径，文件存在。"""
        md_path = render_md(self.feed)
        self.assertTrue(md_path)
        self.assertTrue(Path(md_path).exists())
        content = Path(md_path).read_text(encoding="utf-8")
        self.assertIn("竞品新增AI绘图功能", content)
        self.assertIn("变化摘要", content)
        self.assertIn("战略意图", content)
        self.assertIn("行动建议", content)
        self.assertIn("证据", content)

    def test_render_html_no_change_feed_returns_empty(self):
        """NO_CHANGE feed → 返回空字符串，不渲染。"""
        feed = IntelligenceFeed.objects.create(
            project=self.project,
            job_status=IntelligenceFeed.JobStatus.NO_CHANGE,
        )
        result = render_html(feed)
        self.assertEqual(result, "")

    def test_render_md_no_change_feed_returns_empty(self):
        """NO_CHANGE feed → 返回空字符串，不渲染。"""
        feed = IntelligenceFeed.objects.create(
            project=self.project,
            job_status=IntelligenceFeed.JobStatus.NO_CHANGE,
        )
        result = render_md(feed)
        self.assertEqual(result, "")

    def test_render_html_error_crawl_feed_returns_empty(self):
        """ERROR_CRAWL feed → 返回空字符串，不渲染。"""
        feed = IntelligenceFeed.objects.create(
            project=self.project,
            job_status=IntelligenceFeed.JobStatus.ERROR_CRAWL,
            change_summary="LLM 调用失败",
        )
        result = render_html(feed)
        self.assertEqual(result, "")
