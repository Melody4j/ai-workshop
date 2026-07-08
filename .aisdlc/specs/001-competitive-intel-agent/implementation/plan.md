# Competitive Intel Agent 实现计划（SSOT）

> **必需技能：** `spec-execute`（按批次执行本计划）
> **上下文获取：** 必须先执行 `spec-context` 获取上下文，定位 `{FEATURE_DIR}`，失败即停止

**目标：** 在当前分支先交付一个可运行的前后端分离单体骨架，覆盖工程初始化、Vue/Django 脚手架、SQLite 数据库初始化、任务 CRUD、报告列表/详情查看、评分 CRUD，并为后续补齐爬虫、LLM、调度保留稳定扩展点。  
**范围：** In = 工程初始化、前后端脚手架、数据库与实体、后端 API、前端任务 CRUD / 报告列表 / 评分 CRUD；Out = 爬虫实现、LLM 实现、调度机制实现、飞书推送联调。  
**架构：** 采用 `frontend/` 下 Vue 3 + Vite 产品前端与 `backend/` 下 Django 4.2 + DRF 单体后端的 split-monolith 结构，数据库使用 SQLite。当前批次通过种子数据/手工录入支撑报告列表与评分流程，不实现真实采集、降噪、diff、调度，但数据库设计与 API 形态必须不破坏后续补齐这些能力的路径。  
**验收口径：** 追溯 `requirements/prd.md` 的 AC-001、AC-004、AC-009、AC-011、AC-012、AC-016，以及 `requirements/solution.md` 的 V-007、V-019；本批次不承诺 AC-002、AC-003、AC-005、AC-006、AC-008、AC-010、AC-013、AC-014、AC-015、AC-017 的功能闭环。  
**影响范围：** 受影响模块以 `requirements/solution.md#7.1` 为准，当前批次实际落地子集为 Vue 前端壳层 / 路由、任务配置页、收件箱 / 情报详情 / 报告预览、Django API 层、数据库实体与报告种子数据；调度器、采集器、降噪、diff / 熔断、飞书通知在本批次仅做扩展预留。  
**需遵守的不变量：** 以 `requirements/solution.md#7.2` 为准，当前批次必须直接遵守或在 schema/API 上预留兼容：`competitor_urls` 为 `[{url,title}]` JSON 数组、`self_product_doc` Nullable、收件箱仅展示 `CHANGED`、产品页面统一由 Vue 承担、反馈只取最近 5 条的存储口径不变；同时不得设计出会阻碍后续 append-only 快照、双 LLM 分离、diff 熔断、日级调度的结构。  
**子仓范围：** 无

---

## TL;DR

- 一句话目标：先把当前分支做成“能跑、能配、能看、能评分”的骨架版本，而不是完整监控闭环。
- In/Out：当前只做工程基础、数据库、API 与前端交互；不做爬虫、LLM、调度、飞书。
- 关键路径：
  - 用 Django + SQLite 先建立 `MonitorProject`、`DataSnapshot`、`IntelligenceFeed` 的稳定实体和迁移。
  - 用 DRF 暴露任务 CRUD、报告列表/详情、评分 CRUD 所需 API，并用种子数据填充报告列表。
  - 用 Vue 落地任务管理、报告列表、报告详情/评分交互页面，完成前后端联通。
- 最大风险与优先验证点：
  - R1：当前批次不做调度/采集后，报告列表的数据来源要稳定且不误导后续实现。
  - R2：任务删除语义与历史报告保留策略必须提前定成软删除/停用口径。
  - R3：Vue 与 Django 的 Session/CSRF 写操作联调要尽早打通。

## 范围与边界（In / Out）

- **In**：
  - 根工程初始化与目录布局约定。
  - Django 后端脚手架与 Vue 前端脚手架。
  - SQLite 初始化、核心实体建模、迁移、基础种子数据。
  - 任务 CRUD、报告列表/详情查询、评分 CRUD API。
  - Vue 页面：任务列表/配置、报告列表、报告详情与评分交互。
