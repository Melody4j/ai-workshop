---
title: Merge-back — LLM 系统接入与竞品分析全流程
spec: 004-llm-intel-pipeline
status: done
date: 2026-07-09
---

# Merge-back：004-llm-intel-pipeline

## 晋升清单总览

| ID | 类型 | project 落点 | 状态 | 代码来源 |
|----|------|-------------|------|----------|
| MB-001 | Service Contract | `components/intelligence-scheduler.md#service-contract` | Done | 根项目 |
| MB-002 | Data Contract | `components/intelligence-models.md#data-contract` | Done | 根项目 |
| MB-003 | Component（新建） | `components/llm-service.md` | Done | 根项目 |
| MB-004 | Component（新建） | `components/report-service.md` | Done | 根项目 |
| MB-005 | NFR | `nfr.md` | Not Done | 根项目 |
| MB-006 | API Contract | `components/intelligence-api.md#api-contract` | Done | 根项目 |
| MB-007 | Ops | `ops/index.md` | Done | 根项目 |
| MB-008 | Registry | `index.md` | Done | 根项目 |

> MB-005 标记 Not Done：V 阶段未执行，LLM 延迟/成本基线尚无实测数据。

---

## MB-001：intelligence-scheduler Service Contract 更新

- **project 落点**：`components/intelligence-scheduler.md#service-contract`
- **不变量摘要**（需长期护栏）：
  1. `_process_url` 串接 11 步链路：采集 → LLM 降噪 → 快照入库 → diff 熔断 → LLM diff 判断 → LLM 情报生成 → IntelligenceFeed 入库 → 报告渲染 → 飞书推送
  2. 3 次 LLM 调用独立，不合并（denoise / judge_diff / generate_intel）
  3. 首次爬取或旧格式快照跳过 diff，直接情报生成
  4. LLM 降噪/情报生成失败 → ERROR_CRAWL，不创建快照
  5. 飞书推送异常不中断主流程（try-except 隔离）
- **证据入口**：
  - `backend/apps/intelligence/services/scheduler_service.py`（`_process_url` 11 步链路）
  - `backend/apps/intelligence/tests/test_scheduler_service.py`（23 tests）
  - `backend/apps/intelligence/tests/test_llm_pipeline_e2e.py`（7 E2E tests）
- **状态**：Done
- **代码来源**：根项目 `004-llm-intel-pipeline`

---

## MB-002：intelligence-models Data Contract 更新

- **project 落点**：`components/intelligence-models.md#data-contract`
- **不变量摘要**：
  1. `DataSnapshot.clean_md_path` 语义变更：BS 清洗 → LLM 降噪 MD（文件名 `llm_` 前缀标识）
  2. 旧格式快照兼容：`clean_md_path` 无 `llm_` 前缀时跳过 diff
- **证据入口**：
  - `backend/apps/intelligence/models.py`（DataSnapshot.clean_md_path 字段）
  - `backend/apps/intelligence/services/file_storage.py`（`save_llm_clean_md` 带 `llm_` 前缀）
  - `backend/apps/intelligence/services/scheduler_service.py`（旧格式检测逻辑 line 144-148）
- **状态**：Done
- **代码来源**：根项目 `004-llm-intel-pipeline`

---

## MB-003：llm-service 模块页（新建）

- **project 落点**：`components/llm-service.md`（新建）
- **不变量摘要**：
  1. 3 次独立 LLM 调用：`denoise()` / `judge_diff()` / `generate_intel()`
  2. `generate_intel` 使用 instructor + Pydantic（IntelResult 4 字段结构化输出）
  3. 每次 LLM 调用独立重试（3 次 / 30s 间隔）
  4. LLM 密钥从 `.env` 读取（LLM_API_KEY / LLM_BASE_URL / LLM_MODEL），不硬编码
  5. Negative Few-Shot 注入上限最近 5 条（`user_feedback=-1`）
  6. OpenAI 兼容 API（覆盖 OpenAI / DeepSeek / 通义 / Moonshot）
- **证据入口**：
  - `backend/apps/intelligence/services/llm_service.py`（3 个公开函数）
  - `backend/apps/intelligence/services/llm_client.py`（client 封装 + IntelResult Pydantic）
  - `backend/apps/intelligence/services/retry.py`（重试装饰器）
  - `backend/apps/intelligence/prompts/`（5 套 Prompt 模板）
  - `backend/apps/intelligence/tests/test_llm_service.py`（13 tests）
  - `backend/apps/intelligence/tests/test_llm_client.py`
  - `backend/apps/intelligence/tests/test_prompt_loading.py`
  - `backend/apps/intelligence/tests/test_retry.py`
- **状态**：Done
- **代码来源**：根项目 `004-llm-intel-pipeline`

---

## MB-004：report-service 模块页（新建）

- **project 落点**：`components/report-service.md`（新建）
- **不变量摘要**：
  1. Jinja2 离线渲染 HTML + MD 报告
  2. 模板位于 `backend/apps/intelligence/templates/`（`report.html` + `report.md`）
  3. 渲染后路径回写 `IntelligenceFeed.html_report_path` / `md_table_path`
  4. 渲染失败不中断主流程（scheduler try-except 隔离）
- **证据入口**：
  - `backend/apps/intelligence/services/report_service.py`
  - `backend/apps/intelligence/templates/report.html`
  - `backend/apps/intelligence/templates/report.md`
  - `backend/apps/intelligence/tests/test_report_service.py`
- **状态**：Done
- **代码来源**：根项目 `004-llm-intel-pipeline`

---

## MB-005：NFR LLM 延迟/成本基线

- **project 落点**：`nfr.md`（补充 LLM 延迟/成本 NFR 基线）
- **状态**：Not Done
- **缺口**：V 阶段未执行，LLM 实测延迟（3 次调用总计）与 token 成本基线尚无数据
- **计划**：V 阶段执行后，将 LLM 延迟基线（3 次调用总计 < Xs）和 token 成本（单 URL < Y tokens）写入 `nfr.md`

---

## MB-006：intelligence-api API Contract 更新

- **project 落点**：`components/intelligence-api.md#api-contract`
- **不变量摘要**：
  1. `GET /view/html/{id}`：HTML 报告在线预览（inline，`Content-Type: text/html`），文件不存在返回 404
  2. `GET /api/feeds/{id}/preview_html`：同上，API 路由入口
- **证据入口**：
  - `backend/apps/intelligence/views.py`（`FeedHtmlPreviewView`）
  - `backend/config/urls.py`（根路由 `/view/html/<id>`）
  - `backend/apps/intelligence/urls.py`（API 路由 `/api/feeds/<id>/preview_html`）
  - `backend/apps/intelligence/tests/test_api.py`（4 个 HTML 预览测试）
- **状态**：Done
- **代码来源**：根项目 `004-llm-intel-pipeline`

---

## MB-007：Ops 更新

- **project 落点**：`ops/index.md`
- **新增内容**：
  1. LLM 配置项（`.env`：LLM_API_KEY / LLM_BASE_URL / LLM_MODEL / LLM_TEMPERATURE / LLM_MAX_TOKENS）
  2. LLM 依赖（instructor / pydantic / jinja2 / openai）
  3. 报告产物路径（`{项目根}/data/reports/`）
  4. HTML 预览入口（`/view/html/{id}`）
- **证据入口**：
  - `backend/.env`（gitignored）
  - `backend/requirements/base.txt`
  - `backend/config/settings.py`（LLM 配置读取）
- **状态**：Done
- **代码来源**：根项目 `004-llm-intel-pipeline`

---

## MB-008：Registry 更新

- **project 落点**：`index.md`
- **状态**：Done
