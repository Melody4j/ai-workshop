# 全面优化系统提示词 实现计划（SSOT）

> **必需技能：** `spec-execute`（按批次执行本计划）
> **上下文获取：** 必须先执行 `spec-context` 获取上下文，定位 `{FEATURE_DIR}`，失败即停止

**目标：** 全面优化 5 套系统提示词 + 4 处最小代码改动，解决"报告质量低 + diff 误判"两个核心痛点。
**范围：** In = 5 个 prompt 模板优化 + 4 处代码改动（system message / instructor / Blob 版本一致性 / Pydantic description 对齐 + few-shot 增强）；Out = 链路结构变更 / 数据模型变更 / 新增 LLM 调用 / 前端改动 / temperature 差异化 / difflib 预过滤。
**架构：** 以 prompt 内容优化为主，代码侧仅做局部补丁——denoise/diff_judge 从单条 user message 拆为 system+user 双消息；diff_judge 从手动正则解析 JSON 改为 instructor + Pydantic；prompt_optimizer 读取来源从本地文件改为 Blob；IntelResult Field description 与 prompt 对齐；_format_few_shots 输出完整错误报告。
**验收口径：** solution.md AC-001~AC-010（10 条）。
**影响范围：** llm-service（修改调用方式）、llm-client（IntelResult description 对齐 + 新增 DiffJudgeResult）、prompt-optimizer-service（_read_prompt_file 改 Blob）、prompt-loader（无改动，接口不变）、intelligence-scheduler（无改动，间接受益）。
**需遵守的不变量：**
- 3 次 LLM 调用独立，不合并（来源：llm-service.md#invariants-1）
- IntelResult 5 字段不变（来源：llm_client.py:19-41）
- Negative Few-Shot 注入上限最近 5 条（来源：llm-service.md#invariants-6）
- 每次 LLM 调用独立重试（3 次 / 30s），不降级（来源：llm-service.md#invariants-4）
- optimize_prompts 一次调用返回 intel_system + intel_user（来源：llm-service.md#invariants-9）
- save_prompt 直接覆盖 Blob，无审批步骤（来源：llm-service.md#invariants-11）
**子仓范围：** 无（无 `.gitmodules`）

---

## TL;DR

优化 5 个 prompt 模板（denoise / diff_judge / intel_system / intel_user / prompt_optimizer）+ 4 处最小代码改动（denoise/diff_judge 加 system message、diff_judge 改 instructor、prompt_optimizer 读 Blob、IntelResult description 对齐 + few-shot 增强），分 5 个批次执行，每批次独立可验证。

## 范围与边界

**In：**
- `backend/prompts/denoise.md` — 强化规则+正反例，拆 system+user
- `backend/prompts/diff_judge.md` — 拆 system+user，强化必须忽略清单
- `backend/prompts/intel_system.md` — 消重，负责角色+原则+字段定义
- `backend/prompts/intel_user.md` — 消重，负责数据注入，移除冗余 JSON 模板
- `backend/prompts/prompt_optimizer.md` — 补齐占位符保护列表，优化指令
- `backend/apps/intelligence/services/llm_client.py` — IntelResult Field description 对齐 + 新增 DiffJudgeResult
- `backend/apps/intelligence/services/llm_service.py` — denoise/judge_diff 改 system+user 双消息、judge_diff 改 instructor、_format_few_shots 增强
- `backend/apps/intelligence/services/prompt_optimizer_service.py` — _read_prompt_file 改 Blob 读取

**Out：**
- LLM temperature 差异化配置（转 V-005）
- difflib 行级预过滤（转 V-006）
- 前端 UI 改动
- 数据模型变更
- LLM 调用链路结构调整

## 影响范围与约束

### 受影响模块清单

