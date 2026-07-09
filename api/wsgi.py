"""Vercel Serverless Function 入口。

Vercel Python runtime 仅在 api/ 目录中查找 Serverless Functions，
本文件将请求转发到 Django WSGI application。
"""

import os
import sys
from pathlib import Path

# 将 backend/ 加入 Python 路径，使 Django 配置模块可被导入
_backend_dir = str(Path(__file__).resolve().parent.parent / "backend")
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

from django.core.wsgi import get_wsgi_application  # noqa: E402

application = get_wsgi_application()
