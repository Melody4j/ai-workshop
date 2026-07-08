---
title: Merge-back 资产晋升清单
status: done
---

# Spec 005 飞书推送接入 — Merge-back 资产晋升清单

> 本文件是 Spec 005 merge-back 的需求级 SSOT，记录每条晋升条目的 project 落点、不变量摘要、证据入口与状态。

## 晋升条目

### MB-001: intelligence-models.md — push_status 字段不变量

- **project 落点**：`.aisdlc/project/components/intelligence-models.md`
  - Data Contract → Invariants 新增第 11 条
  - Migration 入口新增 0005
- **不变量摘要**：
  1. `IntelligenceFeed.push_status` 保持兼容 `NOT_PUSHED` / `PUSHED` / `PUSH_FAILED`，默认 `NOT_PUSHED`
  2. `push_status` 与 `job_status` 正交——`job_status` 标识情报结果，`push_status` 标识推送结果，不互相覆盖
  3. 仅 `job_status=CHANGED` 的记录触发推送
- **证据入口**：
  - `backend/apps/intelligence/models.py`（PushStatus 枚举 + push_status 字段）
  - `backend/apps/intelligence/migrations/0005_intelligencefeed_push_status.py`
  - `backend/apps/intelligence/serializers.py`（List + Detail Serializer fields 含 push_status）
  - `backend/apps/intelligence/tests/test_feishu_service.py`（PushStatusFieldTest）
- **状态**：Done
- **代码来源**：根项目

### MB-002: intelligence-api.md — 推送与下载端点契约

- **project 落点**：`.aisdlc/project/components/intelligence-api.md`
  - API Contract → Invariants 新增第 6~8 条
  - Evidence 新增测试入口
- **不变量摘要**：
  1. `POST /api/feeds/{id}/push`：手动触发飞书推送，非 `CHANGED` feed 返回 400
  2. `GET /api/feeds/{id}/download_md`：返回 MD 文件下载流（`Content-Type: text/markdown`），文件不存在返回 404
  3. 推送服务入口为 `feishu_service.push_intelligence(feed_id)`，返回 `"pushed"` / `"push_failed"` / `"skipped"` / `"skipped_no_webhook"` / `"not_found"`
- **证据入口**：
  - `backend/apps/intelligence/urls.py`（feed-push + feed-download-md 路由）
  - `backend/apps/intelligence/views.py`（FeedPushView + FeedDownloadMdView）
  - `backend/apps/intelligence/services/feishu_service.py`（push_intelligence 函数）
  - `backend/apps/intelligence/tests/test_api.py`（FeedPushViewTest + FeedDownloadMdViewTest）
- **状态**：Done
- **代码来源**：根项目

### MB-003: ops/index.md — 飞书推送运维入口

- **project 落点**：`.aisdlc/project/ops/index.md`
  - 新增"飞书推送运维"段落
- **内容摘要**：
  1. `SITE_BASE_URL` 环境变量配置（默认 `http://localhost:5173`），用于飞书卡片按钮绝对 URL
  2. 手动推送 API：`POST /api/feeds/{id}/push`
  3. MD 下载 API：`GET /api/feeds/{id}/download_md`
- **证据入口**：
  - `backend/config/settings.py`（SITE_BASE_URL 配置）
  - `backend/apps/intelligence/services/feishu_service.py`（推送服务）
- **状态**：Done
- **代码来源**：根项目

### MB-004: index.md — Registry 状态更新

- **project 落点**：`.aisdlc/project/index.md`
  - 已晋升资产表新增 005-feishu-push 条目
  - 最近一次 merge-back 更新为 `005-feishu-push`
- **状态**：Done
- **代码来源**：根项目

## 不晋升项（留在 spec 级）

- 飞书卡片 JSON 模板细节（`_build_card` 返回的 JSON 结构）——属于实现细节，不是长期契约，留在 `feishu_service.py` 代码中
- 推送重试参数（MAX_RETRIES=2, RETRY_INTERVAL=30s）——属于配置常量，不是不变量，后续可能调整
- 测试计划 `verification/test-plan.md`——属于本 Spec 交付证据，不晋升到 project

## CONTEXT GAP

- `CONTEXT GAP`：V-008（Spec 004 集成兼容性）尚未验证，Spec 004 merge 后需端到端测试确认 `feishu_service.push_intelligence(feed_id)` 调用点正确
  - 建议动作：Spec 004 merge 后补充集成验证
