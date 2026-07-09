from rest_framework import serializers

from croniter import croniter

from .models import IntelligenceFeed, MonitorProject


class MonitorProjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = MonitorProject
        fields = [
            "id",
            "project_name",
            "competitor_urls",
            "self_product_doc",
            "self_product_doc_name",
            "competitor_contexts",
            "cron",
            "feishu_webhook",
            "refined_rules",
            "is_active",
            "next_run_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "refined_rules", "next_run_at"]

    def validate_cron(self, value):
        if not croniter.is_valid(value):
            raise serializers.ValidationError(
                f"Invalid cron expression: '{value}'. "
                "Use standard 5-field cron (minute hour day month weekday). "
                "Hour range is 0-23, not 0-24."
            )
        return value

    def validate_competitor_urls(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError("competitor_urls must be a list.")

        for item in value:
            if not isinstance(item, dict):
                raise serializers.ValidationError("Each competitor must be an object.")
            if not item.get("title") or not item.get("url"):
                raise serializers.ValidationError("Each competitor must include title and url.")
            if "crawl_hint" in item and not isinstance(item.get("crawl_hint", ""), str):
                raise serializers.ValidationError("crawl_hint must be a string when provided.")

        return value

    def validate_competitor_contexts(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError("competitor_contexts must be a list.")

        for item in value:
            if not isinstance(item, dict):
                raise serializers.ValidationError("Each competitor context must be an object.")
            if not item.get("title") or not item.get("url"):
                raise serializers.ValidationError(
                    "Each competitor context must include title and url."
                )
            if "supplement_doc_name" in item and not isinstance(
                item.get("supplement_doc_name", ""), str
            ):
                raise serializers.ValidationError(
                    "supplement_doc_name must be a string when provided."
                )
            if "supplement_doc_content" in item and not isinstance(
                item.get("supplement_doc_content", ""), str
            ):
                raise serializers.ValidationError(
                    "supplement_doc_content must be a string when provided."
                )

        return value

    def validate(self, attrs):
        competitor_urls = attrs.get(
            "competitor_urls",
            getattr(self.instance, "competitor_urls", []),
        )
        competitor_contexts = attrs.get(
            "competitor_contexts",
            getattr(self.instance, "competitor_contexts", []),
        )

        if competitor_contexts and len(competitor_contexts) != len(competitor_urls):
            raise serializers.ValidationError(
                {
                    "competitor_contexts": (
                        "competitor_contexts must align with competitor_urls by item count."
                    )
                }
            )

        return attrs


class IntelligenceFeedListSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source="project.project_name", read_only=True)

    class Meta:
        model = IntelligenceFeed
        fields = [
            "id",
            "project",
            "project_name",
            "job_status",
            "push_status",
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
            "push_status",
            "competitor_overview",
            "change_summary",
            "strategic_intent",
            "action_suggestion",
            "evidence_diff",
            "diff_text",
            "raw_diff_text",
            "user_feedback",
            "user_comment",
            "html_report_path",
            "md_table_path",
            "published_at",
            "created_at",
            "updated_at",
        ]


class FeedChangeListSerializer(serializers.ModelSerializer):
    """内容变化列表序列化器。

    返回结构: {竞品名称, 变化的前后内容, 意图分析结果}
    - competitor_name: 项目名称（每个监控项目对应一组竞品）
    - diff_text: difflib 原始 diff 文本（变化前后内容）
    - evidence_diff: LLM 提取的证据 diff
    - strategic_intent: LLM 意图分析结果
    """

    competitor_name = serializers.CharField(source="project.project_name", read_only=True)

    class Meta:
        model = IntelligenceFeed
        fields = [
            "id",
            "competitor_name",
            "diff_text",
            "evidence_diff",
            "strategic_intent",
            "published_at",
        ]


class ReportRatingSerializer(serializers.ModelSerializer):
    class Meta:
        model = IntelligenceFeed
        fields = ["user_feedback", "user_comment"]

    def validate_user_feedback(self, value):
        if value not in (-1, 1):
            raise serializers.ValidationError("user_feedback must be either -1 or 1.")
        return value
