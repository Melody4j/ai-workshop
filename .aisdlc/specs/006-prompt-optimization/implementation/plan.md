---
title: I1 Implementation Plan（SSOT）
status: draft
---

# Prompt 自动优化系统 实现计划（SSOT）

> **必需技能：** `spec-execute`（按批次执行本计划）
> **上下文获取：** 必须先执行 `spec-context` 获取上下文，定位 `{FEATURE_DIR}`，失败即停止

**目标：** 用户对报告评"没帮助"(-1)后，后端异步调用 LLM 分析差评原因并优化情报生成 prompt（intel_system + intel_user），覆盖写回文件，下次扫描自动生效。
**范围：** In = diff_text 字段 + PromptVersion 模型 + prompt_optimizer_service + API 端点 + 评分触发 + meta-prompt 模板；Out = 不优化 denoise/diff_judge、不做前端状态展示、不做 A/B 验证
**架构：** threading 异步执行 LLM 优化调用（instructor + Pydantic OptimizedPrompts），优化后覆盖 prompts/ 文件 + PromptVersion 存全文版本。复用现有 @retry、llm_client、prompt_loader 基础设施。
**验收口径：** `requirements/solution.md` Mini-PRD AC-001~AC-008
**影响范围：** `requirements/solution.md#impact-analysis` — intelligence-models / intelligence-api / llm-service / intelligence-scheduler / prompt_loader
**需遵守的不变量：** 3 次 LLM 调用独立不合并；user_feedback 仅 -1/1/null；情报输出固定 4 字段；Negative Few-Shot 上限 5 条；load_prompt 用 str.replace（占位符必须保留）；OpenAI 兼容 API
**子仓范围：** 无

---

## TL;DR

- 一句话目标：评分=-1 触发 LLM 自动优化情报生成 prompt，版本存档，静默生效。
- In：模型变更(diff_text + PromptVersion) + prompt_loader.save_prompt + OptimizedPrompts schema + prompt_optimizer_service + scheduler 存 diff_text + API 端点 + 评分触发 + Admin 注册
- Out：不优化 denoise/diff_judge；不做前端状态展示；不做 A/B 验证
- 关键路径：T1(模型) → T2(save_prompt) → T3(schema+模板) → T4(service) → T5(scheduler存diff) → T6(API+触发) → T7(Admin) → T8(全量验证)
- 最大风险与优先验证点：V-001(prompt 退化)、V-003(threading DB 安全)

---

## 范围与边界（In / Out）

- **In**：
  - IntelligenceFeed 新增 `diff_text` 字段（TextField, blank=True, default=""）
  - PromptVersion 新增模型（prompt_name / content / version / feed_id / optimization_reason）
  - `prompt_loader.save_prompt(name, content)` 写回文件能力
  - `OptimizedPrompts` Pydantic schema（intel_system + intel_user 两字段）
  - `prompts/prompt_optimizer.md` meta-prompt 模板
  - `prompt_optimizer_service.py` 优化服务函数
  - `scheduler_service._process_url` 存 diff_text 到 IntelligenceFeed
  - `POST /api/feeds/{id}/optimize_prompt` 手动触发端点
  - `ReportRatingView` 评分=-1 后 threading 异步触发优化
  - Django Admin 注册 PromptVersion
- **Out**：
  - 不优化 denoise.md / diff_judge.md
  - 不做前端优化状态展示
  - 不做 A/B 对比验证
  - 不做自动回滚机制（手动通过 Django Admin）
  - 不引入消息队列
- **不变量/关键约束**：
  - 优化后的 prompt 文件必须保留 {self_product_doc} / {diff_text} / {negative_few_shots} 占位符
  - 优化是第 4 类 LLM 调用，不影响现有 3 次（denoise / judge_diff / generate_intel）
  - 优化失败不影响评分已保存的结果
  - 仅 user_feedback=-1 触发优化
- **影响面**：models / api / llm-service / scheduler / prompt_loader / admin

---

## 里程碑与节奏

- M0（MVP）：T1~T8 全部完成，全量测试通过，Django check 通过

---

## 依赖与资源

- 环境：本地开发环境（runserver + SQLite），LLM API（.env 配置）
- 外部系统：LLM API（OpenAI 兼容）
- 数据：现有 IntelligenceFeed / DataSnapshot 数据（开发环境）

---

## 风险与验证（可执行）

