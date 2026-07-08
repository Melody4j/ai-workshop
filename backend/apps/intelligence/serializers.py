from rest_framework import serializers

from .models import IntelligenceFeed, MonitorProject


class MonitorProjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = MonitorProject
        fields = [
            "id",
            "project_name",
            "competitor_urls",
            "self_product_doc",
            "cron",
            "feishu_webhook",
            "refined_rules",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "refined_rules"]

    def validate_competitor_urls(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError("competitor_urls must be a list.")

        for item in value:
            if not isinstance(item, dict):
                raise serializers.ValidationError("Each competitor must be an object.")
            if not item.get("title") or not item.get("url"):
                raise serializers.ValidationError("Each competitor must include title and url.")

        return value


class IntelligenceFeedListSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source="project.project_name", read_only=True)

    class Meta:
        model = IntelligenceFeed
        fields = [
            "id",
            "project",
            "project_name",
            "job_status",
            "change_summary",
            "user_feedback",
            "published_at",
            "html_report_path",
            "md_table_path",
        ]


class IntelligenceFeedDetailSerializer(serializers.ModelSerializer):
    project = MonitorProjectSerializer(read_only=True)

    class Meta:
        model = IntelligenceFeed
        fields = [
            "id",
            "project",
            "job_status",
            "change_summary",
            "strategic_intent",
            "action_suggestion",
            "evidence_diff",
            "user_feedback",
            "user_comment",
            "html_report_path",
            "md_table_path",
            "published_at",
            "created_at",
            "updated_at",
        ]


class ReportRatingSerializer(serializers.ModelSerializer):
    class Meta:
        model = IntelligenceFeed
        fields = ["user_feedback", "user_comment"]

    def validate_user_feedback(self, value):
        if value not in (-1, 1):
            raise serializers.ValidationError("user_feedback must be either -1 or 1.")
        return value
