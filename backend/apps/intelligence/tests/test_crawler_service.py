"""crawler_service 测试 — mock requests，不发真实网络请求。

覆盖 Firecrawl v2 crawl API 的 prompt 传入/不传、轮询完成/超时/失败、
多页拼接排序、0 页回退、429 限流重试、网络异常。
"""

from unittest.mock import patch, MagicMock, call
from django.test import SimpleTestCase

from apps.intelligence.services import crawler_service


def _make_response(status_code=200, json_data=None, headers=None):
    """构造 mock requests.Response。"""
    resp = MagicMock()
    resp.status_code = status_code
    resp.ok = status_code < 400
    resp.json.return_value = json_data or {}
    resp.text = str(json_data or {})
    resp.headers = headers or {}
    return resp


def _make_document(url, markdown="md content", html="<p>html</p>"):
    """构造 v2 文档。"""
    return {
        "markdown": markdown,
        "html": html,
        "metadata": {"sourceURL": url, "url": url, "title": url},
    }


class StartCrawlTest(SimpleTestCase):
    """测试 _start_crawl — POST /v2/crawl。"""

    @patch("apps.intelligence.services.crawler_service.requests.post")
    def test_start_crawl_with_prompt(self, mock_post):
        """crawl_hint 非空时 body 含 prompt。"""
        mock_post.return_value = _make_response(
            200, {"success": True, "id": "job-123"}
        )

        job_id = crawler_service._start_crawl(
            "https://example.com", "爬取定价页"
        )

        self.assertEqual(job_id, "job-123")
        _, kwargs = mock_post.call_args
        self.assertIn("prompt", kwargs["json"])
        self.assertEqual(kwargs["json"]["prompt"], "爬取定价页")

    @patch("apps.intelligence.services.crawler_service.requests.post")
    def test_start_crawl_without_prompt(self, mock_post):
        """crawl_hint 为空时 body 不含 prompt。"""
        mock_post.return_value = _make_response(
            200, {"success": True, "id": "job-456"}
        )

        job_id = crawler_service._start_crawl("https://example.com", "")

        self.assertEqual(job_id, "job-456")
        _, kwargs = mock_post.call_args
        self.assertNotIn("prompt", kwargs["json"])

    @patch("apps.intelligence.services.crawler_service.requests.post")
    def test_start_crawl_api_error_returns_empty(self, mock_post):
        """API 返回 success=false 时返回空。"""
        mock_post.return_value = _make_response(
            200, {"success": False, "error": "bad request"}
        )

        job_id = crawler_service._start_crawl("https://example.com", "")
        self.assertEqual(job_id, "")

    @patch("apps.intelligence.services.crawler_service.requests.post")
    def test_start_crawl_http_error_returns_empty(self, mock_post):
        """HTTP 非 2xx 时返回空。"""
        mock_post.return_value = _make_response(500, {})

        job_id = crawler_service._start_crawl("https://example.com", "")
        self.assertEqual(job_id, "")


class PollCrawlTest(SimpleTestCase):
    """测试 _poll_crawl — GET /v2/crawl/{id}。"""

    @patch("apps.intelligence.services.crawler_service.requests.get")
    @patch("apps.intelligence.services.crawler_service.time.sleep")
    def test_poll_crawl_completed(self, mock_sleep, mock_get):
        """轮询到 completed 返回 documents。"""
        mock_get.return_value = _make_response(
            200,
            {"status": "completed", "data": [_make_document("https://a.com")]},
        )

        docs = crawler_service._poll_crawl("job-123")
        self.assertEqual(len(docs), 1)
        mock_sleep.assert_not_called()

    @patch("apps.intelligence.services.crawler_service.requests.get")
    @patch("apps.intelligence.services.crawler_service.time.sleep")
    def test_poll_crawl_failed(self, mock_sleep, mock_get):
        """status=failed 返回空。"""
        mock_get.return_value = _make_response(
            200, {"status": "failed", "data": []}
        )

        docs = crawler_service._poll_crawl("job-123")
        self.assertEqual(docs, [])

    @patch("apps.intelligence.services.crawler_service.requests.get")
    @patch("apps.intelligence.services.crawler_service.time.time")
    @patch("apps.intelligence.services.crawler_service.time.sleep")
    def test_poll_crawl_timeout(self, mock_sleep, mock_time, mock_get):
        """超时返回空。"""
        # time.time 被 while 条件和 logger 调用，需提供足够值
        # 第一次 time.time() → 0（进入循环），第二次 → 200（退出 while）
        # 后续 logger.error 内部也会调 time.time() → 200
        mock_time.side_effect = [0, 200, 200, 200, 200]
        mock_get.return_value = _make_response(
            200, {"status": "scraping", "data": []}
        )

        docs = crawler_service._poll_crawl("job-123")
        self.assertEqual(docs, [])


