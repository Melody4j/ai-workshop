---
title: 竞品补充文档链路打通 + Intel Prompt 优化（I1 实现计划）
status: draft
---

# 竞品补充文档链路打通 + Intel Prompt 优化 实现计划（SSOT）

> **必需技能：** `spec-execute`（按批次执行本计划）
> **上下文获取：** 必须先执行 `spec-context` 获取上下文，定位 `{FEATURE_DIR}`，失败即停止

**目标：** 打通竞品补充文档从 DB → scheduler → LLM → prompt 的完整链路，重写 Intel Prompt 深化分析质量，IntelResult 新增 `competitor_overview` 字段。

**范围：** In = scheduler 链路注入 competitor_context + 重写 intel_system/intel_user prompt + IntelResult 新增 competitor_overview + 同步更新 prompt_optimizer + 报告模板适配 + serializer 适配；Out = 前端表单变更（已存在）、降噪/diff_judge prompt 变更、飞书卡片变更。

**架构：** 按 index 对齐取 competitor_contexts → 格式化为文本 → 注入 intel_user.md `{competitor_context}` 占位符 → IntelResult 扩展为 5 字段 → 同步更新 prompt_optimizer 保护清单 + 报告模板渲染。关键约束：3 次 LLM 调用不合并（不变量 #2）；情报输出固定 5 字段（不变量 #4 修订）。

**验收口径：** 引用 `requirements/solution.md` V-001~V-007 验证清单。

**影响范围：** 引用 `requirements/solution.md#impact-analysis`：intelligence-scheduler / llm-service / llm-client / report-service / prompt-optimizer / intelligence-models / frontend (reports API)。

**需遵守的不变量：**
- 不变量 #2：3 次 LLM 调用独立不合并（来源：`.aisdlc/project/components/llm-service.md#invariants`）
- 不变量 #4（修订）：情报输出固定 5 字段（含 `competitor_overview`），不含价值度字段（来源：`raw.md` R1-Q3）
- 新增不变量：`intel_user.md` 必须包含 `{competitor_context}` 占位符；`prompt_optimizer.md` 保护清单必须包含 `{competitor_context}`

**子仓范围：** 无

---

## TL;DR

- 一句话目标：打通竞品补充文档注入 LLM 的链路 + 重写 Intel Prompt + 新增 `competitor_overview` 字段
- In/Out：In = scheduler/llm_service/llm_client/prompt 模板/报告模板/serializer/prompt_optimizer；Out = 前端表单/飞书卡片/降噪 diff_judge prompt
- 关键路径：T1（DB model + migration）→ T2（IntelResult Pydantic）→ T3（scheduler 传参）→ T4（llm_service generate_intel）→ T5（重写 prompt）→ T6（报告模板）→ T7（prompt_optimizer 兼容）→ T8（serializer 适配）→ T9（前端类型）→ T10（集成测试）
- 最大风险与优先验证点：V-001（占位符完整性）、V-003（空值降级）、V-004（5 字段结构化输出）

---

## 范围与边界（In / Out）

- **In**：
  - `IntelligenceFeed` 模型新增 `competitor_overview` DB 字段 + migration
  - `IntelResult` Pydantic 模型新增 `competitor_overview: str` 字段
  - `scheduler_service._process_url` 按 index 取 `competitor_contexts` 并格式化为文本，传入 `generate_intel`
  - `llm_service.generate_intel` 新增 `competitor_context` 参数，注入 `intel_user.md`
  - 重写 `intel_system.md`（深化分析要求 + 输出结构引导）
  - 重写 `intel_user.md`（新增竞品上下文段落 + 深化输出要求 + 5 字段输出格式）
  - `prompt_optimizer.md` 占位符保护清单新增 `{competitor_context}`
  - `prompt_optimizer_service.py` 的 `ai_report` 拼接新增 `competitor_overview` 段落
  - 报告模板 `report.html.j2` + `report.md.j2` 新增竞品概述渲染区块
  - `IntelligenceFeedDetailSerializer` fields 列表新增 `competitor_overview`
  - 前端 `ReportDetail` 接口新增 `competitor_overview` 字段
- **Out**：
  - 前端表单变更（`competitor_contexts` 已存在，无需修改）
  - 飞书卡片变更（卡片保持 `change_summary` + `strategic_intent` 两段，不新增 `competitor_overview`）
  - 降噪/diff_judge prompt 变更
  - 新增 DB 表
