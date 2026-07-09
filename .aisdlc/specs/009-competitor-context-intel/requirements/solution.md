---
title: 竞品补充文档链路打通 + Intel Prompt 优化（Solution）
status: draft
---

> 目的：把"推荐决策 + 备选方案对比 + 决策依据 + 验证清单"落到一份可评审文档里，作为后续 `prd.md` 与 `prototype.md` 的唯一决策入口。

## 0. 基本信息

- 需求标识：009-competitor-context-intel
- 作者：Claude Code（R1 澄清）
- 状态：draft
- 最后更新：2026-07-09
- 关联链接：`raw.md` R1-Q1~Q5 澄清裁决

## 1. 结论摘要

- **一句话目标**：打通竞品补充文档从 DB → scheduler → LLM → prompt 的完整链路，并重写 Intel Prompt 以深化分析质量。
- **本次 In / Out 边界**：In = scheduler 链路注入 competitor_context + 重写 intel_system/intel_user prompt + IntelResult 新增 competitor_overview 字段 + 同步更新 prompt_optimizer 兼容性 + 报告模板适配；Out = 前端表单变更（已存在）、降噪/diff_judge prompt 变更、新增 DB 表。
- **推荐方案**：按 index 对齐取 competitor_contexts → 格式化为文本 → 注入 intel_user.md 新增 `{competitor_context}` 占位符 → IntelResult 扩展为 5 字段（新增 `competitor_overview`）→ 同步更新 prompt_optimizer 保护清单 + 报告模板渲染。
- **优先验证点**：V-001（占位符完整性）、V-002（优化器兼容性）、V-003（空值降级）。

## 2. 推荐方案

- **方案名**：Index 对齐 + User Prompt 注入 + 5 字段扩展

- **主流程 / 关键机制**（6 步）：
  1. **scheduler_service `_process_url`**：遍历 `competitor_urls` 时按 `enumerate` 索引取 `competitor_contexts[idx]`，提取 `supplement_doc_name` + `supplement_doc_content`，格式化为 `competitor_context` 文本
  2. **传参链路**：`_process_url` → `generate_intel(diff_text, self_product_doc, few_shots, competitor_context)` 新增参数
  3. **Prompt 注入**：`generate_intel` 调用 `load_prompt("intel_user", diff_text=..., negative_few_shots=..., competitor_context=...)`，`intel_user.md` 新增 `## 竞品补充文档` 段落 + `{competitor_context}` 占位符
  4. **IntelResult 扩展**：`IntelResult` Pydantic 模型新增 `competitor_overview: str` 字段，`IntelligenceFeed` 模型新增 `competitor_overview` DB 字段（migration）
  5. **Prompt 重写**：重写 `intel_system.md`（深化分析要求 + 输出结构引导）和 `intel_user.md`（新增竞品上下文段落 + 深化输出要求）
  6. **优化器兼容**：`prompt_optimizer.md` 占位符保护清单新增 `{competitor_context}`；`prompt_optimizer_service.py` 的 `ai_report` 拼接新增 `competitor_overview` 段落

- **关键边界 / 取舍**：
  1. **按 index 对齐**（不按 URL 匹配）：序列化器已保证 `competitor_contexts` 与 `competitor_urls` count 对齐，调度层不重复校验。index 越界时 `competitor_context` 视为空（来源：R1-Q1）
  2. **注入 user prompt**（不注入 system prompt）：竞品上下文是每次分析的具体输入材料，与 diff 同层级；system prompt 聚焦角色定义和我方产品锚定（来源：R1-Q2）
  3. **空值注入占位文本**（不传空字符串）：无补充文档时填"暂无竞品补充文档"，保持 prompt 结构一致性（来源：R1-Q5）
  4. **IntelResult 4→5 字段**：新增 `competitor_overview`，修订不变量 #4 为"固定 5 字段"（来源：R1-Q3）
  5. **同步更新优化器**：`prompt_optimizer.md` 保护清单 + `ai_report` 拼接必须同步更新，否则优化器会删除 `{competitor_context}` 占位符导致链路断裂（来源：R1-Q4）

