from unittest.mock import patch, MagicMock
from django.test import SimpleTestCase

from apps.intelligence.services import crawler_service


SAMPLE_HTML = """
<html>
<head><title>Test Site</title><style>body { color: red; }</style></head>
<body>
<nav><a href="/">Home</a><a href="/about">About</a></nav>
<main>
<h1>Welcome to Test Site</h1>
<p>This is a paragraph about the product.</p>
<p>Another paragraph with details about features.</p>
<p>Third paragraph about pricing and plans.</p>
</main>
<footer><p>Copyright 2026</p><a href="/privacy">Privacy</a></footer>
<script>console.log("hello");</script>
<noscript>Please enable JS</noscript>
<iframe src="ads.html"></iframe>
</body>
</html>
"""

MINIMAL_HTML = """
<html><body><p>Only one line</p></body></html>
"""


class CrawlerServiceTest(SimpleTestCase):
    def test_fetch_success(self):
        with patch("apps.intelligence.services.crawler_service.httpx.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.text = SAMPLE_HTML
            mock_resp.raise_for_status = MagicMock()
            mock_get.return_value = mock_resp

            raw_md, clean_md = crawler_service.fetch_and_clean("https://example.com")

            self.assertEqual(raw_md, SAMPLE_HTML)
            self.assertNotIn("Home", clean_md)
            self.assertNotIn("Copyright", clean_md)
            self.assertIn("Welcome to Test Site", clean_md)
            self.assertGreaterEqual(clean_md.strip().count("\n"), 2)

    def test_dedup_removes_nav_footer(self):
        clean_md = crawler_service._clean_html_to_md(SAMPLE_HTML)
        self.assertNotIn("Home", clean_md)
        self.assertNotIn("About", clean_md)
        self.assertNotIn("Copyright", clean_md)
        self.assertNotIn("Privacy", clean_md)
        self.assertNotIn("console.log", clean_md)
        self.assertNotIn("Please enable JS", clean_md)
        self.assertNotIn("ads.html", clean_md)
        self.assertIn("Welcome to Test Site", clean_md)

    def test_fetch_degrade_to_playwright(self):
        with patch("apps.intelligence.services.crawler_service.httpx.get") as mock_get, \
             patch("apps.intelligence.services.crawler_service._fetch_with_playwright") as mock_pw:
            mock_resp = MagicMock()
            mock_resp.text = MINIMAL_HTML
            mock_resp.raise_for_status = MagicMock()
            mock_get.return_value = mock_resp
            mock_pw.return_value = SAMPLE_HTML

            raw_md, clean_md = crawler_service.fetch_and_clean("https://example.com")

            self.assertEqual(raw_md, SAMPLE_HTML)
            self.assertIn("Welcome to Test Site", clean_md)
            mock_pw.assert_called_once_with("https://example.com")

    def test_fetch_httpx_error_degrades_to_playwright(self):
        with patch("apps.intelligence.services.crawler_service.httpx.get") as mock_get, \
             patch("apps.intelligence.services.crawler_service._fetch_with_playwright") as mock_pw:
            import httpx
            mock_get.side_effect = httpx.RequestError("connection refused")
            mock_pw.return_value = SAMPLE_HTML

            raw_md, clean_md = crawler_service.fetch_and_clean("https://example.com")

            self.assertEqual(raw_md, SAMPLE_HTML)
            self.assertIn("Welcome to Test Site", clean_md)
            mock_pw.assert_called_once_with("https://example.com")

    def test_playwright_also_fails_returns_empty(self):
        with patch("apps.intelligence.services.crawler_service.httpx.get") as mock_get, \
             patch("apps.intelligence.services.crawler_service._fetch_with_playwright") as mock_pw:
            mock_resp = MagicMock()
            mock_resp.text = MINIMAL_HTML
            mock_resp.raise_for_status = MagicMock()
            mock_get.return_value = mock_resp
            mock_pw.return_value = ""

            raw_md, clean_md = crawler_service.fetch_and_clean("https://example.com")

            self.assertEqual(raw_md, "")
            self.assertEqual(clean_md, "")

    def test_fetch_completely_fails_returns_empty(self):
        with patch("apps.intelligence.services.crawler_service.httpx.get") as mock_get, \
             patch("apps.intelligence.services.crawler_service._fetch_with_playwright") as mock_pw:
            import httpx
            mock_get.side_effect = httpx.RequestError("connection refused")
            mock_pw.return_value = ""

            raw_md, clean_md = crawler_service.fetch_and_clean("https://example.com")

            self.assertEqual(raw_md, "")
            self.assertEqual(clean_md, "")
