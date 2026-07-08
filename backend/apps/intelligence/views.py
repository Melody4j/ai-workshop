import os

from django.db.models import QuerySet
from django.http import FileResponse, Http404
from rest_framework import generics, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import IntelligenceFeed, MonitorProject
from .serializers import (
    IntelligenceFeedDetailSerializer,
    IntelligenceFeedListSerializer,
    MonitorProjectSerializer,
    ReportRatingSerializer,
)
from .services import feishu_service


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
        return Response(IntelligenceFeedDetailSerializer(feed).data, status=status.HTTP_200_OK)

    def patch(self, request, pk: int) -> Response:
        feed = self.get_object(pk)
        serializer = ReportRatingSerializer(feed, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
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
