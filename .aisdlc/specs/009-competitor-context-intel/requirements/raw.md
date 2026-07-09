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
