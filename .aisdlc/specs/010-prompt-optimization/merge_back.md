# Merge-back（best-effort）

## Context

- FEATURE_DIR：`/Users/melody/code/ai-workshop/.aisdlc/specs/010-prompt-optimization`
- Branch：`010-prompt-optimization`
- Code source：根项目（`/Users/melody/code/ai-workshop`），无 submodule
- 审计说明：
  - 当前 `implementation/plan.md` 未显式维护 `## Merge-back 待办清单`
  - 本次 merge-back 按“实际已落地且可长期复用”的资产补录
  - 实际落地主题为“稳定化 diff 生成，移除 LLM 输出作为比对真相源”，与分支名存在上下文漂移，以下条目已显式留痕

## 晋升清单

### ADR

| 条目 | project 落点 | 不变量摘要 | 证据入口 | 状态 | 代码来源 |
|---|---|---|---|---|---|
| 无新增 ADR | N/A | 本次未引入新基础设施、未改 DB schema、未新增跨模块架构分层 | `backend/apps/intelligence/services/scheduler_service.py` / `backend/apps/intelligence/services/diff_service.py` | Not Done（N/A） | 根项目 |

缺口与计划：
- 当前只是收紧 service/data contract，没有形成新的架构决策文档。
- 若后续把“raw diff 熔断”前移到 `denoise()` 之前，且涉及链路重排/成本策略，再单开 ADR。

### API Contract

| 条目 | project 落点 | 不变量摘要 | 证据入口 | 状态 | 代码来源 |
|---|---|---|---|---|---|
| 无外部接口 shape 变更 | N/A | 本次未改 serializer 字段 shape，仅收紧 `diff_text` 展示语义 | `backend/apps/intelligence/serializers.py` | Not Done（N/A） | 根项目 |

缺口与计划：
- API 字段名保持兼容，未做 schema / route 调整。
- 若后续需要公开区分 canonical diff 与 raw diff 的前端文案，再在新 Spec 中处理 API/前端协同。

### Service Contract

| 条目 | project 落点 | 不变量摘要 | 证据入口 | 状态 | 代码来源 |
|---|---|---|---|---|---|
| 稳定 diff 调度链路 | `.aisdlc/project/components/intelligence-scheduler.md#service-contract` | 1) `raw_diff_text` 取自 Firecrawl Markdown 原始 diff；2) `raw_diff_text == ""` 直接 NO_CHANGE；3) `diff_text` 改为 canonical diff；4) `diff_text == ""` 继续 NO_CHANGE；5) `llm_clean_md` 不再作为 diff 真相源 | `backend/apps/intelligence/services/scheduler_service.py`、`backend/apps/intelligence/services/diff_service.py`、`backend/apps/intelligence/tests/test_scheduler_service.py`、`backend/apps/intelligence/tests/test_llm_pipeline_e2e.py` | Done | 根项目 |

### Data Contract

| 条目 | project 落点 | 不变量摘要 | 证据入口 | 状态 | 代码来源 |
|---|---|---|---|---|---|
| `diff_text/raw_diff_text` 长期语义收紧 | `.aisdlc/project/components/intelligence-models.md#data-contract` | 1) `raw_md_path` 存 Firecrawl Markdown；2) `clean_md_path` 存 `llm_clean_md`；3) `raw_diff_text` 表示原始 unified diff；4) `diff_text` 表示规则归一化后的稳定 diff；5) 首次抓取/旧格式兼容路径保持原行为 | `backend/apps/intelligence/services/scheduler_service.py`、`backend/apps/intelligence/services/diff_service.py`、`backend/apps/intelligence/serializers.py`、`backend/apps/intelligence/tests/test_diff_service.py` | Done | 根项目 |

### Ops

| 条目 | project 落点 | 不变量摘要 | 证据入口 | 状态 | 代码来源 |
|---|---|---|---|---|---|
| 真实夹具报告链路验证入口 | `.aisdlc/project/ops/index.md` | 1) `backend/.env` 的 `DATABASE_URL` 指向外部 PG（当前验证为 Vercel PG）；2) 真实 E2E 依赖 `FIRECRAWL_API_KEY` / `LLM_API_KEY` / `BLOB_READ_WRITE_TOKEN`；3) 使用 `RUN_FIXTURE_REPORT_E2E=1 ... test_fixture_report_flow_e2e` 进行手工验证 | `backend/config/settings.py`、`backend/apps/intelligence/tests/test_fixture_report_flow_e2e.py` | Done | 根项目 |

### NFR

| 条目 | project 落点 | 不变量摘要 | 证据入口 | 状态 | 代码来源 |
|---|---|---|---|---|---|
| 无新增 NFR 基线 | N/A | 本次验证覆盖正确性回归，但未新增吞吐/延迟/成本阈值 | `backend/apps/intelligence/tests/test_fixture_report_flow_e2e.py` | Not Done | 根项目 |

缺口与计划：
- 当前只验证“误报被压制、真实价格/功能变化仍能出报告”。
- 若后续要把 denoise 前移或压缩 token 成本，需要新增延迟/成本基线再晋升到 `.aisdlc/project/nfr.md`。

### Registry

| 条目 | project 落点 | 不变量摘要 | 证据入口 | 状态 | 代码来源 |
|---|---|---|---|---|---|
| 更新 project registry | `.aisdlc/project/index.md` | 记录本次 best-effort merge-back、更新 scheduler/models/ops 的来源与说明 | `.aisdlc/project/index.md` | Done | 根项目 |

## Not Done / Context Gaps

1. `implementation/plan.md` 无 `## Merge-back 待办清单`
   - 影响：本次 merge-back 只能按代码与测试事实补录，无法逐项对照计划清单清空
   - 计划：后续 Spec 执行阶段补齐 merge-back checklist，避免再次出现审计漂移

2. raw diff 熔断尚未前移到 `denoise()` 之前
   - 影响：原始页面无变化时仍会产生 1 次 denoise LLM 成本
   - 计划：后续单开 Spec 处理链路重排与成本优化

3. 分支主题与实际实现有漂移
   - 影响：`010-prompt-optimization` 分支内同时包含稳定 diff hardening，后续回溯需要依赖本文件
   - 计划：后续提交/PR 描述中继续保留 incident-fix 说明，避免被误归类为纯 prompt 调整
