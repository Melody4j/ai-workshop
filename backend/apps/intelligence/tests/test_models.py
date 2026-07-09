from django.test import TestCase

from apps.intelligence.models import IntelligenceFeed, MonitorProject


class MonitorProjectModelTests(TestCase):
    def test_competitor_urls_defaults_to_empty_list(self) -> None:
        project = MonitorProject.objects.create(
            project_name="AI IDE Monitor",
            cron="0 9 * * *",
        )

        self.assertEqual(project.competitor_urls, [])


class IntelligenceFeedModelTests(TestCase):
    def test_feedback_fields_can_be_persisted(self) -> None:
        project = MonitorProject.objects.create(
            project_name="AI IDE Monitor",
            cron="0 9 * * *",
            competitor_urls=[{"title": "Lovable", "url": "https://lovable.dev"}],
        )

        feed = IntelligenceFeed.objects.create(
            project=project,
            job_status=IntelligenceFeed.JobStatus.CHANGED,
            change_summary="New AI workflow messaging on homepage.",
            strategic_intent="Move up-market with clearer enterprise positioning.",
            action_suggestion="Review our homepage narrative.",
            evidence_diff="Added 'AI workflow' messaging block.",
            html_report_path="/reports/landing-page.html",
            md_table_path="/reports/landing-page.md",
        )

        feed.user_feedback = -1
        feed.user_comment = "This signal is too generic."
        feed.save(update_fields=["user_feedback", "user_comment"])

        refreshed = IntelligenceFeed.objects.get(pk=feed.pk)
        self.assertEqual(refreshed.user_feedback, -1)
        self.assertEqual(refreshed.user_comment, "This signal is too generic.")