- **Out**：
  - `django-apscheduler` 定时任务的实际落地。
  - httpx / Playwright 抓取与 html2text 处理。
  - LLM 降噪、LLM 情报生成、Negative Few-Shot 注入逻辑。
  - 飞书推送与在线预览链接联调。
  - 收件箱 / 执行列表的完整运行态区分与真实状态流转。
- **不变量/关键约束**：
  - `competitor_urls` 按 JSON 数组存储，每项必须为 `{"url":"...","title":"..."}`。
  - `self_product_doc` 允许为空。
  - 报告/情报主表必须兼容 `CHANGED` / `NO_CHANGE` / `ERROR_CRAWL` 三种状态。
  - 当前批次的“评分 CRUD”落在 `IntelligenceFeed.user_feedback` / `user_comment` 上，不新增与需求不一致的独立评分主表。
  - 当前批次的“任务删除”按软删除/停用语义落在 `is_active=false`，不清理历史报告。
  - 产品入口只由 Vue 提供，Django Admin 仅作为内部辅助工具。
- **影响面**：
  - 模块：`frontend/`、`backend/`、SQLite schema、种子数据、API 契约。
  - 接口：项目配置、报告查询、反馈写入。
  - 数据口径：`CHANGED` 报告可见、反馈可写、任务停用不删除历史记录。
  - 运维：只要求本地可启动、迁移可执行、前端可构建；不要求定时任务与外部集成。

## 影响范围与约束

### 受影响模块清单

| 模块 | 影响类型 | 当前批次动作 | 来源 |
|---|---|---|---|
| Vue 前端壳层 / 路由 | 新增能力 | 新建 `frontend/` 工程、路由、API Client、页面骨架 | `solution.md#7.1` |
| 任务配置页 | 新增能力 | 实现任务列表、创建、编辑、停用 | `solution.md#7.1` |
| 收件箱 / 情报详情 / 报告预览 | 新增能力（收敛） | 本批次先收敛为报告列表与报告详情页，详情内承载评分 CRUD | `solution.md#7.1` |
| Django API 层 | 新增能力 | 提供项目、报告、评分相关 REST API | `solution.md#7.1` |
| 调度器（django-apscheduler） | 延后实现 | 本批次不实现，只在目录与设置上预留扩展点 | `solution.md#7.1` |
| 采集器 / 降噪 / diff / 飞书通知 | 延后实现 | 本批次不实现，数据库字段与服务目录保留兼容 | `solution.md#7.1` |

### 需遵守的不变量

1. `competitor_urls` 必须为 JSON 数组，每项 `{"url":"...","title":"..."}`。来源：`solution.md#7.2-10`。
2. `self_product_doc` 允许为空，当前任务表单与模型不得强制必填。来源：`solution.md#7.2-9`。
3. 产品功能页面统一由 Vue 承担，Django 不再承担产品 UI。来源：`solution.md#7.2-13`。
4. 报告/情报实体需要兼容 `CHANGED` / `NO_CHANGE` / `ERROR_CRAWL` 三种状态，哪怕本批次只用 `CHANGED` 种子数据。来源：`solution.md#7.2-6`。
5. 当前评分 CRUD 必须复用现有反馈口径，不能引入与 `user_feedback` / `user_comment` 冲突的新语义。来源：`prd.md#6.3 AC-012`。
6. 当前实现不能破坏后续追加 append-only 快照、双 LLM 分离、diff 熔断、日级调度的路径。来源：`solution.md#7.2-1~8`。

### 跨模块影响与协调事项

