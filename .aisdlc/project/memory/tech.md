# 技术栈与工程护栏

## 技术栈（稳定选择）

- 语言/框架：
  - 后端：Python + Django + Django REST Framework（证据：[backend/requirements/base.txt](../../../backend/requirements/base.txt)、[backend/config/settings.py](../../../backend/config/settings.py)）
  - 前端：Vue 3 + TypeScript + Vite + Element Plus（证据：[frontend/package.json](../../../frontend/package.json)）
- 数据库/缓存/消息：
  - 数据库：SQLite（证据：[backend/config/settings.py](../../../backend/config/settings.py)）
  - 缓存：未落地
  - 消息队列：未落地

## 质量门禁入口（可执行证据）

- lint：缺失（证据：[frontend/package.json](../../../frontend/package.json)）
- test：
  - 后端：`/Users/melody/code/ai-workshop/.venv/bin/python backend/manage.py test apps.intelligence.tests`
  - 前端：当前仅保留构建门禁 `npm --prefix frontend run build`
- 安全扫描：缺失

## NFR 入口

- 当前未建立项目级 NFR 权威文档

## Evidence Gaps（缺口清单）

- 缺口：前端无独立 `lint` / `typecheck` script
  - 期望补齐到的粒度：项目级可执行前端静态门禁入口
  - 候选证据位置：[frontend/package.json](../../../frontend/package.json)
  - 影响：工程质量门禁不完整，收尾验证只能依赖构建通过
- 缺口：项目级 NFR 文档缺失
  - 期望补齐到的粒度：性能、可用性、安全、成本的长期入口
  - 候选证据位置：`.aisdlc/project/nfr.md`
  - 影响：merge-back 时无法沉淀长期非功能约束
- 缺口：Session/CSRF 同域写操作护栏未闭环
  - 期望补齐到的粒度：前端 API client 凭据策略 + 后端 CSRF 入口说明
  - 候选证据位置：[frontend/src/api/client.ts](../../../frontend/src/api/client.ts)、[backend/config/settings.py](../../../backend/config/settings.py)
  - 影响：当前 verification 已阻断 AC-016
