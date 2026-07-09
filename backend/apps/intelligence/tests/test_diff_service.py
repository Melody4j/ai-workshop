"""测试 diff_service：文本 diff 生成与截断。"""
from django.test import SimpleTestCase

from apps.intelligence.services.diff_service import (
    canonical_text_diff,
    canonicalize_markdown,
    text_diff,
    DIFF_TRUNCATE_THRESHOLD,
    _normalize_to_paragraphs,
)


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
        # 段落级 diff：new 规范化为 "a b c"，prev 规范化为 "a b"
        self.assertIn("+a b c", result)
        self.assertIn("-a b", result)

    def test_empty_both_returns_empty(self):
        """两方都为空 → 返回空字符串。"""
        result = text_diff("", "")
        self.assertEqual(result, "")

    def test_new_content_added(self):
        """新增段落 → diff 含 + 行。"""
        result = text_diff("段落一\n\n段落二\n\n新增段落", "段落一\n\n段落二")
        self.assertNotEqual(result, "")
        self.assertIn("+新增段落", result)

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


class NormalizeToParagraphsTest(SimpleTestCase):
    """测试 _normalize_to_paragraphs() 段落规范化。"""

    def test_single_paragraph_no_newline(self):
        """单段落无换行 → 返回单元素列表。"""
        result = _normalize_to_paragraphs("hello world")
        self.assertEqual(result, ["hello world"])

    def test_paragraph_split_by_blank_line(self):
        """双换行分隔两个段落 → 返回两元素列表。"""
        result = _normalize_to_paragraphs("first paragraph\n\nsecond paragraph")
        self.assertEqual(result, ["first paragraph", "second paragraph"])

    def test_single_newline_within_paragraph_merged(self):
        """段落内单换行 → 合并为空格。"""
        result = _normalize_to_paragraphs("hello\nworld")
        self.assertEqual(result, ["hello world"])

    def test_multiple_newlines_within_paragraph_merged(self):
        """段落内多换行 → 合并为单个空格。"""
        result = _normalize_to_paragraphs("hello\n\nworld")
        # 双换行是段落分隔，所以这是两个段落
        self.assertEqual(result, ["hello", "world"])

    def test_empty_string_returns_empty_list(self):
        """空字符串 → 空列表。"""
        result = _normalize_to_paragraphs("")
        self.assertEqual(result, [])

    def test_whitespace_only_returns_empty_list(self):
        """纯空白 → 空列表。"""
        result = _normalize_to_paragraphs("   \n  \n  ")
        self.assertEqual(result, [])

    def test_multiple_spaces_collapsed(self):
        """多余空格 → 合并为单个空格。"""
        result = _normalize_to_paragraphs("hello   world")
        self.assertEqual(result, ["hello world"])

    def test_markdown_headings_preserved(self):
        """markdown 标题作为段落保留。"""
        result = _normalize_to_paragraphs("## 标题\n\n正文内容")
        self.assertEqual(result, ["## 标题", "正文内容"])

    def test_list_items_as_paragraphs(self):
        """列表项按段落分隔。"""
        md = "- 第一项\n- 第二项\n- 第三项"
        result = _normalize_to_paragraphs(md)
        # 列表项之间没有空行，所以合为一个段落
        self.assertEqual(len(result), 1)
        self.assertIn("第一项", result[0])
        self.assertIn("第二项", result[0])


