from django.test import TestCase

from apps.intelligence.models import IntelligenceFeed, MonitorProject


class PushStatusFieldTest(TestCase):
    """push_status 字段基础测试"""

    def test_push_status_default_is_not_pushed(self):
        """新建 IntelligenceFeed 的 push_status 默认为 NOT_PUSHED"""
        project = MonitorProject.objects.create(project_name="测试项目")
        feed = IntelligenceFeed.objects.create(
            project=project,
            job_status=IntelligenceFeed.JobStatus.CHANGED,
        )
        self.assertEqual(feed.push_status, IntelligenceFeed.PushStatus.NOT_PUSHED)

    def test_push_status_choices(self):
        """PushStatus 枚举有 NOT_PUSHED / PUSHED / PUSH_FAILED 三态"""
        choices = [c[0] for c in IntelligenceFeed.PushStatus.choices]
        self.assertIn("NOT_PUSHED", choices)
        self.assertIn("PUSHED", choices)
        self.assertIn("PUSH_FAILED", choices)
