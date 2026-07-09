# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 仓库现状

Django 单体应用，后端位于 `backend/`。已实现：采集调度（Spec 003）、LLM 系统接入与竞品分析全流程（Spec 004）。技术栈为 Python。所有架构与不变量均来自 `.aisdlc/specs/001-competitive-intel-agent/requirements/`（raw / solution / prd / prototype 四份文档为唯一决策入口）。

**已实现模块：**
- `apps/intelligence/services/crawler_service.py`：httpx + BS 去噪采集
- `apps/intelligence/services/scheduler_service.py`：全局扫描 + LLM 全链路串接
- `apps/intelligence/services/llm_service.py`：3 次独立 LLM 调用（降噪 / diff判断 / 情报生成）
- `apps/intelligence/services/diff_service.py`：difflib 文本 diff + 8000 字符截断
- `apps/intelligence/services/report_service.py`：Jinja2 HTML/MD 报告渲染
- `apps/intelligence/services/file_storage.py`：快照文件落盘（raw_html / BS clean_md / LLM clean_md）
- `apps/intelligence/services/llm_client.py`：OpenAI 兼容 client + IntelResult Pydantic schema
- `apps/intelligence/services/retry.py`：通用重试装饰器（3次/30s/耗尽 raise LLMError）
- `apps/intelligence/services/prompt_loader.py`：Prompt 模板加载（str.replace 注入）
- `prompts/`：4 套 Prompt 模板（denoise / diff_judge / intel_system / intel_user）
- `templates/reports/`：Jinja2 报告模板（report.html.j2 / report.md.j2）

**LLM 配置：** `backend/.env`（gitignored），参考 `backend/.env.example`

## 项目背景（Spec 001：自动化竞争情报监控代理）

**目标用户**：个人产品经理 / 独立开发者，单用户场景，无多租户。

**一句话目标**：用户配置自有产品锚定文档 + 5-10 个竞品 URL 后，系统日级采集 → html2text + LLM 降噪 → diff 熔断 → 单次 LLM 情报生成（注入产品锚定）→ 有变化推飞书+存报告 / 无变化熔断。

## 技术栈（已定稿，不要替换）

| 层 | 选型 |
|---|---|
| 语言 | Python 3.10+ |
| Web 框架 | Django 4.2+ |
| 数据库 | SQLite 3 (WAL) |
| 采集 | httpx（优先）+ Playwright（SPA 兜底，可选） |
| HTML→MD | html2text |
| LLM 编排 | instructor + Pydantic（单次直出） |
| 模板 | Jinja2 |
| 调度 | django-apscheduler（cron 表达式，日级） |
| 通知 | 飞书群机器人 webhook（高级卡片） |

部署形态：**Django 单体应用**（Django Admin 后台 + 独立 HTML 消费页 + 飞书卡片）。

## 核心执行链路（6 步最小闭环）

1. **配置**（Django Admin）：登记 `self_product_doc` + 5-10 个竞品 URL（JSON 数组 `[{url,title}]`）+ 飞书 webhook + cron
2. **采集**（django-apscheduler 日级触发）：httpx GET → html2text 转 MD → **LLM 语义降噪**（独立调用）→ 存快照（append-only）
3. **变化识别**：取上一条快照 diff → diff 为空 **熔断**（写 `NO_CHANGE`，零推送零 LLM）；diff 非空进入下一步
4. **情报生成**（单次 LLM 直出）：注入 diff 片段 + `self_product_doc` + 最近 5 条 Negative Few-Shot → 输出 4 字段（变化摘要 / 战略意图 / 行动建议 / 证据 diff）
5. **渲染分发**：Jinja2 渲染 HTML 网页 + MD 表格落盘；推送飞书高级卡片（有变化即推，无分级）
6. **反馈**：用户点"毫无意义"+评语 → 下次 LLM 推理前注入 Negative Few-Shot

## 关键不变量（实现时必须遵守）

1. 快照 append-only——SQLite 触发器硬约束 `UPDATE/DELETE → RAISE(ABORT)`
2. 降噪 LLM、diff 判断 LLM 与情报生成 LLM 是**独立三次调用**，不得合并
3. 情报生成 LLM 仅 LLM diff 判断有意义时触发，不得全量调用
4. 情报输出固定 4 字段，**不含价值度字段**（修订-3 已移除）
5. has_change=True → 推飞书 + 存报告；has_change=False → 熔断退出
6. 收件箱仅展示 `job_status=CHANGED`；`NO_CHANGE`/`ERROR_CRAWL` 仅 Django Admin 可见
7. httpx 优先，Playwright 仅对 SPA 按需降级，不得默认全量 Playwright
8. 调度限 django-apscheduler 日级，不引入消息队列
9. 每个监控任务必须关联 `self_product_doc`（Nullable，允许只上传文件），情报生成时注入 prompt
10. `competitor_urls` 必须为 JSON 数组，每项 `{"url":"...","title":"..."}`，title 标识内容来源
11. Negative Few-Shot 注入上限最近 5 条，超过取最近 5 条
12. `refined_rules` 字段 P1 占位，MVP 不写入
13. 证据 diff 嵌入 `change_summary` 或报告渲染素材，**不独立为 DB 字段**

