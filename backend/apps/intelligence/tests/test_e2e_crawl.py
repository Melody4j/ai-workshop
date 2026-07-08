from datetime import timedelta

from django.test import TestCase, tag
from django.utils import timezone

from apps.intelligence.models import MonitorProject, DataSnapshot, IntelligenceFeed
from apps.intelligence.services import scheduler_service


@tag("e2e", "network")
class E2ECrawlTest(TestCase):
    def test_e2e_real_sites(self):
        project = MonitorProject.objects.create(
            project_name="E2E Test",
            competitor_urls=[
                {"url": "https://www.ihuiwa.com/", "title": "ihuiwa"},
                {"url": "https://www.x-design.com/", "title": "x-design"},
                {"url": "https://www.piccopilot.com/", "title": "piccopilot"},
                {"url": "https://www.weshop.ai/", "title": "weshop"},
                {"url": "https://bandy.ai/", "title": "bandy"},
                {"url": "https://thenewblack.ai/", "title": "thenewblack"},
                {"url": "https://lovable.dev/", "title": "lovable"},
            ],
            cron="*/5 * * * *",
            is_active=True,
        )
        # 绕过 save() 覆盖，手动设 next_run_at 为过去时间触发执行
        MonitorProject.objects.filter(pk=project.pk).update(
            next_run_at=timezone.now() - timedelta(minutes=1)
        )
        project.refresh_from_db()
        scheduler_service.run_scan()

        # 7 条 DataSnapshot
        self.assertEqual(DataSnapshot.objects.filter(project=project).count(), 7)

        # >= 5 条 clean_markdown 非空
        success_count = DataSnapshot.objects.filter(
            project=project, clean_markdown__gt=""
        ).count()
        self.assertGreaterEqual(success_count, 5)

        # 不写 IntelligenceFeed
        self.assertEqual(IntelligenceFeed.objects.filter(project=project).count(), 0)

        # next_run_at 已更新为未来
        project.refresh_from_db()
        self.assertGreater(project.next_run_at, timezone.now())
