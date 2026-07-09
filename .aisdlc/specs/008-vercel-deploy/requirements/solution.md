---
title: Vercel 部署与架构适配方案决策（Solutionate）
status: draft
---

> 目的：把"推荐决策 + 备选方案对比 + 决策依据 + 验证清单"落到一份可评审文档里，作为后续 `prd.md` 与 `prototype.md` 的**唯一决策入口**。
>
> 原则：结论先行；只保留支撑决策的最小信息；不写"待确认问题"清单——所有不确定性统一进入"验证清单"（Owner/截止/动作明确）。

## 0. 基本信息

- 需求标识（分支 / ID）：008-vercel-deploy
- 作者 / 参与评审：Claude + 用户
- 状态：draft
- 最后更新：2026-07-09
- 关联链接：raw.md（R1-Q1~Q8 澄清记录 + Inngest 修订）

## 1. 结论摘要（先给结论）

- 一句话目标：将 Django 单体应用部署到 Vercel，适配 serverless 架构（数据库/调度/文件存储/配置全部重构），并通过 GitHub CI/CD 自动化部署。
- 本次 In / Out 的边界：In = Vercel 部署适配（Postgres + Inngest + Blob + 环境变量配置 + CI/CD + vercel.json）；Out = 业务功能变更、前端 UI 重构、数据迁移。
- 推荐方案：Vercel 同域部署（Django Serverless + Vue 静态），4 个核心系统重构——Vercel Postgres 替代 SQLite、Inngest 替代 BackgroundScheduler + Threading、Vercel Blob 替代本地文件存储、环境变量配置脱敏。
- 优先验证点：V-001（Inngest Cron 集成验证）、V-002（Postgres migration 兼容性）、V-003（Vercel Blob 读写验证）。

## 2. 推荐方案

- 方案名：Vercel 全栈适配（Serverless + Inngest + Postgres + Blob）

- 主流程 / 关键机制：
  1. **部署架构**：同一 Vercel 项目，后端 Django 通过 WSGI 适配为 Serverless Function，前端 Vue 构建为静态文件。`/api` 和 `/view` 路由到 serverless，`/` 路由到静态前端。`vercel.json` 配置路由规则和构建命令。
  2. **调度系统**：引入 Inngest（`pip install inngest`），Inngest Cron 每分钟触发 `run_scan()`，单次执行 5 分钟超时（免费 tier 25,000 次/月）。Django 暴露 `/api/inngest` webhook 端点。移除 `django-apscheduler` + `BackgroundScheduler`。
  3. **异步任务**：手动扫描和 Prompt 优化通过 `inngest_client.send()` 触发 Inngest 事件异步函数，API 立即返回 202。替代 `threading.Thread`，保持异步语义。
  4. **数据库**：统一使用 Vercel Postgres（基于 Neon），`DATABASE_URL` 从环境变量读取，引入 `dj-database-url` 解析连接字符串。DataSnapshot append-only 约束用 Postgres 触发器实现。现有 6 个 migration 在 Postgres 上直接运行建空表，不迁移 SQLite 数据。
  5. **文件存储**：快照文件和报告文件写入 Vercel Blob（REST API + Bearer token），DB 存储 Blob URL（字段名不变，语义从本地路径变为 URL）。Prompt 模板也存入 Blob，`load_prompt` 从 Blob 读取，`save_prompt` 写入 Blob。
  6. **配置脱敏**：`SECRET_KEY`、`DEBUG`、`ALLOWED_HOSTS`、`DATABASES` 全部从环境变量读取。Vercel Dashboard 配置环境变量，`.env.example` 更新为完整模板。
  7. **CI/CD**：GitHub Actions 在 dev 分支 push 时执行：测试 → 构建前端 → Vercel CLI 部署。GitHub Secrets 存储 `VERCEL_TOKEN`、`VERCEL_ORG_ID`、`VERCEL_PROJECT_ID`。

