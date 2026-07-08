# 结构与入口（北极星）

## 项目形态

- 前后端分离单体（split-monolith）：[README.md](../../../README.md)

## 入口（可执行证据）

- 本地启动：
  - 后端：`/Users/melody/code/ai-workshop/.venv/bin/python backend/manage.py migrate`、`/Users/melody/code/ai-workshop/.venv/bin/python backend/manage.py runserver`（证据：[README.md](../../../README.md)、[backend/manage.py](../../../backend/manage.py)）
  - 前端：`npm --prefix frontend install`、`npm --prefix frontend run dev`（证据：[README.md](../../../README.md)、[frontend/package.json](../../../frontend/package.json)）
- 测试：
  - 后端：`/Users/melody/code/ai-workshop/.venv/bin/python backend/manage.py test apps.intelligence.tests`（证据：[backend/apps/intelligence/tests/test_api.py](../../../backend/apps/intelligence/tests/test_api.py)、[backend/apps/intelligence/tests/test_models.py](../../../backend/apps/intelligence/tests/test_models.py)）
  - 前端：`npm --prefix frontend run build`（证据：[frontend/package.json](../../../frontend/package.json)）
- 构建/发布：
  - 前端构建：`npm --prefix frontend run build`（证据：[frontend/package.json](../../../frontend/package.json)）

## 代码地图

- 组件地图：[../components/index.md](../components/index.md)
- 业务地图：[../products/index.md](../products/index.md)

## Evidence Gaps（缺口清单）

- 缺口：项目级 CI / 发布流水线入口缺失
  - 期望补齐到的粒度：可执行的 build / test / deploy 权威入口
  - 候选证据位置：`.github/workflows/`、`Makefile`、`Taskfile.yml`
  - 影响：无法在项目级 memory 中给出稳定的发布/回滚入口
- 缺口：项目级 ops 索引缺失
  - 期望补齐到的粒度：runbook、监控、回滚入口导航
  - 候选证据位置：`.aisdlc/project/ops/`
  - 影响：后续 merge-back 无法直接晋升长期运维入口
- 缺口：README 中后端默认测试命令与当前真实测试入口不一致
  - 期望补齐到的粒度：统一、可信的测试命令入口
  - 候选证据位置：[README.md](../../../README.md)、[.aisdlc/specs/001-competitive-intel-agent/verification/report-2026-07-08-unknown.md](../../specs/001-competitive-intel-agent/verification/report-2026-07-08-unknown.md)
  - 影响：项目级启动/测试入口存在误导风险
