## 竞品补充文档链路打通 + Intel Prompt 优化

### 问题背景

当前情报分析报告质量不够理想，分析内容过于简陋，抓不到重点。经排查发现两个核心问题：

#### 问题 1：竞品补充文档已收集但从未注入 LLM

前端表单已支持为每个竞品上传补充文档（`competitor_contexts` 字段，含 `supplement_doc_name` + `supplement_doc_content`），数据已存入 `MonitorProject.competitor_contexts` JSONField。但该数据在调度链路中被完全跳过：

- `scheduler_service._process_url()` 调用 `generate_intel()` 时未传入 `competitor_contexts`
- `generate_intel()` 方法签名无 `competitor_context` 参数
- `intel_system.md` prompt 只有 `{self_product_doc}` 占位符，无竞品上下文占位符
- `intel_user.md` prompt 只有 `{diff_text}` + `{negative_few_shots}`，无竞品背景

结果：LLM 只能从 diff 的字面内容做泛泛分析，缺乏竞品背景知识，无法深入。

#### 问题 2：Intel Prompt 过于简陋

当前 `intel_system.md` 和 `intel_user.md` 的分析要求过于简单，导致 LLM 输出内容太少：
- 变化摘要仅 1-3 句话
- 战略意图分析不够深入
- 行动建议不够具体
- 缺乏对竞品整体定位和行业态势的理解

### 需求

1. **打通竞品补充文档链路**：`_process_url` 按 URL 匹配 `competitor_contexts` 中对应的条目 → 传入 `generate_intel()` → 注入 prompt 模板
2. **重写 Intel Prompt**：加入竞品背景上下文，深化分析要求，丰富输出结构，让 LLM 能够结合竞品定位和行业态势产出高质量情报分析

## 澄清记录

### R1-Q1：竞品上下文匹配方式（已裁决）

- 本轮结论：调度链路中按 **index 对齐** 匹配 `competitor_contexts[idx]` 与 `competitor_urls[idx]`，与前端数据结构一致。若 index 越界或 `competitor_contexts` 为空，则视为该竞品无补充文档。
- 本轮约束：
  1. `_process_url` 遍历 `competitor_urls` 时，同时按 `enumerate` 索引取 `competitor_contexts[idx]`
  2. 序列化器已保证两个数组 count 对齐（`validate()` 跨字段校验），调度层不再做 URL 匹配
  3. `competitor_contexts` 为空列表或 index 越界时，`supplement_doc_content` 视为空字符串
- 关键决策：按 index 对齐（不按 URL 精确匹配），理由是前端和序列化器已保证对齐，无需重复校验

### R1-Q2：竞品上下文注入位置（已裁决）

- 本轮结论：竞品补充文档注入到 **intel_user.md**（user prompt），与 diff_text、negative_few_shots 同处 user 角色。intel_system.md 保留 self_product_doc + 分析角色定义 + 分析要求。
- 本轮约束：
  1. `intel_user.md` 新增 `{competitor_context}` 占位符，与 `{diff_text}` + `{negative_few_shots}` 并列
  2. `intel_system.md` 不新增竞品上下文占位符，但需重写分析要求以深化输出结构
  3. `generate_intel()` 新增 `competitor_context` 参数，注入到 `load_prompt("intel_user", ...)` 调用
- 关键决策：注入 user prompt（不注入 system prompt），理由是竞品上下文是每次分析的具体输入材料，与 diff 同层级；system prompt 聚焦角色定义和我方产品锚定

### R1-Q3：IntelResult schema 变更（已裁决）

- 本轮结论：IntelResult 从 4 字段扩展为 **5 字段**，新增 `competitor_overview`（竞品概述）。不变量 #4 需修订为"情报输出固定 5 字段"。
- 本轮约束：
  1. 新增字段 `competitor_overview`：基于竞品补充文档和 diff 综合分析，提供竞品整体定位与背景概述，让报告开头有竞品全景视角
  2. 原 4 字段保持不变：`change_summary` / `strategic_intent` / `action_suggestion` / `evidence_diff`
  3. `IntelResult` Pydantic 模型需新增 `competitor_overview: str` 字段
  4. `IntelligenceFeed` 模型需新增 `competitor_overview` DB 字段（需 migration）
  5. 报告模板（HTML + MD）需新增竞品概述的渲染区块
  6. 不变量 #4 修订：从"固定 4 字段，不含价值度字段"改为"固定 5 字段，不含价值度字段"
- 关键决策：新增 `competitor_overview` 字段（不新增 industry_insight / urgency_assessment / signal_level），理由是该字段最直接地利用竞品补充文档提供背景视角，与链路打通目标一致

### R1-Q4：Prompt 优化器兼容性（已裁决）

- 本轮结论：**同步更新** `prompt_optimizer.md`，在占位符保护清单中新增 `{competitor_context}`，并在 `ai_report` 拼接中加入 `competitor_overview` 字段内容。
- 本轮约束：
  1. `prompt_optimizer.md` 第 41 行占位符保护清单新增 `{competitor_context}`（intel_user 中）
  2. `prompt_optimizer_service.py` 中 `ai_report` 拼接新增 `competitor_overview` 段落
  3. 优化器产出的 prompt 必须保留 `{competitor_context}` 占位符，否则后续情报生成会因 `load_prompt` 的 `str.replace` 无法匹配而出错
- 关键决策：同步更新优化器（不跳过），理由是优化器直接覆盖文件，不保护占位符会导致链路断裂

### R1-Q5：空值处理（已裁决）

- 本轮结论：当竞品无补充文档时，prompt 模板始终包含竞品上下文段落，内容注入 **"暂无竞品补充文档"** 占位文本。LLM 看到该信号后可跳过背景分析，聚焦 diff 内容。
- 本轮约束：
  1. `intel_user.md` 模板固定包含 `## 竞品补充文档` 段落 + `{competitor_context}` 占位符
  2. `_process_url` 或 `generate_intel` 在传入前格式化：有内容时拼接 `supplement_doc_name` + `supplement_doc_content`；无内容时填 "暂无竞品补充文档"
  3. 模板结构固定，`load_prompt` 不需要条件分支
- 关键决策：注入空占位文本（不传空字符串），理由是保持 prompt 结构一致性，避免 LLM 因段落缺失而困惑
