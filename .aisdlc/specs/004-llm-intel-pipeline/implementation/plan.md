---
title: I1 Implementation Plan — LLM 系统接入与竞品分析全流程
status: draft
---

> **必需技能：** `spec-execute`（按批次执行本计划）
> **上下文获取：** 必须先执行 `spec-context` 获取上下文，定位 `{FEATURE_DIR}`，失败即停止

**目标：** 在 Spec 003 采集调度层之上补齐 LLM 链路（BS→LLM 叠加降噪 → 混合 diff 熔断 → 单次 LLM 情报生成 → 入库 + Jinja2 报告落盘），打通从"采集后原始 markdown"到"情报入库"的完整闭环。

**范围：** In = LLM 服务抽象层、5 套 Prompt 模板、混合 diff 熔断、instructor 情报生成、IntelligenceFeed 入库、Jinja2 报告、scheduler 集成；Out = 飞书推送、前端变更、多 provider、异步队列。

**架构：** 新增 llm_service（3 次独立 LLM 调用：降噪/diff判断/情报生成）+ diff_service（difflib 文本 diff）+ report_service（Jinja2 渲染），scheduler_service 串接全链路。BS 去噪保留作为 LLM 降噪前置，clean_md_path 语义从 BS 结果覆盖为 LLM 结果，无需 DB migration。

**验收口径：** `requirements/prd.md` AC-001~AC-017（3 场景 + 异常容错 + 配置 Prompt + 旧格式兼容）

**影响范围：** `requirements/solution.md#7. Impact Analysis`：intelligence-scheduler（修改契约）、intelligence-models（语义变更）、llm-service（新增）、report-service（新增）

**需遵守的不变量：**
1. Invariant #2（修订）：3 次 LLM 调用独立，不合并
2. Invariant #3（修订）：情报生成仅在 LLM diff 判断有意义时触发
3. Invariant #4（不变）：情报输出固定 4 字段，不含价值度
4. Invariant #11（不变）：Negative Few-Shot 注入上限最近 5 条
5. Invariant #13（不变）：证据 diff 嵌入 change_summary 或报告素材，不独立为 DB 字段
6. models Invariant #9（不变）：DataSnapshot 字段只存路径不存内容
7. scheduler Invariant #5（修订）：本模块串接 LLM 链路后写 IntelligenceFeed

**子仓范围：** 无（仓库不存在 `.gitmodules`）

---

## TL;DR

- 一句话目标：补齐 LLM 链路（降噪→diff熔断→情报生成→入库+报告），打通采集到情报的完整闭环。
- In/Out：In = LLM 服务层 + Prompt 体系 + diff 熔断 + 情报生成 + 报告落盘 + scheduler 集成；Out = 飞书/前端/多provider/异步队列。
- 关键路径：(1) 依赖+配置+Prompt 模板 → (2) llm_service 三层调用 → (3) diff_service → (4) report_service → (5) scheduler 集成 → (6) 端到端测试。
- 最大风险与优先验证点：R5（instructor 结构化输出可靠性）、R3（混合 diff 熔断准确率）、R10（端到端耗时）。

---

## 范围与边界（In / Out）

- **In**：
  - LLM 服务抽象层（OpenAI 兼容 client，settings.py + .env 配置）
  - 5 套 Prompt 模板（`prompts/` 目录）
  - BS→LLM 叠加降噪（第 1 次 LLM 调用）
  - 文本 diff（difflib）+ LLM 语义 diff 判断（第 2 次 LLM 调用）
  - 情报生成 instructor + Pydantic 4 字段直出（第 3 次 LLM 调用）
  - Negative Few-Shot 注入（最近 5 条 `user_feedback=-1`）
  - IntelligenceFeed 入库（4 字段 + `job_status=CHANGED`）
  - Jinja2 渲染 HTML 网页报告 + MD 表格落盘
  - scheduler_service.run_scan() 串接 LLM 全链路
  - LLM 调用重试机制（2-3 次，间隔 30s）
  - 首次爬取特殊处理（跳过 diff，直接情报生成）
  - 旧格式快照兼容（pre-LLM 快照跳过 diff）
- **Out**：
  - 飞书推送（Spec 001 范围）
  - 前端页面变更（收件箱/详情/报告预览不变）
  - Django Admin 变更
  - 多 LLM provider 支持（仅 OpenAI 兼容）
  - 异步队列/消息中间件
  - `refined_rules` 写入（P1 占位）
- **不变量/关键约束**：见头部"需遵守的不变量"7 条。
- **影响面**：scheduler_service 扩展（串接 LLM 链路）；DataSnapshot.clean_md_path 语义变更；新增 llm_service / diff_service / report_service；settings.py 新增 LLM 配置；requirements 新增依赖。

## 代码工作区清单（如适用）

> 仓库不存在 `.gitmodules`，无子仓。

## 里程碑与节奏

- **M0（MVP）**：全链路可端到端执行——调度触发 → 采集 → LLM 降噪 → diff 熔断 → 情报生成 → 入库 + 报告落盘。对应 Task T1-T13。
- **M1（可选）**：Prompt 调优、重试策略优化、报告格式迭代。不在本计划范围。

---

## 依赖与资源

- 环境/权限：Python 3.10+，已安装 venv（`/Users/melody/code/ai-workshop/.venv`）；需新增 `instructor`、`pydantic`、`openai`、`jinja2`、`python-dotenv` 依赖。
- 外部系统/团队：OpenAI 兼容 LLM API（需用户提供 api_key / base_url / model 配置）。
- 数据/样本：现有 `data/snapshots/` 目录的快照文件；现有 IntelligenceFeed 表（可能有空记录）。
- 发布/变更窗口：无限制（开发环境）。

---

