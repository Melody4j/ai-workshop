---
title: 全面优化系统提示词 — 方案决策（Solutionate）
status: draft
---

> 目的：把"推荐决策 + 备选方案对比 + 决策依据 + 验证清单"落到一份可评审文档里，作为后续 `prd.md` 与 `prototype.md` 的**唯一决策入口**。
>
> 原则：结论先行；只保留支撑决策的最小信息；不写"待确认问题"清单——所有不确定性统一进入"验证清单"（Owner/截止/动作明确）。

## 0. 基本信息

- 需求标识（分支 / ID）：010-prompt-optimization
- 作者 / 参与评审：Claude（AI SDLC）/ 用户
- 状态：draft
- 最后更新：2026-07-09
- 关联链接：raw.md（R1-Q1~Q4 澄清记录）

## 1. 结论摘要（先给结论）

- 一句话目标：全面优化 5 套系统提示词 + 最小代码调整，解决"报告质量低 + diff 误判"两个核心痛点。
- 本次 In / Out 的边界：In = 5 个 prompt 模板优化 + 4 处最小代码改动（system message / instructor / Blob 版本一致性 / Pydantic description 对齐）；Out = 链路结构变更 / 数据模型变更 / 新增 LLM 调用 / 前端改动。
- 推荐方案：分层精准化——denoise 强化规则+示例、diff_judge 拆 system+user 并改 instructor 结构化输出、intel_system/intel_user 消重对齐并强化防编造、prompt_optimizer 补齐占位符+优化指令。
- 优先验证点：V-001（diff 误判率下降）、V-002（报告无编造内容）、V-003（prompt_optimizer 版本一致性修复）。

## 2. 推荐方案

- 方案名：分层精准化优化（Prompt-First + Minimal Code Patch）
- 主流程 / 关键机制（5 层）：

  1. **denoise.md**：将 7 条笼统规则细化为"必须去除 / 必须保留"双列表 + 3 组正反例（SaaS 落地页 / 博客 / 文档站各一组简短示例）；拆出 system message 定义角色（"你是一个专业网页内容编辑"），user message 只放规则+输入+输出要求。
  2. **diff_judge.md**：拆为 system（角色+判断标准+必须忽略清单）+ user（diff_text + self_product_doc）；代码侧改用 instructor + `DiffJudgeResult(BaseModel)` 结构化输出，移除手动 `_extract_json` 正则解析。
  3. **intel_system.md + intel_user.md**：消除两文件间的字段描述重复——intel_system 负责角色+核心原则+字段定义，intel_user 负责数据注入+输出格式模板；移除 intel_user 中与 Pydantic schema 冗余的 JSON 格式模板（instructor 已约束）；对齐 Pydantic `IntelResult` 的 Field description 与 prompt 中的字段描述（消除"1-3 句话 vs 3-5 句话"冲突）。
  4. **prompt_optimizer.md**：补齐占位符保护列表（新增 `{page_content}`）；优化指令增加"不得删除已有占位符""保持字段数量与 IntelResult schema 一致"约束；代码侧修复 `_read_prompt_file` 从本地读取改为从 Blob 读取（用 `load_prompt` 不注入变量时的原始内容）。
  5. **代码改动**：denoise/diff_judge 的调用从单条 user message 改为 system+user 双消息；diff_judge 改用 instructor；prompt_optimizer 的 `_read_prompt_file` 改为 `blob_storage.read_content`；IntelResult Field description 与 prompt 对齐。

- 关键边界/取舍：
  1. 不改 LLM 调用链路结构（3 次独立调用不合并）——约束来源 R1-Q1
  2. 不改 IntelResult 字段数量（保持 5 字段）——约束来源 R1-Q1
  3. 不引入差异化 temperature 配置——虽有问题但属于 settings 层面，不在本次范围（转 V-005）
  4. denoise 保持单一 prompt 不拆分网站类型——约束来源 R1-Q4
  5. negative few-shot 格式增强（输出完整错误报告而非仅摘要）需改 `_format_few_shots` 代码——属于最小代码改动范围

- 为什么选它：
  1. 以 prompt 改动为主，代码改动仅 4 处且都是局部修改，符合用户"避免代码大范围改动"约束（证据：R1-Q1）
  2. 分层优化精准命中两个痛点：diff_judge 强化解决误判、intel_system/intel_user 消重+防编造解决报告质量（证据：raw.md 原始需求）
  3. 基于工作区已有改进迭代而非从零开始，避免已有工作浪费（证据：R1-Q2）

## 3. 备选方案

