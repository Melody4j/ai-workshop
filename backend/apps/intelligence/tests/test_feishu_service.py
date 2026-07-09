from unittest.mock import MagicMock, patch

from django.conf import settings
from django.test import TestCase

from apps.intelligence.models import IntelligenceFeed, MonitorProject
from apps.intelligence.services import feishu_service


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


class BuildCardTest(TestCase):
    """卡片模板构建测试"""

    def setUp(self):
        self.project = MonitorProject.objects.create(
            project_name="AI IDE 监控",
            feishu_webhook="https://open.feishu.cn/open-apis/bot/v2/hook/xxx",
        )
        self.feed = IntelligenceFeed.objects.create(
            project=self.project,
            job_status=IntelligenceFeed.JobStatus.CHANGED,
            change_summary="竞品 A 新增了 AI 代码生成功能",
            strategic_intent="意图抢占 AI 辅助编程市场",
        )

    def test_card_header_contains_project_name(self):
        """卡片标题含项目名"""
        card = feishu_service._build_card(self.feed)
        title_content = card["card"]["header"]["title"]["content"]
        self.assertIn("AI IDE 监控", title_content)

    def test_card_contains_change_summary(self):
        """卡片正文含变化摘要"""
        card = feishu_service._build_card(self.feed)
        elements = card["card"]["elements"]
        md_contents = [
            e.get("text", {}).get("content", "")
            for e in elements
            if e.get("tag") == "div"
        ]
        self.assertTrue(any("竞品 A 新增了 AI 代码生成功能" in c for c in md_contents))

    def test_card_contains_strategic_intent(self):
        """卡片正文含战略意图"""
        card = feishu_service._build_card(self.feed)
        elements = card["card"]["elements"]
        md_contents = [
            e.get("text", {}).get("content", "")
            for e in elements
            if e.get("tag") == "div"
        ]
        self.assertTrue(any("意图抢占 AI 辅助编程市场" in c for c in md_contents))

    def test_card_has_two_action_buttons(self):
        """卡片含 2 个 action button（在线预览 + 下载 MD）"""
        card = feishu_service._build_card(self.feed)
        elements = card["card"]["elements"]
        actions = [e for e in elements if e.get("tag") == "action"]
        self.assertEqual(len(actions), 1)
        buttons = actions[0]["actions"]
        self.assertEqual(len(buttons), 2)

    def test_card_button_urls_contain_site_base_url(self):
        """卡片按钮 URL 使用 SITE_BASE_URL 绝对地址"""
        card = feishu_service._build_card(self.feed)
        elements = card["card"]["elements"]
        actions = [e for e in elements if e.get("tag") == "action"]
        buttons = actions[0]["actions"]
        for btn in buttons:
            self.assertTrue(btn["url"].startswith(settings.SITE_BASE_URL))
        # 在线预览链接
        preview_urls = [b["url"] for b in buttons if "view/html" in b["url"]]
        self.assertEqual(len(preview_urls), 1)
        self.assertIn(str(self.feed.id), preview_urls[0])
        # 下载链接
        download_urls = [b["url"] for b in buttons if "download_md" in b["url"]]
        self.assertEqual(len(download_urls), 1)
        self.assertIn(str(self.feed.id), download_urls[0])


class PushSuccessTest(TestCase):
    """推送成功测试"""

    def setUp(self):
        self.project = MonitorProject.objects.create(
            project_name="测试项目",
            feishu_webhook="https://open.feishu.cn/open-apis/bot/v2/hook/xxx",
        )
        self.feed = IntelligenceFeed.objects.create(
            project=self.project,
            job_status=IntelligenceFeed.JobStatus.CHANGED,
            change_summary="变化摘要",
            strategic_intent="战略意图",
        )

    @patch("apps.intelligence.services.feishu_service.httpx.post")
    @patch("apps.intelligence.services.feishu_service.time.sleep")
    def test_push_success_updates_pushed(self, mock_sleep, mock_post):
        """推送成功后 push_status 更新为 PUSHED"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"StatusCode": 0}
        mock_post.return_value = mock_response

        result = feishu_service.push_intelligence(self.feed.id)

        self.assertEqual(result, "pushed")
        self.feed.refresh_from_db()
        self.assertEqual(self.feed.push_status, IntelligenceFeed.PushStatus.PUSHED)
        mock_post.assert_called_once()
        mock_sleep.assert_not_called()


class PushRetryTest(TestCase):
    """推送失败重试测试"""

    def setUp(self):
        self.project = MonitorProject.objects.create(
            project_name="测试项目",
            feishu_webhook="https://open.feishu.cn/open-apis/bot/v2/hook/xxx",
        )
        self.feed = IntelligenceFeed.objects.create(
            project=self.project,
            job_status=IntelligenceFeed.JobStatus.CHANGED,
            change_summary="变化摘要",
            strategic_intent="战略意图",
        )

    @patch("apps.intelligence.services.feishu_service.httpx.post")
    @patch("apps.intelligence.services.feishu_service.time.sleep")
    def test_push_retry_3_attempts_then_failed(self, mock_sleep, mock_post):
        """推送失败重试 2 次（总共 3 次尝试），最终 push_status=PUSH_FAILED"""
        mock_post.side_effect = Exception("Connection error")

        result = feishu_service.push_intelligence(self.feed.id)

        self.assertEqual(result, "push_failed")
        self.feed.refresh_from_db()
        self.assertEqual(self.feed.push_status, IntelligenceFeed.PushStatus.PUSH_FAILED)
        self.assertEqual(mock_post.call_count, 3)  # 首次 + 2 次重试
        self.assertEqual(mock_sleep.call_count, 2)  # 2 次重试间隔


class WebhookEmptyTest(TestCase):
    """webhook 为空跳过测试"""

    def setUp(self):
        self.project = MonitorProject.objects.create(
            project_name="测试项目",
            feishu_webhook="",
        )
        self.feed = IntelligenceFeed.objects.create(
            project=self.project,
            job_status=IntelligenceFeed.JobStatus.CHANGED,
            change_summary="变化摘要",
            strategic_intent="战略意图",
        )

    @patch("apps.intelligence.services.feishu_service.httpx.post")
    def test_skip_push_when_webhook_empty(self, mock_post):
        """webhook 为空时跳过推送，push_status 保持 NOT_PUSHED"""
        result = feishu_service.push_intelligence(self.feed.id)

        self.assertEqual(result, "skipped_no_webhook")
        self.feed.refresh_from_db()
        self.assertEqual(self.feed.push_status, IntelligenceFeed.PushStatus.NOT_PUSHED)
        mock_post.assert_not_called()


class NonChangedSkipTest(TestCase):
    """非 CHANGED 状态跳过测试"""

    def setUp(self):
        self.project = MonitorProject.objects.create(
            project_name="测试项目",
            feishu_webhook="https://open.feishu.cn/open-apis/bot/v2/hook/xxx",
        )
        self.feed = IntelligenceFeed.objects.create(
            project=self.project,
            job_status=IntelligenceFeed.JobStatus.NO_CHANGE,
            change_summary="",
            strategic_intent="",
        )

    @patch("apps.intelligence.services.feishu_service.httpx.post")
    def test_skip_push_when_not_changed(self, mock_post):
        """job_status 非 CHANGED 时跳过推送"""
        result = feishu_service.push_intelligence(self.feed.id)

        self.assertEqual(result, "skipped")
        self.feed.refresh_from_db()
        self.assertEqual(self.feed.push_status, IntelligenceFeed.PushStatus.NOT_PUSHED)
        mock_post.assert_not_called()