| 模块 | 影响类型 | 关键不变量 | stale? |
|------|----------|-----------|--------|
| llm-service | 修改调用方式（denoise/judge_diff 加 system message、judge_diff 改 instructor、_format_few_shots 增强） | 3 次独立调用不合并；IntelResult 5 字段不变 | yes（知识库记 4 字段，实际 5 字段） |
| llm-client | 修改 IntelResult Field description + 新增 DiffJudgeResult | 5 字段不变 | no |
| prompt-optimizer-service | 修复 _read_prompt_file 读取来源 | optimize_prompts 一次调用返回两个 prompt | no |
| prompt-loader | 无改动 | load_prompt / save_prompt 接口不变 | no |
| intelligence-scheduler | 无代码改动 | 11 步链路不变 | no |

### 需遵守的 API/Data 契约不变量

1. `judge_diff()` 返回值结构不变：`{"has_meaningful_change": bool, "reason": str}`——调用方 scheduler_service 依赖此结构（来源：scheduler_service.py:277-299）
2. `denoise()` 返回值类型不变：`str`——调用方 scheduler_service 依赖（来源：scheduler_service.py:201）
3. `generate_intel()` 返回值类型不变：`IntelResult`——调用方 scheduler_service 依赖（来源：scheduler_service.py:304-309）
4. `_format_few_shots()` 返回值类型不变：`str`——调用方 generate_intel 依赖（来源：llm_service.py:210）
5. `optimize_prompts()` 签名不变：`(feed_id: int) -> dict`——调用方依赖（来源：prompt_optimizer_service.py:21）
6. Prompt 占位符不新增不删除（除 intel_user 已有的 `{page_content}`）：denoise=`{bs_clean_md}`、diff_judge=`{self_product_doc}`+`{diff_text}`、intel_system=`{self_product_doc}`、intel_user=`{diff_text}`+`{page_content}`+`{competitor_context}`+`{negative_few_shots}`、prompt_optimizer=`{user_comment}`+`{diff_text}`+`{clean_md}`+`{ai_report}`+`{current_intel_system}`+`{current_intel_user}`

### 跨模块影响

- 改 `llm_service.judge_diff` → scheduler_service._process_url（调用方，返回值 dict 结构不变，但内部从手动 JSON 改为 instructor）
- 改 `IntelResult Field description` → instructor 结构化输出（description 被 instructor 注入 prompt，需与 intel_system.md 对齐）
- 改 `prompt_optimizer_service._read_prompt_file` → blob_storage.read_content（改为从 Blob 读取，需走 `_get_blob_url` 缓存）
- 改 `_format_few_shots` → generate_intel（输出文本变长，token 用量增加但可控）

## 里程碑与节奏

| 批次 | 任务 | 预估时间 | 交付物 |
|------|------|----------|--------|
| B1 | denoise.md 优化 + 代码改动（system message） | 15 min | denoise.md + llm_service.py denoise() |
| B2 | diff_judge.md 优化 + 代码改动（system message + instructor） | 20 min | diff_judge.md + llm_service.py judge_diff() + llm_client.py DiffJudgeResult |
| B3 | intel_system.md + intel_user.md 优化 + llm_client.py description 对齐 + _format_few_shots 增强 | 25 min | 3 个 .md + llm_client.py + llm_service.py |
| B4 | prompt_optimizer.md 优化 + prompt_optimizer_service.py _read_prompt_file 改 Blob | 15 min | prompt_optimizer.md + prompt_optimizer_service.py |
| B5 | 上传 Blob + 运行测试 | 10 min | Blob 同步 + 测试通过 |

## 依赖与资源

- Vercel Blob 环境变量 `BLOB_READ_WRITE_TOKEN` 已配置
- LLM API 环境变量（LLM_API_KEY / LLM_BASE_URL / LLM_MODEL）已配置
- 无外部团队依赖

## 风险与验证

| 风险 | 验证方式 | Owner |
|------|----------|-------|
| diff_judge 改 instructor 后 LLM 输出格式不兼容 | V-004：连续 20 次调用无 ValueError | DEV |
| denoise 加 system message 后 token 超限 | 检查 max_tokens 配置 + 日志 | DEV |
| prompt_optimizer 从 Blob 读取时 URL 缓存未命中 | V-003：手动触发优化验证 | DEV |
| _format_few_shots 输出变长导致 token 超限 | 检查 few-shot 上限 5 条 × 单条长度 | DEV |