## 风险与验证（可执行）

| # | 风险/假设 | 验证方式 | 成功信号 | 失败信号 | Owner | 截止 | 下一步动作 |
|---|---|---|---|---|---|---|---|
| R1 | LLM 降噪叠加效果优于纯 BS | 5-10 真实站点 BS MD→LLM 降噪，人工对比 | 噪音减少>50%，核心保留>90% | 降噪质量不达标 | FS | I2 | 调 prompt 或加规则预过滤 |
| R2 | 旧格式快照兼容检测正确 | 首次运行检测旧格式→跳过 diff | 旧格式不触发错误 diff | 旧格式 diff 报错 | FS | I2 | 标记旧快照 pre-LLM |
| R3 | 混合 diff 熔断准确率合理 | 20+ 次执行结果统计 | 无意义熔断率 20-60% | 超范围 | FS | I2 | 调 diff 判断 prompt |
| R4 | LLM 重试与失败记录正确 | 模拟超时/限流场景 | 重试耗尽→写 ERROR_CRAWL | 重试逻辑异常 | FS | I2 | 增加重试次数或调间隔 |
| R5 | instructor 结构化输出可靠 | 10+ 真实 diff 测试情报生成 | 4 字段完整率>95% | 解析失败率高 | FS | I2 | 增加格式约束或 fallback |
| R6 | Negative Few-Shot 注入有效 | 有/无对比测试情报质量 | 无意义情报减少>30% | 无改善 | FS+PM | I2 | 减少条数或改摘要注入 |
| R7 | Prompt 变量注入鲁棒 | 超长/空/特殊字符测试 | 极端值不导致 LLM 错误 | LLM 返回错误或空 | FS | I2 | 增加输入清洗和长度截断 |
| R8 | diff 截断策略有效 | 测量典型 diff 长度 | 截断后不超限且核心保留 | 超限或核心丢失 | FS | I2 | 实现 diff 摘要或分段 |
| R9 | Jinja2 报告渲染正确 | 5+ 份报告验证 | HTML 无错、MD 表格正确 | 格式错误 | FS | I2 | 修正 Jinja2 模板 |
| R10 | 端到端耗时可控 | 模拟完整调度执行 | 单 URL <60s | 超时 | FS | I2 | 优化或增加超时控制 |

---

## 验收口径（可追溯）

- 追溯：`requirements/solution.md`（推荐方案 + 10 验证项 + Impact Analysis 13 条不变量）
- 追溯：`requirements/prd.md` AC-001~AC-017（3 场景 + 异常容错 + 配置 Prompt + 旧格式兼容）
- 关键验收点摘要：
  - AC-001：clean_md_path 指向 LLM 降噪后 MD
  - AC-002/AC-003/AC-004：有变化全链路（CHANGED + 4 字段非空 + 报告落盘 + 3 次独立调用）
  - AC-005/AC-006/AC-007：无变化熔断（NO_CHANGE + 零 LLM diff 调用 + 4 字段空）
  - AC-008/AC-009：首次爬取跳过 diff 直接情报生成
  - AC-010~AC-013：LLM 失败重试→ERROR_CRAWL + 单 URL 异常不中断其他
  - AC-014：.env 配置正确加载
  - AC-015：5 套 Prompt 模板变量注入正确
  - AC-016：Negative Few-Shot 5 条注入
  - AC-017：旧格式快照兼容

---

## NEEDS CLARIFICATION（未消除前不得进入 I2）

> 当前无未消除的不确定性。所有关键决策已在 R1 澄清阶段裁决，D2 设计阶段已产出完整设计。

- C1：无
  - 缺什么：无
  - 取证/验证方式：N/A
  - 成功/失败信号：N/A
  - 下一步动作：N/A

---

## 任务清单（SSOT）

### Task T1: 新增依赖与 LLM 配置

- [ ] **状态**：未开始

**代码仓范围：**
- 根项目：`backend/requirements/base.txt`、`backend/config/settings.py`、`backend/.env.example`
- 子仓：无

**文件：**
- 修改：`backend/requirements/base.txt`（新增 instructor、pydantic、openai、jinja2、python-dotenv）
- 修改：`backend/config/settings.py`（新增 LLM 配置块 + dotenv 加载）
- 创建：`backend/.env.example`（LLM 配置模板，不含真实密钥）

**验收点：**
- `pip install` 成功安装所有新依赖
- Django 启动时能从 `.env` 读取 LLM 配置
- `settings.LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL` / `LLM_TEMPERATURE` / `LLM_MAX_TOKENS` 可访问

**步骤 1：添加依赖**
- 修改点：`backend/requirements/base.txt` 追加 `instructor>=1.0.0`、`pydantic>=2.0.0`、`openai>=1.0.0`、`jinja2>=3.1.0`、`python-dotenv>=1.0.0`
- Run: `cd /Users/melody/code/ai-workshop && .venv/bin/pip install -r backend/requirements/base.txt`
- Expected: 所有包安装成功

**步骤 2：添加 .env 加载与 LLM 配置到 settings.py**
- 修改点：`backend/config/settings.py` 顶部加 `from dotenv import load_dotenv; load_dotenv()`，新增 `LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL` / `LLM_TEMPERATURE` / `LLM_MAX_TOKENS` 从 `os.environ` 读取
- Run: `cd /Users/melody/code/ai-workshop/backend && ../.venv/bin/python manage.py check`
- Expected: Django check 通过，无 import 错误

**步骤 3：创建 .env.example**
- 创建 `backend/.env.example`，含 `LLM_API_KEY=`、`LLM_BASE_URL=`、`LLM_MODEL=`、`LLM_TEMPERATURE=0.3`、`LLM_MAX_TOKENS=4096`