| # | 风险/假设 | 验证方式 | 成功信号 | 失败信号 | Owner | 截止 | 下一步动作 |
|---|---|---|---|---|---|---|---|
| R1 | prompt 退化 | 收集 10 次优化前后对比 | ≥7/10 不降低 | <7/10 | DEV | 实现后1周 | 加 A/B 对比机制 |
| R2 | LLM 返回空/截断 | 测试 20 次调用 | 20/20 非空>50字 | 有空/截断 | DEV | 实现后3天 | 加校验逻辑或分两次 |
| R3 | threading DB 连接 | 模拟 10 次并发 | 无连接泄漏 | 有泄漏 | DEV | 实现后3天 | 加 connection.close() |
| R4 | 文件并发写 | 模拟 2 并发写 | 文件不损坏 | 损坏 | DEV | 实现后3天 | 加文件锁 |

---

## 验收口径（可追溯）

- 追溯：`requirements/solution.md` Mini-PRD AC-001~AC-008
- 关键验收点：
  - AC-001：diff_text 字段，CHANGED 非空，NO_CHANGE/ERROR_CRAWL 空字符串
  - AC-002：PromptVersion 每次优化 2 条记录，含全文+version+feed_id
  - AC-003：POST /api/feeds/{id}/optimize_prompt 返回 200
  - AC-004：评分=-1 触发优化；评分=1 不触发
  - AC-005：优化后文件被覆盖
  - AC-006：优化后 prompt 保留占位符
  - AC-007：优化失败记日志，不影响评分
  - AC-008：PromptVersion 可在 Admin 查看

---

## NEEDS CLARIFICATION（未消除前不得进入 I2）

无。所有关键决策已在 R1 六轮澄清中解决。

---

## 任务清单（SSOT）

### Task T1: 模型变更 — IntelligenceFeed.diff_text + PromptVersion + migration

- [ ] **状态**：未开始

**代码仓范围：**
- 根项目：`backend/apps/intelligence/`

**文件：**
- 修改：`backend/apps/intelligence/models.py`（IntelligenceFeed 新增 diff_text；新增 PromptVersion 模型）
- 创建：`backend/apps/intelligence/migrations/0006_diff_text_promptversion.py`（auto-generated）

**验收点：**
- IntelligenceFeed.diff_text 为 TextField(blank=True, default="")
- PromptVersion 含字段：prompt_name(CharField max 50) / content(TextField) / version(IntegerField) / feed(ForeignKey to IntelligenceFeed, null=True, on_delete=SET_NULL) / optimization_reason(TextField blank=True) / created_at(auto_now_add)
- PromptVersion.Meta.ordering = ["-version", "-id"]
- migration 可正常 migrate

**步骤 1：修改 models.py**
- 修改点：IntelligenceFeed 类新增 `diff_text = models.TextField(blank=True, default="")`；文件末尾新增 PromptVersion 类（继承 TimestampedModel）
- PromptVersion 定义：
  ```python
  class PromptVersion(TimestampedModel):
      prompt_name = models.CharField(max_length=50)
      content = models.TextField()
      version = models.IntegerField(default=1)
      feed = models.ForeignKey(
          IntelligenceFeed,
          on_delete=models.SET_NULL,
          null=True,
          blank=True,
          related_name="prompt_versions",
      )
      optimization_reason = models.TextField(blank=True)

      class Meta:
          ordering = ["-version", "-id"]

      def __str__(self):
          return f"{self.prompt_name} v{self.version}"
  ```

**步骤 2：生成 migration**
- Run: `cd /Users/melody/code/ai-workshop && .venv/bin/python manage.py makemigrations intelligence --name diff_text_promptversion`
- Expected: 生成 0006_diff_text_promptversion.py

**步骤 3：运行 migrate**
- Run: `cd /Users/melody/code/ai-workshop && .venv/bin/python manage.py migrate`
- Expected: Applying 0006_diff_text_promptversion... OK

**步骤 4：提交**
- Commit message: `feat: 新增 IntelligenceFeed.diff_text 字段 + PromptVersion 模型`
- 审计信息：
  - repo: `root`
    branch: `006-prompt-optimization`
    commit: `<TBD>`
    pr: `<TBD>`
    changed_files:
      - `backend/apps/intelligence/models.py`
      - `backend/apps/intelligence/migrations/0006_diff_text_promptversion.py`

---

### Task T2: prompt_loader.save_prompt() 写回文件能力

- [ ] **状态**：未开始

