import logging

from django.db.models import QuerySet
from django.http import FileResponse, Http404, HttpResponse
from rest_framework import generics, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

import inngest

from .inngest_client import inngest_client
from .models import IntelligenceFeed, MonitorProject
from .serializers import (
    IntelligenceFeedDetailSerializer,
    IntelligenceFeedListSerializer,
    MonitorProjectSerializer,
    ReportRatingSerializer,
)
from .services import feishu_service

logger = logging.getLogger(__name__)


class ProjectListCreateView(generics.ListCreateAPIView):
    queryset = MonitorProject.objects.all()
    serializer_class = MonitorProjectSerializer
    permission_classes = [AllowAny]


class ProjectDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = MonitorProject.objects.all()
    serializer_class = MonitorProjectSerializer
    permission_classes = [AllowAny]

    def perform_destroy(self, instance: MonitorProject) -> None:
        instance.is_active = False
        instance.save(update_fields=["is_active", "updated_at"])


class ProjectExecuteView(APIView):
    """手动触发项目扫描。

    POST /api/projects/{id}/execute
    通过 Inngest 事件触发异步扫描（采集 → LLM → 报告 → 推送），立即返回 202。
    """

    permission_classes = [AllowAny]

    def post(self, request, pk: int) -> Response:
        try:
            MonitorProject.objects.get(pk=pk)
        except MonitorProject.DoesNotExist:
            raise Http404

        inngest_client.send_sync(
            inngest.Event(
                name="app/scan.project",
                data={"project_id": pk},
            )
        )

        return Response(
            {"detail": "任务已开始执行", "project_id": pk},
            status=status.HTTP_202_ACCEPTED,
        )


class ReportListView(generics.ListAPIView):
    serializer_class = IntelligenceFeedListSerializer
    permission_classes = [AllowAny]

    def get_queryset(self) -> QuerySet[IntelligenceFeed]:
        queryset = IntelligenceFeed.objects.select_related("project").all()
        project_id = self.request.query_params.get("project")
        status_value = self.request.query_params.get("status")
        date_from = self.request.query_params.get("date_from")
        date_to = self.request.query_params.get("date_to")

        if project_id:
            queryset = queryset.filter(project_id=project_id)

        if status_value:
            queryset = queryset.filter(job_status=status_value)

        if date_from:
            queryset = queryset.filter(published_at__date__gte=date_from)

        if date_to:
            queryset = queryset.filter(published_at__date__lte=date_to)

        return queryset


class ReportDetailView(generics.RetrieveAPIView):
    queryset = IntelligenceFeed.objects.select_related("project").all()
    serializer_class = IntelligenceFeedDetailSerializer
    permission_classes = [AllowAny]


class ReportRatingView(APIView):
    permission_classes = [AllowAny]

    def get_object(self, pk: int) -> IntelligenceFeed:
        return IntelligenceFeed.objects.get(pk=pk)

    def post(self, request, pk: int) -> Response:
        feed = self.get_object(pk)
        serializer = ReportRatingSerializer(feed, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        # 评分=-1 时通过 Inngest 事件触发 prompt 优化
        if feed.user_feedback == -1:
            inngest_client.send_sync(
                inngest.Event(
                    name="app/optimize.prompt",
                    data={"feed_id": feed.pk},
                )
            )

        return Response(IntelligenceFeedDetailSerializer(feed).data, status=status.HTTP_200_OK)

    def patch(self, request, pk: int) -> Response:
        feed = self.get_object(pk)
        serializer = ReportRatingSerializer(feed, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        # 评分=-1 时通过 Inngest 事件触发 prompt 优化
        if feed.user_feedback == -1:
            inngest_client.send_sync(
                inngest.Event(
                    name="app/optimize.prompt",
                    data={"feed_id": feed.pk},
                )
            )

        return Response(IntelligenceFeedDetailSerializer(feed).data, status=status.HTTP_200_OK)

    def delete(self, request, pk: int) -> Response:
        feed = self.get_object(pk)
        feed.user_feedback = None
        feed.user_comment = ""
        feed.save(update_fields=["user_feedback", "user_comment", "updated_at"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class FeedPushView(APIView):
    """手动触发飞书推送"""

    permission_classes = [AllowAny]

    def post(self, request, pk: int) -> Response:
        try:
            feed = IntelligenceFeed.objects.get(pk=pk)
        except IntelligenceFeed.DoesNotExist:
            raise Http404

        if feed.job_status != IntelligenceFeed.JobStatus.CHANGED:
            return Response(
                {"detail": "Only CHANGED feeds can be pushed"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        result = feishu_service.push_intelligence(pk)
        feed.refresh_from_db()
        return Response(
            {"push_status": feed.push_status, "result": result},
            status=status.HTTP_200_OK,
        )


class FeedDownloadMdView(APIView):
    """下载 MD 报告文件"""

    permission_classes = [AllowAny]

    def get(self, request, pk: int) -> FileResponse:
        try:
            feed = IntelligenceFeed.objects.get(pk=pk)
        except IntelligenceFeed.DoesNotExist:
            raise Http404

        md_path = feed.md_table_path
        if not md_path or not os.path.exists(md_path):
            raise Http404("MD report file not found")

        filename = os.path.basename(md_path) or f"report_{pk}.md"
        return FileResponse(
            open(md_path, "rb"),
            content_type="text/markdown",
            as_attachment=True,
            filename=filename,
        )


class FeedHtmlPreviewView(APIView):
    """在线预览 HTML 报告（inline，不触发下载）。

    飞书卡片"在线预览"按钮跳转到 /view/html/{id}，由本 view 读取
    feed.html_report_path 文件内容并以 text/html 返回，浏览器直接渲染。
    """

    permission_classes = [AllowAny]

    def get(self, request, pk: int) -> HttpResponse:
        try:
            feed = IntelligenceFeed.objects.get(pk=pk)
        except IntelligenceFeed.DoesNotExist:
            raise Http404

        html_path = feed.html_report_path
        if not html_path or not os.path.exists(html_path):
            raise Http404("HTML report file not found")

        with open(html_path, "rb") as f:
            content = f.read()

        return HttpResponse(content, content_type="text/html; charset=utf-8")


class FeedOptimizePromptView(APIView):
    """手动触发 Prompt 优化。

    POST /api/feeds/{id}/optimize_prompt
    同步调用 prompt_optimizer_service.optimize_prompts，返回优化结果摘要。
    """

    permission_classes = [AllowAny]

    def post(self, request, pk: int) -> Response:
        try:
            feed = IntelligenceFeed.objects.get(pk=pk)
        except IntelligenceFeed.DoesNotExist:
            raise Http404

        from .services.prompt_optimizer_service import optimize_prompts

        result = optimize_prompts(pk)
        return Response(result, status=status.HTTP_200_OK)