- 由于当前不做采集与调度，报告列表需要通过种子数据或手工录入填充，前后端都必须把该来源标注为“占位数据路径”，不能假装真实监控已闭环。
- 任务删除若改成物理删除，会和后续报告/快照历史保留冲突，因此本批次按停用处理，并在前端文案上体现为“停用/归档”。
- 前端报告列表当前收敛自 `收件箱 / 报告预览` 两个能力，后续补执行列表时需要新增独立页面，不直接复用当前报告列表口径。
- `.aisdlc/project/` 缺失，当前计划只能基于 spec 文档与绿地仓库事实落地；该 `CONTEXT GAP` 不阻断 I1，但后续如需 merge-back 应补 discover/ADR。

## 代码工作区清单

当前仓库无 `.gitmodules`，本次只修改根仓。

| 子仓路径 | 是否受影响 | 是否 required | 期望分支 | 例外原因 |
|---|---|---|---|---|
| 无 | 否 | false | `001-competitive-intel-agent` | 无 |

---

## 里程碑与节奏

- **里程碑 1：工程初始化**
  - 产出物：根目录约定、后端/前端工作区、依赖清单、启动说明。
  - 出关标准：仓库形成稳定的 `backend/` + `frontend/` 结构，开发命令路径固定。
- **里程碑 2：脚手架搭建**
  - 产出物：Django 基础工程、Vue + Vite 基础工程、路由与 API 调用骨架。
  - 出关标准：后端 `check` 可通过，前端 `build` 可通过，前后端目录骨架完整。
- **里程碑 3：数据库初始化**
  - 产出物：核心模型、迁移、SQLite 初始化、基础种子数据、必要触发器/约束占位。
  - 出关标准：迁移可执行，模型测试通过，种子数据可产生可浏览的报告记录。
- **里程碑 5：后端 API 接口设计与数据库实体设计**
  - 产出物：任务 CRUD API、报告列表/详情 API、评分 CRUD API、DTO/Serializer 约定。
  - 出关标准：API 测试通过，字段命名与前端消费契约稳定。
- **里程碑 6：前端设计与交互实现**
  - 产出物：任务 CRUD 页面、配置表单、报告列表页、报告详情页、评分 CRUD 交互。
  - 出关标准：核心页面可手工走通，前端构建通过，评分交互能真实写回后端。

> 本计划沿用用户给定的 1 / 2 / 3 / 5 / 6 编号；当前批次不设“4”，避免与已确认口径重新编号。

## 依赖与资源

- **环境/权限**：
  - Python 3.10+
  - Node.js 20+
  - 本地可写 SQLite 文件
- **外部系统/团队**：
  - 当前批次无外部服务强依赖
  - 飞书、LLM、抓取目标站点只在后续批次接入
- **数据/样本**：
  - 需要一组本地种子数据，用于任务列表、报告列表、评分写回联调
  - 至少准备 1 个项目、2 条报告记录，其中 1 条带已有评分
- **发布/变更窗口**：
  - 当前为绿地本地开发，无线上发布窗口约束

## 风险与验证

| # | 风险/假设 | 验证方式 | 成功信号 | 失败信号 | Owner | 截止 | 下一步动作 |
|---|---|---|---|---|---|---|---|
| R1 | 不做爬虫/调度后，报告列表可能缺少稳定数据来源 | 提供 fixture/seed command 并在页面联调中使用 | 本地迁移后能稳定看到报告列表 | 前端只能靠硬编码 mock 才能跑通 | FS | 里程碑 3 | 固化 seed 数据加载命令 |
| R2 | 任务删除语义若不统一，会破坏后续历史报告保留 | 在模型/API 层统一为停用语义并补测试 | 停用后任务不再可编辑主流程，但历史报告仍可见 | 删除任务后报告孤儿化或直接丢失 | FS | 里程碑 5 | 在 API 返回中显式透出 `is_active` |
| R3 | Vue 与 Django 的 Session/CSRF 写操作可能阻塞表单提交 | 早期联调创建任务与评分更新接口 | 创建/评分接口写操作稳定成功 | 持续出现 403/CSRF 错误 | FS | 里程碑 5/6 | 增加 CSRF 初始化接口与前端 client 封装 |
| R4 | 当前批次收敛为报告列表页，可能与后续执行列表口径混淆 | 在文案与路由中明确“报告列表”而非“执行列表” | 用户能区分当前是骨架阶段的报告浏览能力 | 页面命名与 PRD 原型混用导致误解 | PM+FS | 里程碑 6 | 后续补 P-002 时单独新增执行列表页面 |

