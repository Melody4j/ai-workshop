"""飞书推送服务。

在 LLM 情报生成完成后，构建飞书交互式卡片并推送到群机器人 webhook。
推送成功后更新 IntelligenceFeed.push_status 为 PUSHED。
"""

import logging
import time

import httpx
from django.conf import settings

from apps.intelligence.models import IntelligenceFeed

logger = logging.getLogger(__name__)

MAX_RETRIES = 2
RETRY_INTERVAL = 30  # 秒
MAX_CONTENT_LENGTH = 500  # 卡片正文每段最大字符数


def _build_card(feed: IntelligenceFeed) -> dict:
    """构建飞书交互式卡片 JSON。

    卡片结构：标题（项目名）→ 变化摘要 → 分隔线 → 战略意图 → 2 个 action button（在线预览 + 下载 MD）
    """
    change_summary = (feed.change_summary or "")[:MAX_CONTENT_LENGTH]
    strategic_intent = (feed.strategic_intent or "")[:MAX_CONTENT_LENGTH]
    base_url = settings.SITE_BASE_URL.rstrip("/")

    return {
        "msg_type": "interactive",
        "card": {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": f"竞品情报速报 · {feed.project.project_name}",
                },
                "template": "blue",
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"**变化摘要**\n{change_summary}",
                    },
                },
                {"tag": "hr"},
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"**战略意图**\n{strategic_intent}",
                    },
                },
                {
                    "tag": "action",
                    "actions": [
                        {
                            "tag": "button",
                            "text": {"tag": "plain_text", "content": "在线预览"},
                            "url": f"{base_url}/view/html/{feed.id}",
                            "type": "primary",
                        },
                        {
                            "tag": "button",
                            "text": {"tag": "plain_text", "content": "下载 MD"},
                            "url": f"{base_url}/api/feeds/{feed.id}/download_md",
                            "type": "default",
                        },
                    ],
                },
            ],
        },
    }


def push_intelligence(feed_id: int) -> str:
    """推送情报到飞书群机器人。

    Args:
        feed_id: IntelligenceFeed 主键

    Returns:
        "pushed": 推送成功，push_status 已更新为 PUSHED
        "push_failed": 推送失败（重试 2 次后仍失败），push_status 已更新为 PUSH_FAILED
        "skipped": 非 CHANGED 状态，跳过推送
        "skipped_no_webhook": webhook 未配置，跳过推送
        "not_found": feed_id 不存在
    """
    try:
        feed = IntelligenceFeed.objects.select_related("project").get(pk=feed_id)
    except IntelligenceFeed.DoesNotExist:
        logger.error(f"[飞书推送] IntelligenceFeed {feed_id} 不存在")
        return "not_found"

    # 前置校验：仅 CHANGED 推送
    if feed.job_status != IntelligenceFeed.JobStatus.CHANGED:
        logger.info(
            f"[飞书推送] feed {feed_id} job_status={feed.job_status}，跳过推送"
        )
        return "skipped"

    # 前置校验：webhook 为空跳过
    webhook = feed.project.feishu_webhook
    if not webhook:
        logger.info(
            f"[飞书推送] 项目 {feed.project.project_name} webhook 未配置，跳过推送"
        )
        return "skipped_no_webhook"

    # 构建卡片
    card = _build_card(feed)

    # 推送 + 重试（首次 + MAX_RETRIES 次重试 = 总共 MAX_RETRIES + 1 次尝试）
    for attempt in range(1 + MAX_RETRIES):
        try:
            response = httpx.post(webhook, json=card, timeout=10)
            if response.status_code == 200:
                try:
                    result = response.json()
                except Exception:
                    result = {}
                # 飞书成功返回 StatusCode=0 或 code=0；无 body 也视为成功
                status_code = result.get("StatusCode", 0)
                feishu_code = result.get("code", 0)
                if status_code == 0 and feishu_code == 0:
                    feed.push_status = IntelligenceFeed.PushStatus.PUSHED
                    feed.save(update_fields=["push_status"])
                    logger.info(f"[飞书推送] feed {feed_id} 推送成功")
                    return "pushed"
                else:
                    logger.warning(
                        f"[飞书推送] feed {feed_id} 飞书返回错误: {result}"
                    )
            else:
                logger.warning(
                    f"[飞书推送] feed {feed_id} HTTP {response.status_code}"
                )
        except Exception as e:
            logger.error(
                f"[飞书推送] feed {feed_id} 第 {attempt + 1} 次推送异常: {e}"
            )

        # 重试前等待（最后一次不需要等待）
        if attempt < MAX_RETRIES:
            time.sleep(RETRY_INTERVAL)

    # 所有尝试均失败
    feed.push_status = IntelligenceFeed.PushStatus.PUSH_FAILED
    feed.save(update_fields=["push_status"])
    logger.error(
        f"[飞书推送] feed {feed_id} 推送失败（{1 + MAX_RETRIES} 次尝试均失败）"
    )
    return "push_failed"
