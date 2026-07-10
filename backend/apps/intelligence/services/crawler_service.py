"""Firecrawl v2 crawl API 采集服务。

替代旧版 httpx+playwright+BeautifulSoup+html2text 流程。
使用 Firecrawl 云端 crawl API（多页爬取 + AI prompt + 轮询 + 拼接）。
"""

import logging
import time

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

POLL_INTERVAL = 5       # 轮询间隔（秒）
POLL_TIMEOUT = 120      # 总超时（秒）
CRAWL_LIMIT = 50        # 最大爬取页数
FRESH_SCRAPE_OPTIONS = {
    "formats": ["markdown", "html"],
    "maxAge": 0,
    "storeInCache": False,
}


def fetch_with_firecrawl(url: str, crawl_hint: str = "") -> tuple[str, str]:
    """
    使用 Firecrawl v2 crawl API 采集 URL。
    返回 (raw_html, clean_md)。
    crawl_hint 非空时作为 prompt 传入，引导 AI 爬虫聚焦内容。
    失败返回 ("", "")。
    """
    logger.info(f"[Firecrawl] 开始采集 url={url}, crawl_hint={crawl_hint!r}, limit={CRAWL_LIMIT}")

    # 1. 带 prompt crawl（如果 crawl_hint 非空）
    if crawl_hint.strip():
        raw_html, clean_md = _crawl_and_merge(url, crawl_hint.strip())
        if raw_html or clean_md:
            logger.info(f"[Firecrawl] 采集完成(带prompt) url={url}, raw={len(raw_html)} chars, md={len(clean_md)} chars")
            return (raw_html, clean_md)
        # 0 页 → 回退无 prompt
        logger.warning(f"[Firecrawl] 带 prompt 返回 0 页，回退无 prompt: {url}")

    # 2. 无 prompt crawl
    raw_html, clean_md = _crawl_and_merge(url, "")
    logger.info(f"[Firecrawl] 采集完成 url={url}, raw={len(raw_html)} chars, md={len(clean_md)} chars")
    return (raw_html, clean_md)


def _crawl_and_merge(url: str, prompt: str) -> tuple[str, str]:
    """启动 crawl → 轮询 → 合并多页。"""
    try:
        job_id = _start_crawl(url, prompt)
        if not job_id:
            return ("", "")

        documents = _poll_crawl(job_id)
        if not documents:
            return ("", "")

        return _merge_documents(documents)
    except Exception as e:
        logger.error(f"Firecrawl crawl 异常: {url} - {e}", exc_info=True)
        return ("", "")


def _start_crawl(url: str, prompt: str) -> str:
    """POST /v2/crawl，返回 job_id。"""
    headers = {
        "Authorization": f"Bearer {settings.FIRECRAWL_API_KEY}",
        "Content-Type": "application/json",
    }
    body = {
        "url": url,
        "limit": CRAWL_LIMIT,
        "scrapeOptions": dict(FRESH_SCRAPE_OPTIONS),
    }
    if prompt:
        body["prompt"] = prompt

    logger.info(
        "[Firecrawl] 发起 fresh crawl url=%s, limit=%s, scrapeOptions=%s",
        url,
        CRAWL_LIMIT,
        body["scrapeOptions"],
    )

    resp = requests.post(
        f"{settings.FIRECRAWL_API_URL}/v2/crawl",
        json=body,
        headers=headers,
        timeout=30,
    )

    # 429 限流重试
    if resp.status_code == 429:
        retry_after = int(resp.headers.get("Retry-After", "15"))
        logger.warning(f"Firecrawl 限流，等待 {retry_after}s 后重试")
        time.sleep(retry_after)
        resp = requests.post(
            f"{settings.FIRECRAWL_API_URL}/v2/crawl",
            json=body,
            headers=headers,
            timeout=30,
        )

    if not resp.ok:
        logger.error(f"Firecrawl start crawl 失败: {resp.status_code} {resp.text}")
        return ""

    data = resp.json()
    if not data.get("success"):
        logger.error(f"Firecrawl start crawl 不成功: {data}")
        return ""

    job_id = data.get("id", "")
    ai_opts = data.get("promptGeneratedOptions")
    final_opts = data.get("finalCrawlerOptions")
    logger.info(f"[Firecrawl] crawl 任务已创建 job_id={job_id}, prompt={prompt!r}")
    if ai_opts:
        logger.info(f"[Firecrawl] AI 生成参数: {ai_opts}")
    if final_opts:
        logger.info(
            "[Firecrawl] 最终爬取参数: includePaths=%s, maxDepth=%s, limit=%s, "
            "crawlEntireDomain=%s, maxAge=%s, storeInCache=%s",
            final_opts.get("includePaths"),
            final_opts.get("maxDepth"),
            final_opts.get("limit"),
            final_opts.get("crawlEntireDomain"),
            final_opts.get("maxAge"),
            final_opts.get("storeInCache"),
        )

    return job_id


