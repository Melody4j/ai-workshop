"""测试 LLM 降噪服务。"""
from unittest.mock import patch, MagicMock

from django.test import SimpleTestCase, override_settings

from apps.intelligence.services.retry import LLMError


@override_settings(LLM_API_KEY="test-key", LLM_BASE_URL="https://test.example.com/v1")
class DenoiseServiceTest(SimpleTestCase):
    """测试 llm_service.denoise()。"""

    @patch("apps.intelligence.services.llm_service.get_openai_client")
    def test_denoise_success(self, mock_get_client):
        """denoise 正常调用 LLM，返回降噪后 MD。"""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="降噪后MD"))]
        mock_client.chat.completions.create.return_value = mock_response
        mock_get_client.return_value = mock_client

        from apps.intelligence.services.llm_service import denoise

        result = denoise("这是一段有噪音的MD内容用于测试降噪")
        self.assertEqual(result, "降噪后MD")
        mock_client.chat.completions.create.assert_called_once()

    @patch("apps.intelligence.services.llm_service.get_openai_client")
    def test_denoise_empty_input_returns_empty(self, mock_get_client):
        """空输入不调用 LLM，直接返回空字符串。"""
        from apps.intelligence.services.llm_service import denoise

        result = denoise("")
        self.assertEqual(result, "")
        mock_get_client.assert_not_called()

    @patch("apps.intelligence.services.llm_service.get_openai_client")
    def test_denoise_short_input_returns_original(self, mock_get_client):
        """极短输入（<10字符）不调用 LLM，返回原文。"""
        from apps.intelligence.services.llm_service import denoise

        result = denoise("极短")
        self.assertEqual(result, "极短")
        mock_get_client.assert_not_called()

    @patch("apps.intelligence.services.llm_service.time.sleep")
    @patch("apps.intelligence.services.llm_service.get_openai_client")
    def test_denoise_retry_exhausted_raises_llm_error(self, mock_get_client, mock_sleep):
        """LLM 3 次失败 → raise LLMError。"""
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception("API Error")
        mock_get_client.return_value = mock_client

        from apps.intelligence.services.llm_service import denoise

        with self.assertRaises(LLMError):
            denoise("这是一段足够长的MD内容用于测试")

        self.assertEqual(mock_client.chat.completions.create.call_count, 3)
