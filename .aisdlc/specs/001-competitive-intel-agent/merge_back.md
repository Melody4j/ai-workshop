# Merge-back 清单与证据（Spec 001）

## 基本信息

- **FEATURE_DIR**：`/Users/melody/code/ai-workshop/.aisdlc/specs/001-competitive-intel-agent`
- **来源主入口**：`implementation/plan.md#Merge-back 待办清单`
- **project SSOT 根目录**：`/Users/melody/code/ai-workshop/.aisdlc/project`
- **代码来源**：`root repo (/Users/melody/code/ai-workshop)`

## 晋升清单摘要

### ADR

| Item | project 落点 | 不变量摘要 | 证据入口 | 状态 | 代码来源 |
|---|---|---|---|---|---|
| Vue SPA + Django split-monolith 架构决策 | `.aisdlc/project/adr/adr-001-vue-django-split-monolith.md` | 1. 产品页面统一由 Vue 承担 2. Django 作为 JSON API/业务后端 3. SQLite 作为当前批次唯一数据库 4. 单体部署，不引入消息队列或多服务 | `design/design.md`、`requirements/solution.md`、`README.md` | Done | root |

### API Contract（按模块）

| Item | project 落点 | 不变量摘要 | 证据入口 | 状态 | 代码来源 |
|---|---|---|---|---|---|
| 任务配置、报告查询、评分写入 API 入口 | `.aisdlc/project/components/intelligence-api.md#api-contract` | 1. 任务“删除”语义为停用 2. 报告列表支持项目/状态/时间过滤入口 3. 评分仅允许 `-1/1` 4. 收件箱/报告详情消费后端统一 DTO | `backend/apps/intelligence/urls.py`、`backend/apps/intelligence/views.py`、`backend/apps/intelligence/serializers.py` | Done | root |

### Data Contract（按模块）

| Item | project 落点 | 不变量摘要 | 证据入口 | 状态 | 代码来源 |
|---|---|---|---|---|---|
| `MonitorProject` / `IntelligenceFeed` 数据口径 | `.aisdlc/project/components/intelligence-models.md#data-contract` | 1. `competitor_urls` 必须为 `{title,url}` 数组 2. `competitor_contexts` 与竞品数量一一对齐 3. `user_feedback` 取值 `-1/1/null` 4. 报告状态兼容 `CHANGED/NO_CHANGE/ERROR_CRAWL` | `backend/apps/intelligence/models.py`、`backend/apps/intelligence/serializers.py`、`backend/apps/intelligence/migrations/0001_initial.py`、`backend/apps/intelligence/migrations/0002_monitorproject_competitor_contexts_and_more.py` | Done | root |

### Ops

| Item | project 落点 | 不变量摘要 | 证据入口 | 状态 | 代码来源 |
|---|---|---|---|---|---|
| 本地启动 / 构建 / 验证入口 | `.aisdlc/project/ops/index.md` | 1. 后端以 `manage.py` 为唯一入口 2. 前端以 `npm --prefix frontend` scripts 为入口 3. 当前可靠测试入口需显式指向 `apps.intelligence.tests` | `README.md`、`frontend/package.json`、`verification/report-2026-07-08-unknown.md` | Done | root |

### NFR

| Item | project 落点 | 不变量摘要 | 证据入口 | 状态 | 代码来源 |
|---|---|---|---|---|---|
| 当前工程质量与安全门禁基线 | `.aisdlc/project/nfr.md` | 1. 当前质量门禁至少包含 Django check、后端测试、前端 build 2. 同域 Session/CSRF 尚未闭环 3. 前端缺少 lint/typecheck 入口 | `backend/config/settings.py`、`frontend/src/api/client.ts`、`verification/report-2026-07-08-unknown.md` | Done | root |

### Registry

| Item | project 落点 | 不变量摘要 | 证据入口 | 状态 | 代码来源 |
|---|---|---|---|---|---|
| Project registry 收录 Spec 001 晋升结果 | `.aisdlc/project/index.md` | 1. 只登记已晋升资产入口 2. 不复制 spec 细节 3. 明确保留未完成项 | `merge_back.md`、`.aisdlc/project/**` | Done | root |

### Not Done / 保留项

| Item | project 落点 | 不变量摘要 | 证据入口 | 状态 | 缺口与计划 | 代码来源 |
|---|---|---|---|---|---|---|
| `DataSnapshot` append-only 触发器晋升 | `.aisdlc/project/components/intelligence-models.md#data-contract` | 若落地，需以 DB 级硬约束为长期护栏 | `requirements/solution.md#7.2`、`implementation/plan.md#MB-002` | Not Done | 当前代码未实现 SQLite 触发器，只完成模型占位；待后续真实快照链路落地后再晋升 | root |
| 报告种子数据策略晋升 | `.aisdlc/project/ops/index.md` 或 ADR | 需区分“开发 seed”与“正式运行数据来源” | `backend/apps/intelligence/fixtures/sample_reports.json`、`implementation/plan.md#MB-002` | Not Done | 当前仅为骨架阶段联调用 fixture，不适合作为长期项目级规范 | root |
| 前端同域 Session/CSRF 门禁晋升为稳定护栏 | `.aisdlc/project/nfr.md` / `.aisdlc/project/components/intelligence-api.md#api-contract` | 若闭环，需要成为写操作长期护栏 | `verification/report-2026-07-08-unknown.md` | Not Done | 当前 verification 判定 `AC-016` 阻塞，修复后再晋升为 Done | root |

## Done 项落点总览

- ADR：`.aisdlc/project/adr/adr-001-vue-django-split-monolith.md`
- API Contract：`.aisdlc/project/components/intelligence-api.md#api-contract`
- Data Contract：`.aisdlc/project/components/intelligence-models.md#data-contract`
- Ops：`.aisdlc/project/ops/index.md`
- NFR：`.aisdlc/project/nfr.md`
- Registry：`.aisdlc/project/index.md`

## DoD 自检

- [x] `merge_back.md` 已落盘，覆盖 ADR / API / Data / Ops / NFR / Registry / Not Done
- [x] Done 项都有可点击落点与证据入口
- [x] Not Done 项都有缺口与计划
- [x] project 未复制 spec 实现步骤或验证细节
