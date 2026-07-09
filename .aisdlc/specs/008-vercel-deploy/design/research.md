---
title: D1 Research — Vercel 部署与架构适配
status: draft
---

## TL;DR

- **最大风险**：Inngest Python SDK 要求 Django >= 5.0，当前项目使用 Django 4.2+，存在版本兼容性缺口。需升级 Django 或使用 Inngest HTTP API 直连。
- **推荐方向**：升级 Django 到 5.0+（LTS）+ 使用 Inngest SDK 原生 Django 集成 + Vercel Blob 社区 Python 库 `vercel_blob` + 标准 `vercel.json` 配置。
- **已关闭未知项**：4/4（R-01 Inngest+Django、R-02 Vercel Blob Python、R-03 Django WSGI on Vercel、R-04 Migration Postgres 兼容性）。
- **遗留验证项**：2 条（V-009 Django 5.0 升级兼容性、V-010 Vercel 部署保护与 Inngest webhook 冲突）。

## 基本信息

- Date：2026-07-09
- Feature：Vercel 部署与架构适配
- Spec（分支 / ID）：008-vercel-deploy
- 作者：Claude + 用户

## 未知项 → 研究任务映射表

| 未知项 | 类型 | 研究任务编号 | 状态 |
|---|---|---|---|
| Inngest Python SDK 与 Django WSGI 集成模式 | NEEDS CLARIFICATION | T1 (R-01) | 已关闭 → Decision |
| Vercel Blob REST API 的 Python 调用方式 | NEEDS CLARIFICATION | T2 (R-02) | 已关闭 → Decision |
| Vercel Serverless Function 中 Django WSGI 冷启动性能 | 集成点 | T3 (R-03) | 已关闭 → Decision |
| 现有 6 个 migration 中 SQLite 特有语法审计 | 依赖项 | T4 (R-04) | 已关闭 → Decision |

## Research Tasks Completed

### T1. Inngest Python SDK + Django WSGI 集成模式

**Task**: 针对 Vercel serverless 部署场景，研究 Inngest Python SDK 与 Django WSGI 的集成方式，包括 Cron 触发、事件触发、webhook 端点配置。

**研究发现**：
- Inngest Python SDK（v0.5.19）官方支持 Django，提供 `inngest.django.serve()` 方法，返回 `django.urls.resolvers.URLPattern`，直接嵌入 Django URL 路由
- SDK 支持同步（`ContextSync`）和异步（`Context`）两种函数处理器，Django WSGI 同步视图使用 `ContextSync`
- Cron 函数使用 `TriggerCron(cron="* * * * *")` 触发器，标准 5 字段 cron 表达式
- 事件函数使用 `TriggerEvent(event="app/scan.project")` 触发器
- 从 Django 视图触发事件使用 `inngest_client.send_sync(inngest.Event(name=..., data=...))`
- **关键约束**：Inngest Python SDK 要求 Django >= 5.0，当前项目使用 Django 4.2+
- 本地开发使用 Inngest Dev Server：`inngest dev -u http://localhost:8000/api/inngest`
- 环境变量：`INNGEST_EVENT_KEY`（生产）、`INNGEST_SIGNING_KEY`（生产）、`INNGEST_DEV=1`（本地）
- Vercel 部署可通过 Inngest Vercel 集成自动配置环境变量
- Vercel Deployment Protection 可能阻止 Inngest webhook 请求，需禁用或配置 bypass

**Decision**：升级 Django 到 5.0+（LTS），使用 Inngest SDK 原生 Django 集成。

**Rationale**：
- Django 5.2 LTS（2025-04 发布）是当前长期支持版本，Django 4.2 LTS 支持到 2026-04，升级到 5.2 是合理时机
- Inngest SDK 原生 Django 集成（`inngest.django.serve()`）是最简洁的方案，自动处理签名校验、路由注册
- `send_sync()` 方法与 Django WSGI 同步视图完美匹配，无需 ASGI
- 使用 SDK 比 HTTP API 直连更可靠（自动重试、签名校验、错误处理）