**步骤 4：提交**
- Commit message: `feat: 新增 LLM 依赖与配置（instructor/openai/jinja2/python-dotenv）`
- 审计信息：
  - repo: `root`
    branch: `004-llm-intel-pipeline`
    commit: `<TBD>`
    pr: `<TBD>`
    changed_files:
      - `backend/requirements/base.txt`
      - `backend/config/settings.py`
      - `backend/.env.example`

---

### Task T2: 创建 5 套 Prompt 模板

- [ ] **状态**：未开始

**代码仓范围：**
- 根项目：`backend/prompts/`
- 子仓：无

**文件：**
- 创建：`backend/prompts/denoise.md`（数据清洗 Prompt）
- 创建：`backend/prompts/diff_judge.md`（diff 判断 Prompt）
- 创建：`backend/prompts/intel_system.md`（自家产品系统 Prompt）
- 创建：`backend/prompts/intel_user.md`（竞品分析 User Prompt）
- 测试：`backend/apps/intelligence/tests/test_prompt_loading.py`

**验收点：**
- 5 个 Prompt 文件存在且内容符合 `design.md#3.4` 设计
- 模板变量占位符（`{bs_clean_md}` / `{self_product_doc}` / `{diff_text}` / `{negative_few_shots}`）正确存在
- 测试能加载并渲染模板，占位符被正确替换

**步骤 1：写失败测试**
- 修改点：`backend/apps/intelligence/tests/test_prompt_loading.py`
- 测试内容：加载 4 个 Prompt 文件（denoise/diff_judge/intel_system/intel_user），验证文件存在、含正确变量占位符、渲染后占位符被替换
- Run: `cd /Users/melody/code/ai-workshop/backend && ../.venv/bin/python manage.py test apps.intelligence.tests.test_prompt_loading`
- Expected: FAIL（Prompt 文件不存在）

**步骤 2：创建 5 套 Prompt 模板文件**
- 修改点：按 `design.md#3.4` 逐字创建 4 个 Prompt 文件（第 5 套 Pydantic schema 是代码层，无独立文件）
- 文件内容直接复制 `design.md` 中已设计的模板结构

**步骤 3：运行验证**
- Run: `cd /Users/melody/code/ai-workshop/backend && ../.venv/bin/python manage.py test apps.intelligence.tests.test_prompt_loading`
- Expected: PASS（4 个文件加载成功，变量占位符替换正确）

**步骤 4：提交**
- Commit message: `feat: 创建 5 套 Prompt 模板（降噪/diff判断/系统/用户/输出约束）`
- 审计信息：
  - repo: `root`
    branch: `004-llm-intel-pipeline`
    commit: `<TBD>`
    pr: `<TBD>`
    changed_files:
      - `backend/prompts/denoise.md`
      - `backend/prompts/diff_judge.md`
      - `backend/prompts/intel_system.md`
      - `backend/prompts/intel_user.md`
      - `backend/apps/intelligence/tests/test_prompt_loading.py`

---

### Task T3: 实现 LLM Client 封装

- [ ] **状态**：未开始

**代码仓范围：**
- 根项目：`backend/apps/intelligence/services/`
- 子仓：无

**文件：**
- 创建：`backend/apps/intelligence/services/llm_client.py`（OpenAI 兼容 client 封装 + Pydantic schema）
- 创建：`backend/apps/intelligence/services/prompt_loader.py`（Prompt 模板加载与变量注入工具）
- 测试：`backend/apps/intelligence/tests/test_llm_client.py`

**验收点：**
- `get_openai_client()` 返回 OpenAI client 实例，配置来自 settings
- `get_instructor_client()` 返回 instructor-wrapped client
- `IntelResult` Pydantic model 定义 4 字段（change_summary / strategic_intent / action_suggestion / evidence_diff）
- `load_prompt(name, **vars)` 能加载 `prompts/{name}.md` 并替换变量
- 测试通过（mock LLM API）

**步骤 1：写失败测试**
- 修改点：`backend/apps/intelligence/tests/test_llm_client.py`
- 测试内容：
  - `IntelResult` model 可实例化，4 字段类型为 str
  - `load_prompt("denoise", bs_clean_md="test")` 返回含 "test" 不含 `{bs_clean_md}` 的字符串
  - `load_prompt("diff_judge", self_product_doc="doc", diff_text="diff")` 正确替换
  - `load_prompt("intel_system", self_product_doc="doc")` 正确替换
  - `load_prompt("intel_user", diff_text="diff", negative_few_shots="shots")` 正确替换
  - `load_prompt` 对不存在的文件抛出明确异常
- Run: `cd /Users/melody/code/ai-workshop/backend && ../.venv/bin/python manage.py test apps.intelligence.tests.test_llm_client`
- Expected: FAIL（模块不存在）

**步骤 2：实现 llm_client.py**
- 修改点：`backend/apps/intelligence/services/llm_client.py`
- 实现：
  - `from pydantic import BaseModel, Field` → `IntelResult` 4 字段
  - `from openai import OpenAI` + `import instructor`
  - `get_openai_client()` → `OpenAI(api_key=settings.LLM_API_KEY, base_url=settings.LLM_BASE_URL)`
  - `get_instructor_client()` → `instructor.from_openai(get_openai_client())`

**步骤 3：实现 prompt_loader.py**
- 修改点：`backend/apps/intelligence/services/prompt_loader.py`
- 实现：`load_prompt(name: str, **kwargs) -> str`，从 `backend/prompts/{name}.md` 读取，用 `str.format(**kwargs)` 替换变量

**步骤 4：运行验证**
- Run: `cd /Users/melody/code/ai-workshop/backend && ../.venv/bin/python manage.py test apps.intelligence.tests.test_llm_client`
- Expected: PASS

