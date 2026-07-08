---
title: PRD — LLM 系统接入与竞品分析全流程
status: draft
---

目的：把 `requirements/solution.md` 的推荐决策转为**可交付规格**。不写"待确认问题"；未知统一写入第 8 节验证清单。

## 0. 基本信息

- 需求标识（分支 / ID）：004-llm-intel-pipeline
- 作者：FS
- 评审人：PM
- 状态：draft
- 最后更新：2026-07-08
- 关联链接：`requirements/solution.md`、`requirements/raw.md`（含 4 轮澄清记录）

---

## 1. 结论摘要

- 目标：在 Spec 003 采集调度层之上补齐 LLM 链路（BS→LLM 叠加降噪 → 混合 diff 熔断 → 单次 LLM 情报生成 → 入库 + Jinja2 报告落盘），打通从"采集后原始 markdown"到"情报入库"的完整闭环。
- In / Out 边界：In = LLM 服务抽象层、5 套 Prompt 模板、混合 diff 熔断、情报生成（instructor + Pydantic）、IntelligenceFeed 入库、Jinja2 报告渲染落盘、scheduler_service 集成；Out = 飞书推送、前端页面变更、Django Admin 变更、多 provider 支持、异步队列。
- MVP 边界：3 次 LLM 调用全链路同步执行，不引入队列；仅 OpenAI 兼容 API；Jinja2 仅离线报告产物。
- 推荐方案：引用 `requirements/solution.md#2. 推荐方案`——BS→LLM 叠加降噪 + 三层独立 LLM + 混合 diff 熔断 + Jinja2 报告。
- 优先验证点：V-001（LLM 降噪叠加效果）、V-003（混合 diff 熔断准确率）、V-005（instructor 结构化输出可靠性）。

---

## 2. 范围与里程碑

### 2.1 MVP 范围（In / Out）

- **In**：
  - LLM 服务抽象层（OpenAI 兼容，settings.py + .env 配置）
  - 5 套 Prompt 模板（文件系统 `prompts/` 目录）
  - BS→LLM 叠加降噪（第 1 次 LLM 调用）
  - 文本 diff（difflib）+ LLM 语义 diff 判断（第 2 次 LLM 调用）
  - 情报生成 instructor + Pydantic 4 字段直出（第 3 次 LLM 调用）
  - Negative Few-Shot 注入（最近 5 条 `user_feedback=-1`）
  - IntelligenceFeed 入库（4 字段 + `job_status=CHANGED`）
  - Jinja2 渲染 HTML 网页报告 + MD 表格落盘
  - scheduler_service.run_scan() 串接 LLM 全链路
  - LLM 调用重试机制（2-3 次，间隔 30s）
  - 首次爬取特殊处理（跳过 diff，直接情报生成）
- **Out**：
  - 飞书推送（Spec 001 范围，本 Spec 不实现）
  - 前端页面变更（收件箱/详情/报告预览不变）
  - Django Admin 变更
  - 多 LLM provider 支持（仅 OpenAI 兼容）
  - 异步队列/消息中间件
  - `refined_rules` 写入（P1 占位）

### 2.2 里程碑

- MVP：全链路可端到端执行——调度触发 → 采集 → LLM 降噪 → diff 熔断 → 情报生成 → 入库 + 报告落盘
- M1（可选）：Prompt 调优、重试策略优化、报告格式迭代

---

## 3. 核心场景

### 3.1 场景 S-001：日级调度——有变化时全链路执行

- **触发**：django-apscheduler 按 cron 触发 `run_scan()`，项目 `next_run_at <= now`
- **参与者**：调度器 → crawler_service → llm_service → report_service → DB
- **目标**：采集竞品 URL → LLM 降噪 → diff 判断有意义 → 生成 4 字段情报 → 入库 + 报告落盘
- **成功标准**：
  1. DataSnapshot 存入 LLM 降噪后 MD（`clean_md_path` 指向 LLM 结果文件）
  2. IntelligenceFeed 存入 4 字段，`job_status=CHANGED`
  3. HTML 报告 + MD 表格文件已落盘，路径写入 IntelligenceFeed

### 3.2 场景 S-002：日级调度——无变化时熔断退出

