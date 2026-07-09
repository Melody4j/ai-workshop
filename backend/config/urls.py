from django.contrib import admin
from django.urls import include, path

import inngest.django

from apps.intelligence.inngest_client import all_functions, inngest_client
from apps.intelligence.views import FeedHtmlPreviewView

import os
import logging

logger = logging.getLogger(__name__)

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("apps.intelligence.urls")),
    path("view/html/<int:pk>", FeedHtmlPreviewView.as_view(), name="feed-html-preview"),
]

# Inngest webhook 端点（serve 返回 URLPattern，直接展开到 urlpatterns）
# serve_origin：Vercel Serverless 环境中 request.build_absolute_uri() 返回 localhost，
# 需显式指定生产域名，否则 Inngest 注册的 webhook URL 错误
# signing key 缺失时跳过注册，避免阻断整个 Django 应用
try:
    inngest_url = inngest.django.serve(
        client=inngest_client,
        functions=all_functions,
        serve_path="/api/inngest",
        serve_origin=os.environ.get("INNGEST_SERVE_ORIGIN", "") or None,
    )
    urlpatterns.append(inngest_url)
except Exception as e:
    logger.warning(f"[Inngest] webhook 端点注册失败，跳过: {e}")