- **不变量/关键约束**：
  - 不变量 #2：3 次 LLM 调用独立不合并
  - 不变量 #4（修订）：情报输出固定 5 字段
  - 新增不变量：`intel_user.md` 必须包含 `{competitor_context}` 占位符
- **影响面**：7 个模块（intelligence-scheduler / llm-service / llm-client / report-service / prompt-optimizer / intelligence-models / frontend）

## 代码工作区清单

无子仓。本仓库为单体 Django 应用。

---

## 里程碑与节奏

- M0（完整交付）：T1~T10 全部完成，所有测试通过，`competitor_context` 链路端到端可验证。

---

## 依赖与资源

- 环境/权限：`backend/.env`（LLM_API_KEY / LLM_BASE_URL / LLM_MODEL），已有配置
- 外部系统/团队：无
- 数据/样本：已有 MonitorProject 记录（含 `competitor_contexts` 数据），可用于集成测试
- 发布/变更窗口：无限制

---

## 风险与验证（可执行）

| # | 风险/假设 | 验证方式 | 成功信号 | 失败信号 | Owner | 截止 | 下一步动作 |
|---|---|---|---|---|---|---|---|
| R1 | `{competitor_context}` 占位符可能被 `load_prompt` 遗漏 | V-001 单元测试 | 输出不含 `{competitor_context}` | 含字面量 | DEV | I2 后 1 天 | 检查模板拼写与参数名 |
| R2 | 优化器覆盖后可能删除 `{competitor_context}` | V-002 手动触发优化器 | 保留占位符 | 删除 | DEV | I2 后 2 天 | 检查保护清单 |
| R3 | 空值时 `competitor_context` 处理不当 | V-003 单元测试 | 占位文本 | 空字符串/None | DEV | I2 后 1 天 | 检查 index 越界逻辑 |
| R4 | instructor 可能不返回 `competitor_overview` | V-004 集成测试 | 5 字段非空 | 缺字段 | DEV | I2 后 2 天 | 检查 schema + prompt |
| R5 | DB migration 在已有数据上失败 | V-006 执行 migrate | migration 成功 | 失败 | DEV | I2 后 1 天 | 检查字段 default |

---

## 验收口径（可追溯）

- 追溯：`requirements/solution.md` V-001~V-007 验证清单
- 关键验收点：
  1. `load_prompt("intel_user", ...)` 正确替换 `{competitor_context}`（V-001）
  2. `competitor_contexts=[]` 时 `competitor_context` 为"暂无竞品补充文档"（V-003）
  3. `generate_intel` 返回 5 字段非空的 `IntelResult`（V-004）
  4. 报告模板渲染 `competitor_overview` 不报错（V-005）
  5. DB migration 向后兼容（V-006）
  6. Prompt 重写后输出质量提升（V-007）

---

## NEEDS CLARIFICATION（未消除前不得进入 I2）

无。所有关键决策已在 R1 澄清中裁决（R1-Q1~Q5），2 个 Context Gap 已在 I1 阶段确认：
- Serializer：`IntelligenceFeedDetailSerializer.fields` 需新增 `competitor_overview`（T8）
- 飞书卡片：不新增 `competitor_overview`，保持卡片精简（Out of scope）

---

## 任务清单（SSOT）

### Task T1: IntelligenceFeed 模型新增 competitor_overview DB 字段 + migration

- [x] **状态**：完成

**代码仓范围：**
- 根项目：`backend/apps/intelligence/`

**文件：**
- 修改：`backend/apps/intelligence/models.py`（IntelligenceFeed 类，`evidence_diff` 字段后新增 `competitor_overview`）
- 创建：`backend/apps/intelligence/migrations/000X_add_competitor_overview.py`（由 makemigrations 生成）

**验收点：**
- `IntelligenceFeed` 模型含 `competitor_overview = models.TextField(blank=True, default="")` 字段
- `makemigrations` + `migrate` 成功
- 已有记录的 `competitor_overview` 为空字符串

**步骤 1：修改模型**
- 修改点：`backend/apps/intelligence/models.py` IntelligenceFeed 类，在 `evidence_diff` 后新增：
  ```python
  competitor_overview = models.TextField(blank=True, default="")
  ```

**步骤 2：生成并执行 migration**
- Run: `cd /Users/melody/code/ai-workshop-009/backend && python manage.py makemigrations intelligence`
- Expected: 输出 `000X_add_competitor_overview...` 新 migration 文件
- Run: `cd /Users/melody/code/ai-workshop-009/backend && python manage.py migrate intelligence`
- Expected: `Applying intelligence.000X_... OK`

