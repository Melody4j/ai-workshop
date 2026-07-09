"""将本地 prompts/ 目录下的 Prompt 模板上传到 Vercel Blob。

使用方式：
    python manage.py init_prompts_to_blob

前提：BLOB_READ_WRITE_TOKEN 环境变量已配置。
"""

import logging

from django.core.management.base import BaseCommand

from apps.intelligence.services import blob_storage
from apps.intelligence.services.prompt_loader import PROMPTS_DIR

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "将本地 prompts/ 目录下的 Prompt 模板上传到 Vercel Blob"

    def handle(self, *args, **options):
        if not PROMPTS_DIR.exists():
            self.stderr.write(self.style.ERROR(f"prompts 目录不存在: {PROMPTS_DIR}"))
            return

        md_files = sorted(PROMPTS_DIR.glob("*.md"))
        if not md_files:
            self.stderr.write(self.style.WARNING(f"prompts 目录中没有 .md 文件"))
            return

        self.stdout.write(f"找到 {len(md_files)} 个 Prompt 模板，开始上传到 Vercel Blob...")

        success_count = 0
        fail_count = 0

        for md_file in md_files:
            name = md_file.stem  # 文件名（不含 .md 扩展名）
            pathname = f"prompts/{name}.md"

            try:
                content = md_file.read_text(encoding="utf-8")
                blob_url = blob_storage.upload(pathname, content, content_type="text/markdown", allow_overwrite=True)
                self.stdout.write(self.style.SUCCESS(f"  ✅ {name}.md → {blob_url}"))
                success_count += 1
            except Exception as e:
                self.stderr.write(self.style.ERROR(f"  ❌ {name}.md 上传失败: {e}"))
                fail_count += 1

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                f"完成：{success_count} 个成功，{fail_count} 个失败"
            )
        )