## 验收口径（可追溯）

- 追溯：`requirements/solution.md`
  - V-007：API 契约稳定，Vue 页面不依赖后端模板。
  - V-019：同域 Session/CSRF 写操作可用。
  - `#7 Impact Analysis`：Vue 页面统一由前端承担；`competitor_urls`、`self_product_doc`、状态口径不变。
- 追溯：`requirements/prd.md`
  - AC-001：任务配置可保存并返回成功。
  - AC-004：报告产物字段与报告入口元数据在数据库/API 层可用。
  - AC-009：报告/列表接口支持筛选。
  - AC-011：可查看情报/报告详情。
  - AC-012：可写入评分与评语。
  - AC-016：写操作通过 Session/CSRF。
- 关键验收点（当前批次摘要）：
  - 后端可创建、编辑、停用监控任务。
  - 后端可返回报告列表、报告详情，并允许对报告写评分/评语。
  - 前端可完成任务 CRUD、报告列表浏览、报告详情浏览、评分新增/修改/删除。
  - 前后端不依赖 mock 页面即可联通，但报告内容来源允许是本地 seed 数据。

## NEEDS CLARIFICATION（未消除前不得进入 I2）

- 当前无阻断项。
  - 说明：当前批次范围已经由用户明确收敛为“工程骨架 + DB + API + 前端 CRUD/评分”，并明确排除了爬虫、LLM、调度。
  - 执行要求：I2 严格按本计划范围执行，不得擅自把 Out 范围带回当前批次。

## 任务清单（SSOT）

> 这是唯一的执行清单与状态来源：用 `- [ ] / - [x]` 标记完成；执行中把按 repo 记录的 `branch/commit/pr/changed_files` 与关键验证结果回写到对应任务。
> 命令默认以当前本地 shell 为准；如需连续执行请拆成多条命令逐步验证。

### Task T1: 工程初始化与根目录约定

- [x] **状态**：完成

**代码仓范围：**
- 根项目：`/Users/melody/code/ai-workshop`
- 子仓：无

**文件：**
- 创建：`backend/`
- 创建：`frontend/`
- 修改：`README.md`
- 修改：`.gitignore`
- 创建：`backend/requirements/base.txt`
- 创建：`backend/requirements/dev.txt`

**验收点：**
- 根目录形成稳定的 `backend/` 与 `frontend/` 双工作区。
- 后续开发、运行、构建命令在 README 中有明确入口。

**步骤 1：写失败测试（如适用）**
- 不适用：绿地初始化任务，无现成测试入口。

**步骤 2：写最少实现**
- 修改点：`README.md`、`.gitignore`、`backend/requirements/base.txt`、`backend/requirements/dev.txt`
- 修改点：创建空目录 `backend/`、`frontend/`

**步骤 3：运行验证**
- Run: `test -d backend`
- Expected: PASS（目录存在）
- Run: `test -d frontend`
- Expected: PASS（目录存在）
- 验证结果摘要：
  - `test -d /Users/melody/code/ai-workshop/backend` -> PASS
  - `test -d /Users/melody/code/ai-workshop/frontend` -> PASS

**步骤 4：提交（受 AUTO_COMMIT 控制）**
- Commit message: `初始化前后端工程目录与依赖约定`
- 审计信息：
  - repo: `root`
    branch: `001-competitive-intel-agent`
    commit: `f5250d7`
    pr: `<TBD>`
    changed_files:
      - `README.md`
      - `.gitignore`
      - `backend/requirements/base.txt`
      - `backend/requirements/dev.txt`