**步骤 3：提交**
- Commit message: `feat: IntelligenceFeed 新增 competitor_overview 字段（5 字段扩展）`
- 审计信息：
  - repo: `root`
    branch: `009-competitor-context-intel`
    commit: `<TBD>`
    pr: `<TBD>`
    changed_files:
      - `backend/apps/intelligence/models.py`
      - `backend/apps/intelligence/migrations/000X_add_competitor_overview.py`

---

### Task T2: IntelResult Pydantic 模型新增 competitor_overview 字段

- [x] **状态**：完成

**代码仓范围：**
- 根项目：`backend/apps/intelligence/services/`

**文件：**
- 修改：`backend/apps/intelligence/services/llm_client.py`（IntelResult 类）

**验收点：**
- `IntelResult` 含 `competitor_overview: str = Field(..., description="...")` 字段
- 字段顺序：`competitor_overview` 在 `change_summary` 之前（引导 LLM 先输出概述）

**步骤 1：修改 IntelResult**
- 修改点：`backend/apps/intelligence/services/llm_client.py` IntelResult 类，在 `change_summary` 前新增：
  ```python
  competitor_overview: str = Field(
      ...,
      description="竞品整体定位与背景概述，基于补充文档和 diff 综合分析",
  )
  ```

**步骤 2：运行验证**
- Run: `cd /Users/melody/code/ai-workshop-009/backend && python -c "from apps.intelligence.services.llm_client import IntelResult; print(IntelResult.model_fields.keys())"`
- Expected: 输出含 `competitor_overview`，共 5 个字段

**步骤 3：提交**
- Commit message: `feat: IntelResult Pydantic 模型新增 competitor_overview 字段`
- 审计信息：
  - repo: `root`
    branch: `009-competitor-context-intel`
    commit: `<TBD>`
    pr: `<TBD>`
    changed_files:
      - `backend/apps/intelligence/services/llm_client.py`

---

### Task T3: scheduler_service _process_url 按 index 取 competitor_contexts 并传入 generate_intel

- [x] **状态**：完成

**代码仓范围：**
- 根项目：`backend/apps/intelligence/services/`

**文件：**
- 修改：`backend/apps/intelligence/services/scheduler_service.py`

**验收点：**
- `_process_url` 签名新增 `competitor_context` 参数
- `run_scan` 和 `run_scan_for_project` 遍历时按 index 取 `competitor_contexts[idx]`
- `competitor_context` 格式化逻辑：有内容时拼接 `supplement_doc_name` + `supplement_doc_content`；无内容时填"暂无竞品补充文档"
- `generate_intel` 调用传入 `competitor_context`

**步骤 1：修改遍历逻辑**
- 修改点：`scheduler_service.py` `run_scan()` 和 `run_scan_for_project()` 中的遍历循环
- 在 `for idx, item in enumerate(urls, 1):` 内部，按 index 取 `competitor_contexts`：
  ```python
  contexts = project.competitor_contexts or []
  ctx_item = contexts[idx - 1] if (idx - 1) < len(contexts) else {}
  supplement_name = (ctx_item or {}).get("supplement_doc_name", "")
  supplement_content = (ctx_item or {}).get("supplement_doc_content", "")
  ```

**步骤 2：修改 _process_url 签名和调用**
- 修改点：`_process_url` 签名新增 `competitor_context: str = ""`
- 在 `run_scan` / `run_scan_for_project` 调用处传入格式化后的 `competitor_context`
- 格式化逻辑：
  ```python
  if supplement_content and supplement_content.strip():
      competitor_context = f"文档名称：{supplement_name}\n\n文档内容：\n{supplement_content}"
  else:
      competitor_context = "暂无竞品补充文档"
  ```

**步骤 3：修改 generate_intel 调用**
- 修改点：`_process_url` 中 `llm_service.generate_intel(...)` 调用，新增 `competitor_context=competitor_context`

**步骤 4：运行验证**
- Run: `cd /Users/melody/code/ai-workshop-009/backend && python -c "from apps.intelligence.services.scheduler_service import _process_url; import inspect; print(inspect.signature(_process_url))"`
- Expected: 签名含 `competitor_context` 参数

