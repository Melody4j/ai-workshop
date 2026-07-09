---
title: Prompt 自动优化系统方案决策（Solutionate）
status: draft
---

> 目的：把"推荐决策 + 备选方案对比 + 决策依据 + 验证清单"落到一份可评审文档里，作为后续 `prd.md` 与 `prototype.md` 的**唯一决策入口**。
>
> 原则：结论先行；只保留支撑决策的最小信息；不写"待确认问题"清单——所有不确定性统一进入"验证清单"（Owner/截止/动作明确）。

## 0. 基本信息

- 需求标识（分支 / ID）：006-prompt-optimization
- 作者 / 参与评审：FS
- 状态：draft
- 最后更新：2026-07-09
- 关联链接：`raw.md` R1-Q1~Q6 澄清记录

## 1. 结论摘要（先给结论）

- 一句话目标：用户对报告评"没帮助"后，后端自动调用 LLM 分析差评原因并优化情报生成 prompt，下次扫描自动生效。
- 本次 In / Out 的边界：In = prompt 自动优化链路（评分触发→LLM 优化→版本存档→写回文件）；Out = 不优化 denoise/diff_judge prompt、不引入消息队列、不做前端优化状态展示。
- 推荐方案：评分=-1 触发 → threading 异步执行 → LLM 一次返回优化后的 intel_system + intel_user → PromptVersion 存全文 → 覆盖 prompt 文件 → 静默生效。
- 优先验证点：V-001（prompt 退化风险）、V-002（LLM 返回格式可靠性）、V-003（threading 中的 DB 操作安全性）。

## 2. 推荐方案

- 方案名：**Threading 异步 + LLM 一次返回双 prompt + 版本表存全文**

### 主流程 / 关键机制（6 步）

1. **评分保存**：用户在报告页评 -1 + 评语 → `POST /api/reports/{id}/rating`（现有流程）保存到 IntelligenceFeed.user_feedback / user_comment。
2. **异步触发**：评分保存成功后，后端检查 `user_feedback == -1`，若是则启动 `threading.Thread` 执行 prompt 优化，API 立即返回 200。
3. **LLM 优化调用**：后台线程收集 [diff_text + clean_md + AI 分析报告 4 字段 + 用户评语 + 当前 intel_system.md / intel_user.md 全文] → 注入 `prompt_optimizer.md` meta-prompt → 调用 LLM（instructor + Pydantic `OptimizedPrompts` schema）→ 一次返回优化后的 intel_system + intel_user 全文。
4. **版本存档**：将旧版 intel_system.md / intel_user.md 全文写入 PromptVersion 表（含 version 号、feed_id、优化原因）。
5. **写回文件**：将优化后的 intel_system / intel_user 内容覆盖写入 `prompts/intel_system.md` / `prompts/intel_user.md`。
6. **静默生效**：下次 `scheduler_service.run_scan()` 调用 `load_prompt("intel_system")` / `load_prompt("intel_user")` 时自动读取新文件。

### 关键边界 / 取舍

1. **仅 -1 触发**：评分=1 不触发优化（好评说明当前 prompt 够好）。
2. **仅优化情报生成 prompt**：不优化 denoise.md / diff_judge.md（与用户可感知质量关系间接）。
3. **自动生效无审批**：LLM 优化后直接覆盖文件，无需人工审批。退化风险通过 PromptVersion 版本表回滚兜底。
4. **静默执行**：前端不展示优化状态。用户可通过 Django Admin 的 PromptVersion 表查看历史和回滚。
5. **优化失败不影响评分**：threading 内 try-except 捕获 LLMError，记录 logger.error，评分已先于优化保存成功。

### 为什么选它

1. **最小改动复用现有架构**：LLM client（OpenAI 兼容 + instructor）、retry 机制、prompt loader 均已就绪，新增一个 service + 一个模型 + 一个 API 端点即可。（证据：`raw.md` 设计决策 #5 需要新增的组件清单）
2. **threading 符合项目约束**：不引入消息队列（CLAUDE.md 不变量 8），单用户场景下 threading 足够。（证据：`raw.md` R1-Q4）
3. **版本表存全文最简回滚**：prompt 本身几 KB，存全文回滚一行代码搞定，无需回放 diff。（证据：`raw.md` R1-Q3）