## 验收口径

- AC-001：denoise.md 包含"必须去除"和"必须保留"双列表 + ≥ 3 组正反例
- AC-002：diff_judge.md 拆为 system + user，且 judge_diff 调用改用 instructor
- AC-003：intel_system.md 和 intel_user.md 无字段描述重复
- AC-004：IntelResult Field description 与 intel_system.md 字段描述一致
- AC-005：intel_user.md 中移除冗余 JSON 格式模板
- AC-006：prompt_optimizer.md 占位符保护列表包含 `{page_content}`
- AC-007：prompt_optimizer_service._read_prompt_file 从 Blob 读取
- AC-008：_format_few_shots 输出包含完整错误报告
- AC-009：5 个优化后的 prompt 已上传至 Vercel Blob
- AC-010：现有测试 `apps.intelligence.tests` 全部通过

## NEEDS CLARIFICATION

无。所有关键不确定性已在 R1 澄清中消除。

---

## 任务清单（SSOT）

### Task T1: 优化 denoise.md + denoise() 加 system message

- [ ] **状态**：未开始

**文件：**
- 修改：`backend/prompts/denoise.md`（拆为 system 角色定义 + user 规则+输入+输出）
- 修改：`backend/apps/intelligence/services/llm_service.py`（denoise 函数，~第 26-57 行）

**验收点：**
- [AC-001] denoise.md 包含"必须去除"和"必须保留"双列表 + ≥ 3 组正反例
- denoise() 使用 system+user 双消息调用 LLM
- denoise() 返回值类型仍为 `str`
- 占位符 `{bs_clean_md}` 保留在 user 部分

**步骤 1：优化 denoise.md**
- 修改点：`backend/prompts/denoise.md`
- 将原文件拆为两部分（同一文件内用分隔标记）：
  - System 部分：角色定义"你是一个专业网页内容编辑，专门对竞品网站 markdown 进行语义降噪"
  - User 部分：规则（细化"必须去除"和"必须保留"双列表）+ 3 组正反例 + `{bs_clean_md}` 输入 + 输出要求
- 规则细化要点：
  - "必须去除"列表：广告/导航链接/版权声明/cookie 提示/页脚模板/社交分享按钮/重复段落/空白填充/JS 残留
  - "必须保留"列表：产品介绍/功能描述/价格信息/更新日志/核心文案/关键数字/产品名称/CTA 按钮文字
  - 正反例 3 组：SaaS 落地页（正：保留定价表；反：去除"查看更多"按钮）、博客文章（正：保留正文；反：去除作者卡片）、文档站（正：保留 API 说明；反：去除侧边栏目录）

**步骤 2：修改 denoise() 调用方式**
- 修改点：`backend/apps/intelligence/services/llm_service.py`，denoise 函数（~第 26-57 行）
- 改动：
  - `load_prompt` 改为分别加载 system 和 user（denoise.md 文件内用 `---SYSTEM---` 和 `---USER---` 分隔，`load_prompt` 分别读取）
  - 或者更简单：denoise.md 拆为 `denoise_system.md` + `denoise.md`（避免改 load_prompt 逻辑）
  - **选择方案**：拆为两个文件 `denoise_system.md`（角色+不变规则）和 `denoise.md`（user 部分：可变规则+示例+输入+输出），`load_prompt` 不需改动
  - messages 从 `[{"role": "user", "content": prompt}]` 改为 `[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]`
- 保持 `@retry` 装饰器不变
- 保持空输入/极短输入跳过逻辑不变

**步骤 3：运行验证**
- Run: `cd /Users/melody/code/ai-workshop/backend && /Users/melody/code/ai-workshop/.venv/bin/python manage.py test apps.intelligence.tests.test_llm_service`
- Expected: PASS（现有测试通过；如有 mock 需更新 mock 的 messages 结构）