**步骤 5：提交**
- Commit message: `feat: scheduler _process_url 按 index 取 competitor_contexts 并传入 generate_intel`
- 审计信息：
  - repo: `root`
    branch: `009-competitor-context-intel`
    commit: `<TBD>`
    pr: `<TBD>`
    changed_files:
      - `backend/apps/intelligence/services/scheduler_service.py`

---

### Task T4: llm_service generate_intel 新增 competitor_context 参数并注入 prompt

- [x] **状态**：完成

**代码仓范围：**
- 根项目：`backend/apps/intelligence/services/`

**文件：**
- 修改：`backend/apps/intelligence/services/llm_service.py`

**验收点：**
- `generate_intel` 签名新增 `competitor_context: str` 参数
- `load_prompt("intel_user", ...)` 调用新增 `competitor_context=competitor_context`
- 返回的 `IntelResult` 5 字段写入 `IntelligenceFeed`

**步骤 1：修改 generate_intel 签名和 prompt 注入**
- 修改点：`llm_service.py` `generate_intel` 函数
- 签名改为：`def generate_intel(diff_text, self_product_doc, few_shots, competitor_context: str) -> IntelResult:`
- `load_prompt("intel_user", ...)` 调用新增 `competitor_context=competitor_context`

**步骤 2：修改 IntelligenceFeed 写入**
- 修改点：`scheduler_service.py` 中 `IntelligenceFeed.objects.create(...)` 调用
- 新增 `competitor_overview=intel_result.competitor_overview`

**步骤 3：运行验证**
- Run: `cd /Users/melody/code/ai-workshop-009/backend && python -c "from apps.intelligence.services.llm_service import generate_intel; import inspect; print(inspect.signature(generate_intel))"`
- Expected: 签名含 `competitor_context` 参数

**步骤 4：提交**
- Commit message: `feat: generate_intel 新增 competitor_context 参数并注入 intel_user prompt`
- 审计信息：
  - repo: `root`
    branch: `009-competitor-context-intel`
    commit: `<TBD>`
    pr: `<TBD>`
    changed_files:
      - `backend/apps/intelligence/services/llm_service.py`
      - `backend/apps/intelligence/services/scheduler_service.py`

---

### Task T5: 重写 intel_system.md 和 intel_user.md

- [x] **状态**：完成

**代码仓范围：**
- 根项目：`backend/prompts/`

**文件：**
- 修改：`backend/prompts/intel_system.md`
- 修改：`backend/prompts/intel_user.md`

**验收点：**
- `intel_system.md` 深化分析要求，明确 5 字段输出结构引导
- `intel_user.md` 新增 `## 竞品补充文档` 段落 + `{competitor_context}` 占位符
- `intel_user.md` 输出要求更新为 5 字段（新增 `competitor_overview`）
- `load_prompt("intel_user", diff_text="...", negative_few_shots="...", competitor_context="...")` 不残留 `{competitor_context}` 字面量

**步骤 1：重写 intel_system.md**
- 修改点：`backend/prompts/intel_system.md`
- 内容要点：角色定义 + 产品锚定文档 + 深化分析要求（每个字段的输出深度要求 + 引用约束 + 不可编造约束）+ 5 字段输出结构引导

**步骤 2：重写 intel_user.md**
- 修改点：`backend/prompts/intel_user.md`
- 内容要点：竞品变化 diff + 竞品补充文档（`{competitor_context}`）+ 历史反面案例 + 5 字段输出要求 + JSON 格式约束

**步骤 3：运行验证**
- Run: `cd /Users/melody/code/ai-workshop-009/backend && python -c "from apps.intelligence.services.prompt_loader import load_prompt; r = load_prompt('intel_user', diff_text='test', negative_few_shots='test', competitor_context='test'); assert '{competitor_context}' not in r; print('PASS')"`
- Expected: `PASS`

**步骤 4：提交**
- Commit message: `feat: 重写 intel_system/intel_user prompt，新增竞品上下文占位符与 5 字段输出引导`
- 审计信息：
  - repo: `root`
    branch: `009-competitor-context-intel`
    commit: `<TBD>`
    pr: `<TBD>`
    changed_files:
      - `backend/prompts/intel_system.md`
      - `backend/prompts/intel_user.md`

---

### Task T6: 报告模板新增 competitor_overview 渲染区块

- [x] **状态**：完成

**代码仓范围：**
- 根项目：`backend/templates/reports/`

**文件：**
- 修改：`backend/templates/reports/report.html.j2`
- 修改：`backend/templates/reports/report.md.j2`

