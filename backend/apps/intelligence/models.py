from django.db import models
from django.utils import timezone


class TimestampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class MonitorProject(TimestampedModel):
    project_name = models.CharField(max_length=200)
    competitor_urls = models.JSONField(default=list, blank=True)
    self_product_doc = models.TextField(blank=True)
    cron = models.CharField(max_length=100, default="0 9 * * *")
    feishu_webhook = models.URLField(blank=True)
    refined_rules = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self) -> str:
        return self.project_name


class DataSnapshot(TimestampedModel):
    project = models.ForeignKey(
        MonitorProject,
        on_delete=models.CASCADE,
        related_name="snapshots",
    )
    source_title = models.CharField(max_length=200)
    source_url = models.URLField()
    raw_markdown = models.TextField(blank=True)
    clean_markdown = models.TextField(blank=True)
    fetch_time = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-fetch_time", "-id"]

    def __str__(self) -> str:
        return f"{self.project.project_name} - {self.source_title}"


class IntelligenceFeed(TimestampedModel):
    class JobStatus(models.TextChoices):
        CHANGED = "CHANGED", "Changed"
        NO_CHANGE = "NO_CHANGE", "No Change"
        ERROR_CRAWL = "ERROR_CRAWL", "Error Crawl"

    project = models.ForeignKey(
        MonitorProject,
        on_delete=models.CASCADE,
        related_name="feeds",
    )
    job_status = models.CharField(
        max_length=20,
        choices=JobStatus.choices,
        default=JobStatus.CHANGED,
    )
    change_summary = models.TextField(blank=True)
    strategic_intent = models.TextField(blank=True)
    action_suggestion = models.TextField(blank=True)
    evidence_diff = models.TextField(blank=True)
    user_feedback = models.SmallIntegerField(null=True, blank=True)
    user_comment = models.TextField(blank=True)
    html_report_path = models.CharField(max_length=255, blank=True)
    md_table_path = models.CharField(max_length=255, blank=True)
    published_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-published_at", "-id"]

    def __str__(self) -> str:
        return f"{self.project.project_name} - {self.job_status}"