**代码仓范围：**
- 根项目：`backend/apps/intelligence/services/`

**文件：**
- 修改：`backend/apps/intelligence/services/prompt_loader.py`（新增 save_prompt 函数）
- 修改：`backend/apps/intelligence/tests/test_prompt_loading.py`（新增 save_prompt 测试）

**验收点：**
- `save_prompt(name, content)` 将 content 写入 `prompts/{name}.md`（UTF-8 编码）
- 写入后 `load_prompt(name)` 能正确读取新内容
- 不影响现有 `load_prompt` 函数

**步骤 1：写失败测试**
- 修改点：`test_prompt_loading.py` 新增 `test_save_prompt_writes_file` 和 `test_save_prompt_roundtrip`
- Run: `cd /Users/melody/code/ai-workshop && .venv/bin/python manage.py test apps.intelligence.tests.test_prompt_loading --verbosity=2`
- Expected: FAIL（save_prompt 不存在 → AttributeError）

**步骤 2：写最少实现**
- 修改点：`prompt_loader.py` 新增：
  ```python
  def save_prompt(name: str, content: str) -> None:
      """将内容写回 Prompt 模板文件。"""
      file_path = PROMPTS_DIR / f"{name}.md"
      file_path.write_text(content, encoding="utf-8")
      logger.info(f"[Prompt] 已保存模板 {name}，{len(content)} 字符")
  ```

**步骤 3：运行验证**
- Run: `cd /Users/melody/code/ai-workshop && .venv/bin/python manage.py test apps.intelligence.tests.test_prompt_loading --verbosity=2`
- Expected: PASS

**步骤 4：提交**
- Commit message: `feat: prompt_loader 新增 save_prompt 写回文件能力`
- 审计信息：
  - repo: `root`
    branch: `006-prompt-optimization`
    commit: `<TBD>`
    pr: `<TBD>`
    changed_files:
      - `backend/apps/intelligence/services/prompt_loader.py`
      - `backend/apps/intelligence/tests/test_prompt_loading.py`

---

### Task T3: OptimizedPrompts Pydantic schema + prompt_optimizer.md meta-prompt 模板

- [ ] **状态**：未开始

**代码仓范围：**
- 根项目：`backend/apps/intelligence/services/llm_client.py` + `backend/prompts/`

**文件：**
- 修改：`backend/apps/intelligence/services/llm_client.py`（新增 OptimizedPrompts 类）
- 创建：`backend/prompts/prompt_optimizer.md`（优化 meta-prompt 模板）

**验收点：**
- `OptimizedPrompts` Pydantic schema 含 `intel_system: str` + `intel_user: str` 两字段
- `prompt_optimizer.md` 含占位符：`{diff_text}` / `{clean_md}` / `{ai_report}` / `{user_comment}` / `{current_intel_system}` / `{current_intel_user}`
- 模板指令 LLM：分析用户为何不满意 → 优化两个 prompt → 保留占位符

**步骤 1：新增 OptimizedPrompts schema**
- 修改点：`llm_client.py` 新增：
  ```python
  class OptimizedPrompts(BaseModel):
      """LLM prompt 优化结果 schema（2 字段，instructor 约束）。"""
      intel_system: str = Field(..., description="优化后的情报生成 system prompt 全文")
      intel_user: str = Field(..., description="优化后的情报生成 user prompt 全文")
  ```

**步骤 2：创建 prompt_optimizer.md**
- 修改点：`backend/prompts/prompt_optimizer.md`
- 模板内容要点：
  - 角色：Prompt 优化专家
  - 输入：差评报告的 diff_text / clean_md / AI 分析报告 / 用户评语 / 当前两个 prompt 全文
  - 任务：分析用户为何不满意 → 优化两个 prompt → 保留 {self_product_doc} / {diff_text} / {negative_few_shots} 占位符
  - 输出格式：instructor OptimizedPrompts schema

**步骤 3：运行验证**
- Run: `cd /Users/melody/code/ai-workshop && .venv/bin/python -c "from apps.intelligence.services.llm_client import OptimizedPrompts; print(OptimizedPrompts.model_fields.keys())"`
- Expected: `dict_keys(['intel_system', 'intel_user'])`

