# Spec 008：Vercel 部署与架构适配

## 原始需求

将 dev 分支的代码部署到 Vercel，编写 GitHub CI/CD 脚本（dev 分支），配置信息脱敏，env 内容支持从服务器环境变量中设置。

## 约束

1. 代码部署不使用 Docker 形式，GitHub CI/CD 脚本直接运行代码构建和部署
2. 通过 GitHub CI/CD 脚本部署到 Vercel（使用 Vercel CLI）
3. 配置信息全部从环境变量读取（SECRET_KEY、DEBUG、ALLOWED_HOSTS、DATABASES、LLM/Firecrawl 配置等）

## 技术方案（已澄清）

### 平台：Vercel

当前项目是 Django 单体应用，使用 SQLite + APScheduler + 本地文件存储。Vercel 的 serverless 架构与当前项目存在 7 个致命阻断项，需要进行大规模架构重构。

### 调度器：Inngest 替代 BackgroundScheduler

- 当前：django-apscheduler 的 BackgroundScheduler 每 5 秒轮询所有项目的 next_run_at
- 目标：引入 Inngest（https://www.inngest.com），Inngest Cron 每分钟触发 run_scan，单次执行上限 5 分钟（免费 tier 25,000 次/月）
- 影响：scheduler.py、apps.py 需要重构，新增 Inngest webhook 端点，移除 django-apscheduler

### 数据库：Vercel Postgres 替代 SQLite

- 当前：SQLite 3 (WAL)，本地文件 db.sqlite3
- 目标：Vercel Postgres（基于 Neon，免费 tier 60h 计算/月）
- 影响：settings.py DATABASES 配置、Django migrations 需要适配 Postgres、SQLite 触发器（append-only 约束）需要改为 Postgres 触发器或应用层约束

### 文件存储：Vercel Blob 替代本地磁盘

- 当前：快照文件（raw_html / clean_md）和报告文件（html / md）写入本地 data/ 目录，DB 存储绝对路径
- 目标：Vercel Blob 存储，DB 存储 Blob URL
- 影响：file_storage.py、report_service.py、views.py（文件读取返回报告）均需重构

### 配置脱敏

- SECRET_KEY：从环境变量读取
- DEBUG：从环境变量读取（生产环境必须为 False）
- ALLOWED_HOSTS：从环境变量读取
- DATABASES：从环境变量读取（Vercel Postgres 连接字符串）
- LLM_API_KEY / LLM_BASE_URL / LLM_MODEL / LLM_TEMPERATURE / LLM_MAX_TOKENS：已从环境变量读取，保持不变
- FIRECRAWL_API_KEY / FIRECRAWL_API_URL：已从环境变量读取，保持不变
- SITE_BASE_URL：已从环境变量读取，需补充到 .env.example

### Threading 问题

- 当前：views.py 使用 threading.Thread 做异步扫描和 prompt 优化
- Vercel serverless 函数返回后线程即死
- 方案：改用 Inngest 事件触发（`send()` 触发异步函数），保持异步语义不变

### Firecrawl 轮询超时

- 当前：crawler_service.py 中 Firecrawl 轮询最长 120s
- Vercel Hobby 10s / Pro 60s 超时限制
- 需要考虑 Vercel Pro 方案或异步化处理

## 评估结论

Vercel 部署需要对 4 个核心系统进行重构：
1. 数据库系统（SQLite → Vercel Postgres）
2. 调度系统（BackgroundScheduler → Inngest Cron + 事件触发）
3. 文件存储系统（本地磁盘 → Vercel Blob）
4. 配置系统（硬编码 → 环境变量）

此外还需要处理：
5. Threading 异步执行问题（已通过 Inngest 事件触发解决）
6. Firecrawl 轮询超时问题（Inngest 5 分钟超时覆盖 120s 轮询）
7. GitHub CI/CD 脚本编写
8. vercel.json 配置文件
9. 前端部署（Vue 3 + Vite）

## 澄清记录

### R1-Q1：Vercel 前后端部署架构（2026-07-09）

- 本轮结论：前后端同域部署在同一 Vercel 项目中。后端 Django 作为 Vercel Serverless Function（WSGI 适配），前端 Vue 构建为静态文件。同域部署，`/api` 和 `/view` 路由到 serverless function，`/` 路由到静态前端。
- 本轮新增/更新的约束：
  1. 同一 Vercel 项目，同域部署
  2. 后端需要 WSGI → serverless function 适配（需配置 vercel.json）
  3. 前端 Vue 构建产物（dist/）作为静态资源
  4. Vercel serverless 超时限制：Hobby 10s / Pro 60s（影响整个扫描链路）