## 数据模型（3 张表）

- **MonitorProject**：监控项目配置（`self_product_doc` Nullable / `competitor_urls` JSON / `feishu_webhook` / `cron` / `refined_rules` 占位 / `is_active`）
- **DataSnapshot**：快照表（append-only，存 `raw_html_path` + `clean_md_path`（指向 LLM 降噪后 MD）+ `fetch_time`）
- **IntelligenceFeed**：情报表（`job_status` ∈ {CHANGED, NO_CHANGE, ERROR_CRAWL} + 4 字段 + `user_feedback` + `user_comment` + `html_report_path` + `md_table_path`）

## 页面与入口

- **Django Admin**：MonitorProject 配置页（P-001）、IntelligenceFeed 列表页/调度日志（P-002，含 NO_CHANGE/ERROR_CRAWL 筛选）
- **独立 HTML 网页**：收件箱列表页 `/`（P-003，仅 CHANGED）、情报详情页 `/view/intel/{id}`（P-004，含反馈按钮）、HTML 报告预览页 `/view/html/{id}`（P-005）
- **飞书卡片**（D-001）：变化摘要正文 + "在线预览"按钮（跳转 P-005）+ "下载 MD"按钮

## Spec 002：爬虫可行性验证（已完成）

位于 `.aisdlc/specs/002-crawler-feasibility-test/requirements/raw.md`，验证 httpx + html2text + 规则去噪（**不用 LLM**）的最小 MVP。规则：
- httpx 优先；当 markdown < 3 行时降级 Playwright（JS 注入）
- 去噪用 BeautifulSoup 去除 nav/footer/script/style，不使用 LLM
- 去噪后 MD 输出到 `/Users/melody/Desktop/ai-workshop-test`，每站一个 `.md`，文件名为域名
- 测试目标站点：ihuiwa.com、x-design.com、piccopilot.com、weshop.ai、bandy.ai、thenewblack.ai、lovable.dev

## Spec 003：采集调度层（已完成）

位于 `.aisdlc/specs/003-scheduler-crawler/`，实现 django-apscheduler 日级调度 + httpx/BS 采集 + DataSnapshot append-only 入库。核心组件：`scheduler_service.py`（run_scan 全局扫描）、`crawler_service.py`（fetch_and_clean）、`file_storage.py`（快照落盘）、`cron_matcher.py`（cron 表达式解析）。

## Spec 004：LLM 系统接入与竞品分析全流程（已完成）

位于 `.aisdlc/specs/004-llm-intel-pipeline/`，在 Spec 003 采集调度层之上补齐 LLM 链路。核心链路：
1. BS 去噪 → LLM 语义降噪（第 1 次 LLM 调用）→ `clean_md_path` 指向 LLM 版本
2. 文本 diff（difflib）→ diff 为空熔断 `NO_CHANGE`
3. LLM diff 判断（第 2 次 LLM 调用）→ 无意义熔断 `NO_CHANGE`
4. LLM 情报生成（第 3 次 LLM 调用，instructor + Pydantic）→ 4 字段直出
5. IntelligenceFeed(CHANGED) 入库 + Jinja2 HTML/MD 报告落盘

**关键设计决策：**
- OpenAI 兼容 API（覆盖 OpenAI/DeepSeek/通义/Moonshot），不引入多 provider
- 3 次 LLM 调用独立，各有 @retry（3次/30s），耗尽 raise LLMError → ERROR_CRAWL
- 首次爬取跳过 diff（无历史快照），旧格式快照兼容（检测 `llm_` 前缀）
- Negative Few-Shot 注入最近 5 条 `user_feedback=-1` 记录
- `clean_md_path` 语义从 BS 结果覆盖为 LLM 结果（无 DB migration）

## AI SDLC 流程约定

本仓库使用 `.aisdlc/` 目录管理 Spec Pack 流程：
- `.aisdlc/specs/{NNN}-{short-name}/requirements/`：需求侧文档（raw → solution → prd → prototype）
- `.aisdlc/specs/{NNN}-{short-name}/design/`、`implementation/`、`verification/`：设计/实现/验证侧文档
- 每个文档头部的 `status: draft` 等字段标记文档状态
- 需求变更走"修订-N"与"DB-N"裁决记录，**不要直接覆盖原裁决**，新增修订记录并更新不变量

## 关键参考文档入口

- `requirements/raw.md`：原始需求 + R1-Q1~Q8 澄清裁决 + 修订-1~5 + DB-1~4b 裁决
- `requirements/solution.md`：推荐方案 + 备选方案 + V-001~V-018 验证清单 + Impact Analysis（含 13 条不变量）
- `requirements/prd.md`：F-01~F-19 功能清单 + AC-001~AC-017 验收标准 + 规则-1~13
- `requirements/prototype.md`：P-001~P-005 + D-001 页面清单 + T-001~T-028 任务流 + AC→交互节点映射