- **为什么选它**：
  1. 链路最短——直接在现有 11 步链路的 Step 8 注入，不改变前 7 步逻辑（证据：`scheduler_service.py:246-253`）
  2. 占位符注入复用现有 `load_prompt` 的 `str.replace` 机制，不引入新依赖（证据：`prompt_loader.py`）
  3. 5 字段扩展是增量修改，不影响已有 4 字段的 DB/API/报告模板逻辑（证据：`llm_client.py:19-37` IntelResult 定义）

## 3. 备选方案

### 3.1 备选方案：URL 精确匹配 + System Prompt 注入

- **核心机制**：遍历 `competitor_contexts` 找 `url` 字段完全匹配的条目，注入到 `intel_system.md` 新增 `{competitor_context}` 占位符
- **主流程**：`_process_url` 传 `url` → `generate_intel` 内部按 URL 查找匹配条目 → 注入 system prompt
- **边界与取舍**：URL 匹配更健壮但多余（序列化器已保证对齐）；system prompt 注入让竞品背景成为全局上下文
- **适用前提**：当 `competitor_contexts` 与 `competitor_urls` 可能不对齐时
- **不选原因**：序列化器 `validate()` 已保证 count 对齐（`serializers.py:77-96`），URL 匹配是重复校验；system prompt 注入与"每次分析的具体输入"语义不符

### 3.2 备选方案：不改 IntelResult schema，仅深化 prompt

- **核心机制**：仅重写 `intel_system.md` + `intel_user.md`，注入 `competitor_context`，但 IntelResult 保持 4 字段，竞品概述嵌入 `change_summary` 前缀
- **主流程**：prompt 中要求 LLM 在 `change_summary` 开头输出竞品概述段落
- **边界与取舍**：无 DB migration、无报告模板变更，但输出结构不够清晰
- **适用前提**：当不想修改 DB schema 和不变量时
- **不选原因**：用户明确要求新增 `competitor_overview` 字段（R1-Q3），嵌入 `change_summary` 会导致报告渲染和前端展示无法区分概述和摘要

## 4. 决策依据（证据入口清单）

- `raw.md` R1-Q1：匹配方式 → 按 index 对齐
- `raw.md` R1-Q2：注入位置 → user prompt
- `raw.md` R1-Q3：Schema 变更 → 新增 `competitor_overview`，修订不变量 #4
- `raw.md` R1-Q4：优化器兼容 → 同步更新 `prompt_optimizer.md` + `prompt_optimizer_service.py`
- `raw.md` R1-Q5：空值处理 → 注入"暂无竞品补充文档"占位文本
- `backend/apps/intelligence/services/scheduler_service.py:124` `_process_url` 签名（需新增参数）
- `backend/apps/intelligence/services/scheduler_service.py:52-61` 遍历逻辑（需按 index 取 context）
- `backend/apps/intelligence/services/llm_service.py:189-193` `generate_intel` 签名（需新增参数）
- `backend/apps/intelligence/services/llm_service.py:210-215` prompt 注入（需新增 competitor_context）
- `backend/apps/intelligence/services/llm_client.py:19-37` IntelResult 定义（需新增字段）
- `backend/apps/intelligence/services/prompt_optimizer_service.py:51-62` ai_report 拼接（需新增段落）
- `backend/prompts/prompt_optimizer.md:41` 占位符保护清单（需新增）
- `backend/prompts/intel_system.md` 当前模板（需重写）
- `backend/prompts/intel_user.md` 当前模板（需重写）
- `backend/templates/reports/report.html.j2:138-156` HTML 报告模板（需新增段落）
- `backend/templates/reports/report.md.j2:8-24` MD 报告模板（需新增段落）
- `frontend/src/api/reports.ts:16-31` ReportDetail 接口（需新增字段）

