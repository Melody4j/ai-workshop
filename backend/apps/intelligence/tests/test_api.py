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
            "cron": "0 9 * * *",
            "feishu_webhook": "https://example.com/webhook",
            "is_active": True,
        }

        response = self.client.post(reverse("project-list"), payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(MonitorProject.objects.count(), 1)
        self.assertEqual(response.data["competitor_urls"][0]["title"], "Lovable")

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
