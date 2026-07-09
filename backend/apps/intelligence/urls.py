from django.urls import path

from .views import (
    FeedChangeListView,
    FeedDownloadMdView,
    FeedHtmlPreviewView,
    FeedOptimizePromptView,
    FeedPushView,
    ProjectDetailView,
    ProjectExecuteView,
    ProjectListCreateView,
    ReportDetailView,
    ReportListView,
    ReportRatingView,
)

urlpatterns = [
    path("projects", ProjectListCreateView.as_view(), name="project-list"),
    path("projects/<int:pk>", ProjectDetailView.as_view(), name="project-detail"),
    path("projects/<int:pk>/execute", ProjectExecuteView.as_view(), name="project-execute"),
    path("reports", ReportListView.as_view(), name="report-list"),
    path("reports/<int:pk>", ReportDetailView.as_view(), name="report-detail"),
    path("reports/<int:pk>/rating", ReportRatingView.as_view(), name="report-rating"),
    path("feeds/<int:pk>/push", FeedPushView.as_view(), name="feed-push"),
    path("feeds/<int:pk>/download_md", FeedDownloadMdView.as_view(), name="feed-download-md"),
    path("feeds/<int:pk>/preview_html", FeedHtmlPreviewView.as_view(), name="feed-preview-html"),
    path("feeds/<int:pk>/optimize_prompt", FeedOptimizePromptView.as_view(), name="feed-optimize-prompt"),
    path("feeds/changes", FeedChangeListView.as_view(), name="feed-change-list"),
]