- **触发**：同 S-001，但文本 diff 为空或 LLM 判断无意义
- **参与者**：调度器 → crawler_service → llm_service → DB
- **目标**：快速熔断，不触发情报生成 LLM 调用，不推飞书，不生成报告
- **成功标准**：
  1. 文本 diff 为空 → 写 `IntelligenceFeed(NO_CHANGE)`，零 LLM diff 判断调用
  2. 文本 diff 非空但 LLM 判断无意义 → 写 `IntelligenceFeed(NO_CHANGE)`，不触发情报生成
  3. 无 HTML/MD 报告产物

### 3.3 场景 S-003：首次爬取——无上一条快照

- **触发**：项目首次执行，该 URL 无历史 DataSnapshot
- **参与者**：调度器 → crawler_service → llm_service → report_service → DB
- **目标**：跳过 diff，直接 LLM 降噪 + 情报生成，产出首条情报
- **成功标准**：
  1. LLM 降噪正常执行并存入 DataSnapshot
  2. 跳过文本 diff 和 LLM diff 判断
  3. 情报生成 LLM 正常调用，4 字段写入 IntelligenceFeed(CHANGED)
  4. 报告产物落盘

---

## 4. 功能清单

| 功能项 | 优先级 | 里程碑 | 说明/依赖 |
|---|---|---|---|
| F-01 LLM 服务抽象层 | P0 | MVP | OpenAI 兼容 client，config 从 settings.py + .env 读取 |
| F-02 .env 配置加载 | P0 | MVP | python-dotenv 或 Django-environ，加载 LLM_API_KEY/BASE_URL/MODEL 等 |
| F-03 数据清洗 Prompt 模板 | P0 | MVP | `prompts/denoise.md`，输入 BS 去噪 MD，输出 LLM 降噪 MD |
| F-04 LLM 降噪调用 | P0 | MVP | llm_service.denoise()，普通文本补全，重试 2-3 次 |
| F-05 文本 diff 引擎 | P0 | MVP | difflib 对比当前与上一条 LLM 降噪 MD |
| F-06 diff 判断 Prompt 模板 | P0 | MVP | `prompts/diff_judge.md`，输出 {has_meaningful_change, reason} |
| F-07 LLM diff 判断调用 | P0 | MVP | llm_service.judge_diff()，结构化 JSON 输出，重试 2-3 次 |
| F-08 自家产品系统 Prompt 模板 | P0 | MVP | `prompts/system_self_product.md`，system role 注入 self_product_doc |
| F-09 竞品分析系统 Prompt 模板 | P0 | MVP | `prompts/intel_analysis.md`，注入 diff + Few-Shot |
| F-10 输出结果 Prompt + instructor schema | P0 | MVP | Pydantic model 定义 4 字段，instructor 约束输出 |
| F-11 LLM 情报生成调用 | P0 | MVP | llm_service.generate_intel()，instructor + Pydantic，重试 2-3 次 |
| F-12 Negative Few-Shot 注入 | P0 | MVP | 查询最近 5 条 user_feedback=-1，注入情报生成 prompt |
| F-13 IntelligenceFeed 入库 | P0 | MVP | 4 字段 + job_status + 报告路径写入 DB |
| F-14 Jinja2 HTML 报告渲染 | P0 | MVP | `templates/report.html.j2`，渲染 4 字段为 HTML 网页报告 |
| F-15 Jinja2 MD 表格渲染 | P0 | MVP | `templates/report.md.j2`，渲染 4 字段为 MD 表格 |
| F-16 scheduler_service 集成 | P0 | MVP | run_scan() 串接 LLM 链路，扩展止步于 DataSnapshot 的边界 |
| F-17 LLM 重试机制 | P0 | MVP | 通用重试装饰器/工具，2-3 次重试，间隔 30s |
| F-18 首次爬取特殊处理 | P0 | MVP | 检测无上一条快照时跳过 diff，直接情报生成 |
| F-19 旧格式快照兼容 | P0 | MVP | 上一条快照 clean_md_path 为 BS 结果（pre-LLM）时，跳过 diff 直接情报生成 |

---

## 5. 业务规则与口径