## 5. 验证清单

- **V-001**：占位符完整性
  - 风险/假设：`intel_user.md` 重写后 `{competitor_context}` 占位符可能被 `load_prompt` 的 `str.replace` 正确替换
  - 方法：单元测试 `load_prompt("intel_user", diff_text="...", negative_few_shots="...", competitor_context="...")`，断言输出不含 `{competitor_context}` 字面量
  - 成功/失败信号：输出不含 `{competitor_context}` → 成立；含 → 不成立
  - Owner：DEV
  - 截止：I2 实现后 1 天
  - 触发动作：不成立则检查模板文件占位符拼写与 `load_prompt` 调用参数名一致性

- **V-002**：Prompt 优化器兼容性
  - 风险/假设：优化器覆盖 `intel_user.md` 后可能删除 `{competitor_context}` 占位符
  - 方法：手动触发 `optimize_prompts`，检查覆盖后的 `intel_user.md` 是否保留 `{competitor_context}`
  - 成功/失败信号：保留 → 成立；删除 → 不成立
  - Owner：DEV
  - 截止：I2 实现后 2 天
  - 触发动作：不成立则检查 `prompt_optimizer.md` 保护清单是否包含 `{competitor_context}`

- **V-003**：空值降级
  - 风险/假设：`competitor_contexts` 为空或 index 越界时，`competitor_context` 应为"暂无竞品补充文档"
  - 方法：单元测试 `_process_url` 传入 `competitor_contexts=[]`，断言 `generate_intel` 收到的 `competitor_context` 为占位文本
  - 成功/失败信号：占位文本 → 成立；空字符串或 None → 不成立
  - Owner：DEV
  - 截止：I2 实现后 1 天
  - 触发动作：不成立则检查 `_process_url` 的 index 越界处理逻辑

- **V-004**：IntelResult 5 字段结构化输出
  - 风险/假设：instructor + Pydantic 新增 `competitor_overview` 字段后，LLM 可能不返回该字段
  - 方法：集成测试 `generate_intel`，断言返回的 `IntelResult` 实例包含 5 个非空字段
  - 成功/失败信号：5 字段非空 → 成立；缺字段或空 → 不成立
  - Owner：DEV
  - 截止：I2 实现后 2 天
  - 触发动作：不成立则检查 Pydantic schema 定义和 prompt 中是否明确要求输出该字段

- **V-005**：报告模板渲染 competitor_overview
  - 风险/假设：HTML/MD 报告模板新增 `competitor_overview` 段落后，渲染时可能因 DB 字段为 null 而报错
  - 方法：渲染一条 `competitor_overview` 为空字符串的 IntelligenceFeed，检查模板不报错
  - 成功/失败信号：渲染成功且段落显示为空 → 成立；Jinja2 渲染异常 → 不成立
  - Owner：DEV
  - 截止：I2 实现后 1 天
  - 触发动作：不成立则检查模板中 `{{ feed.competitor_overview }}` 是否需要默认值处理

- **V-006**：DB migration 向后兼容
  - 风险/假设：新增 `competitor_overview` 字段的 migration 在已有数据上执行可能失败
  - 方法：在含已有 IntelligenceFeed 记录的 DB 上执行 `makemigrations` + `migrate`
  - 成功/失败信号：migration 成功且已有记录的 `competitor_overview` 为空字符串/null → 成立；migration 失败 → 不成立
  - Owner：DEV
  - 截止：I2 实现后 1 天
  - 触发动作：不成立则检查字段定义 `null=True, blank=True, default=""`

- **V-007**：Prompt 重写后输出质量
  - 风险/假设：重写后的 prompt 可能仍输出简陋分析
  - 方法：用同一组 diff_text + self_product_doc + competitor_context 对比重写前后 prompt 的 LLM 输出
  - 成功/失败信号：重写后输出各字段长度显著增加（>50%），且内容包含竞品背景引用 → 成立；否则不成立
  - Owner：DEV
  - 截止：I2 实现后 3 天
  - 触发动作：不成立则迭代调整 prompt 中的分析要求和输出引导

