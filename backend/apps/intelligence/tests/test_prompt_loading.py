"""测试 Prompt 模板加载与变量注入。"""
from django.test import SimpleTestCase
from apps.intelligence.services.prompt_loader import load_prompt


class PromptLoadingTest(SimpleTestCase):
    """测试 4 套 Prompt 模板文件可加载且变量正确注入。"""

    def test_load_denoise_prompt(self):
        """降噪 prompt：含 {bs_clean_md} 变量，替换后不含占位符。"""
        result = load_prompt("denoise", bs_clean_md="测试内容ABC")
        self.assertIn("测试内容ABC", result)
        self.assertNotIn("{bs_clean_md}", result)

    def test_load_diff_judge_prompt(self):
        """diff 判断 prompt：含 {self_product_doc} 和 {diff_text} 变量。"""
        result = load_prompt(
            "diff_judge",
            self_product_doc="我方产品文档",
            diff_text="竞品变化片段",
        )
        self.assertIn("我方产品文档", result)
        self.assertIn("竞品变化片段", result)
        self.assertNotIn("{self_product_doc}", result)
        self.assertNotIn("{diff_text}", result)

    def test_load_intel_system_prompt(self):
        """系统 prompt：含 {self_product_doc} 变量。"""
        result = load_prompt("intel_system", self_product_doc="锚定文档")
        self.assertIn("锚定文档", result)
        self.assertNotIn("{self_product_doc}", result)

    def test_load_intel_user_prompt(self):
        """用户 prompt：含 {diff_text} 和 {negative_few_shots} 变量。"""
        result = load_prompt(
            "intel_user",
            diff_text="变化diff",
            negative_few_shots="反面案例列表",
        )
        self.assertIn("变化diff", result)
        self.assertIn("反面案例列表", result)
        self.assertNotIn("{diff_text}", result)
        self.assertNotIn("{negative_few_shots}", result)

    def test_load_nonexistent_prompt_raises(self):
        """加载不存在的 prompt 文件应抛出异常。"""
        with self.assertRaises(FileNotFoundError):
            load_prompt("nonexistent_prompt")