**步骤 4：提交**
- Commit message: `feat: 新增 OptimizedPrompts schema + prompt_optimizer.md meta-prompt 模板`
- 审计信息：
  - repo: `root`
    branch: `006-prompt-optimization`
    commit: `<TBD>`
    pr: `<TBD>`
    changed_files:
      - `backend/apps/intelligence/services/llm_client.py`
      - `backend/prompts/prompt_optimizer.md`

---

### Task T4: prompt_optimizer_service.py 优化服务函数

- [ ] **状态**：未开始

**代码仓范围：**
- 根项目：`backend/apps/intelligence/services/`

**文件：**
- 创建：`backend/apps/intelligence/services/prompt_optimizer_service.py`
- 创建：`backend/apps/intelligence/tests/test_prompt_optimizer_service.py`

**验收点：**
- `optimize_prompts(feed_id)` 函数：读取 feed → 收集上下文 → 调用 LLM → 写 PromptVersion → 覆盖文件
- 每次优化生成 2 条 PromptVersion 记录（intel_system + intel_user 各一条）
- version 号自增（查当前 prompt_name 的 max version + 1）
- 优化后的文件保留 {self_product_doc} / {diff_text} / {negative_few_shots} 占位符
- @retry(max_retries=3, delay=30) 装饰器复用
- 优化失败抛 LLMError（由调用方捕获）

**步骤 1：写失败测试**
- 修改点：`test_prompt_optimizer_service.py`
- 测试用例：
  - `test_optimize_prompts_creates_version_records`：mock LLM 返回 → 验证 2 条 PromptVersion 记录 + version 自增
  - `test_optimize_prompts_overwrites_files`：mock LLM → 验证 prompts/ 文件被覆盖
  - `test_optimize_prompts_preserves_placeholders`：mock LLM 返回含占位符 → 验证文件含占位符
  - `test_optimize_prompts_reads_feed_context`：mock LLM → 验证 LLM 调用参数包含 diff_text / clean_md / ai_report / user_comment
  - `test_optimize_prompts_llm_failure_raises`：mock LLM raise → 验证抛 LLMError
- Run: `cd /Users/melody/code/ai-workshop && .venv/bin/python manage.py test apps.intelligence.tests.test_prompt_optimizer_service --verbosity=2`
- Expected: FAIL（模块不存在 → ImportError）

**步骤 2：写最少实现**
- 修改点：创建 `prompt_optimizer_service.py`
- 核心函数：
  ```python
  @retry(max_retries=3, delay=30)
  def optimize_prompts(feed_id: int) -> dict:
      """收集上下文 → LLM 优化 → 版本存档 → 覆盖文件。"""
      # 1. 读取 feed
      # 2. 收集上下文：diff_text(feed.diff_text) / clean_md(读 DataSnapshot.clean_md_path) / ai_report(4字段拼接) / user_comment
      # 3. 读取当前 prompt 全文
      # 4. 注入 prompt_optimizer.md → 调用 LLM (instructor + OptimizedPrompts)
      # 5. 写 PromptVersion 记录（intel_system + intel_user 各一条，version 自增）
      # 6. save_prompt 覆盖文件
      # 7. 返回 {"intel_system_version": N, "intel_user_version": M}
  ```

**步骤 3：运行验证**
- Run: `cd /Users/melody/code/ai-workshop && .venv/bin/python manage.py test apps.intelligence.tests.test_prompt_optimizer_service --verbosity=2`
- Expected: PASS（5 用例全部通过）

**步骤 4：提交**
- Commit message: `feat: 新增 prompt_optimizer_service 优化服务（LLM 优化 + 版本存档 + 文件覆盖）`
- 审计信息：
  - repo: `root`
    branch: `006-prompt-optimization`
    commit: `<TBD>`
    pr: `<TBD>`
    changed_files:
      - `backend/apps/intelligence/services/prompt_optimizer_service.py`
      - `backend/apps/intelligence/tests/test_prompt_optimizer_service.py`

---

### Task T5: scheduler_service._process_url 存 diff_text

- [ ] **状态**：未开始

**代码仓范围：**
- 根项目：`backend/apps/intelligence/services/`

**文件：**
- 修改：`backend/apps/intelligence/services/scheduler_service.py`（_process_url 中所有 IntelligenceFeed.objects.create 调用新增 diff_text 赋值）
- 修改：`backend/apps/intelligence/tests/test_scheduler_service.py`（新增 diff_text 验证）
- 修改：`backend/apps/intelligence/tests/test_llm_pipeline_e2e.py`（新增 diff_text 验证）