- 规则-1：3 次 LLM 调用（降噪、diff 判断、情报生成）各自独立，不得合并（来源：`raw.md#与 Spec 001 不变量的变更` Invariant #2 修订）
- 规则-2：情报生成 LLM 仅在 LLM diff 判断为有意义变化时触发（来源：Invariant #3 修订）
- 规则-3：情报输出固定 4 字段（change_summary / strategic_intent / action_suggestion / evidence_diff），不含价值度字段（来源：Spec 001 Invariant #4）
- 规则-4：Negative Few-Shot 注入上限最近 5 条，取 `user_feedback=-1` 的记录（来源：Spec 001 Invariant #11）
- 规则-5：LLM 密钥必须从 `.env` 读取，不得硬编码或入库（来源：`raw.md#约束`）
- 规则-6：Prompt 模板文件存放在 `prompts/` 目录，不存 DB（来源：`raw.md#约束`）
- 规则-7：LLM 调用同步执行，不引入消息队列（来源：`raw.md#约束`）
- 规则-8：`DataSnapshot.clean_md_path` 语义变更为"LLM 降噪后 MD 路径"，BS 中间态不持久化到 DB（来源：`raw.md#R1-Q2`）
- 规则-9：LLM 调用失败重试 2-3 次（间隔 30s），耗尽写 `IntelligenceFeed(ERROR_CRAWL)`，错误信息存 `change_summary`（来源：`raw.md#R1-Q3`）
- 规则-10：证据 diff 嵌入 `change_summary` 或报告渲染素材，不独立为 DB 字段（来源：Spec 001 Invariant #13）
- 规则-11：`scheduler_service.run_scan()` 原止步于 DataSnapshot 入库，现扩展为串接 LLM 全链路 + IntelligenceFeed 入库（来源：`raw.md#R1-Q1` 约束变更）

---

## 6. 验收标准（AC，可测试）

### 6.1 场景 S-001 的 AC（有变化全链路）

- AC-001：给定一个 active 项目，`run_scan()` 触发后，每个 URL 产出一条 DataSnapshot，其 `clean_md_path` 指向 LLM 降噪后 MD 文件（非 BS 原始去噪结果）
- AC-002：给定当前快照与上一条快照有文本 diff，LLM diff 判断返回 `has_meaningful_change=true`，则 IntelligenceFeed 以 `job_status=CHANGED` 入库，4 字段（change_summary / strategic_intent / action_suggestion / evidence_diff）均非空
- AC-003：IntelligenceFeed 入库后，`html_report_path` 和 `md_table_path` 指向已落盘的文件，HTML 文件可浏览器打开，MD 表格格式正确
- AC-004：3 次 LLM 调用各自独立计费，可通过日志/调用记录确认 3 次调用分别对应降噪、diff 判断、情报生成

### 6.2 场景 S-002 的 AC（无变化熔断）

- AC-005：给定当前快照与上一条快照文本 diff 为空，写 `IntelligenceFeed(NO_CHANGE)`，不触发 LLM diff 判断调用和情报生成调用
- AC-006：给定文本 diff 非空但 LLM 判断 `has_meaningful_change=false`，写 `IntelligenceFeed(NO_CHANGE)`，不触发情报生成调用，无报告产物
- AC-007：`NO_CHANGE` 记录的 4 字段为空，`html_report_path` 和 `md_table_path` 为空字符串

### 6.3 场景 S-003 的 AC（首次爬取）

- AC-008：给定某 URL 无历史 DataSnapshot，`run_scan()` 跳过文本 diff 和 LLM diff 判断，直接调用情报生成 LLM
- AC-009：首次爬取的 IntelligenceFeed 以 `job_status=CHANGED` 入库，4 字段非空，报告产物已落盘

### 6.4 异常与容错的 AC

- AC-010：给定 LLM API 超时/限流，降噪 LLM 重试 2-3 次（间隔 30s）后仍失败，写 `IntelligenceFeed(ERROR_CRAWL)`，`change_summary` 含错误信息，不产生报告
- AC-011：给定 LLM diff 判断调用失败（重试耗尽），写 `IntelligenceFeed(ERROR_CRAWL)`，不触发情报生成
- AC-012：给定采集失败（crawler_service 返回空），写 `IntelligenceFeed(ERROR_CRAWL)`，不进入 LLM 链路
- AC-013：单个 URL 的 LLM 链路异常不中断同一项目其他 URL 的执行，也不中断其他项目

### 6.5 配置与 Prompt 的 AC

