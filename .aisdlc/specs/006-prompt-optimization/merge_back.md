# Merge-back：006-prompt-optimization

> 本文件是 Spec 006 的需求级 merge-back SSOT，记录每条晋升项的 project 落点、不变量摘要、证据入口与状态。

## 晋升清单

### MB-001：intelligence-models 数据契约更新

- **project 落点**：`.aisdlc/project/components/intelligence-models.md#data-contract`
- **变更内容**：
  - `IntelligenceFeed.diff_text`（TextField, blank=True, default=""）— 存储 diff 文本供 prompt 优化上下文使用
  - `PromptVersion` 模型（prompt_name / content / version / feed FK SET_NULL / optimization_reason）— prompt 版本存档与回滚
  - 迁移：`0006_diff_text_promptversion.py`
- **不变量摘要**：
  1. `diff_text` 在所有 `IntelligenceFeed.objects.create()` 调用中写入（CHANGED=实际diff, NO_CHANGE=""或diff, 首次爬取=llm_clean_md全量）
  2. `PromptVersion.version` 按 `prompt_name` 分组自增（max version + 1）
  3. `PromptVersion.feed` 使用 `SET_NULL`，feed 删除后版本记录保留
- **证据入口**：
  - 模型：`backend/apps/intelligence/models.py`
  - 迁移：`backend/apps/intelligence/migrations/0006_diff_text_promptversion.py`
  - 测试：`backend/apps/intelligence/tests/test_api.py`（FeedOptimizePromptViewTest）
- **状态**：Done
- **代码来源**：根项目

### MB-002：llm-service 模块页更新（第 4 类 LLM 调用）

- **project 落点**：`.aisdlc/project/components/llm-service.md#service-contract`
- **变更内容**：
  - 新增第 4 类 LLM 调用：`prompt_optimizer_service.optimize_prompts(feed_id)`
  - 使用 instructor + Pydantic `OptimizedPrompts` schema（intel_system + intel_user 双字段返回）
  - @retry(max_retries=3, delay=30)，与现有 3 次调用一致
  - Prompt 模板：`prompts/prompt_optimizer.md`
  - `prompt_loader.save_prompt(name, content)` 新函数：覆盖写回 prompt 文件
- **不变量摘要**：
  1. 第 4 次 LLM 调用独立于情报生成 3 次调用链路，仅由评分=-1 触发
  2. 一次 LLM 调用返回 intel_system + intel_user 两个 prompt（不分两次）
  3. 返回内容校验：< 50 字符 → raise ValueError
  4. `save_prompt` 直接覆盖文件，无审批步骤（退化风险由 PromptVersion 回滚兜底）
- **证据入口**：
  - 服务：`backend/apps/intelligence/services/prompt_optimizer_service.py`
  - Schema：`backend/apps/intelligence/services/llm_client.py`（OptimizedPrompts）
  - Prompt 加载/保存：`backend/apps/intelligence/services/prompt_loader.py`
  - Prompt 模板：`backend/prompts/prompt_optimizer.md`
  - 测试：`backend/apps/intelligence/tests/test_prompt_optimizer_service.py`
- **状态**：Done
- **代码来源**：根项目

### MB-003：intelligence-api 契约更新

- **project 落点**：`.aisdlc/project/components/intelligence-api.md#api-contract`
- **变更内容**：
  - `POST /api/feeds/{id}/optimize_prompt`：手动触发 prompt 优化，同步返回 `{"intel_system_version": N, "intel_user_version": M}`
  - `ReportRatingView.post()` 和 `patch()`：评分=-1 时异步触发优化（threading.Thread, daemon=True）
  - 前端 `RatingForm.vue`：评分+评语都有时禁用评分控件（isComplete computed）
- **不变量摘要**：
  1. `POST /api/feeds/{id}/optimize_prompt` 同步调用 optimize_prompts，返回版本号
  2. 评分=-1 通过 POST 或 PATCH 均触发异步优化
  3. 评分=+1 不触发优化
  4. 异步优化失败不影响评分保存（threading 内 try-except）
  5. 前端已完成评分（有评分+有评语）时禁用评分控件，需清空后才能重新评分