## 3. 备选方案

### 3.1 备选方案：Django async view + asyncio.create_task

- 核心机制：评分 API 改为 `async def`，用 `asyncio.create_task()` 启动后台优化任务。
- 主流程：同推荐方案，仅异步实现方式不同。
- 边界与取舍：需要 ASGI 服务器（Daphne/Uvicorn）；当前 runserver + APScheduler 是同步模式，混用 async 可能导致 DB 连接管理问题。
- 适用前提：项目已迁移到 ASGI 部署，或需要大量并发优化任务。
- 不选原因：当前项目是同步 WSGE 模式 + 单用户场景，引入 ASGI 增加复杂度无收益。

### 3.2 备选方案：同步执行 + 前端 loading

- 核心机制：评分 API 同步调用 LLM 优化，前端显示 loading 直到优化完成。
- 主流程：评分保存 → 同步调用 LLM 优化 → 返回 200（含优化结果）。
- 边界与取舍：HTTP 请求阻塞 30s+（LLM 调用 + 重试）；用户体验差；可能触发 HTTP 超时。
- 适用前提：优化链路 < 5s（如 LLM 响应极快或用本地模型）。
- 不选原因：LLM 调用 + 3 次重试最长可达 90s+，同步阻塞 HTTP 不可接受。

### 3.3 备选方案：分两次独立 LLM 调用优化

- 核心机制：先调 LLM 优化 intel_system，再调 LLM 优化 intel_user，各自独立 @retry。
- 主流程：收集上下文 → LLM 调用 1（intel_system）→ LLM 调用 2（intel_user）→ 分别写回。
- 边界与取舍：成本翻倍（2 次 LLM 调用）；但每次返回更聚焦不易截断。
- 适用前提：单次返回两个 prompt 容易被 LLM 截断（max_tokens 不足）。
- 不选原因：prompt 本身不长（几百字），一次返回两个仍在 max_tokens 范围内。R1-Q2 已决策一次返回。

## 4. 决策依据（证据入口清单）

- `raw.md` 设计决策 #1~#6：优化范围、生效方式、触发时机、few-shot、LLM 输入、diff 存储
- `raw.md` R1-Q1~Q6：6 轮澄清结论（触发条件、返回格式、版本表设计、异步方式、失败处理、前端交互）
- `.aisdlc/project/components/llm-service.md`：现有 3 次 LLM 调用架构、IntelResult Pydantic schema、@retry 机制
- `.aisdlc/project/components/intelligence-scheduler.md`：11 步链路、Step 8 generate_intel 调用点
- `.aisdlc/project/components/intelligence-models.md`：IntelligenceFeed 字段定义、DataSnapshot.clean_md_path 语义
- `.aisdlc/project/components/intelligence-api.md`：现有评分 API（ReportRatingView POST/PATCH/DELETE）
- `backend/apps/intelligence/services/prompt_loader.py`：load_prompt 实现（str.replace，需新增 save_prompt）
- `backend/apps/intelligence/services/llm_service.py`：generate_intel 调用方式（instructor + Pydantic）

## 5. 验证清单（V-xxx，可执行）

- V-001：prompt 退化风险
  - 风险/假设：LLM 优化的 prompt 可能比原版更差（更冗长/更模糊/偏离意图）
  - 方法：收集 10 次优化前后的 prompt 对比，人工评估"清晰度/具体性/可执行性"三项指标
  - 成功/失败信号：≥ 7/10 次优化后 prompt 三项指标不降低为成立；否则退化风险高
  - Owner：DEV
  - 截止：实现后 1 周内
  - 触发动作：不成立则增加"优化前 A/B 对比"机制（新 prompt 在历史数据上验证后才生效）