**Alternatives considered**：
- 方案 A：不升级 Django，使用 Inngest HTTP API 直连（`httpx.post("https://inn.gs/e/{key}", json=...)`）。不选原因：需要手动实现签名校验、webhook 端点、函数注册逻辑，复杂度高且易出错。
- 方案 B：不升级 Django，降级 Inngest SDK 到支持 Django 4.x 的版本。不选原因：未确认是否存在支持 4.x 的版本，且旧版本可能缺少关键功能和安全修复。
- 方案 C：放弃 Inngest，回退 Vercel Cron + 同步执行。不选原因：60s 超时限制无法覆盖完整扫描链路，且用户已选择 Inngest 方案。

**Evidence**：
- Inngest Python SDK PyPI：https://pypi.org/project/inngest/
- Inngest Django 示例：https://github.com/inngest/inngest-py/tree/main/examples/django
- Inngest 文档：https://www.inngest.com/docs
- Django 版本支持路线图：https://www.djangoproject.com/download/

### T2. Vercel Blob REST API Python 调用方式

**Task**: 研究 Vercel Blob 存储在 Python 环境中的调用方式（无官方 Python SDK），包括上传、下载、删除、列表操作。

**研究发现**：
- Vercel Blob REST API 基地址：`https://blob.vercel-storage.com`
- 认证方式：Bearer token（`Authorization: Bearer {BLOB_READ_WRITE_TOKEN}`）
- 社区 Python 库 `vercel_blob`（v0.4.2，PyPI），活跃维护，支持 put/get/delete/list/head/copy
- 上传：`vercel_blob.put(pathname, content_bytes, opts)` → 返回 `{"url": "...", "downloadUrl": "...", "pathname": "...", "contentType": "..."}`
- 下载：直接 `requests.get(blob_url)` 读取内容（公共 store 无需认证）
- 删除：`vercel_blob.delete(blob_url)` 支持单个或批量
- 文件组织：通过 pathname 中的 `/` 隐式创建目录结构（如 `snapshots/1/20240101_raw.html`）
- 公共 store：URL 可直接被浏览器访问，适合 HTML 报告预览
- 文件大小限制：单次 PUT ~4.5MB，multipart 上传支持到 5TB（本项目文件 2KB-100KB，远在限制内）
- 缓存：更新/删除后 CDN 传播最多 60s

**Decision**：使用社区 Python 库 `vercel_blob`（`pip install vercel_blob`）作为 Vercel Blob 客户端。

**Rationale**：
- 社区库 `vercel_blob` 封装了所有需要的操作（put/get/delete/list），API 简洁
- 直接使用 REST API 也可行，但库封装减少了重复代码和错误处理
- 公共 store 模式下，Blob URL 可直接被浏览器访问，无需代理即可实现 HTML 报告预览
- 文件大小远在限制内，无需 multipart

**Alternatives considered**：
- 方案 A：直接使用 REST API（requests + Bearer token）。不选原因：需手动处理认证、错误重试、响应解析，代码冗余。
- 方案 B：使用 AWS S3 + boto3。不选原因：需额外 AWS 账号，与 Vercel 集成不如 Vercel Blob 原生。
- 方案 C：使用 Cloudflare R2。不选原因：需额外 Cloudflare 账号，增加复杂度。

**Evidence**：
- `vercel_blob` PyPI：https://pypi.org/project/vercel_blob/
- Vercel Blob 文档：https://vercel.com/docs/storage/vercel-blob
- Vercel Blob REST API 参考：https://vercel.com/docs/storage/vercel-blob/quickstart

### T3. Vercel Serverless Function Django WSGI 冷启动与配置

**Task**: 研究 Django WSGI 应用在 Vercel Serverless 上的部署配置、冷启动性能、静态文件服务、环境变量处理。