- 关键边界/取舍：
  1. **不迁移现有数据**：开发环境 SQLite 数据不迁移到 Postgres，生产从空表开始。代价是丢失开发环境测试数据，但避免 migration 兼容性问题。
  2. **不拆分 11 步扫描链路**：保持 `run_scan` 整体执行，不拆分为 Inngest 多步骤。Inngest 5 分钟超时足够覆盖完整链路。代价是单步失败需整体重试（由 Inngest 重试机制覆盖）。
  3. **DB 字段名不变**：`raw_html_path` / `clean_md_path` / `html_report_path` / `md_table_path` 字段名保持不变，但语义从本地绝对路径变为 Blob URL。代价是代码中字段名的语义可能误导，但避免 migration。
  4. **开发环境也用 Postgres**：统一开发与生产数据库，避免 SQLite/Postgres 行为差异。代价是开发环境需要 Postgres 实例。
  5. **Prompt 模板存入 Blob**：运行时不再读取代码仓库 `prompts/` 目录，改为从 Blob 读取。初始版本需通过初始化脚本上传到 Blob。

- 为什么选它：
  1. Inngest 5 分钟超时 >> Vercel 60s，根本性解决扫描链路超时问题（证据：R1-Q2 + R1-Q3 修订）
  2. Inngest 事件触发完美替代 threading.Thread，保持异步语义且 serverless 兼容（证据：R1-Q4 修订）
  3. 统一 Postgres 消除开发/生产环境差异，降低兼容性风险（证据：R1-Q5）
  4. Vercel Blob 是 Vercel 原生服务，与 Vercel 项目集成最好（证据：R1-Q6）

## 3. 备选方案

### 3.1 备选方案：Railway 部署（零架构重构）

- 核心机制：Django 直接部署到 Railway，支持持久化卷（SQLite 可用）+ background worker（调度器可跑），无需重构数据库/调度/文件存储。
- 主流程：Django app 直接部署 → Railway 提供 persistent volume → SQLite + APScheduler + 本地文件存储原样运行。
- 边界与取舍：不使用 Vercel；不需要 Inngest/Vercel Postgres/Vercel Blob；CI/CD 仍可用 GitHub Actions。
- 适用前提：用户愿意更换部署平台；接受 Railway 的定价模型。
- 不选原因：用户明确坚持 Vercel 部署（R1 用户决策）。

### 3.2 备选方案：Vercel + Vercel Cron + 同步执行（不引入 Inngest）

- 核心机制：使用 Vercel Cron 每分钟触发 run_scan，threading 改为同步执行。需升级 Vercel Pro（60s 超时）。
- 主流程：Vercel Cron → `/api/cron/scan` → run_scan 同步执行 → 手动扫描和 Prompt 优化也同步执行。
- 边界与取舍：不引入 Inngest；手动扫描和 Prompt 优化需用户等待；Vercel Pro 60s 可能不够覆盖完整链路。
- 适用前提：项目少且 LLM 响应快；用户接受同步等待。
- 不选原因：60s 超时风险高（R1-Q2 评估 32-95s）；同步执行用户体验差（R1-Q4 原方案被用户否决）。

### 3.3 备选方案：Vercel + Vercel Cron + 步骤拆分异步化

- 核心机制：将 11 步扫描链路拆分为多个 Vercel Serverless Function，通过 DB 状态机串接，突破 60s 限制。
- 主流程：Cron 触发 → 采集 → DB 标记 → 降噪 → DB 标记 → diff → ... → 推送。
- 边界与取舍：不引入 Inngest；每个步骤独立部署为 serverless function；需要 DB 状态机管理步骤间传递。
- 适用前提：愿意承担高复杂度；对引入外部服务有顾虑。
- 不选原因：复杂度过高（11 个 function + 状态机）；Inngest 已提供更好的多步骤方案且用户选择不拆分。

## 4. 决策依据（证据入口清单）

- `raw.md` R1-Q1：同域 Serverless + 静态部署架构决策
- `raw.md` R1-Q2：扫描链路耗时评估（32-95s happy path，120s Firecrawl 轮询）
- `raw.md` R1-Q3 修订：Inngest Cron 替代 Vercel Cron（5 分钟 >> 60s）
- `raw.md` R1-Q4 修订：Inngest 事件触发替代 threading.Thread
- `raw.md` R1-Q5：统一 Postgres，不迁移数据
- `raw.md` R1-Q6：DB 存 Blob URL，字段名不变
- `raw.md` R1-Q7：Prompt 模板存入 Vercel Blob
- `raw.md` R1-Q8：CI/CD = 测试 + 构建前端 + Vercel CLI 部署
- `.aisdlc/project/components/intelligence-scheduler.md`：调度链路 11 步 + Evidence Gaps（scheduler 生产环境启动问题）
- `.aisdlc/project/components/intelligence-models.md`：DataSnapshot append-only 未实现 + 字段路径语义
- `.aisdlc/project/components/intelligence-api.md`：Threading 异步扫描 + Prompt 优化
- `.aisdlc/project/components/report-service.md`：报告渲染文件路径回写
- `.aisdlc/project/components/llm-service.md`：3 次 LLM 调用独立 + retry 30s 间隔
- `backend/config/settings.py`：SECRET_KEY/DEBUG/ALLOWED_HOSTS 硬编码 + SQLite 配置 + 环境变量使用情况
- `backend/apps/intelligence/services/crawler_service.py`：Firecrawl POLL_TIMEOUT=120s
- `backend/apps/intelligence/services/retry.py`：LLM 重试 3 次/30s 间隔
- `backend/apps/intelligence/views.py`：threading.Thread 两处使用