- V-002：LLM 返回格式可靠性
  - 风险/假设：instructor + Pydantic 约束 `OptimizedPrompts` schema 时，LLM 可能返回空字符串或截断内容
  - 方法：测试 20 次 LLM 优化调用，检查返回的 intel_system / intel_user 是否为非空有效字符串
  - 成功/失败信号：20/20 次返回非空且 > 50 字符为成立；否则需要加校验逻辑或改分两次调用
  - Owner：DEV
  - 截止：实现后 3 天内
  - 触发动作：不成立则增加返回内容校验（空或过短 → 不覆盖文件 + 记录日志）

- V-003：threading 中 DB 操作安全性
  - 风险/假设：Django ORM 在子线程中可能遇到数据库连接问题（连接泄漏 / connection closed）
  - 方法：在测试中模拟 10 次并发优化触发，检查 DB 连接是否正常关闭、是否有连接泄漏
  - 成功/失败信号：无连接泄漏、无 connection closed 异常为成立
  - Owner：DEV
  - 截止：实现后 3 天内
  - 触发动作：不成立则在子线程中显式调用 `django.db.connection.close()` 或改用 `django.db.connections['default'].close()`

- V-004：diff_text 字段存储完整性
  - 风险/假设：IntelligenceFeed.diff_text 可能在某些路径下为空（首次爬取 / 旧格式兼容 / diff 为空熔断）
  - 方法：检查所有 IntelligenceFeed 创建路径，确认 diff_text 在 NO_CHANGE / ERROR_CRAWL 场景下的值
  - 成功/失败信号：CHANGED 记录的 diff_text 非空；NO_CHANGE / ERROR_CRAWL 记录的 diff_text 为空字符串（非 null）
  - Owner：DEV
  - 截止：实现时
  - 触发动作：不成立则修正赋值逻辑，确保 diff_text 始终有值（空字符串兜底）

- V-005：prompt 文件写回的并发安全
  - 风险/假设：两个评分几乎同时触发优化，可能同时写同一个 prompt 文件
  - 方法：模拟 2 个并发优化线程，检查文件最终内容是否一致（最后一个写入胜出）
  - 成功/失败信号：文件不损坏、内容完整为成立；文件损坏或内容截断为不成立
  - Owner：DEV
  - 截止：实现后 3 天内
  - 触发动作：不成立则加文件锁（`fcntl.flock`）或 threading.Lock

- V-006：PromptVersion 回滚有效性
  - 风险/假设：回滚操作可能因版本号管理错误导致回滚到错误版本
  - 方法：测试回滚到 N-1 / N-2 版本，确认文件内容与版本表记录一致
  - 成功/失败信号：回滚后文件内容 == PromptVersion 表对应记录的 content 字段
  - Owner：DEV
  - 截止：实现时
  - 触发动作：不成立则修正版本号管理逻辑

## 6. 迭代记录

- 2026-07-09：初始版本。基于 raw.md 6 条设计决策 + 6 轮澄清结论产出推荐方案（threading 异步 + LLM 一次返回双 prompt + 版本表存全文）+ 3 个备选方案 + 6 条验证清单。

## 7. Impact Analysis

### 7.1 受影响模块

| 模块 | 影响类型 | 关键不变量 | stale? |
|------|----------|-----------|--------|
| intelligence-models | 新增字段 + 新增模型 | IntelligenceFeed 新增 diff_text（TextField）；新增 PromptVersion 模型 | no |
| intelligence-api | 新增端点 | POST /api/feeds/{id}/optimize_prompt（手动触发优化）；ReportRatingView 评分后内部触发 | no |
| llm-service | 新增第 4 类 LLM 调用 | prompt_optimizer_service.optimize_prompts()；instructor + Pydantic OptimizedPrompts schema | no |
| intelligence-scheduler | 修改 | _process_url Step 9 写 IntelligenceFeed 时存入 diff_text | no |
| prompt_loader | 新增函数 | save_prompt(name, content) 写回文件能力 | no |

### 7.2 需遵守的不变量