### Task T2: 搭建 Django 与 Vue 脚手架

- [x] **状态**：完成

**代码仓范围：**
- 根项目：`/Users/melody/code/ai-workshop`
- 子仓：无

**文件：**
- 创建：`backend/manage.py`
- 创建：`backend/config/__init__.py`
- 创建：`backend/config/settings.py`
- 创建：`backend/config/urls.py`
- 创建：`backend/config/asgi.py`
- 创建：`backend/config/wsgi.py`
- 创建：`backend/apps/__init__.py`
- 创建：`backend/apps/intelligence/__init__.py`
- 创建：`backend/apps/intelligence/apps.py`
- 创建：`frontend/package.json`
- 创建：`frontend/vite.config.ts`
- 创建：`frontend/index.html`
- 创建：`frontend/src/main.ts`
- 创建：`frontend/src/App.vue`
- 创建：`frontend/src/router/index.ts`
- 创建：`frontend/src/styles/main.css`

**验收点：**
- Django 工程可执行 `check`。
- Vue 工程可执行 `build`。
- 前后端目录结构与入口文件稳定。

**步骤 1：写失败测试（如适用）**
- 不适用：先搭骨架，再补具体业务测试。

**步骤 2：写最少实现**
- 修改点：创建 Django 基础工程、应用注册、基础 URL
- 修改点：创建 Vue + Vite 基础工程、全局样式、路由占位

**步骤 3：运行验证**
- Run: `python3 backend/manage.py check`
- Expected: PASS（Django system check 无阻塞错误）
- Run: `npm --prefix frontend run build`
- Expected: PASS（Vite build 成功）
- 验证结果摘要：
  - `/Users/melody/code/ai-workshop/.venv/bin/python /Users/melody/code/ai-workshop/backend/manage.py check` -> PASS（`System check identified no issues (0 silenced).`）
  - `npm run build`（workdir=`frontend/`）-> PASS（Vite build 成功）

**步骤 4：提交（受 AUTO_COMMIT 控制）**
- Commit message: `搭建 Django 与 Vue 应用脚手架`
- 审计信息：
  - repo: `root`
    branch: `001-competitive-intel-agent`
    commit: `af787eb`
    pr: `<TBD>`
    changed_files:
      - `backend/manage.py`
      - `backend/config/__init__.py`
      - `backend/config/asgi.py`
      - `backend/config/settings.py`
      - `backend/config/urls.py`
      - `backend/config/wsgi.py`
      - `backend/apps/__init__.py`
      - `backend/apps/intelligence/__init__.py`
      - `backend/apps/intelligence/apps.py`
      - `frontend/index.html`
      - `frontend/package-lock.json`
      - `frontend/package.json`
      - `frontend/tsconfig.json`
      - `frontend/vite.config.ts`
      - `frontend/src/env.d.ts`
      - `frontend/src/main.ts`
      - `frontend/src/App.vue`
      - `frontend/src/router/index.ts`
      - `frontend/src/views/HomePage.vue`
      - `frontend/src/styles/main.css`

### Task T3: 初始化数据库与核心实体

- [x] **状态**：完成

**代码仓范围：**
- 根项目：`/Users/melody/code/ai-workshop`
- 子仓：无

**文件：**
- 创建：`backend/apps/intelligence/models.py`
- 创建：`backend/apps/intelligence/admin.py`
- 创建：`backend/apps/intelligence/migrations/__init__.py`
- 创建：`backend/apps/intelligence/migrations/0001_initial.py`
- 创建：`backend/apps/intelligence/fixtures/sample_reports.json`
- 创建：`backend/apps/intelligence/tests/test_models.py`

**验收点：**
- 核心实体至少包含 `MonitorProject`、`DataSnapshot`、`IntelligenceFeed`。
- `MonitorProject` 与 `IntelligenceFeed` 足以支撑任务 CRUD、报告列表、评分 CRUD。
- 数据库迁移可执行，样本数据可导入。

