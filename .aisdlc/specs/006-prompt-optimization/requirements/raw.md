# Prompt 自动优化系统

## 原始需求

完善系统的 AI 分析报告评分系统。当某个任务执行完成后，用户可以在报告页面对本次的输出结果进行实时评价。评价后调用后端的一个新的评分接口，调用本地的评分 prompt + 本次评分结果 + 系统的分析与生成的 prompt，发送给 LLM，让 LLM 去优化系统的相关 prompt 再改写系统的 prompt，帮助 LLM 在生成报告时更好地去迭代，升级系统的分析 prompt。

## 设计决策（已确认）

### 1. 优化范围

仅优化 `prompts/intel_system.md` 和 `prompts/intel_user.md`（情报生成 prompt），不优化 `denoise.md` 和 `diff_judge.md`。

### 2. 生效方式

LLM 优化的 prompt 自动生效，无需人工审批。需加版本表（PromptVersion）做回滚兜底。

### 3. 触发时机

仅当用户评分 = -1（没帮助）时触发优化。评分 = 1（有帮助）只存评分不触发优化。异步执行，不阻塞评分 API 响应。

### 4. 正向 few-shot

不需要。保持现有 negative few-shot 机制不变。

### 5. 优化 LLM 的输入

- 爬取到的 diff 文档（存储在 IntelligenceFeed.diff_text 新字段）
- clean 文档（LLM 降噪后的 MD，从 DataSnapshot.clean_md_path 读取）
- AI 生成的分析报告 MD（IntelligenceFeed 的 4 字段内容）
- 用户评分（user_feedback: -1 或 1）+ 用户评语（user_comment）
- 当前 intel_system.md 和 intel_user.md 的内容
- 优化 meta-prompt（新模板 prompt_optimizer.md）

### 6. diff 文档存储

在 IntelligenceFeed 新增 `diff_text` 字段（TextField），在扫描时计算 diff 后直接存入。原因：评分时重建 diff 可能因快照变化导致与实际执行时的 diff 不一致。

## 优化链路

```
用户在报告页评分 → 保存 rating（现有流程）
→ 异步触发 prompt 优化：
   收集 [diff_text + clean_md + AI 生成的分析报告 + 用户评分+评语 + 当前 intel_system/intel_user 内容]
   → 注入优化 meta-prompt → 发送给 LLM
   → LLM 返回优化后的 intel_system + intel_user
   → 写入 PromptVersion 版本表 + 覆盖 prompt 文件
   → 下次扫描自动生效
```

## 需要新增的组件

- `PromptVersion` 模型：版本表，存历史 prompt 内容，支持回滚
- `prompts/prompt_optimizer.md`：优化 meta-prompt 模板
- `apps/intelligence/services/prompt_optimizer_service.py`：优化服务函数
- `POST /api/feeds/{id}/optimize_prompt`：触发优化的 API 端点
- `prompt_loader.save_prompt()`：写回 prompt 文件能力
- IntelligenceFeed 新增 `diff_text` 字段 + migration
- 前端评分保存后异步调用优化接口

## 澄清记录

### R1-Q1：评分=1 时是否也触发优化？

- 本轮结论：仅评分 = -1（没帮助）时触发 LLM prompt 优化。评分 = 1（有帮助）只存评分不触发优化。
- 关键决策：差评才有改进方向 → 触发优化；好评说明当前 prompt 已够好 → 不触发。
- 约束更新：设计决策 #3 已从"每次评分都触发"修订为"仅 -1 触发"。

### R1-Q2：LLM 优化返回格式？

- 本轮结论：一次 LLM 调用同时返回优化后的 intel_system + intel_user，使用 instructor + Pydantic 结构化输出（OptimizedPrompts schema，含 intel_system / intel_user 两个字符串字段）。
- 关键决策：一次调用成本低，且两个 prompt 本身是配合使用的（system + user），一起优化更 coherent。

### R1-Q3：PromptVersion 版本表设计？

- 本轮结论：存全文。每次优化存一条记录，包含 prompt_name + 完整 prompt 内容 + version 号 + 触发优化的 feed_id + 优化原因（user_comment）。回滚时直接读取历史版本全文写回文件。
- 关键决策：prompt 本身不长（几 KB），存全文回滚最简单。

### R1-Q4：异步实现方式？

- 本轮结论：用 Python threading.Thread 启动后台线程执行 LLM 优化。评分 API 保存评分后立即返回 200，后台线程异步执行优化。线程异常通过 logger 记录，不影响评分本身。
- 关键决策：项目约束不引入消息队列，单用户场景下 threading 足够。不使用 Django async view（当前同步模式 + APScheduler，引入 ASGI 增加复杂度）。

### R1-Q5：优化失败处理？

- 本轮结论：优化 LLM 调用复用现有 @retry(max_retries=3, delay=30) 装饰器，重试耗尽后抛 LLMError，在 threading 内捕获并记录 logger.error。评分本身不受影响（评分已先于优化保存成功）。不向前端报错，静默失败。
- 关键决策：优化是"尽力而为"的增强功能，不应影响核心评分流程。

### R1-Q6：前端交互？

- 本轮结论：前端静默执行。评分保存成功后前端只显示"评分已保存"，不展示优化状态。优化完全在后端静默执行，用户无感知。下次报告生成时自动使用新 prompt。
- 关键决策：减少前端复杂度。用户可通过 PromptVersion 表（Django Admin）查看优化历史和回滚。
