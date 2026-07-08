---
title: LLM 系统接入与竞品分析全流程（Solutionate）
status: draft
---

> 目的：把"推荐决策 + 备选方案对比 + 决策依据 + 验证清单"落到一份可评审文档里，作为后续 `prd.md` 与 `prototype.md` 的唯一决策入口。
>
> 原则：结论先行；只保留支撑决策的最小信息；不写"待确认问题"清单——所有不确定性统一进入"验证清单"（Owner/截止/动作明确）。

## 0. 基本信息

- 需求标识（分支 / ID）：004-llm-intel-pipeline
- 作者 / 参与评审：FS（作者）；PM（待评审）
- 状态：draft
- 最后更新：2026-07-08
- 关联链接：`{FEATURE_DIR}/requirements/raw.md`（含 4 轮澄清记录）

## 1. 结论摘要（先给结论）

- 一句话目标：在 Spec 003 采集调度层之上补齐 LLM 链路（BS→LLM 叠加降噪 → 混合 diff 熔断 → 单次 LLM 情报生成 → 入库 + 报告落盘），打通从"采集后原始 markdown"到"情报入库"的完整闭环。
- 本次 In / Out 的边界：In = LLM 服务抽象层、5 套 Prompt 模板、混合 diff 熔断（文本 diff + LLM 语义判断）、情报生成（instructor + Pydantic）、结果写入 IntelligenceFeed、Jinja2 报告渲染落盘、scheduler_service 集成；Out = 飞书推送、前端页面变更、Django Admin 变更、多 provider 支持、异步队列。
- 推荐方案：**"BS→LLM 叠加降噪 + 三层独立 LLM 调用 + 混合 diff 熔断 + instructor 结构化情报 + Jinja2 报告落盘"全链路**。crawler_service 不改，新增 llm_service 承接 3 次 LLM 调用，新增 report_service 承接渲染落盘，scheduler_service 串接全链路。
- 优先验证点：V-001（LLM 降噪叠加效果）、V-003（混合 diff 熔断准确率）、V-005（instructor 结构化输出可靠性）。

## 2. 推荐方案

- 方案名：**BS→LLM 叠加降噪 + 三层独立 LLM + 混合 diff 熔断 + Jinja2 报告**
- 主流程 / 关键机制：

  1. **采集（已有，不改）**：`crawler_service.fetch_and_clean(url)` → 返回 `(raw_html, bs_clean_md)`，BS 去噪已实现。
  2. **LLM 降噪（第 1 次 LLM）**：`llm_service.denoise(bs_clean_md)` → 输入 BS 去噪后 MD，输出 LLM 语义降噪后 MD。结果覆盖写入 `clean_md_path`（文件覆盖，DB 字段不新增）。
  3. **文本 diff**：`diff_service.text_diff(new_clean_md, prev_clean_md)` → 用 difflib 对比当前 LLM 降噪 MD 与上一条快照的 LLM 降噪 MD。diff 为空 → 写 `IntelligenceFeed(NO_CHANGE)`，零 LLM 调用，结束。
  4. **LLM diff 判断（第 2 次 LLM）**：diff 非空 → `llm_service.judge_diff(diff_text, self_product_doc)` → 输出 `{has_meaningful_change, reason}`。判断无意义 → 写 `NO_CHANGE`，结束。
  5. **情报生成（第 3 次 LLM）**：判断有意义 → `llm_service.generate_intel(diff_text, self_product_doc, few_shots)` → instructor + Pydantic 直出 4 字段。
  6. **入库 + 报告**：4 字段写入 `IntelligenceFeed(CHANGED)` → `report_service.render(feed)` → Jinja2 渲染 HTML + MD → 路径写入 `html_report_path` / `md_table_path`。
  7. **调度集成**：`scheduler_service.run_scan()` 在 DataSnapshot 入库后串接步骤 2-6。首次爬取（无上一条快照）跳过步骤 3-4，直接进入步骤 5。

- 关键边界 / 取舍：

  1. **BS→LLM 叠加，不替换**：BS 粗筛保留，LLM 精炼叠加在后。`crawler_service` 不改，`clean_md_path` 语义从"BS 去噪"变为"LLM 降噪最终结果"。
  2. **3 次 LLM 独立调用，不合并**：降噪、diff 判断、情报生成各自独立计费、独立重试。不跨步骤重试。
  3. **覆盖存储，无需 migration**：`DataSnapshot.clean_md_path` 改存 LLM 降噪后 MD 路径。BS 中间态不持久化到 DB。
  4. **重试+失败记录**：每个 LLM 调用重试 2-3 次（间隔 30s），耗尽写 `IntelligenceFeed(ERROR_CRAWL)`，错误信息存 `change_summary`。不降级。
  5. **Jinja2 仅离线产物**：Jinja2 只渲染 HTML/MD 报告文件，不承担前端 UI。模板与 Prompt 文件同目录体系。
  6. **首次爬取特殊处理**：无上一条快照时跳过 diff（步骤 3-4），直接情报生成（步骤 5），避免首次无意义熔断。