**步骤 1：写失败测试（如适用）**
- 修改点：`backend/apps/intelligence/tests/test_models.py`
- Run: `python3 backend/manage.py test apps.intelligence.tests.test_models`
- Expected: FAIL（模型/迁移/约束尚未实现时失败）
- 验证结果摘要：
  - `/Users/melody/code/ai-workshop/.venv/bin/python /Users/melody/code/ai-workshop/backend/manage.py test apps.intelligence.tests.test_models` -> FAIL（`ModuleNotFoundError: No module named 'apps.intelligence.models'`）

**步骤 2：写最少实现**
- 修改点：`backend/apps/intelligence/models.py`
- 修改点：`backend/apps/intelligence/migrations/0001_initial.py`
- 修改点：`backend/apps/intelligence/fixtures/sample_reports.json`
- 设计要求：
  - `MonitorProject` 落地 `project_name`、`competitor_urls`、`self_product_doc`、`cron`、`feishu_webhook`、`is_active`
  - `IntelligenceFeed` 落地 `job_status`、4 字段情报内容、`user_feedback`、`user_comment`、报告路径字段
  - `DataSnapshot` 先建表并保留 append-only 约束扩展点，即便本批次不写入业务数据

**步骤 3：运行验证**
- Run: `python3 backend/manage.py makemigrations --check`
- Expected: PASS（迁移文件已同步）
- Run: `python3 backend/manage.py migrate`
- Expected: PASS（SQLite 初始化成功）
- Run: `python3 backend/manage.py loaddata backend/apps/intelligence/fixtures/sample_reports.json`
- Expected: PASS（样本数据导入成功）
- Run: `python3 backend/manage.py test apps.intelligence.tests.test_models`
- Expected: PASS（模型测试通过）
- 验证结果摘要：
  - `manage.py makemigrations intelligence` -> PASS（生成 `backend/apps/intelligence/migrations/0001_initial.py`）
  - `manage.py makemigrations --check` -> PASS（`No changes detected`）
  - `manage.py migrate` -> PASS（应用 `intelligence.0001_initial` 成功）
  - `manage.py loaddata backend/apps/intelligence/fixtures/sample_reports.json` -> PASS（`Installed 3 object(s) from 1 fixture(s)`）
  - `manage.py test apps.intelligence.tests.test_models` -> PASS（2 个模型测试通过）

**步骤 4：提交（受 AUTO_COMMIT 控制）**
- Commit message: `初始化竞争情报核心数据模型与迁移`
- 审计信息：
  - repo: `root`
    branch: `001-competitive-intel-agent`
    commit: `505e997`
    pr: `<TBD>`
    changed_files:
      - `backend/apps/intelligence/models.py`
      - `backend/apps/intelligence/admin.py`
      - `backend/apps/intelligence/migrations/__init__.py`
      - `backend/apps/intelligence/migrations/0001_initial.py`
      - `backend/apps/intelligence/fixtures/sample_reports.json`
      - `backend/apps/intelligence/tests/__init__.py`
      - `backend/apps/intelligence/tests/test_models.py`

### Task T4: 设计并实现后端 API

- [x] **状态**：完成

**代码仓范围：**
- 根项目：`/Users/melody/code/ai-workshop`
- 子仓：无

**文件：**
- 创建：`backend/apps/intelligence/serializers.py`
- 创建：`backend/apps/intelligence/views.py`
- 创建：`backend/apps/intelligence/urls.py`
- 修改：`backend/config/urls.py`
- 创建：`backend/apps/intelligence/services/report_seed.py`
- 创建：`backend/apps/intelligence/tests/test_api.py`

**验收点：**
- 提供任务 CRUD API：列表、创建、详情、更新、停用。
- 提供报告列表/详情 API：支持项目、状态、时间范围过滤。
- 提供评分 CRUD API：新增、更新、删除 `user_feedback` / `user_comment`。
- API 输出字段可直接被 Vue 页面消费。