### 3.1 备选方案：纯提示词改动（Zero Code Change）

- 核心机制：只改 5 个 .md 文件，不动任何 .py 文件。denoise/diff_judge 继续用纯 user message + 手动 JSON 解析。
- 主流程：5 个 prompt 模板各自优化规则和示例 → 上传 Blob → 完成。
- 边界与取舍：不修复 diff_judge JSON 解析脆弱性；不修复 prompt_optimizer 版本不一致；不加 system message。
- 适用前提：用户严格限制代码改动 / 代码已冻结。
- 不选原因：用户已明确允许"最小代码改动"（R1-Q1），纯 prompt 无法解决 diff_judge 正则解析脆弱性和 prompt_optimizer 版本不一致两个结构性缺陷。

### 3.2 备选方案：提示词 + 中等代码改动

- 核心机制：在推荐方案基础上，额外做：独立 temperature 配置（denoise 低 / diff_judge 低 / 情报生成中）、negative few-shot 格式增强（输出完整错误报告）、difflib 行级预过滤（去掉仅空白差异的行）。
- 主流程：prompt 优化 + 6-8 处代码改动 + settings 新增配置项。
- 边界与取舍：改动面更大，需要更多测试覆盖；但效果更彻底。
- 适用前提：愿意接受中等代码改动量 / 有充分测试覆盖。
- 不选原因：超出用户"最小代码改动"预期（R1-Q1），且 difflib 预过滤属于 diff_service 层改动，不在 prompt 优化范畴。相关改进转验证清单 V-005、V-006。

## 4. 决策依据（证据入口清单）

- `{FEATURE_DIR}/requirements/raw.md`：
  - 原始需求："提示词过于粗糙和简单，无法真正有效输出有价值的报告" + "经常因为一些无意义的diff而误判"
  - R1-Q1：代码改动边界 = 提示词 + 最小代码改动
  - R1-Q2：基于工作区版本迭代
  - R1-Q3：全部 5 个 prompt 纳入优化范围
  - R1-Q4：denoise 强化规则+示例，不做网站类型差异化
- 项目知识库：
  - `.aisdlc/project/components/llm-service.md`：3 次独立 LLM 调用契约 + IntelResult schema + Negative Few-Shot 上限 5 条
  - `.aisdlc/project/components/intelligence-scheduler.md`：11 步链路 + 首次爬取跳过 diff
- 代码证据：
  - `backend/apps/intelligence/services/llm_service.py`：denoise/judge_diff 用纯 user message + 手动 JSON 解析
  - `backend/apps/intelligence/services/llm_client.py`：IntelResult Field description 与 prompt 字段描述不一致
  - `backend/apps/intelligence/services/prompt_optimizer_service.py:120-126`：`_read_prompt_file` 从本地文件系统读取
  - `backend/prompts/`：5 个 prompt 模板当前内容

## 5. 验证清单（V-xxx，可执行）

- V-001：diff 误判率是否下降
  - 风险/假设：强化 diff_judge 规则+示例后，无意义 diff 误报率应下降
  - 方法：选取 10 条历史 CHANGED 记录（含已知无意义变化的误报案例），用优化后的 diff_judge prompt 重新判断，对比 has_meaningful_change 结果
  - 成功/失败信号：误报率（无意义变化被判断为 meaningful）从当前水平下降 ≥ 50% 为成立；否则不成立
  - Owner：DEV
  - 截止：实现完成后 2 天
  - 触发动作：不成立则进一步强化"必须忽略"清单或考虑 difflib 预过滤（V-006）

- V-002：报告无编造内容
  - 风险/假设：强化防编造规则后，情报报告中不应出现 diff 和页面内容中不存在的功能/产品/定价信息
  - 方法：选取 5 条历史报告，人工核对每个字段（尤其 competitor_overview 和 strategic_intent）中的事实声明是否有 diff/页面内容支撑
  - 成功/失败信号：0 条编造内容为成立；≥ 1 条编造为不成立
  - Owner：DEV
  - 截止：实现完成后 2 天
  - 触发动作：不成立则在 intel_system.md 中进一步强化"严禁编造"规则或增加正例/反例

- V-003：prompt_optimizer 版本一致性修复
  - 风险/假设：将 `_read_prompt_file` 改为从 Blob 读取后，prompt_optimizer 读取的 prompt 版本应与运行时 load_prompt 一致
  - 方法：手动触发一次 prompt 优化（评分 -1），检查 optimize_prompts 读取的 current_intel_system/intel_user 是否为 Blob 上的最新版本
  - 成功/失败信号：读取内容与 Blob 上一致为成立；读取到本地旧版本为不成立
  - Owner：DEV
  - 截止：实现完成后 1 天
  - 触发动作：不成立则检查 blob_storage.read_content 调用路径

