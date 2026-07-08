# Ops Index

## Run

- 后端迁移：`/Users/melody/code/ai-workshop/.venv/bin/python backend/manage.py migrate`
- 后端启动：`/Users/melody/code/ai-workshop/.venv/bin/python backend/manage.py runserver`
- 前端启动：`npm --prefix frontend run dev`

## Verify

- Django check：`/Users/melody/code/ai-workshop/.venv/bin/python backend/manage.py check`
- 后端测试（当前可靠入口）：`/Users/melody/code/ai-workshop/.venv/bin/python backend/manage.py test apps.intelligence.tests`
- 前端构建：`npm --prefix frontend run build`

## Evidence

- [README.md](../../../README.md)
- [frontend/package.json](../../../frontend/package.json)
- [backend/apps/intelligence/tests/test_api.py](../../../backend/apps/intelligence/tests/test_api.py)
- [backend/apps/intelligence/tests/test_models.py](../../../backend/apps/intelligence/tests/test_models.py)
- [verification/report-2026-07-08-unknown.md](../../specs/001-competitive-intel-agent/verification/report-2026-07-08-unknown.md)

## Evidence Gaps

- 缺口：README 默认后端测试命令当前不可靠
  - 影响：项目级验证入口需显式指向 `apps.intelligence.tests`
- 缺口：未建立 CI / rollback / monitoring 权威入口
  - 影响：ops 目前仅能覆盖本地开发与最小验证