**步骤 5：提交**
- Commit message: `feat: 实现 LLM client 封装与 Prompt 加载器`
- 审计信息：
  - repo: `root`
    branch: `004-llm-intel-pipeline`
    commit: `<TBD>`
    pr: `<TBD>`
    changed_files:
      - `backend/apps/intelligence/services/llm_client.py`
      - `backend/apps/intelligence/services/prompt_loader.py`
      - `backend/apps/intelligence/tests/test_llm_client.py`

---

### Task T4: 实现 LLM 重试机制

- [ ] **状态**：未开始

**代码仓范围：**
- 根项目：`backend/apps/intelligence/services/`
- 子仓：无

**文件：**
- 创建：`backend/apps/intelligence/services/retry.py`（通用重试装饰器）
- 测试：`backend/apps/intelligence/tests/test_retry.py`

**验收点：**
- `@retry(max_retries=3, delay=30)` 装饰器：失败重试 3 次，间隔 30s（测试中缩短间隔）
- 重试耗尽后 raise `LLMError`（自定义异常）
- 每次重试有日志记录
- 测试通过（mock 函数抛异常，验证调用次数）

**步骤 1：写失败测试**
- 修改点：`backend/apps/intelligence/tests/test_retry.py`
- 测试内容：
  - 装饰 `@retry(max_retries=3, delay=0)` 的函数前 2 次抛异常、第 3 次成功 → 最终成功，调用 3 次
  - 装饰 `@retry(max_retries=3, delay=0)` 的函数 3 次全失败 → raise LLMError，调用 3 次
  - 装饰 `@retry(max_retries=2, delay=0)` → 失败时调用 2 次
- Run: `cd /Users/melody/code/ai-workshop/backend && ../.venv/bin/python manage.py test apps.intelligence.tests.test_retry`
- Expected: FAIL（模块不存在）

**步骤 2：实现 retry.py**
- 修改点：`backend/apps/intelligence/services/retry.py`
- 实现：
  - `class LLMError(Exception): pass`
  - `def retry(max_retries=3, delay=30):` 装饰器，用 `time.sleep(delay)` 间隔，耗尽 raise `LLMError`
  - 每次重试 `logger.warning` 记录

**步骤 3：运行验证**
- Run: `cd /Users/melody/code/ai-workshop/backend && ../.venv/bin/python manage.py test apps.intelligence.tests.test_retry`
- Expected: PASS

**步骤 4：提交**
- Commit message: `feat: 实现 LLM 通用重试机制（2-3次/30s间隔/耗尽raise LLMError）`
- 审计信息：
  - repo: `root`
    branch: `004-llm-intel-pipeline`
    commit: `<TBD>`
    pr: `<TBD>`
    changed_files:
      - `backend/apps/intelligence/services/retry.py`
      - `backend/apps/intelligence/tests/test_retry.py`

---

### Task T5: 实现 LLM 降噪服务

- [ ] **状态**：未开始

**代码仓范围：**
- 根项目：`backend/apps/intelligence/services/`
- 子仓：无

**文件：**
- 创建：`backend/apps/intelligence/services/llm_service.py`（含 denoise 函数）
- 测试：`backend/apps/intelligence/tests/test_llm_service.py`

**验收点：**
- `denoise(bs_clean_md: str) -> str` 调用 LLM 文本补全，输入 BS 去噪 MD，输出 LLM 降噪 MD
- 使用 `prompts/denoise.md` 模板
- 被 `@retry` 装饰，失败重试
- 空/极短输入不调用 LLM，直接返回原文
- 测试通过（mock LLM API）

**步骤 1：写失败测试**
- 修改点：`backend/apps/intelligence/tests/test_llm_service.py`
- 测试内容：
  - `denoise("有噪音的MD")` mock LLM 返回 "降噪后MD" → 返回 "降噪后MD"
  - `denoise("")` → 返回 ""，不调用 LLM
  - `denoise("极短")` → 返回 "极短"（长度<阈值不调用 LLM）
  - mock LLM 3 次失败 → raise LLMError
- Run: `cd /Users/melody/code/ai-workshop/backend && ../.venv/bin/python manage.py test apps.intelligence.tests.test_llm_service`
- Expected: FAIL（模块不存在）

**步骤 2：实现 llm_service.py 的 denoise 函数**
- 修改点：`backend/apps/intelligence/services/llm_service.py`
- 实现：
  - `from .llm_client import get_openai_client`
  - `from .prompt_loader import load_prompt`
  - `from .retry import retry, LLMError`
  - `@retry(max_retries=3, delay=30)` 装饰 `denoise(bs_clean_md)`
  - 空输入或 <10 字符直接返回
  - 调用 `client.chat.completions.create()` 普通文本补全

**步骤 3：运行验证**
- Run: `cd /Users/melody/code/ai-workshop/backend && ../.venv/bin/python manage.py test apps.intelligence.tests.test_llm_service`
- Expected: PASS

**步骤 4：提交**
- Commit message: `feat: 实现 LLM 降噪服务（denoise + 重试 + 空输入保护）`
- 审计信息：
  - repo: `root`
    branch: `004-llm-intel-pipeline`
    commit: `<TBD>`
    pr: `<TBD>`
    changed_files:
      - `backend/apps/intelligence/services/llm_service.py`
      - `backend/apps/intelligence/tests/test_llm_service.py`

---

### Task T6: 实现 diff_service（文本 diff + 截断）

- [ ] **状态**：未开始

**代码仓范围：**
- 根项目：`backend/apps/intelligence/services/`
- 子仓：无

**文件：**
- 创建：`backend/apps/intelligence/services/diff_service.py`
- 测试：`backend/apps/intelligence/tests/test_diff_service.py`