- V-004：diff_judge instructor 结构化输出稳定性
  - 风险/假设：改用 instructor + Pydantic 后，diff_judge 不再出现 JSON 解析失败
  - 方法：连续执行 20 次 judge_diff 调用（含各种 diff 格式：空/超长/含 JSON 特殊字符/含 markdown 代码块），检查是否出现 ValueError
  - 成功/失败信号：0 次 JSON 解析失败为成立；≥ 1 次为不成立
  - Owner：DEV
  - 截止：实现完成后 1 天
  - 触发动作：不成立则检查 DiffJudgeResult schema 定义和 instructor 配置

- V-005：LLM temperature 差异化配置
  - 风险/假设：denoise/diff_judge 应低温度（确定性），情报生成可稍高（创造性），当前一刀切可能影响效果
  - 方法：对比 temperature=0 vs 0.3 vs 0.7 下 denoise 和 diff_judge 的输出稳定性
  - 成功/失败信号：低温度下输出一致性显著提升为成立；无差异为不成立
  - Owner：DEV
  - 截止：本次 Spec 完成后评估
  - 触发动作：成立则开新 Spec 增加 settings 层 temperature 差异化配置

- V-006：difflib 行级预过滤
  - 风险/假设：difflib 产生的字符级 diff 包含大量噪音（空白/emoji/标点），在 diff_judge 之前做行级预过滤可减少 LLM 负担
  - 方法：在 diff_service.text_diff 中增加行级过滤（去掉仅空白差异的行），对比过滤前后 diff_judge 的判断准确率
  - 成功/失败信号：过滤后准确率提升 ≥ 10% 为成立；否则不成立
  - Owner：DEV
  - 截止：本次 Spec 完成后评估
  - 触发动作：成立则开新 Spec 修改 diff_service

- V-007：negative few-shot 格式增强效果
  - 风险/假设：当前 few-shot 只输出摘要+评语，LLM 难以学习"什么算笼统"；增强为完整错误报告后学习效果应提升
  - 方法：对比增强前后，情报报告中"被用户评为没帮助"的比例变化
  - 成功/失败信号：差评率下降 ≥ 20% 为成立；否则不成立
  - Owner：DEV
  - 截止：本次 Spec 完成后 1 周观察
  - 触发动作：不成立则考虑增加正例（good few-shot）而非仅负例

## 6. 迭代记录

- 2026-07-09：初始版本。基于 R1-Q1~Q4 四轮澄清裁决，产出推荐方案"分层精准化优化"。核心决策：5 个 prompt 全部优化 + 4 处最小代码改动（system message / instructor / Blob 版本一致性 / Pydantic description 对齐）。备选方案排除"纯提示词"（不解决结构性缺陷）和"中等代码改动"（超用户预期）。

## 7. Impact Analysis（需求影响分析）

### 7.1 受影响模块

| 模块 | 影响类型 | 关键不变量 | stale? |
|------|----------|-----------|--------|
| llm-service | 修改契约（denoise/judge_diff 调用方式变更） | 3 次独立调用不合并；IntelResult 5 字段不变 | yes（知识库记 4 字段，实际 5 字段） |
| prompt-loader | 读取方式不变（仍从 Blob 读取） | load_prompt / save_prompt 接口不变 | no |
| prompt-optimizer-service | 修复 _read_prompt_file 读取来源 | optimize_prompts 一次调用返回两个 prompt | no |
| intelligence-scheduler | 无代码改动，间接受益于 prompt 优化 | 11 步链路不变 | no |
| llm-client | IntelResult Field description 对齐 | 5 字段不变 | no |

### 7.2 需遵守的不变量

- 3 次 LLM 调用独立，不合并（来源：`.aisdlc/project/components/llm-service.md#invariants-1`）
- IntelResult 5 字段不变：competitor_overview / change_summary / strategic_intent / action_suggestion / evidence_diff（来源：`llm_client.py:19-41`）
- Negative Few-Shot 注入上限最近 5 条（来源：`.aisdlc/project/components/llm-service.md#invariants-6`）
- 每次 LLM 调用独立重试（3 次 / 30s 间隔），不降级（来源：`.aisdlc/project/components/llm-service.md#invariants-4`）
- optimize_prompts 一次 LLM 调用返回 intel_system + intel_user 两个 prompt（来源：`.aisdlc/project/components/llm-service.md#invariants-9`）
- save_prompt 直接覆盖 Blob，无审批步骤（来源：`.aisdlc/project/components/llm-service.md#invariants-11`）