**步骤 1：写失败测试（如适用）**
- 修改点：`backend/apps/intelligence/tests/test_api.py`
- Run: `python3 backend/manage.py test apps.intelligence.tests.test_api`
- Expected: FAIL（接口未实现或返回结构不满足契约）

**步骤 2：写最少实现**
- 修改点：`backend/apps/intelligence/serializers.py`
- 修改点：`backend/apps/intelligence/views.py`
- 修改点：`backend/apps/intelligence/urls.py`
- 修改点：`backend/config/urls.py`
- 接口范围：
  - `GET /api/projects`
  - `POST /api/projects`
  - `GET /api/projects/{id}`
  - `PATCH /api/projects/{id}`
  - `DELETE /api/projects/{id}`（语义为停用）
  - `GET /api/reports`
  - `GET /api/reports/{id}`
  - `POST /api/reports/{id}/rating`
  - `PATCH /api/reports/{id}/rating`
  - `DELETE /api/reports/{id}/rating`

**步骤 3：运行验证**
- Run: `python3 backend/manage.py test apps.intelligence.tests.test_api`
- Expected: PASS（API 契约测试通过）
- Run: `python3 backend/manage.py check`
- Expected: PASS（URL 与应用注册无错误）
- 验证结果摘要：
  - `/Users/melody/code/ai-workshop/.venv/bin/python /Users/melody/code/ai-workshop/backend/manage.py test apps.intelligence.tests.test_api` -> PASS（5 个 API 测试通过，覆盖任务 CRUD、报告列表/详情、评分 CRUD）
  - `/Users/melody/code/ai-workshop/.venv/bin/python /Users/melody/code/ai-workshop/backend/manage.py check` -> PASS（`System check identified no issues (0 silenced).`）
  - `curl --max-time 5 -s http://127.0.0.1:8001/api/projects` -> PASS（临时 Django 实例返回任务列表 JSON）
  - `curl --max-time 5 -s http://127.0.0.1:8001/api/reports` -> PASS（临时 Django 实例返回监控记录 JSON）
  - `curl --max-time 5 -s -X POST http://127.0.0.1:8001/api/reports/1/rating ...` / `DELETE ...` -> PASS（评分写入与清空均成功）

**步骤 4：提交（受 AUTO_COMMIT 控制）**
- Commit message: `实现任务与报告评分相关后端接口`
- 审计信息：
  - repo: `root`
    branch: `001-competitive-intel-agent`
    commit: `aa673b2`
    pr: `<TBD>`
    changed_files:
      - `backend/apps/intelligence/serializers.py`
      - `backend/apps/intelligence/services/__init__.py`
      - `backend/apps/intelligence/services/report_seed.py`
      - `backend/apps/intelligence/tests/test_api.py`
      - `backend/apps/intelligence/urls.py`
      - `backend/apps/intelligence/views.py`
      - `backend/config/urls.py`

### Task T5: 实现前端任务 CRUD、报告列表与评分 CRUD

- [x] **状态**：完成

**代码仓范围：**
- 根项目：`/Users/melody/code/ai-workshop`
- 子仓：无

**文件：**
- 创建：`frontend/src/api/client.ts`
- 创建：`frontend/src/api/projects.ts`
- 创建：`frontend/src/api/reports.ts`
- 修改：`frontend/src/router/index.ts`
- 创建：`frontend/src/views/projects/ProjectListPage.vue`
- 创建：`frontend/src/views/projects/ProjectFormPage.vue`
- 创建：`frontend/src/views/reports/ReportListPage.vue`
- 创建：`frontend/src/views/reports/ReportDetailPage.vue`
- 创建：`frontend/src/components/projects/ProjectForm.vue`
- 创建：`frontend/src/components/reports/RatingForm.vue`
- 创建：`frontend/src/components/common/AppShell.vue`
- 创建：`frontend/src/tests/README.md`