- AC-014：`.env` 文件中配置 `LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL`，Django 启动时正确加载，LLM 服务可正常调用
- AC-015：`prompts/` 目录下存在 5 套 Prompt 模板文件，变量（self_product_doc / diff_text / few_shots）正确注入，LLM 返回不含模板占位符
- AC-016：Negative Few-Shot 查询 `user_feedback=-1` 的记录，取最近 5 条注入情报生成 prompt；不足 5 条时按实际数量注入；无记录时不注入

### 6.6 旧格式兼容的 AC

- AC-017：给定上一条快照的 `clean_md_path` 为 BS 结果（pre-LLM 格式），当前快照跳过 diff，直接情报生成，不报错

---

## 7. 异常与边界

- 异常/边界-1：LLM API 超时/限流 → 重试 2-3 次（间隔 30s），耗尽写 ERROR_CRAWL（规则-9）
- 异常/边界-2：LLM 返回格式不规范（instructor 解析失败）→ 重试 2-3 次，耗尽写 ERROR_CRAWL
- 异常/边界-3：diff 片段过长（超 LLM token 限制）→ 截断至阈值后送 LLM（V-008 验证）
- 异常/边界-4：self_product_doc 为空 → 仍执行 LLM 链路，prompt 中标注"无产品锚定文档"
- 异常/边界-5：旧格式快照（BS 结果）→ 跳过 diff 直接情报生成（AC-017）
- 异常/边界-6：单 URL 异常不中断其他 URL/项目（AC-013）
- 异常/边界-7：首次爬取无上一条快照 → 跳过 diff 直接情报生成（AC-008）

---

## 8. 风险/依赖与验证清单

| 风险/假设/依赖 | 验证信号 | 方法 | Owner | 截止 | 触发动作 |
|---|---|---|---|---|---|
| LLM 降噪叠加效果优于纯 BS（V-001） | 噪音减少 >50%，核心保留 >90% | 5-10 真实站点 BS MD → LLM 降噪，人工对比 | FS | I2 | 不达标则调 prompt 或加规则预过滤 |
| 旧格式快照兼容检测正确（V-002） | 旧格式不触发错误 diff | 首次运行检测旧格式→跳过 diff | FS | I2 | 不一致则标记旧快照 pre-LLM |
| 混合 diff 熔断准确率合理（V-003） | 无意义熔断率 20-60% | 20+ 次执行结果统计 | FS | I2 | 超范围则调 diff 判断 prompt |
| LLM 重试与失败记录正确（V-004） | 重试耗尽→写 ERROR_CRAWL | 模拟超时/限流场景 | FS | I2 | 频繁失败则增加重试次数 |
| instructor 结构化输出可靠（V-005） | 4 字段完整率 >95% | 10+ 真实 diff 测试 | FS | I2 | 不达标则增加格式约束或 fallback |
| Negative Few-Shot 注入有效（V-006） | 有 Few-Shot 时无意义情报减少 >30% | 有/无对比测试 | FS+PM | I2 | 不显著则减少条数或改摘要注入 |
| Prompt 变量注入鲁棒（V-007） | 极端值不导致 LLM 错误 | 超长/空/特殊字符测试 | FS | I2 | 异常则增加输入清洗 |
| Diff 截断策略有效（V-008） | 截断后不超限且核心变化保留 | 测量典型 diff 长度 | FS | I2 | 超限则实现 diff 摘要 |
| Jinja2 报告渲染正确（V-009） | HTML 无错、MD 表格正确 | 5+ 份报告验证 | FS | I2 | 格式错则修模板 |
| 端到端耗时可控（V-010） | 单 URL <60s | 模拟完整调度执行 | FS | I2 | 超时则优化或增加超时控制 |

---

## 9. 原型产出判定

- **交互变化结论**：无。本 Spec 纯后端服务层实现，不涉及前端页面/交互变更。IntelligenceFeed 有真实数据后前端消费路径天然兼容，无需改动。
- **页面与入口**：复用现有页面，不新增页面。
- **关键控件/字段与校验**：无前端变更。

---

## 10. 追溯链接

- `requirements/solution.md`：推荐方案 + 3 备选 + 10 验证项 + Impact Analysis
- `requirements/raw.md`：4 轮澄清记录（R1-Q1~Q4）+ 不变量变更声明
- 术语与口径：`project/memory/glossary.md`
- Spec 001 solution.md：原 13 条不变量（#2/#3 本 Spec 修订）
- 项目知识库：`components/intelligence-models.md`、`components/intelligence-scheduler.md`