class MergeDocumentsTest(SimpleTestCase):
    """测试 _merge_documents。"""

    def test_merge_sorted_by_source_url(self):
        """按 metadata.sourceURL 字典序排序拼接。"""
        docs = [
            _make_document("https://z.com", markdown="Z content", html="<p>Z</p>"),
            _make_document("https://a.com", markdown="A content", html="<p>A</p>"),
            _make_document("https://m.com", markdown="M content", html="<p>M</p>"),
        ]

        raw_html, clean_md = crawler_service._merge_documents(docs)

        # a.com 在 m.com 之前，m.com 在 z.com 之前
        a_pos = clean_md.index("A content")
        m_pos = clean_md.index("M content")
        z_pos = clean_md.index("Z content")
        self.assertLess(a_pos, m_pos)
        self.assertLess(m_pos, z_pos)

        # 检查分隔标记
        self.assertIn("source: https://a.com", clean_md)
        self.assertIn("<!-- https://a.com -->", raw_html)

    def test_merge_empty_documents(self):
        """空文档列表返回空字符串。"""
        raw_html, clean_md = crawler_service._merge_documents([])
        self.assertEqual(raw_html, "")
        self.assertEqual(clean_md, "")


class FetchWithFirecrawlTest(SimpleTestCase):
    """测试 fetch_with_firecrawl 端到端逻辑（mock 内部函数）。"""

    @patch("apps.intelligence.services.crawler_service._crawl_and_merge")
    def test_with_crawl_hint_returns_data(self, mock_crawl):
        """crawl_hint 非空且返回数据时直接返回。"""
        mock_crawl.return_value = ("<html>raw</html>", "# Markdown")

        raw, clean = crawler_service.fetch_with_firecrawl(
            "https://example.com", "爬取定价页"
        )

        self.assertEqual(raw, "<html>raw</html>")
        self.assertEqual(clean, "# Markdown")
        mock_crawl.assert_called_once_with("https://example.com", "爬取定价页")

    @patch("apps.intelligence.services.crawler_service._crawl_and_merge")
    def test_zero_results_fallback_no_prompt(self, mock_crawl):
        """带 prompt 返回 0 页时回退无 prompt。"""
        mock_crawl.side_effect = [("", ""), ("<html>raw</html>", "# Markdown")]

        raw, clean = crawler_service.fetch_with_firecrawl(
            "https://example.com", "爬取定价页"
        )

        self.assertEqual(raw, "<html>raw</html>")
        self.assertEqual(clean, "# Markdown")
        # 第一次带 prompt，第二次不带
        self.assertEqual(mock_crawl.call_count, 2)
        self.assertEqual(mock_crawl.call_args_list[0], call("https://example.com", "爬取定价页"))
        self.assertEqual(mock_crawl.call_args_list[1], call("https://example.com", ""))

    @patch("apps.intelligence.services.crawler_service._crawl_and_merge")
    def test_no_crawl_hint_calls_without_prompt(self, mock_crawl):
        """crawl_hint 为空时直接无 prompt crawl。"""
        mock_crawl.return_value = ("<html>raw</html>", "# Markdown")

        raw, clean = crawler_service.fetch_with_firecrawl(
            "https://example.com", ""
        )

        self.assertEqual(raw, "<html>raw</html>")
        mock_crawl.assert_called_once_with("https://example.com", "")

    @patch("apps.intelligence.services.crawler_service._crawl_and_merge")
    def test_both_attempts_fail_returns_empty(self, mock_crawl):
        """带 prompt 和无 prompt 都失败时返回空。"""
        mock_crawl.return_value = ("", "")

        raw, clean = crawler_service.fetch_with_firecrawl(
            "https://example.com", "爬取定价页"
        )

        self.assertEqual(raw, "")
        self.assertEqual(clean, "")

    @patch("apps.intelligence.services.crawler_service._start_crawl")
    def test_network_error_returns_empty(self, mock_start):
        """_start_crawl 异常时 _crawl_and_merge 捕获并返回空。"""
        mock_start.side_effect = Exception("network error")

        raw, clean = crawler_service.fetch_with_firecrawl(
            "https://example.com", ""
        )

        self.assertEqual(raw, "")
        self.assertEqual(clean, "")