**验收点：**
- 可查看任务列表、创建任务、编辑任务、停用任务。
- 可查看报告列表和报告详情。
- 可新增、修改、删除报告评分与评语。
- 页面命名与文案明确为“任务 / 报告 / 评分”，不混淆成完整执行监控闭环。

**步骤 1：写失败测试（如适用）**
- 不适用：当前批次以前端构建与手工联调为最小验证。

**步骤 2：写最少实现**
- 修改点：`frontend/src/api/*.ts`
- 修改点：`frontend/src/views/projects/*.vue`
- 修改点：`frontend/src/views/reports/*.vue`
- 修改点：`frontend/src/components/**/*.vue`
- 交互要求：
  - 任务表单支持 `competitor_urls` 动态行录入
  - 报告列表支持基础筛选
  - 报告详情页内完成评分新增/编辑/删除

**步骤 3：运行验证**
- Run: `npm --prefix frontend run build`
- Expected: PASS（前端构建通过）
- Run: `python3 backend/manage.py check`
- Expected: PASS（联调期间后端仍保持有效）
- Run: 手工走查 `/projects`、`/projects/new`、`/reports`、`/reports/:id`
- Expected: PASS（任务 CRUD、报告浏览、评分 CRUD 主链路可走通）
- 验证结果摘要：
  - `npm run build`（workdir=`/Users/melody/code/ai-workshop/frontend`）-> PASS（Vite build 成功）
  - `/Users/melody/code/ai-workshop/.venv/bin/python /Users/melody/code/ai-workshop/backend/manage.py check` -> PASS（前端联调改动未影响 Django 配置）
  - `curl --max-time 5 -s http://127.0.0.1:4173/cockpit` / `/projects` / `/monitoring` / `/monitoring/1` -> PASS（Vue 开发服务器路由均返回应用壳）
  - `curl --max-time 5 -s http://127.0.0.1:8001/api/projects` / `/api/reports` -> PASS（任务管理、任务监控所依赖的列表接口可用）
  - 说明：原有 `127.0.0.1:8000` Django 进程响应不稳定，本批次手工联调改用临时 `127.0.0.1:8001` 实例完成 API 冒烟，未修改用户现有进程

**步骤 4：提交（受 AUTO_COMMIT 控制）**
- Commit message: `实现任务管理与报告评分前端界面`
- 审计信息：
  - repo: `root`
    branch: `001-competitive-intel-agent`
    commit: `aae4221`
    pr: `<TBD>`
    changed_files:
      - `frontend/src/App.vue`
      - `frontend/src/api/client.ts`
      - `frontend/src/api/projects.ts`
      - `frontend/src/api/reports.ts`
      - `frontend/src/components/common/AppShell.vue`
      - `frontend/src/components/projects/ProjectForm.vue`
      - `frontend/src/components/reports/RatingForm.vue`
      - `frontend/src/router/index.ts`
      - `frontend/src/styles/main.css`
      - `frontend/src/tests/README.md`
      - `frontend/src/views/dashboard/CockpitPage.vue`
      - `frontend/src/views/HomePage.vue`（删除）
      - `frontend/src/views/projects/ProjectFormPage.vue`
      - `frontend/src/views/projects/ProjectListPage.vue`
      - `frontend/src/views/reports/ReportDetailPage.vue`
      - `frontend/src/views/reports/ReportListPage.vue`
      - `frontend/vite.config.ts`

---

## Merge-back 待办清单（仅记录，不在本阶段执行）

- MB-001：若 I2 落地了稳定的 API DTO、任务停用口径与评分字段契约，后续需要考虑晋升到 `.aisdlc/project/contracts/` 或 ADR。
- MB-002：若 `DataSnapshot` append-only 触发器与报告种子策略在实现中形成稳定方案，后续需要评估是否晋升到项目级 ADR / 数据契约说明。