- 关键决策：部署架构 = 同域 Serverless + 静态
- 遗留歧义：Vercel serverless 超时 vs 完整扫描链路耗时（采集 + 3次LLM + 渲染 + 推送，可能超过60s）→ 对应验证项 V-001

### R1-Q2：扫描链路耗时评估（2026-07-09）

- 本轮结论：用户判断单次扫描链路不会耗时太久（<60s）。代码分析显示单 URL happy path 约 32-95s，但 `run_scan()` 会遍历所有到期项目的所有 URL，总耗时可能远超 60s。LLM 重试间隔 30s，失败场景耗时显著增加。Firecrawl 轮询超时 120s（快速完成场景 10-30s）。
- 本轮新增/更新的约束：
  1. 用户判断单次扫描在可接受时间内完成
  2. 需升级 Vercel Pro（60s 超时）以覆盖 happy path
  3. run_scan 批量处理所有到期项目的超时风险需通过验证项覆盖
- 关键决策：接受用户判断，超时风险转入验证清单
- 遗留歧义：Vercel Cron 触发 run_scan（全量）还是按项目拆分触发？→ 下轮澄清

### R1-Q3：调度方案（2026-07-09，修订：引入 Inngest）

- 本轮结论：引入 Inngest 替代 Vercel Cron 作为调度系统。Inngest Cron 每分钟触发 run_scan，单次执行上限 5 分钟（免费 tier），远超 Vercel Cron 的 60s 限制。`run_scan()` 内部通过 `next_run_at <= now` 过滤到期项目执行。保留 `cron_matcher.py` 计算各项目 `next_run_at`。
- 本轮新增/更新的约束：
  1. 引入 `inngest` Python SDK（`pip install inngest`），Python 3.10+ 已满足
  2. 新增 Inngest Cron Function，cron 表达式 `* * * * *`（每分钟），调用 `run_scan()`
  3. Django 需暴露 Inngest webhook 端点（如 `/api/inngest`），供 Inngest 平台调用
  4. 移除 `BackgroundScheduler`、`django-apscheduler` 依赖、`apps.py ready()` 中的 `start_scheduler()`
  5. `cron_matcher.py` 保留，仍用于计算各项目的 `next_run_at`
  6. 环境变量新增：`INNGEST_EVENT_KEY`、`INNGEST_SIGNING_KEY`
  7. 本地开发使用 Inngest Dev Server（`npx inngest-cli dev -u http://localhost:8000/api/inngest`）
  8. 不拆分 11 步扫描链路为多步骤，保持 run_scan 整体执行
- 关键决策：Inngest Cron 替代 Vercel Cron + BackgroundScheduler
- 遗留歧义：Threading 异步执行（手动触发扫描 + prompt 优化）在 serverless 中的替代方案 → 下轮澄清

### R1-Q4：Threading 异步执行替代方案（2026-07-09，修订：引入 Inngest）

- 本轮结论：两处 `threading.Thread` 全部改为 Inngest 事件触发异步执行。1) 手动触发项目扫描（`POST /api/projects/{id}/execute`）改为 `inngest_client.send({"name": "app/scan.project", "data": {"project_id": pk}})` 触发 Inngest 异步函数，API 立即返回 202；2) 评分=-1 时 prompt 优化改为 `inngest_client.send({"name": "app/optimize.prompt", "data": {"feed_id": pk}})` 触发 Inngest 异步函数。
- 本轮新增/更新的约束：
  1. 移除 `views.py` 中的 `threading.Thread`、`_async_run_scan`、`_async_optimize_prompts`
  2. 新增 Inngest Function：`scan_project`（事件 `app/scan.project` 触发，调用 `run_scan_for_project`）
  3. 新增 Inngest Function：`optimize_prompt`（事件 `app/optimize.prompt` 触发，调用 `optimize_prompts`）
  4. 手动扫描 API 仍返回 202（Inngest 异步执行，用户不需等待）
  5. 评分=-1 触发的 prompt 优化仍为异步（Inngest 异步执行，用户不需等待）
  6. Inngest 单次执行 5 分钟超时，足够覆盖扫描和优化链路
  7. Inngest 自带重试机制，可替代 `retry.py` 中的重试逻辑（但本次不重构 retry.py，保持现有逻辑）
- 关键决策：Inngest 事件触发替代 threading.Thread，保持异步语义
- 遗留歧义：SQLite → Postgres 迁移策略（现有数据迁移？append-only 约束？）→ 下轮澄清

### R1-Q5：SQLite → Postgres 迁移策略（2026-07-09）

