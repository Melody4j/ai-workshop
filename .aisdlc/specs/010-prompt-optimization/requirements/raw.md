现在系统中的提示词过于粗糙和简单，无法真正有效输出有价值的报告，而且经常因为一些无意义的diff而误判给出错误的分析报告，需要全面优化系统的提示词，改动尽量从提示词去改动，避免代码层面的大范围改动

## 澄清记录

### R1-Q1：代码改动边界

- 本轮结论：允许"提示词 + 最小代码改动"。以 prompt 改动为主，允许少量 Python 调整，包括：
  - 给 denoise / diff_judge 加 system message（当前只有 user message）
  - diff_judge 改用 instructor 结构化输出（替代手动正则解析 JSON）
  - 修复 prompt_optimizer 从本地读 prompt 而非 Blob 的版本不一致问题
  - 不改动链路结构（3 次 LLM 调用独立不变）和数据模型（IntelResult 字段不变）
- 本轮新增约束：
  1. 不改动 LLM 调用链路结构（3 次独立调用不合并）
  2. 不改动数据模型（IntelResult 5 字段不变）
  3. 不引入新的 LLM 调用次数

### R1-Q2：工作区修改基础

- 本轮结论：基于工作区当前版本继续迭代。工作区版本在 HEAD 基础上已做了一些改进（intel_system.md 防编造强化、intel_user.md 新增 {page_content} 占位符、diff_judge.md 严格标准），这些改进作为本次全面优化的起点。
- 本轮新增约束：
  1. 工作区已有修改（含 prompt + 对应代码）作为本次优化的基础，不撤销
  2. Blob 已同步为工作区版本，本次优化完成后需重新上传 Blob

### R1-Q3：优化范围

- 本轮结论：全部 5 个 prompt 模板均纳入优化范围，包括 prompt_optimizer.md（元优化 prompt）。
- 本轮新增约束：
  1. 优化对象：denoise.md / diff_judge.md / intel_system.md / intel_user.md / prompt_optimizer.md
  2. prompt_optimizer.md 的优化需同步更新占位符保护列表（新增 {page_content}）

### R1-Q4：denoise 降噪策略

- 本轮结论：保持单一 prompt，但增加更具体的规则和正/反例，不做网站类型差异化区分。让 LLM 通过更明确的规则和示例来判断什么该保留、什么该去除。
- 本轮新增约束：
  1. denoise 保持单一 prompt，不拆分为多个网站类型版本
  2. 优化方向：规则细化 + 保留/去除的正例反例
