from django.contrib import admin

from .models import DataSnapshot, IntelligenceFeed, MonitorProject, PromptVersion


@admin.register(MonitorProject)
class MonitorProjectAdmin(admin.ModelAdmin):
    list_display = ("project_name", "is_active", "cron", "updated_at")
    search_fields = ("project_name",)
    list_filter = ("is_active",)


@admin.register(DataSnapshot)
class DataSnapshotAdmin(admin.ModelAdmin):
    list_display = ("project", "source_title", "fetch_time")
    search_fields = ("project__project_name", "source_title", "source_url")


@admin.register(IntelligenceFeed)
class IntelligenceFeedAdmin(admin.ModelAdmin):
    list_display = ("project", "job_status", "published_at", "user_feedback")
    search_fields = ("project__project_name", "change_summary")
    list_filter = ("job_status", "user_feedback")


@admin.register(PromptVersion)
class PromptVersionAdmin(admin.ModelAdmin):
    list_display = ("prompt_name", "version", "feed", "optimization_reason", "created_at")
    list_filter = ("prompt_name",)
    readonly_fields = ("created_at", "updated_at")
    ordering = ("-version", "-id")