- 本轮结论：开发和生产环境统一使用 Postgres，不再使用 SQLite。开发环境也切换到 Postgres（可以是 Vercel Postgres 或本地 Postgres）。现有 SQLite 数据不迁移，Vercel Postgres 上直接运行 migrations 建空表。
- 本轮新增/更新的约束：
  1. 移除 SQLite 相关配置，DATABASES 统一使用 Postgres
  2. `settings.py` 中 DATABASES 从环境变量读取（`DATABASE_URL` 或 `POSTGRES_URL`）
  3. 需引入 `dj-database-url` 或类似库解析 Postgres 连接字符串
  4. DataSnapshot append-only 约束：SQLite 触发器未实现，Postgres 中需新建触发器或改为应用层约束（建议 Postgres 触发器）
  5. 现有 6 个 migration 需验证在 Postgres 上兼容（主要检查 SQLite 特有语法）
  6. `django_apscheduler` 的 DjangoJobStore 也使用数据库，迁移后需确保 Postgres 兼容
  7. 开发环境也需要本地 Postgres 或连接 Vercel Postgres
- 关键决策：统一 Postgres，不迁移现有数据，append-only 用 Postgres 触发器
- 遗留歧义：Vercel Blob 集成方式（DB 路径字段如何改？文件读写如何改？）→ 下轮澄清

### R1-Q6：Vercel Blob 集成方式（2026-07-09）

- 本轮结论：DB 存储 Vercel Blob URL。文件写入 Vercel Blob 后获取 URL，URL 存入 DB。读取时从 Blob URL 下载或重定向。
- 本轮新增/更新的约束：
  1. `file_storage.py` 重构：`save_snapshot()` 写入 Vercel Blob，返回 Blob URL 存入 DB
  2. `report_service.py` 重构：`render_html()` / `render_md()` 写入 Vercel Blob，返回 Blob URL 存入 DB
  3. `views.py` 重构：`FeedDownloadMdView` 和 `FeedHtmlPreviewView` 从 Blob URL 读取内容或重定向
  4. DB 字段名保持不变（`raw_html_path` / `clean_md_path` / `html_report_path` / `md_table_path`），但语义从本地绝对路径变为 Blob URL
  5. 需引入 Vercel Blob HTTP API（Python 无官方 SDK，使用 REST API + Bearer token）
  6. `BLOB_READ_WRITE_TOKEN` 从环境变量读取
  7. `prompt_loader.py` 的 `save_prompt()` 也需要适配（如果 prompts/ 目录不可写）
- 关键决策：DB 存 Blob URL，字段名不变语义变更
- 遗留歧义：prompt 文件存储（prompts/ 目录在 serverless 中只读）→ 下轮澄清

### R1-Q7：Prompt 文件存储方案（2026-07-09）

- 本轮结论：Prompt 模板全部存入 Vercel Blob。`load_prompt` 从 Blob 读取，`save_prompt` 写入 Blob。初始版本通过 migration 或启动脚本上传。
- 本轮新增/更新的约束：
  1. `prompt_loader.py` 重构：`load_prompt()` 从 Vercel Blob 读取模板，`save_prompt()` 写入 Vercel Blob
  2. `prompts/` 目录中的初始模板文件仍保留在代码仓库中（作为初始化源），但运行时不再直接读取
  3. 需新增初始化脚本或 migration：首次部署时将 `prompts/*.md` 上传到 Vercel Blob
  4. `PROMPTS_DIR` 常量改为从环境变量读取 Blob 路径前缀或直接使用 Blob API
  5. `PromptVersion` 表继续使用（存档历史版本），与 Blob 中的当前版本互补
- 关键决策：Prompt 模板存入 Vercel Blob
- 遗留歧义：GitHub CI/CD 脚本范围（Vercel token/org ID？前后端部署顺序？）→ 下轮澄清

### R1-Q8：GitHub CI/CD 脚本范围（2026-07-09）

- 本轮结论：GitHub Actions 在 dev 分支 push 时执行三步：1) 运行 Django 测试；2) 构建前端（Vue 3 + Vite）；3) 用 Vercel CLI 部署到 Vercel。数据库 migration 不在 CI/CD 中执行（通过 Vercel 构建钩子或手动执行）。
- 本轮新增/更新的约束：
  1. GitHub Actions workflow 文件位于 `.github/workflows/deploy-dev.yml`
  2. 触发条件：push 到 `dev` 分支
  3. 步骤：checkout → setup Python → install deps → run tests → setup Node → build frontend → install Vercel CLI → vercel deploy --prod
  4. GitHub Secrets 需要：`VERCEL_TOKEN`、`VERCEL_ORG_ID`、`VERCEL_PROJECT_ID`
  5. Vercel 环境变量在 Vercel Dashboard 中配置（不在 GitHub Actions 中传递）
  6. 数据库 migration 通过 Vercel build 钩子或部署后手动执行 `python manage.py migrate`
- 关键决策：CI/CD = 测试 + 构建前端 + Vercel CLI 部署
- 遗留歧义：无（澄清完成）