- 为什么选它（可追溯到证据）：

  1. `raw.md#R1-Q1`：用户裁决叠加架构，BS 粗筛 + LLM 精炼，`crawler_service` 不改。
  2. `raw.md#R1-Q2`：用户裁决覆盖 `clean_md_path`，无需 migration，BS 中间态不持久化。
  3. `raw.md#R1-Q3`：用户裁决重试+失败记录，不降级，LLM 失败即任务失败。
  4. `raw.md#R1-Q4`：用户裁决 Jinja2 渲染报告，仅离线产物。
  5. Spec 001 Invariant #2（修订）：3 次独立 LLM 调用不得合并。
  6. Spec 001 Invariant #3（修订）：情报生成仅在 LLM diff 判断有意义时触发。

## 3. 备选方案

### 3.1 备选方案：LLM 替代 BS 去噪

- 核心机制：移除 BeautifulSoup 去噪，LLM 直接处理 html2text 原始输出。
- 主流程：html2text → LLM 降噪 → diff → LLM diff 判断 → 情报生成 → 入库
- 边界与取舍：减少一层处理；LLM 输入更长、负担更重、成本更高
- 适用前提：LLM 成本极低或 token 预算充裕
- 不选原因：`raw.md#R1-Q1` 用户已裁决叠加架构；BS 粗筛能降低 LLM 输入长度和成本。

### 3.2 备选方案：逐级降级容错

- 核心机制：降噪失败→用 BS 结果兜底；diff 判断失败→视为有变化；情报生成失败→写空报告。
- 主流程：同推荐方案，但每步 LLM 失败时降级而非直接失败
- 边界与取舍：最大化可用性；但降级输出质量不一致，难以追溯
- 适用前提：对可用性要求高于质量一致性
- 不选原因：`raw.md#R1-Q3` 用户已裁决重试+失败记录，不降级；LLM 失败即任务失败。

### 3.3 备选方案：新增 DB 字段存储 LLM 降噪结果

- 核心机制：DataSnapshot 新增 `llm_clean_md_path` 字段，BS 结果和 LLM 结果都持久化。
- 主流程：BS 结果存 `clean_md_path`，LLM 结果存 `llm_clean_md_path`，diff 用后者
- 边界与取舍：两层结果都可追溯；但需 migration，增加存储
- 适用前提：需要对比 BS 和 LLM 降噪质量
- 不选原因：`raw.md#R1-Q2` 用户已裁决覆盖现有字段，无需 migration，BS 中间态不持久化。

## 4. 决策依据（证据入口清单）

- `raw.md#功能需求 1`：LLM 服务抽象层配置项（OpenAI 兼容、settings.py + .env）
- `raw.md#功能需求 2`：5 套 Prompt 模板（文件系统存储）
- `raw.md#功能需求 3`：混合 diff 熔断方案 C
- `raw.md#功能需求 4`：情报生成 4 字段 + Negative Few-Shot 5 条
- `raw.md#功能需求 5`：分析结果产出入库
- `raw.md#功能需求 6`：调度服务集成 + 首次爬取特殊处理
- `raw.md#R1-Q1`：LLM 降噪=叠加（BS→LLM）
- `raw.md#R1-Q2`：存储=覆盖 clean_md_path，无需 migration
- `raw.md#R1-Q3`：容错=重试 2-3 次 + 失败写 ERROR_CRAWL
- `raw.md#R1-Q4`：报告渲染=Jinja2
- `raw.md#与 Spec 001 不变量的变更`：Invariant #2/#3 修订
- Spec 001 `solution.md#7.2`：原 13 条不变量（#2/#3 需修订，其余遵守）
- 项目知识库 `components/intelligence-models.md`：DataSnapshot 字段从 TextField 重构为路径字段（migration 0004）
- 项目知识库 `components/intelligence-scheduler.md`：scheduler_service 止步于 DataSnapshot 入库

## 5. 验证清单（V-xxx，可执行）