## 5. 验证清单（V-xxx，可执行）

- V-001：Inngest Cron + Django webhook 集成验证
  - 风险/假设：Inngest Python SDK 与 Django WSGI 集成可能存在异步兼容问题
  - 方法：本地用 Inngest Dev Server（`npx inngest-cli dev -u http://localhost:8000/api/inngest`）验证 webhook 端点响应、Cron 触发、事件 `send()` 触发
  - 成功/失败信号：Cron 每分钟成功触发 run_scan + `send()` 事件成功触发对应函数 = 成立；webhook 404/签名校验失败/异步报错 = 不成立
  - Owner：DEV
  - 截止：I2 第 1 批次结束前
  - 触发动作：不成立则调研 Inngest Django 示例 repo（github.com/inngest/inngest-py/tree/main/examples/django）或回退 Vercel Cron 方案

- V-002：Postgres migration 兼容性验证
  - 风险/假设：现有 6 个 migration 可能包含 SQLite 特有语法（如 JSONField 实现差异）
  - 方法：在 Vercel Postgres 上执行 `python manage.py migrate`，检查每条 migration 是否成功
  - 成功/失败信号：6 条 migration 全部成功 = 成立；任一 migration 报错 = 不成立
  - Owner：DEV
  - 截止：I2 第 1 批次结束前
  - 触发动作：不成立则修复 migration 中的 SQLite 特有语法，新增 Postgres 兼容 migration

- V-003：Vercel Blob 读写验证
  - 风险/假设：Vercel Blob REST API 在 Python 环境中可能存在认证或上传大小限制问题
  - 方法：编写 blob_storage 服务模块，测试上传/下载/删除文件（HTML/MD/Prompt 模板）
  - 成功/失败信号：文件成功上传并获取 URL + 从 URL 下载内容一致 = 成立；上传失败/URL 不可访问/内容不一致 = 不成立
  - Owner：DEV
  - 截止：I2 第 2 批次结束前
  - 触发动作：不成立则调研 Vercel Blob API 限制或回退到外部 S3

- V-004：run_scan 批量超时风险
  - 风险/假设：多个项目同时到期时，run_scan 串行处理所有 URL 可能超过 Inngest 5 分钟超时
  - 方法：模拟 5 个项目 × 5 个 URL = 25 次 `_process_url`，测量总耗时
  - 成功/失败信号：25 次 _process_url 总耗时 < 5 分钟 = 成立；超过 5 分钟 = 不成立
  - Owner：DEV
  - 截止：V 阶段测试
  - 触发动作：不成立则将 run_scan 改为按项目拆分为多个 Inngest 事件

- V-005：Vercel Serverless Function Django WSGI 适配验证
  - 风险/假设：Django WSGI 应用在 Vercel Serverless 环境中可能存在冷启动慢/静态文件服务问题
  - 方法：部署到 Vercel 预览环境，测试 API 响应时间 + 静态文件加载 + Django Admin 可用性
  - 成功/失败信号：API 响应 < 3s（含冷启动）+ 静态文件正常加载 + Admin 可访问 = 成立；冷启动 > 10s 或 Admin 不可用 = 不成立
  - Owner：DEV
  - 截止：I2 第 3 批次结束前
  - 触发动作：不成立则优化 WSGI 配置或调研 ASGI 适配