**研究发现**：
- Vercel 自动检测 Django（发现 `manage.py` → 读取 `DJANGO_SETTINGS_MODULE` → 使用 `WSGI_APPLICATION`）
- `vercel.json` 配置 `rewrites` 将 `/api/*`、`/view/*`、`/admin/*` 路由到 Django WSGI，其余路径服务 Vue 静态文件
- Vercel 在构建时自动运行 `collectstatic`
- 冷启动预期 1-3s（Python + Django），Fluid Compute（2025-04 后新项目自动启用）提供字节码缓存减少冷启动
- 超时限制：Hobby 300s / Pro 800s（远超之前认为的 60s）
- 内存：Hobby 1GB / Pro 2GB 或 4GB
- `load_dotenv()` 在 Vercel 上无需使用（Vercel 直接注入环境变量到 `os.environ`），本地开发可用 `.env.local`
- Bundle 大小限制 500MB，需用 `excludeFiles` 排除测试文件
- 数据库 migration 需通过 CI 或手动执行，不能在 serverless 函数内执行
- Django Admin 在 Vercel 上可用，但冷启动时可能较慢
- `vercel.json` 需配置 `functions` 的 `maxDuration`（Inngest webhook 端点需较长超时）

**关键发现**：Vercel Hobby/Pro 的 serverless 超时实际上是 300s/800s，**远超之前评估的 10s/60s**。这意味着：
- Inngest 函数的 5 分钟（300s）超时与 Vercel Hobby 的 300s 一致
- 完整扫描链路（32-95s happy path）在 Vercel 上完全可行
- 之前的超时风险评估过于保守

**Decision**：使用 `vercel.json` 配置 Django WSGI + Vue 静态文件同域部署，无需额外优化冷启动。

**Rationale**：
- Vercel 原生支持 Django 自动检测和部署，配置简单
- 300s 超时远超扫描链路需求，无需担心超时
- Fluid Compute 减少冷启动影响
- `rewrites` 规则实现同域路由，前端无需 CORS 配置

**Alternatives considered**：
- 方案 A：使用 ASGI 适配。不选原因：项目当前使用 WSGI，ASGI 改造范围大且无明确收益。
- 方案 B：前后端分两个 Vercel 项目。不选原因：需配置 CORS，增加复杂度。
- 方案 C：使用 Railway 部署后端。不选原因：用户坚持 Vercel。

**Evidence**：
- Vercel Python/Django 文档：https://vercel.com/docs/functions/runtimes/python
- Vercel 函数限制：https://vercel.com/docs/functions/limitations
- Fluid Compute 文档：https://vercel.com/docs/functions/fluid-compute
- Vercel Django 部署指南：https://vercel.com/guides/deploy-django-to-vercel

### T4. 现有 Migration Postgres 兼容性审计

**Task**: 审计现有 6 个 Django migration 文件，检查是否有 SQLite 特有语法导致 Postgres 不兼容。

**研究发现**：
- 6 个 migration 全部使用标准 Django ORM 操作（CreateModel / AddField / RemoveField），无 `RunSQL` 原始 SQL
- 无 SQLite 特有语法（无 AUTOINCREMENT、无 PRAGMA、无 sqlite 函数）
- `JSONField` 使用 2 处（`competitor_urls` / `competitor_contexts`），Django JSONField 在 Postgres 上使用原生 `jsonb`，完全兼容
- DataSnapshot append-only 触发器：migrations 中未包含任何触发器定义（当前也未在 SQLite 中实现），需在 Postgres 中新建
- 标准字段类型（BigAutoField / CharField / TextField / DateTimeField / URLField / BooleanField / SmallIntegerField / IntegerField / ForeignKey）全部 Postgres 兼容
- `django_apscheduler` 的 DjangoJobStore 表也通过标准 migration 创建，Postgres 兼容

**Decision**：所有 migration 无需修改，可直接在 Postgres 上运行 `python manage.py migrate`。

