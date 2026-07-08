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

## Scheduler 运维

- 调度注册入口：`backend/apps/intelligence/apps.py` ready() hook
- 启动条件：`RUN_MAIN=true`（runserver worker 进程）
- 生产环境限制：gunicorn/uwsgi 不设 `RUN_MAIN`，scheduler 不会自动启动；多 worker 部署会重复触发
- 采集文件存储：`{项目根}/data/snapshots/{project_id}/{YYYYMMDD}/{HHMMSS}_{domain}.{ext}`

## Evidence

- [README.md](../../../README.md)
- [frontend/package.json](../../../frontend/package.json)
- [backend/requirements/base.txt](../../../backend/requirements/base.txt)
- [backend/apps/intelligence/tests/test_api.py](../../../backend/apps/intelligence/tests/test_api.py)
- [backend/apps/intelligence/tests/test_models.py](../../../backend/apps/intelligence/tests/test_models.py)
- [backend/apps/intelligence/tests/test_scheduler_service.py](../../../backend/apps/intelligence/tests/test_scheduler_service.py)
- [verification/report-2026-07-08-unknown.md](../../specs/001-competitive-intel-agent/verification/report-2026-07-08-unknown.md)

## Evidence Gaps

- 缺口：README 默认后端测试命令当前不可靠
  - 影响：项目级验证入口需显式指向 `apps.intelligence.tests`
- 缺口：未建立 CI / rollback / monitoring 权威入口
  - 影响：ops 目前仅能覆盖本地开发与最小验证
- 缺口：生产环境 scheduler 启动方案未落地
  - 影响：MVP 阶段仅支持 runserver 本地开发；生产部署需另行处理 scheduler 启动与多 worker 互斥