- V-006：Postgres DataSnapshot append-only 触发器验证
  - 风险/假设：Postgres 触发器语法与 SQLite 不同，需要重新编写
  - 方法：编写 Postgres 触发器 SQL，测试 UPDATE/DELETE 是否被 RAISE 阻止
  - 成功/失败信号：UPDATE/DELETE 被 RAISE(EXCEPTION) 阻止 = 成立；操作成功执行 = 不成立
  - Owner：DEV
  - 截止：I2 第 1 批次结束前
  - 触发动作：不成立则修正触发器 SQL 或回退到应用层约束

- V-007：Prompt 模板初始化到 Blob 验证
  - 风险/假设：首次部署时 prompts/ 目录下的模板需要上传到 Vercel Blob
  - 方法：编写初始化脚本（management command），执行后验证 Blob 中存在所有 4 套模板
  - 成功/失败信号：4 套模板（denoise / diff_judge / intel_system / intel_user）全部在 Blob 中可读 = 成立；任一模板缺失 = 不成立
  - Owner：DEV
  - 截止：I2 第 2 批次结束前
  - 触发动作：不成立则修复初始化脚本或手动上传模板

- V-008：GitHub Actions CI/CD 部署验证
  - 风险/假设：Vercel CLI 在 GitHub Actions 中部署可能需要特定配置
  - 方法：push 到 dev 分支，观察 GitHub Actions 日志和 Vercel 部署状态
  - 成功/失败信号：测试通过 + 前端构建成功 + Vercel 部署成功 = 成立；任一步骤失败 = 不成立
  - Owner：DEV
  - 截止：I2 第 3 批次结束前
  - 触发动作：不成立则检查 Vercel token/org/project ID 配置或调整 workflow

## 6. 迭代记录

- 2026-07-09：初始版本。基于 R1-Q1~Q8 澄清记录产出推荐方案 + 3 个备选方案 + 8 条验证清单 + Impact Analysis。

## 7. Impact Analysis

### 7.1 受影响模块

| 模块 | 影响类型 | 关键不变量 | stale? |
|------|----------|-----------|--------|
| intelligence-models | 修改契约（DB 从 SQLite → Postgres，字段语义从路径 → URL） | DataSnapshot append-only 触发器需 Postgres 重写；字段名不变语义变更 | yes |
| intelligence-scheduler | 修改契约（BackgroundScheduler → Inngest Cron + 事件触发） | 调度链路 11 步不变；next_run_at 计算逻辑不变；移除 apps.py ready() 启动 | yes |
| intelligence-api | 修改契约（threading → Inngest send()；文件读取 → Blob URL） | API 路由不变；手动扫描仍返回 202；评分=-1 仍异步触发优化 | yes |
| report-service | 修改契约（本地文件 → Vercel Blob） | Jinja2 渲染不变；路径回写变为 URL 回写 | yes |
| llm-service | 间接影响（prompt_loader 从文件 → Blob） | 3 次 LLM 调用独立不变；retry 逻辑不变；PromptVersion 表不变 | no |
| frontend-console | 间接影响（API 域名变更，但同域部署无需改 CORS） | API 调用路径不变（相对路径） | no |

### 7.2 需遵守的不变量

- 3 次 LLM 调用独立，不合并（来源：`.aisdlc/project/components/llm-service.md#invariants`）
- 情报输出固定 4 字段，不含价值度字段（来源：`CLAUDE.md` 关键不变量 #4）
- has_change=True → 推飞书 + 存报告；has_change=False → 熔断退出（来源：`CLAUDE.md` 关键不变量 #5）
- 快照 append-only——Postgres 触发器硬约束 UPDATE/DELETE → RAISE(EXCEPTION)（来源：`CLAUDE.md` 关键不变量 #1，原 SQLite 触发器未实现，本次在 Postgres 中实现）
- 每个监控任务必须关联 self_product_doc（来源：`CLAUDE.md` 关键不变量 #9）
- competitor_urls 必须为 JSON 数组，每项 {"url":"...","title":"..."}（来源：`CLAUDE.md` 关键不变量 #10）
- Negative Few-Shot 注入上限最近 5 条（来源：`CLAUDE.md` 关键不变量 #11）
- 收件箱仅展示 job_status=CHANGED（来源：`CLAUDE.md` 关键不变量 #6）
- DB 字段名不变（raw_html_path / clean_md_path / html_report_path / md_table_path），语义从本地路径变为 Blob URL（来源：R1-Q6 决策）

### 7.3 跨模块影响