- **证据入口**：
  - 路由：`backend/apps/intelligence/urls.py`
  - 视图：`backend/apps/intelligence/views.py`（FeedOptimizePromptView, ReportRatingView）
  - 前端：`frontend/src/components/reports/RatingForm.vue`
  - 测试：`backend/apps/intelligence/tests/test_api.py`（FeedOptimizePromptViewTest, ReportRatingOptimizeTriggerTest）
- **状态**：Done
- **代码来源**：根项目

### MB-004：intelligence-scheduler 服务契约更新

- **project 落点**：`.aisdlc/project/components/intelligence-scheduler.md#service-contract`
- **变更内容**：
  - `_process_url` 所有 `IntelligenceFeed.objects.create()` 调用添加 `diff_text` 参数
  - CHANGED：diff_text = 实际 diff 内容
  - NO_CHANGE（文本diff空）：diff_text = ""
  - NO_CHANGE（LLM判断无意义）：diff_text = diff内容
  - ERROR_CRAWL：diff_text = "" 或 diff内容
  - 首次爬取/旧格式：diff_text = llm_clean_md 全量
  - `run_scan()` 无活跃项目时直接 return（不打印日志）
- **不变量摘要**：
  1. 所有 IntelligenceFeed 记录创建时必须写入 diff_text（空或非空由场景决定）
  2. diff_text 是 prompt 优化的上下文来源（非独立展示字段）
- **证据入口**：
  - 服务：`backend/apps/intelligence/services/scheduler_service.py`
  - 测试：`backend/apps/intelligence/tests/test_scheduler_service.py`
- **状态**：Done
- **代码来源**：根项目

### MB-005：prompt_loader 模块页更新

- **project 落点**：`.aisdlc/project/components/llm-service.md#service-contract`（合并到 llm-service 模块页，不单独建组件页）
- **变更内容**：
  - `save_prompt(name, content)` 新函数：将内容写回 `prompts/{name}.md`（UTF-8）
  - 与 `load_prompt` 共享 `PROMPTS_DIR` 路径
- **不变量摘要**：
  1. `save_prompt` 直接覆盖文件，无版本控制（版本控制由 PromptVersion 表负责）
  2. 仅 `prompt_optimizer_service` 调用 `save_prompt`
- **证据入口**：
  - 代码：`backend/apps/intelligence/services/prompt_loader.py`
  - 测试：`backend/apps/intelligence/tests/test_prompt_loading.py`
- **状态**：Done
- **代码来源**：根项目

### MB-006：ops 更新

- **project 落点**：`.aisdlc/project/ops/index.md`
- **变更内容**：
  - Prompt 优化服务入口：`backend/apps/intelligence/services/prompt_optimizer_service.py`
  - Prompt 版本管理：Django Admin → PromptVersion（查看历史 / 回滚）
  - Prompt 文件位置：`backend/prompts/intel_system.md` / `backend/prompts/intel_user.md`（可被覆盖）
  - 回滚操作：从 PromptVersion 复制 content 回 prompt 文件
  - APScheduler 日志级别调整为 WARNING（减少调度噪声）
- **证据入口**：
  - Admin：`backend/apps/intelligence/admin.py`（PromptVersionAdmin）
  - 配置：`backend/config/settings.py`（LOGGING）
  - 服务：`backend/apps/intelligence/services/prompt_optimizer_service.py`
- **状态**：Done
- **代码来源**：根项目

### MB-007：registry 更新

- **project 落点**：`.aisdlc/project/index.md`
- **变更内容**：
  - 更新已晋升资产表：intelligence-models / intelligence-api / intelligence-scheduler / llm-service / ops 增加 006-prompt-optimization 来源
  - 最近一次 merge-back 更新为 `006-prompt-optimization`
- **状态**：Done
- **代码来源**：根项目