- 3 次 LLM 调用独立不合并（来源：`.aisdlc/project/components/llm-service.md` Invariant 1）—— prompt 优化是第 4 类独立调用，不影响现有 3 次
- IntelligenceFeed.user_feedback 仅允许 -1 / 1 / null（来源：`intelligence-models.md` Invariant 7）—— 优化触发条件基于此
- 情报输出固定 4 字段，不含价值度字段（来源：`llm-service.md` Invariant 7）—— 优化后的 prompt 仍需输出 4 字段
- Negative Few-Shot 注入上限最近 5 条（来源：`llm-service.md` Invariant 5）—— 优化后的 intel_user.md 必须保留 {negative_few_shots} 占位符
- load_prompt 使用 str.replace 而非 str.format（来源：`prompt_loader.py`）—— 优化后的 prompt 模板必须保留 {self_product_doc} / {diff_text} / {negative_few_shots} 占位符
- OpenAI 兼容 API（来源：`llm-service.md` Invariant 6）—— 优化 LLM 调用复用同一 client

### 7.3 跨模块影响

- **scheduler_service → IntelligenceFeed**：Step 9 创建 IntelligenceFeed 时需额外赋值 diff_text（影响 `_process_url` 中所有创建 IntelligenceFeed 的路径，包括 CHANGED / NO_CHANGE / ERROR_CRAWL）
- **ReportRatingView → prompt_optimizer_service**：评分保存后触发优化（新增调用关系）
- **prompt_optimizer_service → prompt_loader**：新增 save_prompt 写回能力（load_prompt 已有，save_prompt 新增）
- **prompt_optimizer_service → llm_client**：复用 get_instructor_client() + 新增 OptimizedPrompts Pydantic schema
- **PromptVersion → prompt_loader**：回滚时通过 save_prompt 写回历史版本

### 7.4 Context Gaps

- 无 CONTEXT GAP。所有必读文件均成功读取，模块 SSOT 均为最新（Spec 004 merge-back 后已更新）。

## 8. Mini-PRD

- **MVP 范围**：
  - In：IntelligenceFeed 新增 diff_text 字段；PromptVersion 模型；prompt_optimizer_service；POST /api/feeds/{id}/optimize_prompt 端点；评分=-1 后 threading 异步触发优化；prompt_loader.save_prompt；prompt_optimizer.md meta-prompt 模板；scheduler_service 存 diff_text
  - Out：不优化 denoise/diff_judge；不做前端优化状态展示；不做 A/B 对比验证；不做自动回滚机制（手动通过 Django Admin 回滚）

- **验收标准（AC）**：
  1. AC-001：IntelligenceFeed 新增 diff_text 字段，CHANGED 记录的 diff_text 非空，NO_CHANGE / ERROR_CRAWL 记录的 diff_text 为空字符串
  2. AC-002：PromptVersion 模型存在，每次优化生成 2 条记录（intel_system + intel_user 各一条），含完整 prompt 全文 + version 号 + feed_id
  3. AC-003：POST /api/feeds/{id}/optimize_prompt 端点可手动触发优化，返回 200 + 优化结果摘要
  4. AC-004：评分=-1 时后端自动异步触发优化；评分=1 时不触发
  5. AC-005：优化后 prompts/intel_system.md 和 prompts/intel_user.md 文件内容被覆盖为新版本
  6. AC-006：优化后的 prompt 文件仍保留 {self_product_doc} / {diff_text} / {negative_few_shots} 占位符（不破坏 load_prompt 注入机制）
  7. AC-007：优化失败（LLM 重试耗尽）时记录 logger.error，不影响评分已保存的结果
  8. AC-008：PromptVersion 表可通过 Django Admin 查看，支持手动回滚（读取历史版本 content 写回文件）

- **交互变化结论**：无前端交互变化。评分流程不变，优化静默执行。

- **影响面**：
  - 模型：IntelligenceFeed（新增字段）、PromptVersion（新增模型）
  - 接口：POST /api/feeds/{id}/optimize_prompt（新增）
  - 服务：prompt_optimizer_service.py（新增）、prompt_loader.py（新增 save_prompt）、scheduler_service.py（修改 _process_url 存 diff_text）
  - Prompt 模板：prompts/prompt_optimizer.md（新增）
  - Migration：0006_intelligencefeed_diff_text + 0007_promptversion