**步骤 4：提交（AUTO_COMMIT=true）**
- Commit message: `feat: denoise 拆为 system+user 双消息，强化降噪规则+正反例`

---

### Task T2: 优化 diff_judge.md + judge_diff() 加 system message + 改 instructor

- [ ] **状态**：未开始

**文件：**
- 创建：`backend/prompts/diff_judge_system.md`（system 部分：角色+判断标准+必须忽略清单）
- 修改：`backend/prompts/diff_judge.md`（user 部分：diff_text+self_product_doc+输出要求）
- 修改：`backend/apps/intelligence/services/llm_client.py`（新增 `DiffJudgeResult` Pydantic schema）
- 修改：`backend/apps/intelligence/services/llm_service.py`（judge_diff 函数，~第 60-106 行；移除 `_extract_json`）

**验收点：**
- [AC-002] diff_judge.md 拆为 system+user，judge_diff 调用改用 instructor
- judge_diff() 返回值仍为 `dict`（`{"has_meaningful_change": bool, "reason": str}`）
- `_extract_json` 函数可移除（不再需要手动 JSON 解析）
- 占位符 `{self_product_doc}` + `{diff_text}` 保留在 user 部分

**步骤 1：创建 diff_judge_system.md**
- 创建：`backend/prompts/diff_judge_system.md`
- 内容：角色定义"你是一个竞品分析专家" + 判断标准 + 必须忽略清单（emoji/空格/标点/排版/样式/日期/cookie/纯链接/图片alt/同义替换）+ 严格标准"宁可漏过不可误报"

**步骤 2：优化 diff_judge.md（user 部分）**
- 修改：`backend/prompts/diff_judge.md`
- 保留 `{self_product_doc}` 和 `{diff_text}` 占位符
- 移除 JSON 输出格式模板（instructor 约束输出结构）
- 移除角色定义和判断规则（已移至 system）
- 保留简要输出要求："请判断以上竞品变化是否有分析价值"

**步骤 3：新增 DiffJudgeResult Pydantic schema**
- 修改：`backend/apps/intelligence/services/llm_client.py`
- 在 `IntelResult` 之后新增：
  ```python
  class DiffJudgeResult(BaseModel):
      """diff 判断结果 Pydantic schema（instructor 约束）。"""
      has_meaningful_change: bool = Field(..., description="diff 是否有分析价值")
      reason: str = Field(..., description="判断理由")
  ```

**步骤 4：修改 judge_diff() 调用方式**
- 修改：`backend/apps/intelligence/services/llm_service.py`，judge_diff 函数（~第 60-106 行）
- 改动：
  - import 增加 `DiffJudgeResult`（从 `.llm_client`）
  - `load_prompt` 分别加载 `diff_judge_system`（不注入变量）和 `diff_judge`（注入 self_product_doc + diff_text）
  - client 从 `get_openai_client()` 改为 `get_instructor_client()`
  - 调用改为 `client.chat.completions.create(response_model=DiffJudgeResult, ...)`
  - 返回值从手动解析改为 `{"has_meaningful_change": result.has_meaningful_change, "reason": result.reason}`
  - 移除 `_extract_json` 函数（~第 109-142 行）及其 import `json` / `re`（如无其他引用）
- 保持 `@retry` 装饰器不变
- 保持空 diff 直接返回逻辑不变

**步骤 5：运行验证**
- Run: `cd /Users/melody/code/ai-workshop/backend && /Users/melody/code/ai-workshop/.venv/bin/python manage.py test apps.intelligence.tests.test_llm_service`
- Expected: PASS（如有 mock 需更新为 instructor 返回模式）

**步骤 6：提交（AUTO_COMMIT=true）**
- Commit message: `feat: diff_judge 拆 system+user，改用 instructor 结构化输出`

---

### Task T3: 优化 intel_system.md + intel_user.md + IntelResult description 对齐 + few-shot 增强

