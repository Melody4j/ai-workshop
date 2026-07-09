"""测试 diff_service：文本 diff 生成与截断。"""
from django.test import SimpleTestCase

from apps.intelligence.services.diff_service import text_diff, DIFF_TRUNCATE_THRESHOLD


class TextDiffTest(SimpleTestCase):
    """测试 text_diff() 函数。"""

    def test_identical_content_returns_empty(self):
        """内容完全相同 → 返回空字符串。"""
        result = text_diff("a\nb\nc", "a\nb\nc")
        self.assertEqual(result, "")

    def test_different_content_returns_diff(self):
        """内容不同 → 返回非空 diff，含变化标记。"""
        result = text_diff("a\nb\nc", "a\nb")
        self.assertNotEqual(result, "")
        # diff 中应包含新增 c 的标记（new_md 比 prev_md 多了 c）
        self.assertIn("+c", result)

    def test_empty_both_returns_empty(self):
        """两方都为空 → 返回空字符串。"""
        result = text_diff("", "")
        self.assertEqual(result, "")

    def test_new_content_added(self):
        """新增内容 → diff 含 + 行。"""
        result = text_diff("a\nb\nc\n新增", "a\nb")
        self.assertIn("+c", result)
        self.assertIn("+新增", result)

    def test_long_diff_truncated(self):
        """diff 输出超过阈值 → 截断至阈值以内，含截断标记。"""
        # 构造超长 diff：新内容比旧内容多很多行
        new_lines = "\n".join(f"line_{i}" for i in range(1000))
        old_lines = "\n".join(f"old_line_{i}" for i in range(500))
        result = text_diff(new_lines, old_lines)

        # diff 应被截断
        self.assertLessEqual(len(result), DIFF_TRUNCATE_THRESHOLD + 200)  # 截断标记本身有长度
        # 应含截断标记
        self.assertIn("...截断", result)

    def test_short_diff_not_truncated(self):
        """短 diff 不被截断。"""
        result = text_diff("a\nb\nc", "a\nb")
        self.assertNotIn("...截断", result)