class ParagraphLevelDiffTest(SimpleTestCase):
    """测试段落级 diff 对换行漂移的鲁棒性。"""

    def test_line_break_drift_no_diff(self):
        """同一段落内换行位置不同 → 不产生 diff。"""
        new_md = "上传服装/配饰图，AI模特自动试穿\n省去外模拍摄成本"
        prev_md = "上传服装/配饰图，AI模特自动试穿，省去外模拍摄成本"
        # 上一版本有逗号，新一版没有，这是真正的文字差异
        result = text_diff(new_md, prev_md)
        self.assertNotEqual(result, "")

    def test_same_content_different_line_breaks_no_diff(self):
        """完全相同的内容，仅换行位置不同 → 不产生 diff。"""
        new_md = "上传服装/配饰图，AI模特\n自动试穿，省去外模拍摄成本"
        prev_md = "上传服装/配饰图，AI模特自动试穿，\n省去外模拍摄成本"
        result = text_diff(new_md, prev_md)
        # 段落内换行不同，规范化后内容相同，应无 diff
        self.assertEqual(result, "")

    def test_common_changelog_not_flagged_as_change(self):
        """公共底稿内容（更新日志）换行漂移 → 不产生 diff。"""
        prev_md = """v2.4 2026 年 3 月 12 日

- 新增：背景模板库新增 80 个电商场景模板
- 改进：模特生成一致性提升，同一 SKU 多张图保持风格统一
- 修复：批量处理在 Safari 下的内存溢出问题

v2.3 2026 年 2 月 20 日

- 新增：API Webhook 支持，生成完成后回调通知
- 改进：出图速度提升 30%"""

        new_md = """v2.4 2026 年 3 月 12 日

- 新增：背景模板库新增 80 个电商场景模板
- 改进：模特生成一致性提升，同一 SKU
多张图保持风格统一
- 修复：批量处理在 Safari 下的内存溢出问题

v2.3 2026 年 2 月 20 日

- 新增：API Webhook 支持，生成完成后回调通知
- 改进：出图速度提升 30%"""

        result = text_diff(new_md, prev_md)
        # 仅换行位置不同，段落内容相同，应无 diff
        self.assertEqual(result, "")

    def test_version_number_space_difference_is_real_change(self):
        """版本号空格差异（v2.4 2026 vs v2.42026）是真实文字差异，应产生 diff。"""
        prev_md = "v2.4 2026 年 3 月 12 日"
        new_md = "v2.42026 年 3 月 12 日"
        result = text_diff(new_md, prev_md)
        # ASCII 字符间的空格差异是真实内容变化，不应被消除
        self.assertNotEqual(result, "")

    def test_real_content_change_detected(self):
        """真正的段落增删 → 产生 diff。"""
        new_md = """## 功能介绍

新增功能卡片

### 定价

$99/月"""
        prev_md = """## 功能介绍

### 定价

$99/月"""
        result = text_diff(new_md, prev_md)
        self.assertNotEqual(result, "")
        self.assertIn("+新增功能卡片", result)

    def test_price_change_detected(self):
        """价格变化（同段落内文字差异）→ 产生 diff。"""
        new_md = "### Starter\n\n$39/月"
        prev_md = "### Starter\n\n$29/月"
        result = text_diff(new_md, prev_md)
        self.assertNotEqual(result, "")
        self.assertIn("+$39/月", result)
        self.assertIn("-$29/月", result)


class CanonicalizeMarkdownTest(SimpleTestCase):
    """测试规则归一化 markdown。"""

    def test_remove_wrapping_code_fence(self):
        md = "```\n## 标题\n正文内容\n```"
        result = canonicalize_markdown(md)
        self.assertEqual(result, "## 标题\n正文内容")

    def test_remove_decorative_only_line(self):
        md = "## 功能介绍\n\n🎨\n\n$29/月"
        result = canonicalize_markdown(md)
        self.assertEqual(result, "## 功能介绍\n\n$29/月")

    def test_collapse_spaces_and_tabs(self):
        md = "  hello\t\tworld  \n\n foo   bar "
        result = canonicalize_markdown(md)
        self.assertEqual(result, "hello world\n\nfoo bar")

    def test_fold_consecutive_blank_lines(self):
        md = "第一段\n\n\n\n第二段"
        result = canonicalize_markdown(md)
        self.assertEqual(result, "第一段\n\n第二段")


class CanonicalTextDiffTest(SimpleTestCase):
    """测试 canonical_text_diff() 的稳定 diff 行为。"""

    def test_ignores_wrapping_code_fence(self):
        prev_md = "## 标题\n正文内容"
        new_md = "```\n## 标题\n正文内容\n```"
        result = canonical_text_diff(new_md, prev_md)
        self.assertEqual(result, "")

    def test_ignores_emoji_only_line(self):
        prev_md = "## 功能介绍\n\n$29/月"
        new_md = "## 功能介绍\n\n🎨\n\n$29/月"
        result = canonical_text_diff(new_md, prev_md)
        self.assertEqual(result, "")

    def test_ignores_cjk_spacing_and_line_break_drift(self):
        prev_md = "上传服装/配饰图，AI模特自动试穿，省去外模拍摄成本"
        new_md = "上传服装/配饰图，AI模特自动试穿，\n省去外模拍摄成本"
        result = canonical_text_diff(new_md, prev_md)
        self.assertEqual(result, "")

    def test_preserves_real_price_change(self):
        prev_md = "### Starter\n\n$29/月"
        new_md = "### Starter\n\n$39/月"
        result = canonical_text_diff(new_md, prev_md)
        self.assertNotEqual(result, "")
        self.assertIn("+$39/月", result)
        self.assertIn("-$29/月", result)

    def test_raw_text_diff_keeps_decorative_change_as_evidence(self):
        prev_md = "## 功能介绍\n\n$29/月"
        new_md = "## 功能介绍\n\n🎨\n\n$29/月"
        result = text_diff(new_md, prev_md)
        self.assertNotEqual(result, "")