- [ ] **状态**：未开始

**文件：**
- 修改：`backend/prompts/intel_system.md`（角色+核心原则+字段定义，消除与 intel_user 的重复）
- 修改：`backend/prompts/intel_user.md`（数据注入+输出要求，移除冗余 JSON 模板和重复字段描述）
- 修改：`backend/apps/intelligence/services/llm_client.py`（IntelResult Field description 对齐）
- 修改：`backend/apps/intelligence/services/llm_service.py`（_format_few_shots 增强，~第 166-185 行）

**验收点：**
- [AC-003] intel_system.md 和 intel_user.md 无字段描述重复
- [AC-004] IntelResult Field description 与 intel_system.md 字段描述一致
- [AC-005] intel_user.md 中移除冗余 JSON 格式模板
- [AC-008] _format_few_shots 输出包含完整错误报告（4-5 字段）
- 占位符不变：intel_system=`{self_product_doc}`、intel_user=`{diff_text}`+`{page_content}`+`{competitor_context}`+`{negative_few_shots}`

**步骤 1：优化 intel_system.md**
- 修改：`backend/prompts/intel_system.md`
- 保留：角色定义 + `{self_product_doc}` + 核心原则（严禁编造/事实与推断分离/竞品身份准确/证据可追溯/分析结合产品定位）
- 保留：5 个字段的定义（每个字段 1-2 句话描述，作为唯一权威定义）
- 移除：输出格式模板（instructor 已约束）

**步骤 2：优化 intel_user.md**
- 修改：`backend/prompts/intel_user.md`
- 保留：`{diff_text}` + `{page_content}` + `{competitor_context}` + `{negative_few_shots}` 占位符
- 保留：重要提醒（防编造 4 条）
- 移除：5 个字段的重复描述（已在 intel_system 定义）
- 移除：JSON 输出格式模板（instructor 已约束）
- 保留：简要输出要求"请基于以上信息，按照系统提示中定义的字段输出分析报告"

**步骤 3：对齐 IntelResult Field description**
- 修改：`backend/apps/intelligence/services/llm_client.py`，IntelResult 类（~第 19-41 行）
- 将 5 个字段的 description 与 intel_system.md 中的字段定义完全对齐：
  - `competitor_overview`: "竞品的实际业务定位、核心产品、目标用户概述。基于页面内容和补充文档，不从 diff 推断。2-4 段。"
  - `change_summary`: "严格基于 diff 描述发生了什么变化，点明变化类型。3-5 句话。"
  - `strategic_intent`: "基于实际变化推断竞品战略目的。如变化不实质，直接说明。标注事实推断与假设。"
  - `action_suggestion`: "结合我方产品定位，给出具体可执行的行动建议，包含优先级（高/中/低）。"
  - `evidence_diff`: "从 diff 中选取关键变化原文片段，格式为引用 + 标注支撑的分析结论。不得编造引文。"

**步骤 4：增强 _format_few_shots**
- 修改：`backend/apps/intelligence/services/llm_service.py`，_format_few_shots 函数（~第 166-185 行）
- 改动：每条 few-shot 从仅输出 `change_summary` + `user_comment` 扩展为输出完整错误报告：
  ```
  ### 反面案例 {idx}
  - 变化摘要：{feed.change_summary}
  - 战略意图：{feed.strategic_intent}
  - 行动建议：{feed.action_suggestion}
  - 用户评语（为何无意义）：{feed.user_comment or '无评语'}
  ```
- 保持空列表返回"暂无反面案例"不变
- 保持返回类型 `str` 不变

**步骤 5：运行验证**
- Run: `cd /Users/melody/code/ai-workshop/backend && /Users/melody/code/ai-workshop/.venv/bin/python manage.py test apps.intelligence.tests.test_llm_service apps.intelligence.tests.test_llm_client`
- Expected: PASS

**步骤 6：提交（AUTO_COMMIT=true）**
- Commit message: `feat: intel_system/intel_user 消重对齐，IntelResult description 统一，few-shot 增强`