**验收点：**
- `text_diff(new_md: str, prev_md: str) -> str` 用 difflib.unified_diff 生成 diff
- 内容完全相同 → 返回空字符串
- diff 输出超过 8000 字符 → 截断（保留头部 4000 + 尾部 4000 + 中间省略标记）
- 测试通过

**步骤 1：写失败测试**
- 修改点：`backend/apps/intelligence/tests/test_diff_service.py`
- 测试内容：
  - `text_diff("a\nb", "a\nb")` → 返回 ""
  - `text_diff("a\nb\nc", "a\nb")` → 返回含 "+c" 的非空 diff
  - `text_diff(long_new, long_prev)` 生成 >8000 字符 → 返回 <=8000 字符，含截断标记
  - `text_diff("", "")` → 返回 ""
- Run: `cd /Users/melody/code/ai-workshop/backend && ../.venv/bin/python manage.py test apps.intelligence.tests.test_diff_service`
- Expected: FAIL（模块不存在）

**步骤 2：实现 diff_service.py**
- 修改点：`backend/apps/intelligence/services/diff_service.py`
- 实现：
  - `import difflib`
  - `DIFF_TRUNCATE_THRESHOLD = 8000`
  - `text_diff(new_md, prev_md)` → `difflib.unified_diff`，join 为字符串
  - `_truncate_diff(diff_text)` → 超 8000 字符截断头尾

**步骤 3：运行验证**
- Run: `cd /Users/melody/code/ai-workshop/backend && ../.venv/bin/python manage.py test apps.intelligence.tests.test_diff_service`
- Expected: PASS

**步骤 4：提交**
- Commit message: `feat: 实现 diff_service（difflib 文本 diff + 8000 字符截断）`
- 审计信息：
  - repo: `root`
    branch: `004-llm-intel-pipeline`
    commit: `<TBD>`
    pr: `<TBD>`
    changed_files:
      - `backend/apps/intelligence/services/diff_service.py`
      - `backend/apps/intelligence/tests/test_diff_service.py`

---

### Task T7: 实现 LLM diff 判断服务

- [ ] **状态**：未开始

**代码仓范围：**
- 根项目：`backend/apps/intelligence/services/`
- 子仓：无

**文件：**
- 修改：`backend/apps/intelligence/services/llm_service.py`（追加 judge_diff 函数）
- 修改：`backend/apps/intelligence/tests/test_llm_service.py`（追加 judge_diff 测试）

**验收点：**
- `judge_diff(diff_text: str, self_product_doc: str) -> dict` 返回 `{"has_meaningful_change": bool, "reason": str}`
- 使用 `prompts/diff_judge.md` 模板
- 被 `@retry` 装饰
- LLM 返回的 JSON 被正确解析
- diff_text 为空 → 直接返回 `{"has_meaningful_change": False, "reason": "无变化"}`
- 测试通过（mock LLM API）

**步骤 1：写失败测试**
- 修改点：`backend/apps/intelligence/tests/test_llm_service.py` 追加测试类
- 测试内容：
  - `judge_diff("有变化", "产品文档")` mock LLM 返回 `{"has_meaningful_change": true, "reason": "功能更新"}` → 返回 dict
  - `judge_diff("", "产品文档")` → 返回 `{"has_meaningful_change": False, "reason": "无变化"}`，不调用 LLM
  - mock LLM 返回非 JSON → 重试后 raise LLMError
- Run: `cd /Users/melody/code/ai-workshop/backend && ../.venv/bin/python manage.py test apps.intelligence.tests.test_llm_service`
- Expected: FAIL（judge_diff 未实现）

**步骤 2：实现 judge_diff 函数**
- 修改点：`backend/apps/intelligence/services/llm_service.py` 追加 `judge_diff`
- 实现：
  - `@retry(max_retries=3, delay=30)` 装饰
  - 空 diff 直接返回 `{"has_meaningful_change": False, "reason": "无变化"}`
  - 调用 LLM 文本补全，解析返回 JSON

**步骤 3：运行验证**
- Run: `cd /Users/melody/code/ai-workshop/backend && ../.venv/bin/python manage.py test apps.intelligence.tests.test_llm_service`
- Expected: PASS

**步骤 4：提交**
- Commit message: `feat: 实现 LLM diff 判断服务（judge_diff + JSON 解析 + 重试）`
- 审计信息：
  - repo: `root`
    branch: `004-llm-intel-pipeline`
    commit: `<TBD>`
    pr: `<TBD>`
    changed_files:
      - `backend/apps/intelligence/services/llm_service.py`
      - `backend/apps/intelligence/tests/test_llm_service.py`

---

### Task T8: 实现 LLM 情报生成服务（instructor + Pydantic）

- [ ] **状态**：未开始

**代码仓范围：**
- 根项目：`backend/apps/intelligence/services/`
- 子仓：无

**文件：**
- 修改：`backend/apps/intelligence/services/llm_service.py`（追加 generate_intel 函数 + Negative Few-Shot 查询）
- 修改：`backend/apps/intelligence/tests/test_llm_service.py`（追加 generate_intel 测试）

**验收点：**
- `generate_intel(diff_text: str, self_product_doc: str, few_shots: list) -> IntelResult` 返回 Pydantic 实例
- 使用 `prompts/intel_system.md` + `prompts/intel_user.md` 模板
- 使用 `instructor` + `IntelResult` Pydantic schema 约束输出
- 被 `@retry` 装饰
- `get_negative_few_shots(project_id, limit=5)` 查询最近 5 条 `user_feedback=-1` 的 IntelligenceFeed
- 测试通过（mock LLM API）