### 7.3 跨模块影响

- 改 llm_service.judge_diff → 需关注 scheduler_service._process_url（调用方，返回值结构 `{"has_meaningful_change": bool, "reason": str}` 不变，但解析方式从手动 JSON 改为 instructor 直接返回 dict）
- 改 IntelResult Field description → 需关注 instructor 结构化输出（description 会被 instructor 注入 prompt，需与 intel_system/intel_user 中的字段描述对齐）
- 改 prompt_optimizer_service._read_prompt_file → 需关注 blob_storage.read_content（改为从 Blob 读取，需处理 Blob URL 缓存）
- 改 denoise/diff_judge 调用为 system+user 双消息 → 需关注 LLM token 用量（system message 增加 token 消耗，但总量可控）

### 7.4 Context Gaps

- `CONTEXT GAP`：`.aisdlc/project/components/llm-service.md` 记录 IntelResult 为 4 字段，实际代码为 5 字段（含 competitor_overview）→ 建议动作：本次 Spec 完成后 merge-back 时更新知识库
- `CONTEXT GAP`：`.aisdlc/project/components/intelligence-scheduler.md` 记录"首次爬取跳过 diff，直接情报生成"，但工作区代码已改为"首次爬取建立基线 NO_CHANGE"→ 建议动作：本次 Spec 完成后 merge-back 时更新知识库

## 8. Mini-PRD

- **MVP 范围**：
  - In：
    - 优化 5 个 prompt 模板内容（denoise / diff_judge / intel_system / intel_user / prompt_optimizer）
    - denoise/diff_judge 拆分为 system message + user message
    - diff_judge 改用 instructor + DiffJudgeResult Pydantic schema
    - prompt_optimizer 的 _read_prompt_file 改为从 Blob 读取
    - IntelResult Field description 与 prompt 字段描述对齐
    - negative few-shot 格式增强（_format_few_shots 输出完整错误报告）
    - 优化后重新上传 Blob
    - 修复 CHANGED/ERROR_CRAWL 记录缺失 raw_diff_text 字段（scheduler_service.py 3 处 create 调用补传）
  - Out：
    - LLM temperature 差异化配置（转 V-005）
    - difflib 行级预过滤（转 V-006）
    - 前端 UI 改动
    - 数据模型变更
    - LLM 调用链路结构调整

- **验收标准（AC）**：
  1. AC-001：denoise.md 包含"必须去除"和"必须保留"双列表 + ≥ 3 组正反例
  2. AC-002：diff_judge.md 拆为 system（角色+判断标准+必须忽略清单）+ user（diff_text+self_product_doc），且 diff_judge 调用改用 instructor 结构化输出
  3. AC-003：intel_system.md 和 intel_user.md 无字段描述重复（intel_system 负责定义，intel_user 负责注入）
  4. AC-004：IntelResult 的 5 个 Field description 与 intel_system.md 中的字段描述一致（无"1-3 句话 vs 3-5 句话"冲突）
  5. AC-005：intel_user.md 中移除与 Pydantic schema 冗余的 JSON 格式模板（instructor 已约束输出结构）
  6. AC-006：prompt_optimizer.md 占位符保护列表包含 `{page_content}`
  7. AC-007：prompt_optimizer_service._read_prompt_file 从 Blob 读取而非本地文件系统
  8. AC-008：_format_few_shots 输出包含完整错误报告（4-5 字段）而非仅摘要+评语
  9. AC-009：5 个优化后的 prompt 已上传至 Vercel Blob
  10. AC-010：现有测试 `apps.intelligence.tests` 全部通过
  11. AC-011：所有 IntelligenceFeed.objects.create 调用都显式传入 raw_diff_text（CHANGED + NO_CHANGE + ERROR_CRAWL）

- **交互变化结论**：无前端交互变化。本次为纯后端 prompt + 代码优化。

- **影响面**：
  - `backend/prompts/*.md`（5 个文件）
  - `backend/apps/intelligence/services/llm_service.py`（denoise/judge_diff 调用方式）
  - `backend/apps/intelligence/services/llm_client.py`（IntelResult Field description + 新增 DiffJudgeResult）
  - `backend/apps/intelligence/services/prompt_optimizer_service.py`（_read_prompt_file 改 Blob 读取）
  - `backend/apps/intelligence/services/scheduler_service.py`（3 处 create 调用补传 raw_diff_text）