**验收点：**
- HTML 模板在"变化摘要"前新增"竞品概述"区块
- MD 模板在"变化摘要"前新增"竞品概述"段落
- `competitor_overview` 为空字符串时渲染不报错

**步骤 1：修改 HTML 模板**
- 修改点：`report.html.j2` 在 `<div class="section">变化摘要</div>` 前新增：
  ```html
  <div class="section">
      <div class="section-title">竞品概述</div>
      <div class="section-content">{{ feed.competitor_overview }}</div>
  </div>
  ```

**步骤 2：修改 MD 模板**
- 修改点：`report.md.j2` 在 `## 变化摘要` 前新增：
  ```markdown
  ## 竞品概述

  {{ feed.competitor_overview }}

  ```

**步骤 3：运行验证**
- Run: `cd /Users/melody/code/ai-workshop-009/backend && python -c "
from jinja2 import Environment, FileSystemLoader
env = Environment(loader=FileSystemLoader('templates/reports'))
t = env.get_template('report.html.j2')
class FakeFeed:
    competitor_overview = ''
    change_summary = 'test'
    strategic_intent = 'test'
    action_suggestion = 'test'
    evidence_diff = 'test'
    class project:
        project_name = 'test'
    class job_status:
        CHANGED = 'CHANGED'
    job_status = 'CHANGED'
    def published_at(self): return None
from datetime import datetime
class F:
    competitor_overview = ''
    change_summary = 't'
    strategic_intent = 't'
    action_suggestion = 't'
    evidence_diff = 't'
    published_at = datetime.now()
    class project:
        project_name = 't'
    job_status = 'CHANGED'
print(t.render(feed=F()))
print('PASS')
"`
- Expected: `PASS`（渲染不报错）

**步骤 4：提交**
- Commit message: `feat: 报告模板新增竞品概述渲染区块`
- 审计信息：
  - repo: `root`
    branch: `009-competitor-context-intel`
    commit: `<TBD>`
    pr: `<TBD>`
    changed_files:
      - `backend/templates/reports/report.html.j2`
      - `backend/templates/reports/report.md.j2`

---

### Task T7: prompt_optimizer 兼容性更新

- [x] **状态**：完成

**代码仓范围：**
- 根项目：`backend/prompts/` + `backend/apps/intelligence/services/`

**文件：**
- 修改：`backend/prompts/prompt_optimizer.md`
- 修改：`backend/apps/intelligence/services/prompt_optimizer_service.py`

**验收点：**
- `prompt_optimizer.md` 占位符保护清单新增 `{competitor_context}`
- `prompt_optimizer_service.py` 的 `ai_report` 拼接新增 `competitor_overview` 段落

**步骤 1：修改 prompt_optimizer.md**
- 修改点：`backend/prompts/prompt_optimizer.md` 第 41 行附近，保护清单新增 `{competitor_context}`
- 原：`intel_user 中：{diff_text} 和 {negative_few_shots}`
- 改：`intel_user 中：{diff_text}、{negative_few_shots} 和 {competitor_context}`

**步骤 2：修改 ai_report 拼接**
- 修改点：`prompt_optimizer_service.py` `ai_report` 字符串拼接，在 `## 变化摘要` 前新增：
  ```python
  ai_report = f"""## 竞品概述
  {feed.competitor_overview}

  ## 变化摘要
  {feed.change_summary}
  ...
  ```

**步骤 3：运行验证**
- Run: `cd /Users/melody/code/ai-workshop-009/backend && python -c "from apps.intelligence.services.prompt_loader import load_prompt; r = load_prompt('prompt_optimizer', diff_text='t', clean_md='t', ai_report='t', user_comment='t', current_intel_system='t', current_intel_user='t'); print('PASS')"`
- Expected: `PASS`

**步骤 4：提交**
- Commit message: `feat: prompt_optimizer 兼容 competitor_context 占位符与 competitor_overview 字段`
- 审计信息：
  - repo: `root`
    branch: `009-competitor-context-intel`
    commit: `<TBD>`
    pr: `<TBD>`
    changed_files:
      - `backend/prompts/prompt_optimizer.md`
      - `backend/apps/intelligence/services/prompt_optimizer_service.py`

---

### Task T8: IntelligenceFeedDetailSerializer 新增 competitor_overview 字段

- [x] **状态**：完成

**代码仓范围：**
- 根项目：`backend/apps/intelligence/`

**文件：**
- 修改：`backend/apps/intelligence/serializers.py`