**验收点：**
- CHANGED 记录的 diff_text 非空（含实际 diff 内容或首次爬取的 clean_md）
- NO_CHANGE 记录的 diff_text 为空字符串（diff 为空熔断时）
- ERROR_CRAWL 记录的 diff_text 为空字符串
- 首次爬取（skip_diff=True）的 CHANGED 记录 diff_text = llm_clean_md（全量内容）

**步骤 1：修改 scheduler_service.py**
- 修改点：`_process_url` 中所有 `IntelligenceFeed.objects.create(...)` 调用添加 `diff_text=diff_text`
  - Step 9 CHANGED 创建：`diff_text=diff_text`（此时 diff_text 有值）
  - Step 6 NO_CHANGE 熔断（diff 为空）：`diff_text=""`
  - Step 7 NO_CHANGE 熔断（LLM 判断无意义）：`diff_text=diff_text`（此时 diff_text 有值，但判断无意义）
  - 采集失败 / LLM 失败 ERROR_CRAWL：`diff_text=""`（此时 diff_text 未赋值，默认 ""）
- 注意：diff_text 变量在函数开头已初始化为 `""`（现有代码 `diff_text = ""`），需确保各路径正确赋值

**步骤 2：新增测试**
- 修改点：`test_scheduler_service.py` 新增 `test_changed_feed_stores_diff_text` / `test_no_change_feed_empty_diff_text`
- 修改点：`test_llm_pipeline_e2e.py` 的 `test_S001_full_chain_changed` 新增 diff_text 断言

**步骤 3：运行验证**
- Run: `cd /Users/melody/code/ai-workshop && .venv/bin/python manage.py test apps.intelligence.tests.test_scheduler_service apps.intelligence.tests.test_llm_pipeline_e2e --verbosity=2`
- Expected: PASS

**步骤 4：提交**
- Commit message: `feat: scheduler_service 存储 diff_text 到 IntelligenceFeed`
- 审计信息：
  - repo: `root`
    branch: `006-prompt-optimization`
    commit: `<TBD>`
    pr: `<TBD>`
    changed_files:
      - `backend/apps/intelligence/services/scheduler_service.py`
      - `backend/apps/intelligence/tests/test_scheduler_service.py`
      - `backend/apps/intelligence/tests/test_llm_pipeline_e2e.py`

---

### Task T6: API 端点 + ReportRatingView 评分触发

- [ ] **状态**：未开始

**代码仓范围：**
- 根项目：`backend/apps/intelligence/views.py` + `urls.py`

**文件：**
- 修改：`backend/apps/intelligence/views.py`（新增 FeedOptimizePromptView；修改 ReportRatingView post 方法评分=-1 后 threading 触发）
- 修改：`backend/apps/intelligence/urls.py`（新增路由）
- 修改：`backend/apps/intelligence/tests/test_api.py`（新增 API 测试）

**验收点：**
- `POST /api/feeds/{id}/optimize_prompt`：手动触发优化，返回 200 + 优化结果摘要
- ReportRatingView POST 评分=-1 后启动 threading.Thread 执行 optimize_prompts
- ReportRatingView POST 评分=1 不触发优化
- 评分 API 响应不等待优化完成（立即返回 200）
- threading 内 try-except 捕获异常 + logger.error

**步骤 1：写失败测试**
- 修改点：`test_api.py` 新增：
  - `test_optimize_prompt_endpoint`：POST /api/feeds/{id}/optimize_prompt → 200
  - `test_rating_minus1_triggers_optimization`：mock optimize_prompts → 评分=-1 → 验证被调用
  - `test_rating_plus1_does_not_trigger`：评分=1 → 验证 optimize_prompts 未被调用
  - `test_optimize_prompt_feed_not_found`：不存在 feed_id → 404
- Run: `cd /Users/melody/code/ai-workshop && .venv/bin/python manage.py test apps.intelligence.tests.test_api --verbosity=2`
- Expected: FAIL（端点不存在 → 404 或 ImportError）

**步骤 2：写最少实现**
- 修改点：`views.py`
  - 新增 `FeedOptimizePromptView`（APIView，POST 方法调 prompt_optimizer_service.optimize_prompts）
  - 修改 `ReportRatingView.post`：评分保存后检查 `user_feedback == -1`，若是则 `threading.Thread(target=optimize_prompts, args=(feed.pk,)).start()`
  - threading 导入：`import threading, logging`
  - 异常处理：`threading.Thread` 内包装 `_async_optimize_prompts(feed_id)` 函数，try-except logger.error