**步骤 1：写失败测试**
- 修改点：`backend/apps/intelligence/tests/test_llm_service.py` 追加测试类
- 测试内容：
  - `generate_intel("diff", "doc", [])` mock instructor 返回 IntelResult → 返回 IntelResult 实例，4 字段非空
  - `get_negative_few_shots(project_id)` 创建 3 条 `user_feedback=-1` → 返回 3 条
  - `get_negative_few_shots` 无记录 → 返回空列表
  - `get_negative_few_shots` 有 7 条 → 返回最近 5 条
- Run: `cd /Users/melody/code/ai-workshop/backend && ../.venv/bin/python manage.py test apps.intelligence.tests.test_llm_service`
- Expected: FAIL（generate_intel / get_negative_few_shots 未实现）

**步骤 2：实现 generate_intel 与 get_negative_few_shots**
- 修改点：`backend/apps/intelligence/services/llm_service.py` 追加
- 实现：
  - `@retry(max_retries=3, delay=30)` 装饰 `generate_intel`
  - `get_instructor_client()` + `client.chat.completions.create(response_model=IntelResult)`
  - `get_negative_few_shots(project_id, limit=5)` → `IntelligenceFeed.objects.filter(project_id=..., user_feedback=-1).order_by("-published_at")[:5]`
  - Few-Shot 格式化为"### 反面案例 N\n- 摘要：{change_summary}\n- 用户评语：{user_comment}"

**步骤 3：运行验证**
- Run: `cd /Users/melody/code/ai-workshop/backend && ../.venv/bin/python manage.py test apps.intelligence.tests.test_llm_service`
- Expected: PASS

**步骤 4：提交**
- Commit message: `feat: 实现 LLM 情报生成服务（instructor + Pydantic + Negative Few-Shot）`
- 审计信息：
  - repo: `root`
    branch: `004-llm-intel-pipeline`
    commit: `<TBD>`
    pr: `<TBD>`
    changed_files:
      - `backend/apps/intelligence/services/llm_service.py`
      - `backend/apps/intelligence/tests/test_llm_service.py`

---

### Task T9: 实现 report_service（Jinja2 HTML/MD 报告渲染）

- [ ] **状态**：未开始

**代码仓范围：**
- 根项目：`backend/apps/intelligence/services/`、`backend/templates/reports/`
- 子仓：无

**文件：**
- 创建：`backend/apps/intelligence/services/report_service.py`
- 创建：`backend/templates/reports/report.html.j2`
- 创建：`backend/templates/reports/report.md.j2`
- 测试：`backend/apps/intelligence/tests/test_report_service.py`

**验收点：**
- `render_html(feed: IntelligenceFeed) -> str` 渲染 HTML 报告，返回文件绝对路径
- `render_md(feed: IntelligenceFeed) -> str` 渲染 MD 表格，返回文件绝对路径
- 落盘路径：`SNAPSHOT_STORAGE_DIR/reports/{project_id}/{date}/{feed_id}.html|md`
- HTML 可浏览器打开，MD 表格格式正确
- NO_CHANGE/ERROR_CRAWL feed 不渲染（返回空字符串）
- 测试通过

**步骤 1：写失败测试**
- 修改点：`backend/apps/intelligence/tests/test_report_service.py`
- 测试内容：
  - 创建 CHANGED feed（4 字段非空） → `render_html` 返回路径，文件存在，含 4 字段内容
  - `render_md` 返回路径，文件存在，含 MD 表格格式
  - NO_CHANGE feed → `render_html` / `render_md` 返回 ""
  - ERROR_CRAWL feed → 同上返回 ""
- Run: `cd /Users/melody/code/ai-workshop/backend && ../.venv/bin/python manage.py test apps.intelligence.tests.test_report_service`
- Expected: FAIL（模块不存在）

**步骤 2：创建 Jinja2 模板**
- 创建 `backend/templates/reports/report.html.j2`：HTML 页面，展示 4 字段（标题/项目名/时间 + 变化摘要/战略意图/行动建议/证据 diff）
- 创建 `backend/templates/reports/report.md.j2`：MD 表格，4 字段为表格行

**步骤 3：实现 report_service.py**
- 修改点：`backend/apps/intelligence/services/report_service.py`
- 实现：
  - `from jinja2 import Environment, FileSystemLoader`
  - `render_html(feed)` / `render_md(feed)` → 只对 CHANGED feed 渲染
  - 落盘到 `SNAPSHOT_STORAGE_DIR/reports/{project_id}/{date}/{feed_id}.html|md`

**步骤 4：运行验证**
- Run: `cd /Users/melody/code/ai-workshop/backend && ../.venv/bin/python manage.py test apps.intelligence.tests.test_report_service`
- Expected: PASS

**步骤 5：提交**
- Commit message: `feat: 实现 report_service（Jinja2 HTML/MD 报告渲染 + 落盘）`
- 审计信息：
  - repo: `root`
    branch: `004-llm-intel-pipeline`
    commit: `<TBD>`
    pr: `<TBD>`
    changed_files:
      - `backend/apps/intelligence/services/report_service.py`
      - `backend/templates/reports/report.html.j2`
      - `backend/templates/reports/report.md.j2`
      - `backend/apps/intelligence/tests/test_report_service.py`

---

### Task T10: 实现 file_storage 覆盖写入支持

- [ ] **状态**：未开始

**代码仓范围：**
- 根项目：`backend/apps/intelligence/services/`
- 子仓：无

**文件：**
- 修改：`backend/apps/intelligence/services/file_storage.py`（新增 save_llm_clean_md 函数）
- 修改：`backend/apps/intelligence/tests/test_scheduler_service.py` 或新建 `test_file_storage.py`