- 改了 intelligence-scheduler（移除 BackgroundScheduler → Inngest）→ 需关注 intelligence-models（django_apscheduler DjangoJobStore 表将不再使用，需从 INSTALLED_APPS 移除或保留表不删）
- 改了 intelligence-models（SQLite → Postgres）→ 需关注所有使用 ORM 的模块（intelligence-api / intelligence-scheduler / llm-service / report-service），Postgres JSONField 与 SQLite JSONField 实现不同
- 改了 report-service（本地文件 → Vercel Blob）→ 需关注 intelligence-api（FeedDownloadMdView / FeedHtmlPreviewView 从本地读文件改为从 Blob URL 读取）
- 改了 llm-service 的 prompt_loader（文件 → Blob）→ 需关注 prompt_optimizer_service（save_prompt 写入 Blob 而非文件）
- 改了 settings.py（环境变量配置）→ 需关注所有从 settings 读取配置的模块
- 新增 Inngest 集成 → 需关注 vercel.json（Inngest webhook 路由）和 GitHub Actions（Inngest 环境变量不在 CI/CD 中传递）

### 7.4 Context Gaps

- `CONTEXT GAP`：Inngest Python SDK 与 Django 集成的具体代码模式未在本仓库验证 → 建议动作：I2 第 1 批次先做 V-001 验证
- `CONTEXT GAP`：Vercel Blob REST API 的 Python 调用方式未验证（无官方 Python SDK）→ 建议动作：I2 第 2 批次先做 V-003 验证
- `CONTEXT GAP`：Vercel Serverless Function 中 Django WSGI 的冷启动性能未知 → 建议动作：V-005 验证
- `CONTEXT GAP`：现有 6 个 migration 中是否有 SQLite 特有语法未审计 → 建议动作：I2 第 1 批次先做 V-002 验证

## 8. Mini-PRD

- **MVP 范围**：
  - In：Vercel 部署适配（vercel.json + WSGI 适配 + 静态前端）、Vercel Postgres 配置 + migration、Inngest 集成（Cron + 事件触发）、Vercel Blob 集成（快照 + 报告 + Prompt）、配置环境变量化、GitHub Actions CI/CD
  - Out：业务功能变更、前端 UI 重构、数据迁移、Playwright 适配

- **验收标准（AC）**：
  1. push 到 dev 分支 → GitHub Actions 自动运行测试 + 构建前端 + 部署到 Vercel
  2. Vercel 部署后，前端页面可访问，API 可调用
  3. Inngest Cron 每分钟触发 run_scan，到期项目被执行
  4. 手动触发项目扫描 → Inngest 事件触发 → 扫描完成 → 报告可查看
  5. 评分=-1 → Inngest 事件触发 → Prompt 优化完成
  6. 快照文件和报告文件存储在 Vercel Blob，DB 存储 Blob URL
  7. Prompt 模板从 Vercel Blob 读取，优化后写入 Blob
  8. SECRET_KEY / DEBUG / ALLOWED_HOSTS / DATABASE_URL 等从环境变量读取
  9. DataSnapshot append-only 约束在 Postgres 中通过触发器实现
  10. Django Admin 在 Vercel 上可访问

- **交互变化结论**：无前端交互变化。API 接口路径和返回格式不变，仅内部执行机制变更（threading → Inngest）。

- **影响面**：
  - 页面/入口：无新增，现有 P-001~P-005 + D-001 不变
  - 接口：API 路由不变；新增 `/api/inngest` webhook 端点（Inngest 内部使用）
  - 配置：`.env.example` 更新（新增 INNGEST_EVENT_KEY / INNGEST_SIGNING_KEY / BLOB_READ_WRITE_TOKEN / DATABASE_URL 等）；Vercel Dashboard 环境变量配置
  - 依赖：新增 `inngest`、`dj-database-url`；移除 `django-apscheduler`（可选保留用于 DjangoJobStore 表兼容）

- **本地开发环境**：
  - Postgres：`.env` 中配置 `DATABASE_URL` 指向 Vercel Postgres 远程实例或本地 Postgres
  - Vercel Blob：`.env` 中配置 `BLOB_READ_WRITE_TOKEN`，直接连接 Vercel Blob 服务（不做本地适配层）
  - Inngest：本地运行 `npx inngest-cli dev -u http://localhost:8000/api/inngest`
  - Django 单元测试：mock 外部服务（Inngest / Blob），不需要真实连接
  - E2E 测试：需要真实 Postgres + Inngest Dev Server + Vercel Blob 连接