- **V-001** LLM 降噪叠加效果
  - 风险/假设：BS→LLM 叠加降噪后内容质量是否优于纯 BS
  - 方法：取 5-10 个真实站点 BS 去噪后 MD，送 LLM 降噪，人工对比降噪前后
  - 成功/失败信号：LLM 降噪后噪音进一步减少 >50%，核心内容保留 >90%
  - Owner：FS
  - 截止：I2
  - 触发动作：不达标则调整降噪 prompt 或增加规则预过滤

- **V-002** clean_md_path 覆盖存储的兼容性
  - 风险/假设：已有快照的 clean_md_path 存的是 BS 结果，新快照存 LLM 结果，diff 可能不一致
  - 方法：首次运行时检测上一条快照是否为旧格式，若是则跳过 diff 直接情报生成
  - 成功/失败信号：旧格式快照不触发错误 diff，新格式快照 diff 正常
  - Owner：FS
  - 截止：I2
  - 触发动作：不一致则标记旧快照为"pre-LLM"，diff 时跳过

- **V-003** 混合 diff 熔断准确率
  - 风险/假设：文本 diff 非空但 LLM 判断无意义变化的比例是否合理
  - 方法：收集 20+ 次执行结果，统计文本 diff 非空→LLM 判断无意义的比例
  - 成功/失败信号：无意义熔断率在 20-60% 之间（过低=LLM 未识别噪音，过高=漏报真实变化）
  - Owner：FS
  - 截止：I2
  - 触发动作：超出范围则调整 diff 判断 prompt

- **V-004** LLM 调用重试与失败记录
  - 风险/假设：LLM API 不稳定时重试 2-3 次可能不够
  - 方法：模拟超时/限流场景，验证重试逻辑和 ERROR_CRAWL 写入
  - 成功/失败信号：重试 2-3 次后失败→写 ERROR_CRAWL，change_summary 含错误信息
  - Owner：FS
  - 截止：I2
  - 触发动作：频繁失败则增加重试次数或调整间隔

- **V-005** instructor + Pydantic 结构化输出可靠性
  - 风险/假设：instructor 可能因 LLM 返回格式不规范而解析失败
  - 方法：用 10+ 个真实 diff 片段测试情报生成，验证 4 字段完整输出
  - 成功/失败信号：4 字段完整率 >95%
  - Owner：FS
  - 截止：I2
  - 触发动作：不达标则增加输出格式约束或 fallback 解析

- **V-006** Negative Few-Shot 注入效果
  - 风险/假设：注入 5 条 Negative Few-Shot 后 prompt 膨胀导致质量下降
  - 方法：有/无 Few-Shot 对比测试情报质量
  - 成功/失败信号：有 Few-Shot 时"无意义"情报减少 >30%
  - Owner：FS + PM
  - 截止：I2
  - 触发动作：不显著则减少条数或改用摘要注入

- **V-007** Prompt 模板变量注入
  - 风险/假设：Prompt 模板中的变量（self_product_doc、diff_text、few_shots）注入格式不当导致 LLM 误解
  - 方法：用极端值（超长文本、空文本、特殊字符）测试模板渲染
  - 成功/失败信号：极端值不导致 LLM 返回错误或空输出
  - Owner：FS
  - 截止：I2
  - 触发动作：异常则增加输入清洗和长度截断

- **V-008** Diff 片段长度控制
  - 风险/假设：diff 片段过长导致 LLM token 超限
  - 方法：测量典型 diff 片段长度，设定截断阈值（如 8000 字符）
  - 成功/失败信号：截断后 LLM 不超限且核心变化保留
  - Owner：FS
  - 截止：I2
  - 触发动作：超限则实现 diff 片段摘要或分段处理

- **V-009** Jinja2 报告渲染产物
  - 风险/假设：渲染的 HTML/MD 报告格式不规范或内容缺失
  - 方法：渲染 5+ 份报告，验证 HTML 可浏览器打开、MD 可正确解析
  - 成功/失败信号：HTML 渲染无错、MD 表格格式正确
  - Owner：FS
  - 截止：I2
  - 触发动作：格式错误则修正 Jinja2 模板

- **V-010** scheduler_service 集成端到端
  - 风险/假设：串接全链路后单次执行时间过长或异常未捕获
  - 方法：模拟完整调度执行，测量端到端耗时和异常处理
  - 成功/失败信号：单 URL 端到端 <60s，异常不中断其他 URL
  - Owner：FS
  - 截止：I2
  - 触发动作：超时则优化 LLM 调用并行度或增加超时控制