**验收点：**
- `save_llm_clean_md(project_id, url, content, fetch_time) -> str` 将 LLM 降噪 MD 保存到文件，返回路径
- 路径格式与 `save_clean_md` 一致（同目录，文件名加 `llm_` 前缀区分）
- 空内容返回空字符串
- 测试通过

**步骤 1：写失败测试**
- 修改点：`backend/apps/intelligence/tests/test_file_storage.py`（新建）
- 测试内容：
  - `save_llm_clean_md(1, "https://example.com", "LLM降噪MD", now)` → 返回非空路径，文件存在，内容正确
  - `save_llm_clean_md(1, "https://example.com", "", now)` → 返回 ""
- Run: `cd /Users/melody/code/ai-workshop/backend && ../.venv/bin/python manage.py test apps.intelligence.tests.test_file_storage`
- Expected: FAIL（函数不存在）

**步骤 2：实现 save_llm_clean_md**
- 修改点：`backend/apps/intelligence/services/file_storage.py` 追加函数
- 实现：复用 `_save_content`，ext 为 "md"，文件名加 `llm_` 前缀

**步骤 3：运行验证**
- Run: `cd /Users/melody/code/ai-workshop/backend && ../.venv/bin/python manage.py test apps.intelligence.tests.test_file_storage`
- Expected: PASS

**步骤 4：提交**
- Commit message: `feat: 新增 save_llm_clean_md（LLM 降噪 MD 落盘）`
- 审计信息：
  - repo: `root`
    branch: `004-llm-intel-pipeline`
    commit: `<TBD>`
    pr: `<TBD>`
    changed_files:
      - `backend/apps/intelligence/services/file_storage.py`
      - `backend/apps/intelligence/tests/test_file_storage.py`

---

### Task T11: scheduler_service 集成 LLM 全链路

- [ ] **状态**：未开始

**代码仓范围：**
- 根项目：`backend/apps/intelligence/services/scheduler_service.py`
- 子仓：无

**文件：**
- 修改：`backend/apps/intelligence/services/scheduler_service.py`（扩展 run_scan 串接 LLM 链路）
- 修改：`backend/apps/intelligence/tests/test_scheduler_service.py`（更新测试 + 新增 LLM 链路测试）

**验收点：**
- run_scan() 在 DataSnapshot 入库后串接：LLM 降噪 → 覆盖 clean_md_path → diff 熔断 → 情报生成 → 入库 + 报告落盘
- 首次爬取（无上一条快照）→ 跳过 diff，直接情报生成
- 旧格式快照兼容（检测上一条是否 pre-LLM）→ 跳过 diff
- 采集失败 → 写 IntelligenceFeed(ERROR_CRAWL)，不进入 LLM 链路
- LLM 失败（重试耗尽）→ 写 IntelligenceFeed(ERROR_CRAWL)，错误信息存 change_summary
- 单 URL 异常不中断其他 URL
- 原有测试（test_scheduler_service.py）需更新以适配新逻辑
- 新测试覆盖：全链路 CHANGED、文本 diff 空熔断 NO_CHANGE、LLM 判断无意义 NO_CHANGE、首次爬取 CHANGED、LLM 失败 ERROR_CRAWL、单 URL 异常不中断

**步骤 1：更新现有失败测试**
- 修改点：`backend/apps/intelligence/tests/test_scheduler_service.py`
- 修改：
  - `test_run_scan_does_not_write_intelligence_feed` → 改为 `test_run_scan_writes_intelligence_feed`（验证现在会写 IntelligenceFeed）
  - 所有 mock `fetch_and_clean` 的测试需追加 mock `llm_service.denoise` / `llm_service.judge_diff` / `llm_service.generate_intel` / `report_service.render_html` / `report_service.render_md`
- Run: `cd /Users/melody/code/ai-workshop/backend && ../.venv/bin/python manage.py test apps.intelligence.tests.test_scheduler_service`
- Expected: FAIL（scheduler_service 未扩展）

**步骤 2：扩展 scheduler_service.py**
- 修改点：`backend/apps/intelligence/services/scheduler_service.py`
- 实现逻辑（每个 URL 循环内，DataSnapshot 入库后）：
  ```
  1. 采集失败（raw_md/clean_md 为空）→ 写 IntelligenceFeed(ERROR_CRAWL, change_summary="采集失败")，continue
  2. LLM 降噪：llm_service.denoise(bs_clean_md) → llm_clean_md
     - 失败（LLMError）→ 写 IntelligenceFeed(ERROR_CRAWL, change_summary=str(error))，continue
  3. LLM 降噪 MD 覆盖写入文件：file_storage.save_llm_clean_md() → 更新 DataSnapshot.clean_md_path
  4. 获取上一条快照（排除当前条）
  5. 首次爬取（无上一条）→ 跳过 diff，直接步骤 8
  6. 旧格式兼容检测（上一条 clean_md_path 不含 llm_ 前缀 → pre-LLM）→ 跳过 diff，直接步骤 8
  7. 文本 diff：diff_service.text_diff(当前llm_md, 上一条llm_md)
     - diff 为空 → 写 IntelligenceFeed(NO_CHANGE)，continue
  8. LLM diff 判断：llm_service.judge_diff(diff_text, self_product_doc)
     - 失败 → 写 ERROR_CRAWL，continue
     - has_meaningful_change=False → 写 NO_CHANGE，continue
  9. 情报生成：llm_service.generate_intel(diff_text, self_product_doc, few_shots)
     - 失败 → 写 ERROR_CRAWL，continue
  10. 写 IntelligenceFeed(CHANGED, 4字段)
  11. 报告渲染：report_service.render_html(feed) + render_md(feed)
  12. 更新 feed.html_report_path / md_table_path
  ```
- 每个步骤用 try-except 包裹，异常写 ERROR_CRAWL 不中断

