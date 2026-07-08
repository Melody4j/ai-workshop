"""测试 file_storage：save_raw_html / save_clean_md / save_llm_clean_md。"""
import shutil
from datetime import datetime
from pathlib import Path

from django.test import TestCase, override_settings

from apps.intelligence.services.file_storage import (
    save_raw_html,
    save_clean_md,
    save_llm_clean_md,
)


@override_settings(SNAPSHOT_STORAGE_DIR="/tmp/ai-workshop-test-file-storage")
class FileStorageTest(TestCase):
    """测试文件存储服务。"""

    def setUp(self):
        self.storage_dir = Path("/tmp/ai-workshop-test-file-storage")
        if self.storage_dir.exists():
            shutil.rmtree(self.storage_dir)
        self.fetch_time = datetime(2025, 1, 15, 9, 30, 0)

    def test_save_llm_clean_md_returns_path_and_file_exists(self):
        """save_llm_clean_md → 返回非空路径，文件存在，内容正确。"""
        path = save_llm_clean_md(1, "https://example.com", "LLM降噪后的MD内容", self.fetch_time)
        self.assertTrue(path)
        self.assertTrue(Path(path).exists())
        content = Path(path).read_text(encoding="utf-8")
        self.assertEqual(content, "LLM降噪后的MD内容")

    def test_save_llm_clean_md_filename_has_llm_prefix(self):
        """save_llm_clean_md → 文件名包含 llm_ 前缀。"""
        path = save_llm_clean_md(1, "https://example.com", "内容", self.fetch_time)
        filename = Path(path).name
        self.assertTrue(filename.startswith("llm_"))
        self.assertIn("example.com", filename)

    def test_save_llm_clean_md_empty_returns_empty(self):
        """save_llm_clean_md → 空内容返回空字符串。"""
        path = save_llm_clean_md(1, "https://example.com", "", self.fetch_time)
        self.assertEqual(path, "")

    def test_save_clean_md_no_llm_prefix(self):
        """save_clean_md → 文件名不含 llm_ 前缀（BS 清洗版本）。"""
        path = save_clean_md(1, "https://example.com", "BS清洗MD", self.fetch_time)
        filename = Path(path).name
        self.assertFalse(filename.startswith("llm_"))

    def test_save_llm_and_bs_in_same_directory(self):
        """save_llm_clean_md 和 save_clean_md 在同一目录，文件名不同。"""
        bs_path = save_clean_md(1, "https://example.com", "BS版本", self.fetch_time)
        llm_path = save_llm_clean_md(1, "https://example.com", "LLM版本", self.fetch_time)
        self.assertEqual(Path(bs_path).parent, Path(llm_path).parent)
        self.assertNotEqual(bs_path, llm_path)
