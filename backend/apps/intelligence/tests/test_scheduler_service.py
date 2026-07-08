from unittest.mock import patch
from datetime import timedelta
from django.test import TestCase
from django.utils import timezone

from apps.intelligence.models import MonitorProject, DataSnapshot, IntelligenceFeed
from apps.intelligence.services import scheduler_service


class SchedulerServiceTest(TestCase):
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

    @patch("apps.intelligence.services.scheduler_service.crawler_service.fetch_and_clean")
    def test_run_scan_active_project_due(self, mock_fetch):
        mock_fetch.return_value = ("<html></html>", "line1\nline2\nline3")
        project = self._create_project(next_run_at=timezone.now() - timedelta(minutes=1))
        scheduler_service.run_scan()
        self.assertEqual(DataSnapshot.objects.filter(project=project).count(), 2)
        project.refresh_from_db()
        self.assertGreater(project.next_run_at, timezone.now())

    @patch("apps.intelligence.services.scheduler_service.crawler_service.fetch_and_clean")
    def test_run_scan_active_project_not_due(self, mock_fetch):
        project = self._create_project(next_run_at=timezone.now() + timedelta(hours=1))
        scheduler_service.run_scan()
        mock_fetch.assert_not_called()
        self.assertEqual(DataSnapshot.objects.filter(project=project).count(), 0)

    @patch("apps.intelligence.services.scheduler_service.crawler_service.fetch_and_clean")
    def test_run_scan_inactive_project_skipped(self, mock_fetch):
        project = self._create_project(
            is_active=False,
            next_run_at=timezone.now() - timedelta(minutes=1),
        )
        scheduler_service.run_scan()
        mock_fetch.assert_not_called()
        self.assertEqual(DataSnapshot.objects.filter(project=project).count(), 0)

    @patch("apps.intelligence.services.scheduler_service.crawler_service.fetch_and_clean")
    def test_run_scan_next_run_at_none_triggers(self, mock_fetch):
        mock_fetch.return_value = ("<html></html>", "line1\nline2\nline3")
        project = self._create_project(next_run_at=None)
        # update 不能设 None，直接用 filter update
        MonitorProject.objects.filter(pk=project.pk).update(next_run_at=None)
        project.refresh_from_db()
        scheduler_service.run_scan()
        self.assertEqual(DataSnapshot.objects.filter(project=project).count(), 2)
        project.refresh_from_db()
        self.assertGreater(project.next_run_at, timezone.now())

    @patch("apps.intelligence.services.scheduler_service.crawler_service.fetch_and_clean")
    def test_run_scan_fetch_failure_writes_empty_snapshot(self, mock_fetch):
        mock_fetch.return_value = ("", "")
        project = self._create_project(next_run_at=timezone.now() - timedelta(minutes=1))
        scheduler_service.run_scan()
        snapshots = DataSnapshot.objects.filter(project=project)
        self.assertEqual(snapshots.count(), 2)
        for snap in snapshots:
            self.assertEqual(snap.raw_markdown, "")
            self.assertEqual(snap.clean_markdown, "")

    @patch("apps.intelligence.services.scheduler_service.crawler_service.fetch_and_clean")
    def test_run_scan_does_not_write_intelligence_feed(self, mock_fetch):
        mock_fetch.return_value = ("<html></html>", "line1\nline2\nline3")
        project = self._create_project(next_run_at=timezone.now() - timedelta(minutes=1))
        scheduler_service.run_scan()
        self.assertEqual(IntelligenceFeed.objects.filter(project=project).count(), 0)

    @patch("apps.intelligence.services.scheduler_service.crawler_service.fetch_and_clean")
    def test_run_scan_partial_failure_continues(self, mock_fetch):
        mock_fetch.side_effect = [
            ("", ""),  # 第 1 个 URL 失败
            ("<html></html>", "line1\nline2\nline3"),  # 第 2 个 URL 成功
            ("<html></html>", "line1\nline2\nline3"),  # 第 3 个 URL 成功
        ]
        project = self._create_project(
            competitor_urls=[
                {"url": "https://a.com", "title": "A"},
                {"url": "https://b.com", "title": "B"},
                {"url": "https://c.com", "title": "C"},
            ],
            next_run_at=timezone.now() - timedelta(minutes=1),
        )
        scheduler_service.run_scan()
        self.assertEqual(DataSnapshot.objects.filter(project=project).count(), 3)
        empty_snap = DataSnapshot.objects.filter(project=project, raw_markdown="")
        self.assertEqual(empty_snap.count(), 1)

    @patch("apps.intelligence.services.scheduler_service.crawler_service.fetch_and_clean")
    def test_run_scan_empty_url_skipped(self, mock_fetch):
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

    @patch("apps.intelligence.services.scheduler_service.crawler_service.fetch_and_clean")
    def test_run_scan_updates_next_run_at(self, mock_fetch):
        mock_fetch.return_value = ("<html></html>", "line1\nline2\nline3")
        project = self._create_project(next_run_at=timezone.now() - timedelta(minutes=1))
        old_next = project.next_run_at
        scheduler_service.run_scan()
        project.refresh_from_db()
        self.assertGreater(project.next_run_at, old_next)
        self.assertGreater(project.next_run_at, timezone.now())