**Rationale**：
- 6 个 migration 全部使用标准 Django ORM 操作，无数据库特有语法
- JSONField 在 Postgres 上表现更好（原生 jsonb 查询性能优于 SQLite text 存储）
- 唯一需要新增的是 DataSnapshot append-only Postgres 触发器（通过新 migration 的 RunSQL 创建）

**Alternatives considered**：
- 方案 A：重写所有 migration。不选原因：无必要，现有 migration 完全兼容。
- 方案 B：使用 Django 的 `makemigrations` 重新生成。不选原因：会丢失 migration 历史，影响生产升级。

**Evidence**：
- `backend/apps/intelligence/migrations/0001_initial.py` ~ `0006_diff_text_promptversion.py`（全部审计通过）
- `backend/apps/intelligence/models.py`（JSONField 使用确认）
- Django JSONField 文档：https://docs.djangoproject.com/en/4.2/ref/models/fields/#jsonfield

## 风险与验证清单

> 以下未知项无法在本轮 D1 完全关闭，需在 I2 实现阶段验证。

- V-009：Django 5.0+ 升级兼容性验证
  - 风险/假设：Django 4.2 → 5.2 升级可能引入 breaking changes（如 `USE_L10N` 移除、`DEFAULT_FILE_STORAGE` 改名等）
  - 方法：升级 Django 版本后运行全部测试套件（14 个测试模块），检查 deprecation warnings 和 breaking changes
  - 成功/失败信号：全部测试通过 + 无 breaking change 报错 = 成立；任一测试失败或 import error = 不成立
  - Owner：DEV
  - 截止：I2 第 1 批次结束前
  - 触发动作：不成立则逐项修复 breaking changes 或回退到 Django 4.2 + Inngest HTTP API 直连方案

- V-010：Vercel Deployment Protection 与 Inngest webhook 冲突
  - 风险/假设：Vercel Deployment Protection（Vercel Access）可能阻止 Inngest 平台对 `/api/inngest` webhook 的请求
  - 方法：部署到 Vercel 预览环境，在 Inngest Dashboard 注册 webhook URL，触发测试事件
  - 成功/失败信号：Inngest 能成功调用 webhook 并触发函数 = 成立；Inngest 收到 403/401 = 不成立
  - Owner：DEV
  - 截止：I2 第 3 批次结束前
  - 触发动作：不成立则禁用 Deployment Protection 或配置 Vercel Protection Bypass header

## 对 D2 的可引用输入

- **调度系统**：使用 Inngest SDK `inngest.django.serve()` 注册 webhook 端点，`TriggerCron` 定义 Cron 函数，`TriggerEvent` 定义事件函数，`send_sync()` 从视图触发事件。需先升级 Django 到 5.0+。
- **文件存储**：使用 `vercel_blob` Python 库（`pip install vercel_blob`），公共 store 模式，`put()` 上传返回 URL，`requests.get(url)` 读取内容。pathname 组织目录结构。
- **部署配置**：`vercel.json` 配置 `rewrites` 路由 `/api/*`、`/view/*`、`/admin/*` 到 Django WSGI，`outputDirectory` 指向 `frontend/dist`。`functions.maxDuration` 设为 300（Hobby）或更高（Pro）。
- **数据库**：所有 migration 兼容 Postgres，无需修改。新增 1 个 migration 创建 DataSnapshot append-only Postgres 触发器（PL/pgSQL）。需安装 `psycopg2-binary`。
- **环境变量**：`INNGEST_EVENT_KEY`、`INNGEST_SIGNING_KEY`、`BLOB_READ_WRITE_TOKEN`、`DATABASE_URL`、`DJANGO_SECRET_KEY` 等。Vercel Dashboard 配置，或通过 Inngest Vercel 集成自动注入。
- **超时限制修正**：Vercel Hobby 300s / Pro 800s（非之前认为的 10s/60s），扫描链路超时风险大幅降低。Inngest 5 分钟（300s）与 Hobby 一致。