---

### Task T4: 优化 prompt_optimizer.md + _read_prompt_file 改 Blob

- [ ] **状态**：未开始

**文件：**
- 修改：`backend/prompts/prompt_optimizer.md`（补齐占位符保护列表 + 优化指令）
- 修改：`backend/apps/intelligence/services/prompt_optimizer_service.py`（_read_prompt_file，~第 120-126 行）

**验收点：**
- [AC-006] prompt_optimizer.md 占位符保护列表包含 `{page_content}`
- [AC-007] _read_prompt_file 从 Blob 读取而非本地文件系统
- prompt_optimizer.md 占位符不变：`{user_comment}`+`{diff_text}`+`{clean_md}`+`{ai_report}`+`{current_intel_system}`+`{current_intel_user}`

**步骤 1：优化 prompt_optimizer.md**
- 修改：`backend/prompts/prompt_optimizer.md`
- 改动：
  - 占位符保护列表更新为：
    - intel_system 中：`{self_product_doc}`
    - intel_user 中：`{diff_text}`、`{page_content}`、`{negative_few_shots}` 和 `{competitor_context}`
  - 新增约束："保持字段数量与 IntelResult schema（5 字段）一致，不得增删字段定义"
  - 新增约束："不得删除已有的防编造规则和必须忽略清单"
  - 保留现有优化方向示例和"增量优化""保持简洁"原则

**步骤 2：修改 _read_prompt_file 改为从 Blob 读取**
- 修改：`backend/apps/intelligence/services/prompt_optimizer_service.py`，_read_prompt_file 函数（~第 120-126 行）
- 改动：
  - 移除 `from .prompt_loader import PROMPTS_DIR`（如无其他引用）
  - 改为调用 `blob_storage.read_content` + `prompt_loader._get_blob_url` 读取 Blob 上的原始内容：
    ```python
    def _read_prompt_file(name: str) -> str:
        """读取 prompt 模板文件原始内容（从 Blob 读取，不注入变量）。"""
        from .prompt_loader import _get_blob_url
        from . import blob_storage
        pathname = f"prompts/{name}.md"
        return blob_storage.read_content(_get_blob_url(pathname))
    ```
- 保持 optimize_prompts() 其他逻辑不变

**步骤 3：运行验证**
- Run: `cd /Users/melody/code/ai-workshop/backend && /Users/melody/code/ai-workshop/.venv/bin/python manage.py test apps.intelligence.tests.test_prompt_optimizer_service apps.intelligence.tests.test_prompt_loading`
- Expected: PASS

**步骤 4：提交（AUTO_COMMIT=true）**
- Commit message: `feat: prompt_optimizer 补齐占位符保护，_read_prompt_file 改为 Blob 读取`

---

### Task T5: 上传 Blob + 全量测试

- [ ] **状态**：未开始

**文件：**
- 无新文件修改，仅执行上传和测试

**验收点：**
- [AC-009] 5 个优化后的 prompt 已上传至 Vercel Blob（注意：实际为 6 个文件，因新增 denoise_system.md 和 diff_judge_system.md）
- [AC-010] 现有测试 `apps.intelligence.tests` 全部通过

**步骤 1：上传所有 prompt 到 Blob**
- Run: `cd /Users/melody/code/ai-workshop/backend && /Users/melody/code/ai-workshop/.venv/bin/python manage.py init_prompts_to_blob`
- Expected: "完成：N 个成功，0 个失败"（N 应为 6-7 个 .md 文件，含新增的 _system.md）

**步骤 2：运行全量测试**
- Run: `cd /Users/melody/code/ai-workshop/backend && /Users/melody/code/ai-workshop/.venv/bin/python manage.py test apps.intelligence.tests`
- Expected: 全部 PASS

**步骤 3：提交（AUTO_COMMIT=true）**
- Commit message: `chore: 上传优化后的 prompt 到 Blob，全量测试通过`
