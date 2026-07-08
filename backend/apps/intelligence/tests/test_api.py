import os
import tempfile
from unittest.mock import MagicMock, patch

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.intelligence.models import IntelligenceFeed, MonitorProject


class ProjectApiTests(APITestCase):
    def test_create_project_with_competitors(self) -> None:
        payload = {
            "project_name": "Prompt IDE Monitor",
            "competitor_urls": [
                {"title": "Lovable", "url": "https://lovable.dev"},
                {"title": "v0", "url": "https://v0.dev"},
            ],
            "self_product_doc": "We help teams observe AI product changes.",
            "self_product_doc_name": "self-product.md",
            "competitor_contexts": [
                {
                    "title": "Lovable",
                    "url": "https://lovable.dev",
                    "supplement_doc_name": "lovable-notes.md",
                    "supplement_doc_content": "Focus on fast landing pages and prompt-to-app flow.",
                },
                {
                    "title": "v0",
                    "url": "https://v0.dev",
                    "supplement_doc_name": "",
                    "supplement_doc_content": "",
                },
            ],
            "cron": "0 9 * * *",
            "feishu_webhook": "https://example.com/webhook",
            "is_active": True,
        }

        response = self.client.post(reverse("project-list"), payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(MonitorProject.objects.count(), 1)
        self.assertEqual(response.data["competitor_urls"][0]["title"], "Lovable")
        self.assertEqual(response.data["self_product_doc_name"], "self-product.md")
        self.assertEqual(
            response.data["competitor_contexts"][0]["supplement_doc_name"],
            "lovable-notes.md",
        )

    def test_create_project_with_crawl_hint(self) -> None:
        """competitor_urls 含 crawl_hint 字段时创建成功。"""
        payload = {
            "project_name": "Crawl Hint Test",
            "competitor_urls": [
                {
                    "title": "Lovable",
                    "url": "https://lovable.dev",
                    "crawl_hint": "爬取定价页和功能列表",
                },
            ],
            "self_product_doc": "",
            "self_product_doc_name": "",
            "competitor_contexts": [],
            "cron": "0 9 * * *",
            "feishu_webhook": "",
            "is_active": True,
        }

        response = self.client.post(reverse("project-list"), payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        project = MonitorProject.objects.get()
        self.assertEqual(
            project.competitor_urls[0]["crawl_hint"], "爬取定价页和功能列表"
        )

    def test_create_project_without_crawl_hint(self) -> None:
        """competitor_urls 不含 crawl_hint 字段时创建成功（兼容旧数据）。"""
        payload = {
            "project_name": "No Crawl Hint",
            "competitor_urls": [
                {"title": "v0", "url": "https://v0.dev"},
            ],
            "self_product_doc": "",
            "self_product_doc_name": "",
            "competitor_contexts": [],
            "cron": "0 9 * * *",
            "feishu_webhook": "",
            "is_active": True,
        }

        response = self.client.post(reverse("project-list"), payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(MonitorProject.objects.count(), 1)

    def test_delete_project_marks_it_inactive(self) -> None:
        project = MonitorProject.objects.create(
            project_name="Prompt IDE Monitor",
            competitor_urls=[{"title": "Lovable", "url": "https://lovable.dev"}],
            cron="0 9 * * *",
        )

        response = self.client.delete(reverse("project-detail", kwargs={"pk": project.pk}))

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        project.refresh_from_db()
        self.assertFalse(project.is_active)


class ReportApiTests(APITestCase):
    def setUp(self) -> None:
        self.project = MonitorProject.objects.create(
            project_name="AI IDE Monitor",
            competitor_urls=[{"title": "Lovable", "url": "https://lovable.dev"}],
            cron="0 9 * * *",
        )
        self.changed_feed = IntelligenceFeed.objects.create(
            project=self.project,
            job_status=IntelligenceFeed.JobStatus.CHANGED,
            change_summary="Homepage update",
            strategic_intent="Move up-market",
            action_suggestion="Review homepage messaging",
            evidence_diff="Added new section",
            html_report_path="/reports/homepage.html",
            md_table_path="/reports/homepage.md",
        )
        self.no_change_feed = IntelligenceFeed.objects.create(
            project=self.project,
            job_status=IntelligenceFeed.JobStatus.NO_CHANGE,
            change_summary="No material changes",
            html_report_path="",
            md_table_path="",
        )

    def test_report_list_filters_by_status(self) -> None:
        response = self.client.get(reverse("report-list"), {"status": "CHANGED"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["id"], self.changed_feed.id)

    def test_report_detail_returns_project_payload(self) -> None:
        response = self.client.get(reverse("report-detail", kwargs={"pk": self.changed_feed.pk}))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["project"]["project_name"], "AI IDE Monitor")

    def test_rating_crud_flow(self) -> None:
        create_response = self.client.post(
            reverse("report-rating", kwargs={"pk": self.changed_feed.pk}),
            {"user_feedback": -1, "user_comment": "Need stronger actionability."},
            format="json",
        )
        self.assertEqual(create_response.status_code, status.HTTP_200_OK)
        self.changed_feed.refresh_from_db()
        self.assertEqual(self.changed_feed.user_feedback, -1)

        update_response = self.client.patch(
            reverse("report-rating", kwargs={"pk": self.changed_feed.pk}),
            {"user_feedback": 1, "user_comment": "This one is useful."},
            format="json",
        )
        self.assertEqual(update_response.status_code, status.HTTP_200_OK)
        self.changed_feed.refresh_from_db()
        self.assertEqual(self.changed_feed.user_feedback, 1)
        self.assertEqual(self.changed_feed.user_comment, "This one is useful.")

        delete_response = self.client.delete(
            reverse("report-rating", kwargs={"pk": self.changed_feed.pk})
        )
        self.assertEqual(delete_response.status_code, status.HTTP_204_NO_CONTENT)
        self.changed_feed.refresh_from_db()
        self.assertIsNone(self.changed_feed.user_feedback)
        self.assertEqual(self.changed_feed.user_comment, "")


class FeedPushViewTest(APITestCase):
    """飞书推送触发 API 测试"""

    def setUp(self) -> None:
        self.project = MonitorProject.objects.create(
            project_name="测试项目",
            feishu_webhook="https://open.feishu.cn/open-apis/bot/v2/hook/xxx",
        )
        self.changed_feed = IntelligenceFeed.objects.create(
            project=self.project,
            job_status=IntelligenceFeed.JobStatus.CHANGED,
            change_summary="变化摘要",
            strategic_intent="战略意图",
        )
        self.no_change_feed = IntelligenceFeed.objects.create(
            project=self.project,
            job_status=IntelligenceFeed.JobStatus.NO_CHANGE,
        )

    @patch("apps.intelligence.services.feishu_service.httpx.post")
    @patch("apps.intelligence.services.feishu_service.time.sleep")
    def test_push_changed_feed_returns_pushed(self, mock_sleep, mock_post) -> None:
        """CHANGED feed 推送成功返回 200 + push_status=PUSHED"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"StatusCode": 0}
        mock_post.return_value = mock_response

        response = self.client.post(
            reverse("feed-push", kwargs={"pk": self.changed_feed.pk})
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["push_status"], "PUSHED")

    def test_push_non_changed_feed_returns_400(self) -> None:
        """非 CHANGED feed 推送返回 400"""
        response = self.client.post(
            reverse("feed-push", kwargs={"pk": self.no_change_feed.pk})
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class FeedDownloadMdViewTest(APITestCase):
    """MD 报告下载 API 测试"""

    def setUp(self) -> None:
        self.project = MonitorProject.objects.create(
            project_name="测试项目",
            feishu_webhook="https://open.feishu.cn/open-apis/bot/v2/hook/xxx",
        )
        # 创建临时 MD 文件
        self.md_fd, self.md_path = tempfile.mkstemp(suffix=".md")
        with os.fdopen(self.md_fd, "w") as f:
            f.write("# 竞品情报报告\n\n这是测试内容。")

        self.feed = IntelligenceFeed.objects.create(
            project=self.project,
            job_status=IntelligenceFeed.JobStatus.CHANGED,
            change_summary="变化摘要",
            strategic_intent="战略意图",
            md_table_path=self.md_path,
        )

    def tearDown(self) -> None:
        if os.path.exists(self.md_path):
            os.unlink(self.md_path)

    def test_download_md_returns_file(self) -> None:
        """GET /api/feeds/{id}/download_md 返回 MD 文件下载流"""
        response = self.client.get(
            reverse("feed-download-md", kwargs={"pk": self.feed.pk})
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("text/markdown", response["Content-Type"])
        self.assertIn("attachment", response["Content-Disposition"])

    def test_download_md_not_found(self) -> None:
        """md_table_path 为空时返回 404"""
        self.feed.md_table_path = ""
        self.feed.save(update_fields=["md_table_path"])

        response = self.client.get(
            reverse("feed-download-md", kwargs={"pk": self.feed.pk})
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class FeedHtmlPreviewViewTest(APITestCase):
    """HTML 报告在线预览 API 测试"""

    def setUp(self) -> None:
        self.project = MonitorProject.objects.create(
            project_name="测试项目",
            feishu_webhook="https://open.feishu.cn/open-apis/bot/v2/hook/xxx",
        )
        # 创建临时 HTML 报告文件
        self.html_fd, self.html_path = tempfile.mkstemp(suffix=".html")
        with os.fdopen(self.html_fd, "w") as f:
            f.write("<html><body><h1>竞品情报报告</h1></body></html>")

        self.feed = IntelligenceFeed.objects.create(
            project=self.project,
            job_status=IntelligenceFeed.JobStatus.CHANGED,
            change_summary="变化摘要",
            strategic_intent="战略意图",
            html_report_path=self.html_path,
        )

    def tearDown(self) -> None:
        if os.path.exists(self.html_path):
            os.unlink(self.html_path)

    def test_preview_html_returns_inline_html(self) -> None:
        """GET /api/feeds/{id}/preview_html 返回 HTML 内容（inline，非下载）"""
        response = self.client.get(
            reverse("feed-preview-html", kwargs={"pk": self.feed.pk})
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("text/html", response["Content-Type"])
        # inline 预览，不是 attachment 下载
        self.assertNotIn("attachment", response.get("Content-Disposition", ""))
        self.assertIn(b"<html>", response.content)

    def test_preview_html_via_root_url(self) -> None:
        """GET /view/html/{id} 根路由也能正常返回 HTML"""
        response = self.client.get(f"/view/html/{self.feed.pk}")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("text/html", response["Content-Type"])
        self.assertIn("竞品情报报告".encode("utf-8"), response.content)

    def test_preview_html_not_found(self) -> None:
        """html_report_path 为空时返回 404"""
        self.feed.html_report_path = ""
        self.feed.save(update_fields=["html_report_path"])

        response = self.client.get(
            reverse("feed-preview-html", kwargs={"pk": self.feed.pk})
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_preview_html_feed_not_found(self) -> None:
        """不存在的 feed_id 返回 404"""
        response = self.client.get("/view/html/99999")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class FeedOptimizePromptViewTest(APITestCase):
    """Prompt 优化 API 测试"""

    def setUp(self) -> None:
        self.project = MonitorProject.objects.create(
            project_name="测试项目",
            competitor_urls=[{"url": "https://example.com", "title": "Example"}],
            cron="0 9 * * *",
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

    def test_optimize_prompt_endpoint(self) -> None:
        """POST /api/feeds/{id}/optimize_prompt → 200 + 优化结果摘要"""
        with patch("apps.intelligence.services.prompt_optimizer_service.optimize_prompts") as mock_opt:
            mock_opt.return_value = {"intel_system_version": 1, "intel_user_version": 1}

            response = self.client.post(
                reverse("feed-optimize-prompt", kwargs={"pk": self.feed.pk})
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("intel_system_version", response.data)
        self.assertIn("intel_user_version", response.data)
        mock_opt.assert_called_once_with(self.feed.pk)

    def test_optimize_prompt_feed_not_found(self) -> None:
        """不存在的 feed_id → 404"""
        response = self.client.post(
            reverse("feed-optimize-prompt", kwargs={"pk": 99999})
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class ReportRatingOptimizeTriggerTest(APITestCase):
    """评分=-1 异步触发 Prompt 优化测试"""

    def setUp(self) -> None:
        self.project = MonitorProject.objects.create(
            project_name="测试项目",
            competitor_urls=[{"url": "https://example.com", "title": "Example"}],
            cron="0 9 * * *",
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
        )

    @patch("apps.intelligence.views._async_optimize_prompts")
    def test_rating_minus1_triggers_optimization(self, mock_async) -> None:
        """评分=-1 → 启动 threading 执行 optimize_prompts"""
        response = self.client.post(
            reverse("report-rating", kwargs={"pk": self.feed.pk}),
            {"user_feedback": -1, "user_comment": "分析太笼统"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.feed.refresh_from_db()
        self.assertEqual(self.feed.user_feedback, -1)
        # _async_optimize_prompts 被调用（threading target）
        mock_async.assert_called_once_with(self.feed.pk)

    @patch("apps.intelligence.views._async_optimize_prompts")
    def test_rating_plus1_does_not_trigger(self, mock_async) -> None:
        """评分=1 → 不触发优化"""
        response = self.client.post(
            reverse("report-rating", kwargs={"pk": self.feed.pk}),
            {"user_feedback": 1, "user_comment": "很有帮助"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.feed.refresh_from_db()
        self.assertEqual(self.feed.user_feedback, 1)
        # _async_optimize_prompts 未被调用
        mock_async.assert_not_called()