## 6. Context Gaps

- `CONTEXT GAP`：`.aisdlc/project/components/` 中无 LLM 相关模块页（llm_service / report_service 尚未存在）
  - 建议动作：I1/I2 阶段新建模块页并 merge-back
- `CONTEXT GAP`：`.aisdlc/project/nfr.md` 未定义 LLM 调用延迟/成本 NFR
  - 建议动作：V-010 补充端到端耗时基线，后续 merge-back 到 nfr.md

## 7. Impact Analysis

### 7.1 受影响模块

| 模块 | 影响类型 | 关键不变量 | stale? |
|------|----------|-----------|--------|
| intelligence-scheduler | 修改契约 | `scheduler_service.run_scan()` 当前止步于 DataSnapshot 入库（Invariant #5），本 Spec 扩展为串接 LLM 链路 + IntelligenceFeed 入库 | yes（service contract 变更） |
| intelligence-models | 语义变更 | `DataSnapshot.clean_md_path` 语义从"BS 去噪 MD"变为"LLM 降噪 MD"；无需新增字段 | no（字段不变，语义变更） |
| llm-service（新增） | 新增能力 | 3 次独立 LLM 调用，各自重试，不合并 | N/A |
| report-service（新增） | 新增能力 | Jinja2 渲染 HTML/MD 报告，路径写入 IntelligenceFeed | N/A |
| intelligence-api | 读取数据 | IntelligenceFeed 将有真实数据，前端消费路径不变 | no |

### 7.2 需遵守的不变量

1. **Invariant #2（修订）**：降噪 LLM、diff 判断 LLM、情报生成 LLM 是 3 次独立调用，不得合并（来源：`raw.md#与 Spec 001 不变量的变更`）
2. **Invariant #3（修订）**：情报生成 LLM 仅在 LLM diff 判断为有意义变化时触发（来源：`raw.md#与 Spec 001 不变量的变更`）
3. **Invariant #4（不变）**：情报输出固定 4 字段，不含价值度字段（来源：Spec 001 solution.md#7.2）
4. **Invariant #5（不变）**：has_change=True → 推飞书 + 存报告；has_change=False → 熔断退出（来源：Spec 001 solution.md#7.2；飞书推送不在本 Spec 范围）
5. **Invariant #11（不变）**：Negative Few-Shot 注入上限最近 5 条（来源：Spec 001 solution.md#7.2）
6. **Invariant #13（不变）**：证据 diff 嵌入 change_summary 或报告渲染素材，不独立为 DB 字段（来源：Spec 001 solution.md#7.2）
7. **scheduler Invariant #5（修订）**：原"本模块不写 IntelligenceFeed"→ 修订为"本模块串接 LLM 链路后写 IntelligenceFeed"（来源：`components/intelligence-scheduler.md`）
8. **models Invariant #9（不变）**：DataSnapshot 字段只存绝对文件路径，不存内容（来源：`components/intelligence-models.md`）

### 7.3 跨模块影响

- scheduler_service 扩展 → 需关注 crawler_service 接口不变（`fetch_and_clean` 返回值不改）
- scheduler_service 扩展 → 需关注 file_storage 接口（LLM 降噪后 MD 需覆盖写入 clean_md_path 对应文件）
- IntelligenceFeed 有真实数据 → 前端消费路径（收件箱/详情/报告预览）无需改动，数据天然兼容
- LLM 配置引入 .env → 需关注 settings.py 加载顺序和 Django manage.py 对 .env 的支持

### 7.4 Context Gaps

- `CONTEXT GAP`：intelligence-scheduler 模块页的 service contract 标注"本模块不写 IntelligenceFeed"，本 Spec 修订此约束 → 建议动作：I2 完成后 merge-back 更新模块页
- `CONTEXT GAP`：无 LLM 相关模块页 → 建议动作：I1/I2 阶段新建 `components/llm-service.md` 和 `components/report-service.md`
- `CONTEXT GAP`：nfr.md 未定义 LLM 延迟/成本 NFR → 建议动作：V-010 验证后补充

## 8. 迭代记录

- 2026-07-08：R1 澄清初始化，完成 4 轮需求裁决（降噪架构=叠加、存储=覆盖字段、容错=重试+失败记录、报告渲染=Jinja2），产出 solution.md。
- 2026-07-08：修订 Spec 001 Invariant #2/#3，增加 diff 判断为第 3 次独立 LLM 调用，情报生成触发条件升级为"LLM diff 判断有意义"。
