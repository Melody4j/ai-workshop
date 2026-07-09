# Ops Index

## Run

- 后端迁移：`/Users/melody/code/ai-workshop/.venv/bin/python backend/manage.py migrate`
- 后端启动：`/Users/melody/code/ai-workshop/.venv/bin/python backend/manage.py runserver`
- 前端启动：`npm --prefix frontend run dev`
- Playwright 浏览器安装（首次）：`playwright install chromium`

## Verify

- Django check：`/Users/melody/code/ai-workshop/.venv/bin/python backend/manage.py check`
- 后端测试（当前可靠入口）：`/Users/melody/code/ai-workshop/.venv/bin/python backend/manage.py test apps.intelligence.tests`
- 后端测试（排除 E2E 网络测试）：`/Users/melody/code/ai-workshop/.venv/bin/python backend/manage.py test apps.intelligence.tests --exclude-tag=e2e`
- 前端构建：`npm --prefix frontend run build`

## Dependencies

- 依赖清单：[backend/requirements/base.txt](../../../backend/requirements/base.txt)
- 新增依赖（Spec 003）：django-apscheduler、httpx、html2text、beautifulsoup4、playwright、croniter
- 新增依赖（Spec 004）：instructor、pydantic、jinja2、openai
- 新增依赖（Spec 006）：无（复用 instructor + pydantic）

## Scheduler 运维

- 调度注册入口：`backend/apps/intelligence/apps.py` ready() hook
- 启动条件：`RUN_MAIN=true`（runserver worker 进程）
- 生产环境限制：gunicorn/uwsgi 不设 `RUN_MAIN`，scheduler 不会自动启动；多 worker 部署会重复触发
- 采集文件存储：`{项目根}/data/snapshots/{project_id}/{YYYYMMDD}/{HHMMSS}_{domain}.{ext}`
- LLM 降噪文件存储：`{项目根}/data/snapshots/{project_id}/{YYYYMMDD}/llm_{HHMMSS}_{domain}.md`（`llm_` 前缀标识）
- APScheduler 日志级别：`WARNING`（Spec 006 调整，减少调度噪声）
- 报告产物存储：`{项目根}/data/reports/`

## Prompt 优化运维（Spec 006 新增）

- 优化服务：`backend/apps/intelligence/services/prompt_optimizer_service.py`
- 触发方式：评分=-1 自动触发（threading 异步）或 `POST /api/feeds/{id}/optimize_prompt` 手动触发
- Prompt 文件（可覆盖）：`backend/prompts/intel_system.md` / `backend/prompts/intel_user.md`
- 版本管理：Django Admin → PromptVersion（查看历史版本 / optimization_reason / feed 关联）
- 回滚操作：从 PromptVersion 记录复制 content 回对应 prompt 文件（手动操作）
- 优化失败处理：threading 内 try-except 捕获，logger.error 记录，不影响评分保存

## LLM 配置

- 配置文件：`backend/.env`（gitignored，不入库）
- 配置项：`LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL` / `LLM_TEMPERATURE` / `LLM_MAX_TOKENS`
- 读取入口：`backend/config/settings.py`（从 `os.environ` 读取）
- LLM 服务：`backend/apps/intelligence/services/llm_service.py`（3 次情报链路调用 + 1 次 prompt 优化调用）
- 重试机制：3 次 / 30s 间隔（`backend/apps/intelligence/services/retry.py`）

## 飞书推送运维

- 配置项：`SITE_BASE_URL`（环境变量，默认 `http://localhost:5173`），用于飞书卡片按钮绝对 URL
- 推送服务：`backend/apps/intelligence/services/feishu_service.py`
- 手动推送 API：`POST /api/feeds/{id}/push`（仅 CHANGED feed 可推送）
- MD 下载 API：`GET /api/feeds/{id}/download_md`
- HTML 预览：`GET /view/html/{id}`（inline，`text/html`）或 `GET /api/feeds/{id}/preview_html`
- 推送重试：2 次重试间隔 30s（同步 sleep，不引入消息队列）
- 推送状态追踪：`IntelligenceFeed.push_status`（NOT_PUSHED / PUSHED / PUSH_FAILED）

## Evidence

- [README.md](../../../README.md)
- [frontend/package.json](../../../frontend/package.json)
- [backend/requirements/base.txt](../../../backend/requirements/base.txt)
- [backend/apps/intelligence/tests/test_api.py](../../../backend/apps/intelligence/tests/test_api.py)
- [backend/apps/intelligence/tests/test_models.py](../../../backend/apps/intelligence/tests/test_models.py)
- [backend/apps/intelligence/tests/test_scheduler_service.py](../../../backend/apps/intelligence/tests/test_scheduler_service.py)
- [backend/apps/intelligence/tests/test_feishu_service.py](../../../backend/apps/intelligence/tests/test_feishu_service.py)
- [backend/apps/intelligence/tests/test_prompt_optimizer_service.py](../../../backend/apps/intelligence/tests/test_prompt_optimizer_service.py)
- [backend/apps/intelligence/tests/test_llm_pipeline_e2e.py](../../../backend/apps/intelligence/tests/test_llm_pipeline_e2e.py)
- [backend/apps/intelligence/tests/test_llm_service.py](../../../backend/apps/intelligence/tests/test_llm_service.py)
- [verification/report-2026-07-08-unknown.md](../../specs/001-competitive-intel-agent/verification/report-2026-07-08-unknown.md)

## Evidence Gaps

- 缺口：README 默认后端测试命令当前不可靠
  - 影响：项目级验证入口需显式指向 `apps.intelligence.tests`
- 缺口：未建立 CI / rollback / monitoring 权威入口
  - 影响：ops 目前仅能覆盖本地开发与最小验证
- 缺口：生产环境 scheduler 启动方案未落地
  - 影响：MVP 阶段仅支持 runserver 本地开发；生产部署需另行处理 scheduler 启动与多 worker 互斥