## 6. 迭代记录

- 2026-07-09：R1 澄清完成，产出 solution.md 初版。5 项关键决策已裁决（匹配方式/注入位置/Schema 变更/优化器兼容/空值处理），确定了 7 项验证清单和 Impact Analysis。

## 7. Impact Analysis

### 7.1 受影响模块

| 模块 | 影响类型 | 关键不变量 | stale? |
|------|----------|-----------|--------|
| intelligence-scheduler | 修改契约：`_process_url` 新增 competitor_context 传参 | 不变量 #2（3 次独立 LLM 调用不合并）不受影响 | no |
| llm-service | 修改契约：`generate_intel` 新增参数 + prompt 注入 | 不变量 #2（3 次独立调用）不受影响；不变量 #4 修订（4→5 字段） | no |
| llm-client | 修改 schema：IntelResult 新增 `competitor_overview` | 不变量 #4 修订（4→5 字段） | no |
| report-service | 无代码变更，模板变更 | 报告模板新增段落 | no |
| prompt-optimizer | 修改契约：保护清单 + ai_report 拼接 | 不变量 #9（优化器一次返回两个 prompt）不受影响 | no |
| intelligence-models | 新增 DB 字段：`IntelligenceFeed.competitor_overview` | 不变量 #4 修订；需 migration | no |
| frontend (reports API) | 修改类型：`ReportDetail` 接口新增字段 | 前端通过 iframe 渲染 HTML 报告，不直接渲染字段 | no |

### 7.2 需遵守的不变量

- **不变量 #2（修订）**：3 次 LLM 调用独立不合并 → 本次仅修改第 3 次（generate_intel）的参数和 prompt，不合并调用（来源：`.aisdlc/project/components/llm-service.md#invariants`）
- **不变量 #4（修订）**：情报输出固定 **5** 字段（原 4 字段 + `competitor_overview`），不含价值度字段（来源：`raw.md` R1-Q3）
- **不变量 #6（修订）**：Negative Few-Shot 注入上限最近 5 条 → 不受影响
- **不变量 #9（修订）**：每个监控任务必须关联 `self_product_doc` → 不受影响
- **新增不变量**：`intel_user.md` 必须包含 `{competitor_context}` 占位符；`prompt_optimizer.md` 保护清单必须包含 `{competitor_context}`

### 7.3 跨模块影响

- 改了 `IntelResult` schema → 需关注 `llm_client.py`（Pydantic 模型）→ `llm_service.py`（generate_intel 调用）→ `scheduler_service.py`（_process_url 传参）→ `report_service.py`（报告模板渲染）→ `prompt_optimizer_service.py`（ai_report 拼接）
- 改了 `intel_user.md` 新增占位符 → 需关注 `prompt_optimizer.md`（保护清单）→ 否则优化器覆盖后链路断裂
- 改了 `IntelligenceFeed` 模型 → 需关注 DB migration → `serializers.py`（是否需要暴露新字段到 API）→ 前端 `ReportDetail` 接口

### 7.4 Context Gaps

- `CONTEXT GAP`：前端 `ReportDetail` 接口是否需要新增 `competitor_overview` 字段 → 当前前端通过 iframe 渲染 HTML 报告，不直接渲染情报字段，但 API 序列化器可能需要暴露该字段以保持接口一致性。建议动作：在 I1 plan 阶段确认 serializer 是否需要更新。
- `CONTEXT GAP`：飞书推送卡片是否需要展示 `competitor_overview` → 当前 `feishu_service.py` 推送内容基于 `change_summary`，需确认是否新增 `competitor_overview` 到卡片。建议动作：在 I1 plan 阶段检查 `feishu_service.py` 推送内容。