**步骤 3：新增路由**
- 修改点：`urls.py` 新增 `path("feeds/<int:pk>/optimize_prompt", FeedOptimizePromptView.as_view(), name="feed-optimize-prompt")`

**步骤 4：运行验证**
- Run: `cd /Users/melody/code/ai-workshop && .venv/bin/python manage.py test apps.intelligence.tests.test_api --verbosity=2`
- Expected: PASS

**步骤 5：提交**
- Commit message: `feat: 新增 prompt 优化 API 端点 + 评分=-1 异步触发优化`
- 审计信息：
  - repo: `root`
    branch: `006-prompt-optimization`
    commit: `<TBD>`
    pr: `<TBD>`
    changed_files:
      - `backend/apps/intelligence/views.py`
      - `backend/apps/intelligence/urls.py`
      - `backend/apps/intelligence/tests/test_api.py`

---

### Task T7: Django Admin 注册 PromptVersion

- [ ] **状态**：未开始

**代码仓范围：**
- 根项目：`backend/apps/intelligence/admin.py`

**文件：**
- 修改：`backend/apps/intelligence/admin.py`（新增 PromptVersionAdmin）

**验收点：**
- PromptVersion 在 Admin 可查看（list_display: prompt_name / version / feed / optimization_reason / created_at）
- 支持按 prompt_name 筛选
- readonly_fields: created_at / updated_at

**步骤 1：修改 admin.py**
- 修改点：新增 PromptVersion 注册
  ```python
  @admin.register(PromptVersion)
  class PromptVersionAdmin(admin.ModelAdmin):
      list_display = ("prompt_name", "version", "feed", "optimization_reason", "created_at")
      list_filter = ("prompt_name",)
      readonly_fields = ("created_at", "updated_at")
      ordering = ("-version", "-id")
  ```

**步骤 2：运行验证**
- Run: `cd /Users/melody/code/ai-workshop && .venv/bin/python manage.py check`
- Expected: no issues

**步骤 3：提交**
- Commit message: `feat: Django Admin 注册 PromptVersion（查看历史 + 回滚入口）`
- 审计信息：
  - repo: `root`
    branch: `006-prompt-optimization`
    commit: `<TBD>`
    pr: `<TBD>`
    changed_files:
      - `backend/apps/intelligence/admin.py`

---

### Task T8: 全量验证

- [ ] **状态**：未开始

**代码仓范围：**
- 根项目

**文件：**
- 无文件变更（仅运行验证命令）

**验收点：**
- 后端全量测试通过（排除 e2e_crawl 网络测试）
- Django check 无错误
- 前端 build 成功

**步骤 1：后端全量测试**
- Run: `cd /Users/melody/code/ai-workshop && .venv/bin/python manage.py test apps.intelligence --verbosity=2 --exclude-tag=e2e_crawl`
- Expected: All tests OK

**步骤 2：Django check**
- Run: `cd /Users/melody/code/ai-workshop && .venv/bin/python manage.py check`
- Expected: no issues

**步骤 3：前端 build**
- Run: `cd /Users/melody/code/ai-workshop/frontend && npm run build`
- Expected: built successfully

**步骤 4：回写 plan.md 审计信息**
- 修改点：将 T1~T7 的 commit hash 回写到各任务的审计信息中

**步骤 5：提交**
- Commit message: `chore: 全量验证通过 + plan.md 审计信息回写`
- 审计信息：
  - repo: `root`
    branch: `006-prompt-optimization`
    commit: `<TBD>`
    pr: `<TBD>`
    changed_files:
      - `.aisdlc/specs/006-prompt-optimization/implementation/plan.md`

---

## Merge-back 待办清单（仅记录，不在本阶段执行）

- MB-001：intelligence-models 数据契约更新（diff_text 字段 + PromptVersion 模型）
- MB-002：llm-service 模块页更新（第 4 类 LLM 调用：prompt_optimizer_service）
- MB-003：intelligence-api 契约更新（POST /api/feeds/{id}/optimize_prompt 端点）
- MB-004：intelligence-scheduler 服务契约更新（_process_url 存 diff_text）
- MB-005：prompt_loader 模块页更新（save_prompt 新函数）
- MB-006：ops 更新（prompt_optimizer 配置 / PromptVersion 管理）
- MB-007：registry 更新到 006-prompt-optimization
