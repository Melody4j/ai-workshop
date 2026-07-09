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
    self_product_doc_name = models.CharField(max_length=255, blank=True)
    competitor_contexts = models.JSONField(default=list, blank=True)
    cron = models.CharField(max_length=100, default="0 9 * * *")
    feishu_webhook = models.URLField(blank=True)
    refined_rules = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    next_run_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self) -> str:
        return self.project_name

    def save(self, *args, **kwargs):
        from apps.intelligence.services.cron_matcher import get_next_run

        if not self.pk or self._state.adding:
            # 新建项目
            self.next_run_at = get_next_run(self.cron, timezone.now())
        else:
            # 更新：检查 cron 是否变更
            old = MonitorProject.objects.filter(pk=self.pk).values_list("cron", flat=True).first()
            if old != self.cron:
                self.next_run_at = get_next_run(self.cron, timezone.now())
        super().save(*args, **kwargs)


class DataSnapshot(TimestampedModel):
    project = models.ForeignKey(
        MonitorProject,
        on_delete=models.CASCADE,
        related_name="snapshots",
    )
    source_title = models.CharField(max_length=200)
    source_url = models.URLField()
    raw_html_path = models.CharField(max_length=512, blank=True)
    clean_md_path = models.CharField(max_length=512, blank=True)
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

    class PushStatus(models.TextChoices):
        NOT_PUSHED = "NOT_PUSHED", "Not Pushed"
        PUSHED = "PUSHED", "Pushed"
        PUSH_FAILED = "PUSH_FAILED", "Push Failed"

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
    push_status = models.CharField(
        max_length=20,
        choices=PushStatus.choices,
        default=PushStatus.NOT_PUSHED,
    )
    change_summary = models.TextField(blank=True)
    strategic_intent = models.TextField(blank=True)
    action_suggestion = models.TextField(blank=True)
    evidence_diff = models.TextField(blank=True)
    user_feedback = models.SmallIntegerField(null=True, blank=True)
    user_comment = models.TextField(blank=True)
    html_report_path = models.CharField(max_length=255, blank=True)
    md_table_path = models.CharField(max_length=255, blank=True)
    diff_text = models.TextField(blank=True, default="")
    published_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-published_at", "-id"]

    def __str__(self) -> str:
        return f"{self.project.project_name} - {self.job_status}"


class PromptVersion(TimestampedModel):
    """Prompt 版本表：每次 LLM 优化后存档历史版本，支持回滚。"""

    prompt_name = models.CharField(max_length=50)
    content = models.TextField()
    version = models.IntegerField(default=1)
    feed = models.ForeignKey(
        IntelligenceFeed,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="prompt_versions",
    )
    optimization_reason = models.TextField(blank=True)

    class Meta:
        ordering = ["-version", "-id"]

    def __str__(self) -> str:
        return f"{self.prompt_name} v{self.version}"
