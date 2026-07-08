import logging

import httpx
from bs4 import BeautifulSoup
import html2text
from playwright.sync_api import sync_playwright, Error as PlaywrightError

logger = logging.getLogger(__name__)


def fetch_and_clean(url: str) -> tuple[str, str]:
    """
    采集 URL 并清洗为 markdown。
    返回 (raw_markdown, clean_markdown)。
    raw_markdown = 原始 HTML 字符串。
    clean_markdown = BeautifulSoup 去噪后 HTML 经 html2text 转换的 MD。
    失败返回 ("", "")。
    """
    # 1. httpx 采集
    raw_html = _fetch_with_httpx(url)
    if raw_html:
        clean_md = _clean_html_to_md(raw_html)
        if clean_md.strip().count("\n") >= 2:  # >= 3 行
            logger.info(f"httpx 采集成功: {url}")
            return (raw_html, clean_md)
        logger.warning(f"httpx 采集内容不足 3 行，降级 Playwright: {url}")

    # 2. Playwright 降级
    raw_html_pw = _fetch_with_playwright(url)
    if raw_html_pw:
        clean_md_pw = _clean_html_to_md(raw_html_pw)
        logger.info(f"Playwright 采集成功: {url}")
        return (raw_html_pw, clean_md_pw)

    # 3. 全部失败
    logger.error(f"采集失败: {url}")
    return ("", "")


def _fetch_with_httpx(url: str) -> str:
    """httpx GET，返回 HTML 字符串，失败返回空字符串。"""
    try:
        resp = httpx.get(
            url,
            timeout=30,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        resp.raise_for_status()
        return resp.text
    except httpx.RequestError as e:
        logger.warning(f"httpx 请求失败: {url} - {e}")
        return ""
    except httpx.HTTPStatusError as e:
        logger.warning(f"httpx 状态码异常: {url} - {e}")
        return ""


def _fetch_with_playwright(url: str) -> str:
    """Playwright 采集，返回 HTML 字符串，失败返回空字符串。"""
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.goto(url, timeout=30000)
            html = page.content()
            browser.close()
            return html
    except PlaywrightError as e:
        logger.warning(f"Playwright 采集失败: {url} - {e}")
        return ""
    except Exception as e:
        logger.warning(f"Playwright 未知异常: {url} - {e}")
        return ""


def _clean_html_to_md(html: str) -> str:
    """BeautifulSoup 去噪 + html2text 转 MD。"""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all(["nav", "footer", "script", "style", "noscript", "iframe"]):
        tag.decompose()
    h = html2text.HTML2Text()
    h.body_width = 0  # 不折行
    return h.handle(str(soup))