**验收点：**
- `IntelligenceFeedDetailSerializer.Meta.fields` 列表新增 `competitor_overview`

**步骤 1：修改 serializer**
- 修改点：`serializers.py` `IntelligenceFeedDetailSerializer.Meta.fields`，在 `change_summary` 前新增 `"competitor_overview"`

**步骤 2：运行验证**
- Run: `cd /Users/melody/code/ai-workshop-009/backend && python -c "from apps.intelligence.serializers import IntelligenceFeedDetailSerializer; print(IntelligenceFeedDetailSerializer.Meta.fields)"`
- Expected: 列表含 `competitor_overview`

**步骤 3：提交**
- Commit message: `feat: IntelligenceFeedDetailSerializer 暴露 competitor_overview 字段`
- 审计信息：
  - repo: `root`
    branch: `009-competitor-context-intel`
    commit: `<TBD>`
    pr: `<TBD>`
    changed_files:
      - `backend/apps/intelligence/serializers.py`

---

### Task T9: 前端 ReportDetail 接口新增 competitor_overview 字段

- [x] **状态**：完成

**代码仓范围：**
- 根项目：`frontend/src/`

**文件：**
- 修改：`frontend/src/api/reports.ts`

**验收点：**
- `ReportDetail` 接口新增 `competitor_overview: string` 字段

**步骤 1：修改接口类型**
- 修改点：`frontend/src/api/reports.ts` `ReportDetail` 接口，在 `change_summary` 前新增 `competitor_overview: string`

**步骤 2：提交**
- Commit message: `feat: 前端 ReportDetail 接口新增 competitor_overview 字段`
- 审计信息：
  - repo: `root`
    branch: `009-competitor-context-intel`
    commit: `<TBD>`
    pr: `<TBD>`
    changed_files:
      - `frontend/src/api/reports.ts`

---

### Task T10: 集成测试与端到端验证

- [x] **状态**：完成

**代码仓范围：**
- 根项目：`backend/apps/intelligence/tests/`

**文件：**
- 创建：`backend/apps/intelligence/tests/test_competitor_context.py`

**验收点：**
- V-001：`load_prompt("intel_user", ...)` 不残留 `{competitor_context}` 字面量
- V-003：`competitor_contexts=[]` 时 `competitor_context` 为"暂无竞品补充文档"
- V-004：`generate_intel` 返回 5 字段（需 mock LLM）
- V-005：报告模板渲染 `competitor_overview` 为空时不报错
- V-006：migration 向后兼容

**步骤 1：写测试**
- 修改点：创建 `backend/apps/intelligence/tests/test_competitor_context.py`
- 测试用例：
  1. `test_load_prompt_replaces_competitor_context`：V-001
  2. `test_empty_competitor_contexts_returns_placeholder`：V-003
  3. `test_generate_intel_returns_5_fields`（mock LLM）：V-004
  4. `test_report_template_renders_empty_competitor_overview`：V-005

**步骤 2：运行测试**
- Run: `cd /Users/melody/code/ai-workshop-009/backend && python manage.py test apps.intelligence.tests.test_competitor_context -v2`
- Expected: 所有测试 PASS

**步骤 3：运行已有测试确保不回归**
- Run: `cd /Users/melody/code/ai-workshop-009/backend && python manage.py test apps.intelligence -v2`
- Expected: 所有已有测试 PASS（可能需调整因 IntelResult 签名变更导致的测试）

**步骤 4：提交**
- Commit message: `test: 竞品补充文档链路集成测试（V-001/V-003/V-004/V-005）`
- 审计信息：
  - repo: `root`
    branch: `009-competitor-context-intel`
    commit: `<TBD>`
    pr: `<TBD>`
    changed_files:
      - `backend/apps/intelligence/tests/test_competitor_context.py`

---

## Merge-back 待办清单（仅记录，不在本阶段执行）

- MB-001：不变量 #4 修订（4→5 字段）需晋升到 `.aisdlc/project/components/llm-service.md` 和 `CLAUDE.md`
- MB-002：`IntelResult` 5 字段定义需晋升到 `.aisdlc/project/components/llm-client.md`（如有）
- MB-003：新增不变量（`intel_user.md` 必须包含 `{competitor_context}` 占位符）需晋升到 `.aisdlc/project/components/llm-service.md`
- MB-004：`IntelligenceFeed` 新增 `competitor_overview` 字段需更新 `.aisdlc/project/components/intelligence-models.md`
