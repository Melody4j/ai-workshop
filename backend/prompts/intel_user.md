请分析以下竞品变化，产出深度竞争情报报告。

## 竞品变化 diff

{diff_text}

## 竞品补充文档

{competitor_context}

## 历史反面案例（请避免类似分析）

{negative_few_shots}

## 输出要求

请输出以下 5 个字段，每个字段都要内容充实、分析深入：

1. **竞品概述（competitor_overview）**：基于补充文档和变化内容，概述竞品整体定位、核心业务、目标用户和竞争策略。2-4 段。
2. **变化摘要（change_summary）**：简述竞品发生了什么变化，点明变化类型和重点。3-5 句话。
3. **战略意图（strategic_intent）**：推断竞品此举的战略目的，分析对我方和行业的影响，标注事实推断与假设。
4. **行动建议（action_suggestion）**：结合我方产品定位，给出 3-5 条具体可执行的行动建议，包含优先级和时间敏感性。
5. **证据 diff（evidence_diff）**：从 diff 中选取最有分析价值的 3-5 个关键变化片段，格式为 `> 变化片段` + 标注支撑的分析结论。不要全量复制 diff。

## 输出格式

严格按 JSON 格式输出，每个字段为字符串类型：

```json
{
  "competitor_overview": "...",
  "change_summary": "...",
  "strategic_intent": "...",
  "action_suggestion": "...",
  "evidence_diff": "..."
}
```