**步骤 3：运行验证**
- Run: `cd /Users/melody/code/ai-workshop/backend && ../.venv/bin/python manage.py test apps.intelligence.tests.test_scheduler_service`
- Expected: PASS

**步骤 4：提交**
- Commit message: `feat: scheduler_service 集成 LLM 全链路（降噪→diff熔断→情报生成→入库+报告）`
- 审计信息：
  - repo: `root`
    branch: `004-llm-intel-pipeline`
    commit: `<TBD>`
    pr: `<TBD>`
    changed_files:
      - `backend/apps/intelligence/services/scheduler_service.py`
      - `backend/apps/intelligence/tests/test_scheduler_service.py`

---

### Task T12: 端到端集成测试

- [ ] **状态**：未开始

**代码仓范围：**
- 根项目：`backend/apps/intelligence/tests/`
- 子仓：无

**文件：**
- 创建：`backend/apps/intelligence/tests/test_llm_pipeline_e2e.py`

**验收点：**
- 场景 S-001（有变化全链路）：mock 全链路 → DataSnapshot.clean_md_path 指向 LLM MD + IntelligenceFeed(CHANGED, 4字段非空) + 报告文件落盘
- 场景 S-002（无变化熔断）：mock 文本 diff 为空 → IntelligenceFeed(NO_CHANGE) + 零 LLM diff 调用
- 场景 S-002（LLM 判断无意义）：mock judge_diff 返回 False → NO_CHANGE
- 场景 S-003（首次爬取）：无上一条快照 → 跳过 diff + 直接情报生成 + CHANGED
- AC-013（单 URL 异常不中断）：第 1 个 URL LLM 失败、第 2 个成功 → 第 1 个 ERROR_CRAWL、第 2 个 CHANGED
- AC-017（旧格式兼容）：上一条 clean_md_path 无 llm_ 前缀 → 跳过 diff

**步骤 1：写端到端测试**
- 修改点：`backend/apps/intelligence/tests/test_llm_pipeline_e2e.py`
- 测试内容：mock crawler_service + llm_service + report_service，验证完整 run_scan() 流程
- Run: `cd /Users/melody/code/ai-workshop/backend && ../.venv/bin/python manage.py test apps.intelligence.tests.test_llm_pipeline_e2e`
- Expected: FAIL（scheduler_service 集成已完成但测试可能需调整 mock）

**步骤 2：调试测试通过**
- 修改点：根据失败信号调整 mock 或实现
- Run: `cd /Users/melody/code/ai-workshop/backend && ../.venv/bin/python manage.py test apps.intelligence.tests.test_llm_pipeline_e2e`
- Expected: PASS

**步骤 3：全量测试回归**
- Run: `cd /Users/melody/code/ai-workshop/backend && ../.venv/bin/python manage.py test apps.intelligence`
- Expected: ALL PASS

**步骤 4：提交**
- Commit message: `test: 端到端集成测试（S-001/S-002/S-003 + 异常不中断 + 旧格式兼容）`
- 审计信息：
  - repo: `root`
    branch: `004-llm-intel-pipeline`
    commit: `<TBD>`
    pr: `<TBD>`
    changed_files:
      - `backend/apps/intelligence/tests/test_llm_pipeline_e2e.py`

---

### Task T13: .env 文件创建与文档更新

- [ ] **状态**：未开始

**代码仓范围：**
- 根项目：`backend/.env`、`backend/.gitignore`
- 子仓：无

**文件：**
- 创建：`backend/.env`（真实 LLM 配置，不入 git）
- 修改：`backend/.gitignore`（确保 .env 被忽略，.env.example 不忽略）
- 修改：`CLAUDE.md`（更新仓库现状，标注 LLM 链路已实现）

**验收点：**
- `.env` 文件存在且含 LLM 配置
- `git status` 不显示 `.env`
- `git status` 显示 `.env.example`
- CLAUDE.md 更新标注 Spec 004 已完成

**步骤 1：创建 .env**
- 创建 `backend/.env`，从 `.env.example` 复制并填入真实配置（需用户提供 api_key）
- 修改 `backend/.gitignore` 追加 `.env`

**步骤 2：更新 CLAUDE.md**
- 修改点：`CLAUDE.md` 仓库现状段落，标注 LLM 链路已实现
- 注意：仅更新事实状态，不改动技术栈描述

**步骤 3：验证**
- Run: `cd /Users/melody/code/ai-workshop && git status backend/.env`
- Expected: 不显示（被 gitignore）
- Run: `cd /Users/melody/code/ai-workshop/backend && ../.venv/bin/python manage.py check`
- Expected: PASS

**步骤 4：提交**
- Commit message: `chore: 创建 .env 配置 + 更新 .gitignore 与 CLAUDE.md`
- 审计信息：
  - repo: `root`
    branch: `004-llm-intel-pipeline`
    commit: `<TBD>`
    pr: `<TBD>`
    changed_files:
      - `backend/.gitignore`
      - `CLAUDE.md`

---

## Merge-back 待办清单（仅记录，不在本阶段执行）

- MB-001：I2 完成后，更新 `project/components/intelligence-scheduler.md` 的 service contract（Invariant #5 修订为"本模块串接 LLM 链路后写 IntelligenceFeed"）
- MB-002：I2 完成后，更新 `project/components/intelligence-models.md` 的 data contract（clean_md_path 语义变更：BS→LLM）
- MB-003：I2 完成后，新建 `project/components/llm-service.md` 模块页（3 次独立 LLM 调用 + 重试机制）
- MB-004：I2 完成后，新建 `project/components/report-service.md` 模块页（Jinja2 渲染）
- MB-005：V-010 验证后，补充 `project/nfr.md` 的 LLM 延迟/成本 NFR 基线
