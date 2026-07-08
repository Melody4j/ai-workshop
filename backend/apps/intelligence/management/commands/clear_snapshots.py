"""清理历史快照（DataSnapshot + 关联文件）。

用法：
  python manage.py clear_snapshots            # 清理所有项目
  python manage.py clear_snapshots --project-id 1  # 只清理指定项目
"""
import os

from django.core.management.base import BaseCommand

from apps.intelligence.models import DataSnapshot


class Command(BaseCommand):
    help = "清理历史快照（DataSnapshot 记录 + 关联文件）"

    def add_arguments(self, parser):
        parser.add_argument(
            "--project-id",
            type=int,
            default=None,
            help="只清理指定项目的快照（不指定则清理全部）",
        )

    def handle(self, *args, **options):
        project_id = options.get("project_id")
        qs = DataSnapshot.objects.all()
        if project_id:
            qs = qs.filter(project_id=project_id)

        total = qs.count()
        if total == 0:
            self.stdout.write(self.style.WARNING("无快照可清理。"))
            return

        files_deleted = 0
        for snapshot in qs:
            for path_field in ["raw_html_path", "clean_md_path"]:
                path = getattr(snapshot, path_field, "")
                if path and os.path.exists(path):
                    try:
                        os.remove(path)
                        files_deleted += 1
                    except OSError as e:
                        self.stderr.write(f"删除文件失败: {path} - {e}")

        qs.delete()
        self.stdout.write(
            self.style.SUCCESS(f"已清理 {total} 条快照，删除 {files_deleted} 个文件。")
        )
