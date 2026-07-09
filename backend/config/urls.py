from django.contrib import admin
from django.urls import include, path

import inngest.django

from apps.intelligence.inngest_client import all_functions, inngest_client
from apps.intelligence.views import FeedHtmlPreviewView

# Inngest webhook 端点（serve 返回 URLPattern，直接展开到 urlpatterns）
inngest_url = inngest.django.serve(
    client=inngest_client,
    functions=all_functions,
    serve_path="/api/inngest",
)

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("apps.intelligence.urls")),
    path("view/html/<int:pk>", FeedHtmlPreviewView.as_view(), name="feed-html-preview"),
    inngest_url,
]