def _poll_crawl(job_id: str) -> list:
    """GET /v2/crawl/{id} 轮询直到完成/失败/超时。"""
    headers = {"Authorization": f"Bearer {settings.FIRECRAWL_API_KEY}"}
    deadline = time.time() + POLL_TIMEOUT

    while time.time() < deadline:
        resp = requests.get(
            f"{settings.FIRECRAWL_API_URL}/v2/crawl/{job_id}",
            headers=headers,
            timeout=30,
        )

        # 429 限流处理
        if resp.status_code == 429:
            retry_after = int(resp.headers.get("Retry-After", "15"))
            remaining = deadline - time.time()
            time.sleep(min(retry_after, max(remaining, 0)))
            continue

        if not resp.ok:
            logger.error(f"Firecrawl poll 失败: {resp.status_code}")
            return []

        data = resp.json()
        status = data.get("status", "")

        if status == "completed":
            documents = data.get("data", [])
            total = data.get("total", len(documents))
            completed = data.get("completed", len(documents))
            credits = data.get("creditsUsed", "?")
            logger.info(f"[Firecrawl] 轮询完成 job_id={job_id}, 返回 {len(documents)} 页 "
                        f"(total={total}, completed={completed}, creditsUsed={credits})")
            for i, doc in enumerate(documents):
                src_url = doc.get("metadata", {}).get("sourceURL", "N/A")
                md_len = len(doc.get("markdown", ""))
                logger.info(f"[Firecrawl]   页 {i+1}: {src_url} ({md_len} chars)")
            return documents
        elif status in ("failed", "cancelled"):
            logger.error(f"Firecrawl job {status}: {job_id}")
            return []

        time.sleep(POLL_INTERVAL)

    logger.error(f"Firecrawl 轮询超时 {POLL_TIMEOUT}s: {job_id}")
    return []


def _merge_documents(documents: list) -> tuple[str, str]:
    """按 metadata.sourceURL 字典序排序，拼接 markdown + html。"""
    def get_url(doc):
        return doc.get("metadata", {}).get("sourceURL", "")

    sorted_docs = sorted(documents, key=get_url)

    md_parts = []
    html_parts = []
    for doc in sorted_docs:
        url = get_url(doc)
        md = doc.get("markdown", "")
        html = doc.get("html", "")
        if md:
            md_parts.append(f"\n\n---\nsource: {url}\n\n{md}")
        if html:
            html_parts.append(f"\n<!-- {url} -->\n{html}")

    raw_html = "\n".join(html_parts)
    clean_md = "\n".join(md_parts)
    logger.info(f"[Firecrawl] 合并完成: {len(documents)} 页 → raw_html={len(raw_html)} chars, clean_md={len(clean_md)} chars")
    return (raw_html, clean_md)


def fetch_and_clean(url: str, crawl_hint: str = "") -> tuple[str, str]:
    """兼容旧签名的代理函数。

    返回 (raw_html, clean_md)。
    raw_html = Firecrawl 返回的多页 HTML 拼接。
    clean_md = Firecrawl 返回的多页 Markdown 拼接。
    失败返回 ("", "")。
    """
    return fetch_with_firecrawl(url, crawl_hint)
