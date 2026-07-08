"""测试 LLM 通用重试装饰器。"""
from unittest.mock import patch, MagicMock

from django.test import SimpleTestCase

from apps.intelligence.services.retry import retry, LLMError


class RetryDecoratorTest(SimpleTestCase):
    """测试 @retry 装饰器行为。"""

    @patch("apps.intelligence.services.retry.time.sleep")
    def test_succeed_on_third_attempt(self, mock_sleep):
        """前 2 次失败、第 3 次成功 → 最终成功，调用 3 次。"""

        call_count = {"n": 0}

        @retry(max_retries=3, delay=0)
        def flaky_func():
            call_count["n"] += 1
            if call_count["n"] < 3:
                raise Exception("transient error")
            return "success"

        result = flaky_func()
        self.assertEqual(result, "success")
        self.assertEqual(call_count["n"], 3)
        # delay=0 仍然会调用 sleep，但参数为 0
        self.assertEqual(mock_sleep.call_count, 2)

    @patch("apps.intelligence.services.retry.time.sleep")
    def test_all_retries_exhausted_raises_llm_error(self, mock_sleep):
        """3 次全失败 → raise LLMError，调用 3 次。"""

        call_count = {"n": 0}

        @retry(max_retries=3, delay=0)
        def always_fail():
            call_count["n"] += 1
            raise Exception("persistent error")

        with self.assertRaises(LLMError) as ctx:
            always_fail()

        self.assertEqual(call_count["n"], 3)
        self.assertIn("persistent error", str(ctx.exception))

    @patch("apps.intelligence.services.retry.time.sleep")
    def test_max_retries_2(self, mock_sleep):
        """max_retries=2 → 失败时调用 2 次。"""

        call_count = {"n": 0}

        @retry(max_retries=2, delay=0)
        def always_fail():
            call_count["n"] += 1
            raise Exception("error")

        with self.assertRaises(LLMError):
            always_fail()

        self.assertEqual(call_count["n"], 2)

    @patch("apps.intelligence.services.retry.time.sleep")
    def test_succeed_on_first_attempt_no_retry(self, mock_sleep):
        """第 1 次就成功 → 不重试，sleep 不被调用。"""

        @retry(max_retries=3, delay=30)
        def good_func():
            return "ok"

        result = good_func()
        self.assertEqual(result, "ok")
        mock_sleep.assert_not_called()

    @patch("apps.intelligence.services.retry.time.sleep")
    def test_delay_applied_between_retries(self, mock_sleep):
        """重试间隔正确传递给 time.sleep。"""
        call_count = {"n": 0}

        @retry(max_retries=3, delay=5)
        def always_fail():
            call_count["n"] += 1
            raise Exception("error")

        with self.assertRaises(LLMError):
            always_fail()

        self.assertEqual(call_count["n"], 3)
        # 2 次重试，每次 sleep(5)
        self.assertEqual(mock_sleep.call_count, 2)
        mock_sleep.assert_called_with(5)
