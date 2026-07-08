from django.contrib import admin
from django.urls import include, path

from apps.intelligence.views import FeedHtmlPreviewView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("apps.intelligence.urls")),
    path("view/html/<int:pk>", FeedHtmlPreviewView.as_view(), name="feed-html-preview"),
]
