---
title: LinkFox 风格前端 UI 重构实现计划（SSOT）
status: draft
---

目的：把 `requirements/*` 转为可直接执行的实现计划，并将其作为唯一执行清单与状态 SSOT（checkbox + 步骤 + 验证 + 提交点 + 审计信息）。
落盘位置：`/Users/melody/code/ai-workshop/.aisdlc/specs/011-linkfox-ui-redesign/implementation/plan.md`

> 约束：
> - 必须先执行 `spec-context` 获取上下文，拿到 `FEATURE_DIR=/Users/melody/code/ai-workshop/.aisdlc/specs/011-linkfox-ui-redesign`
> - D0 判定：本次需求只触及前端 UI/布局/视觉，不改 API/路由语义/数据契约，可跳过 design 直接进入 I1
> - 所有不确定性只写在 `## NEEDS CLARIFICATION`，未消除前不得进入 I2

# LinkFox 风格前端 UI 重构实现计划（SSOT）

> **必需技能：** `spec-execute`（按批次执行本计划）
> **上下文获取：** 必须先执行 `spec-context` 获取上下文，定位 `{FEATURE_DIR}`，失败即停止

**目标：** 在不改动现有业务功能、路由与 API 契约的前提下，把当前 Vue 控制台重构为高保真参考 LinkFox AI 官网视觉语言的品牌化工作台。  
**范围：** In = 全局骨架、设计 token、`/cockpit`、`/projects`、`/projects/new`、`/projects/:id/edit`、`/monitoring`、`/monitoring/:id` 的布局与样式重构；Out = 后端逻辑、接口语义、路由能力、数据模型与业务流程变更。  
**架构：** 继续使用现有 `Vue 3 + Element Plus + Vite` 工程，不新增前端框架或业务路由。先在 `AppShell.vue` 与 `main.css` 建立新的导航骨架和视觉 token，再逐页重排仪表盘、列表页、详情页和表单页，保持现有 API 调用层与组件边界基本稳定。  
**验收口径：** 对齐 `requirements/prd.md` 的 `AC-001` 到 `AC-012`，以及 `requirements/prototype.md` 的 `P-001` 到 `P-006` 页面与 `T-001` 到 `T-020` 主链路。  
**影响范围：** `frontend-console`（页面骨架、样式系统、页面布局）、`intelligence-api`（只读消费契约稳定性校验）、`report-service`（详情页预览/下载/评分入口继续可见），来源见 `requirements/solution.md#7-impact-analysis`。  
**需遵守的不变量：** 保留任务 CRUD、报告列表/详情查看、评分 CRUD 和现有前后端分离工作台骨架；保持 `/cockpit`、`/projects`、`/projects/new`、`/projects/:id/edit`、`/monitoring`、`/monitoring/:id` 路由语义不变；保留评分、HTML 预览、MD 下载、项目启停和立即执行入口。  
**子仓范围：** 无（当前仓库无 `.gitmodules`，本次仅修改根项目 `frontend/`）。

---

## TL;DR（3-7 行）

- 一句话目标：用一轮前端 UI 系统性重构，把当前管理台升级为更有品牌感、但仍适合高频工作的 LinkFox 风格工作台。
- In/Out：只动 `frontend/src/` 下的骨架、样式和页面编排；不动后端 API、业务路由和数据契约。
- 关键路径（1-3 条）：
  - 先改 `frontend/src/components/common/AppShell.vue` + `frontend/src/styles/main.css`，建立统一设计 token 和全局容器语义。
  - 再分别重构 `CockpitPage.vue`、`ProjectListPage.vue`、`ProjectForm.vue`、`ReportListPage.vue`、`ReportDetailPage.vue`。
  - 最后做窄屏适配和全链路烟测，确保扫描效率、阅读效率和核心操作不回退。
- 最大风险与优先验证点：`R1` 导航品牌化后效率下降、`R2` 页面信息密度失衡、`R3` 详情页与表单页重排导致交互回退。

---

## 范围与边界（In / Out）

- **In**：
  - 重构 `frontend/src/components/common/AppShell.vue` 的品牌区、侧边导航、顶部辅助信息和主内容容器
  - 重构 `frontend/src/styles/main.css` 的色板、背景层、卡片、表格、按钮、标签、表单、空状态和响应式规则
  - 重构 `frontend/src/views/dashboard/CockpitPage.vue`，保持工作台首页定位
  - 重构 `frontend/src/views/projects/ProjectListPage.vue` 与 `frontend/src/views/projects/ProjectFormPage.vue`
  - 重构 `frontend/src/components/projects/ProjectForm.vue` 为分区编辑页
  - 重构 `frontend/src/views/reports/ReportListPage.vue` 与 `frontend/src/views/reports/ReportDetailPage.vue`
- **Out**：
  - `frontend/src/api/*.ts` 的接口语义调整
  - `frontend/src/router/index.ts` 的业务路由新增/删除/改语义
  - 后端模型、报告生成链路、评分写回语义、下载/预览接口改造
  - 新增营销页、登录页、设置页等 `prototype.md` 未声明页面
- **不变量/关键约束**：
  - `/cockpit` 必须继续是工作台首页，不改成营销 hero 页
  - 侧边导航仍是主导航，品牌表达只能增强，不得削弱主要任务入口
  - 列表页、详情页、表单页允许重排，但必须保持中等信息密度与扫描效率
  - 详情页必须继续提供评分、HTML 预览、MD 下载和多状态阅读路径
- **影响面**（模块/接口/权限/数据口径/运维）：
  - 模块：`frontend-console` 为主；`intelligence-api`、`report-service` 仅做消费契约稳定性校验
  - 接口/权限/数据口径：无新增接口、无权限模型变化、无数据迁移
  - 运维：仅需前端构建与本地路由烟测，无额外发布基础设施变更
  - `CONTEXT GAP`：`.aisdlc/project/components/` 尚无独立 `frontend-console` 模块页，本计划以代码证据和 `requirements/solution.md#7-impact-analysis` 为准

## 代码工作区清单（如适用）

- 本仓库当前无 `.gitmodules`
- 本次仅涉及根项目：`/Users/melody/code/ai-workshop/frontend/`

---

## 里程碑与节奏

- M0（MVP）：
  - 完成全局骨架与设计 token 重构
  - 完成 5 个核心页面面的版式升级：仪表盘、项目列表、项目表单、监控列表、报告详情
  - 跑通构建校验与主要页面烟测，确认 AC-001~AC-012 未回退
- M1（可选）：
  - 收敛窄屏细节、微交互和视觉一致性
  - 将实现中沉淀出的页面规则回流到后续 merge-back 资产

> M0 对应 T1~T5；M1 仅在 M0 完成且仍有余量时处理局部 polish，不新增业务范围。

---

## 依赖与资源

- 环境/权限：
  - 现有前端工程 `frontend/package.json` 已具备 `dev`、`build`、`preview` 脚本
  - 需要本地可运行 Node/npm 环境
- 外部系统/团队：
  - 无新增外部系统依赖
  - 视觉参考来自 `requirements/raw.md` 指定的 LinkFox 官网
- 数据/样本：
  - 依赖现有项目/报告接口返回的数据形态
  - 详情页状态验证需覆盖 `CHANGED`、`NO_CHANGE`、`ERROR_CRAWL`
- 发布/变更窗口（如适用）：
  - 无特殊窗口要求；以前端构建通过和页面烟测通过作为进入合并前门禁

---

## 风险与验证（可执行）

| # | 风险/假设 | 验证方式 | 成功信号 | 失败信号 | Owner | 截止 | 下一步动作 |
|---|---|---|---|---|---|---|---|
| R1 | 品牌区和新导航层级压过工作台入口 | 本地走查 `/cockpit`、`/projects`、`/monitoring` 三条首屏路径 | 主要入口首屏可见或单次导航即可到达 | 需要额外查找/滚动才能进入主工作流 | FE | T2 完成后 | 压缩品牌区、增强一级导航显著性 |
| R2 | 新色板和卡片层级导致列表扫描效率下降 | 对 `/projects` 和 `/monitoring` 做 10 秒任务型定位检查 | 状态、时间、摘要、操作按钮可稳定快速定位 | 关键信息被装饰层或留白稀释 | FE | T4 完成后 | 提高信息密度，减少装饰性留白 |
| R3 | 详情页双栏/分区布局在低信息量状态下失衡 | 用 `CHANGED`、`NO_CHANGE`、`ERROR_CRAWL` 三类数据手动走查 `/monitoring/:id` | 三种状态下阅读路径和操作路径都清晰 | 某一状态出现空洞、断裂或核心操作漂移 | FE | T4 完成后 | 退回单主栏 + 次栏摘要的更稳结构 |
| R4 | 表单分区增强后录入节奏被拖慢 | 用“创建一个完整监控任务”流程走查 `/projects/new` | 字段分组更清晰，保存链路未明显变长 | 高优先级字段被说明块或装饰区淹没 | FE | T3 完成后 | 合并区块、压缩说明和弱化非必要装饰 |
| R5 | 当前前端无视觉自动化基线，容易留下样式回归 | 以 `npm run build` + 页面手动烟测作为最小验证组合 | 构建通过且 5 个核心页面无布局崩坏 | 构建失败或任一页面主流程不可达 | FE | 每个任务完成后 | 先修复构建/布局问题，再继续下个任务 |

---

## 验收口径（可追溯）

- 追溯：`requirements/solution.md`
  - `## 2. 推荐方案`：品牌化工作台高保真重构方案
  - `## 5. 验证清单`：`V-001`、`V-002`、`V-003`、`V-004`、`V-005`
  - `## 7. Impact Analysis`：受影响模块与不变量
- 追溯：`requirements/prd.md`
  - `AC-001`~`AC-003`：仪表盘保持工作台定位且入口高效可达
  - `AC-004`~`AC-007`：项目列表与监控列表的状态、摘要、时间、操作可快速扫描
  - `AC-008`~`AC-012`：详情页分区阅读与项目表单分区编辑保持高效
- 追溯：`requirements/prototype.md`
  - `P-001`~`P-006` 页面清单
  - `T-001`~`T-020` 核心任务流
- 关键验收点（摘要）：
  - 导航骨架、色板与页面区块形成统一设计语言
  - 核心业务操作入口全部保留且更易识别
  - 列表页、详情页、表单页在视觉升级后仍保持后台工作台效率

---

## NEEDS CLARIFICATION（未消除前不得进入 I2）

- C1：
  - 缺什么：当前无阻断性澄清项；规格已覆盖页面清单、主链路、验收口径和边界约束
  - 取证/验证方式：进入 I2 前再次对照 `requirements/prd.md` 的 `AC-001`~`AC-012` 与 `requirements/prototype.md` 的 `P-001`~`P-006`
  - 成功/失败信号：若实现范围仍停留在既有 6 个页面与既有业务入口内，则成功；若新增页面、改业务路由或要求改 API 语义，则失败
  - 下一步动作：成功则进入 `spec-execute`；失败则回流 `spec-product-prd` 或 `spec-product-prototype` 更新规格

---

## 任务清单（SSOT）

> 这是唯一的执行清单与状态来源：用 `- [ ] / - [x]` 标记完成；执行中把 `branch/commit/pr/changed_files` 与关键验证结果回写到对应任务。
> 命令默认使用当前仓库 shell 兼容写法，同一行多命令用 `;` 分隔。

### Task T1: 建立全局导航骨架与设计 token

- [x] **状态**：完成

**代码仓范围：**
- 根项目：`/Users/melody/code/ai-workshop`
- 子仓：无

**文件：**
- 创建：无
- 修改：
  - `frontend/src/components/common/AppShell.vue`
  - `frontend/src/styles/main.css`
- 测试：无（当前前端无自动化 UI 测试基线，使用构建与手动烟测）

**验收点：**
- 侧边导航仍为主导航，品牌区与顶部辅助区就位
- 全局色板、背景层、边框、圆角、按钮和卡片语义统一更新
- 页面主容器、区块间距和通用标题区可复用于所有核心页面

**步骤 1：写失败测试（如适用）**
- Run: 不适用（当前仓库无前端快照/组件测试基线）
- Expected: 记录为 N/A，并在步骤 3 用构建 + 手动烟测替代
- Result: N/A（当前批次沿用 plan 中约定，以构建验证代替）

**步骤 2：写最少实现**
- 修改点：
  - `frontend/src/components/common/AppShell.vue`
  - `frontend/src/styles/main.css`

**步骤 3：运行验证**
- Run: `cd /Users/melody/code/ai-workshop/frontend; npm run build`
- Expected: PASS（Vite 构建成功，无 TypeScript 报错）
- Result: PASS（2026-07-10：`npm run build` 通过；仅有既有 Vite chunk size warning，无类型或构建错误）

**步骤 4：提交（频繁提交；commit message 必须中文）**
- Commit message: `完成前端骨架与任务配置首批重构`
- 审计信息：
  - repo: `root`
    branch: `011-linkfox-ui-redesign`
    commit: `9cd05fb`
    pr: `<TBD>`
    changed_files:
      - `frontend/src/components/common/AppShell.vue`
      - `frontend/src/styles/main.css`

### Task T2: 重构仪表盘为品牌化工作台首页

- [x] **状态**：完成

**代码仓范围：**
- 根项目：`/Users/melody/code/ai-workshop`
- 子仓：无

**文件：**
- 创建：无
- 修改：
  - `frontend/src/views/dashboard/CockpitPage.vue`
  - `frontend/src/styles/main.css`
- 测试：无（使用构建与首屏任务走查）

**验收点：**
- `/cockpit` 首屏同时呈现品牌区、关键指标和主要入口
- 最近重大变更区更清晰，但不挤占工作台主体
- 满足 `AC-001`、`AC-002`、`AC-003`

**步骤 1：写失败测试（如适用）**
- Run: 不适用（当前无仪表盘自动化 UI 断言）
- Expected: 记录为 N/A，并在步骤 3 通过构建与人工走查验证
- Result: N/A（当前批次未引入新的前端自动化基线）

**步骤 2：写最少实现**
- 修改点：
  - `frontend/src/views/dashboard/CockpitPage.vue`
  - `frontend/src/styles/main.css`

**步骤 3：运行验证**
- Run: `cd /Users/melody/code/ai-workshop/frontend; npm run build`
- Expected: PASS（构建通过，且后续本地打开 `/cockpit` 时主入口首屏可达）
- Result: PASS（2026-07-10：`npm run build` 通过；仪表盘模板和样式改动未引入构建错误）

**步骤 4：提交（频繁提交；commit message 必须中文）**
- Commit message: `完成前端骨架与任务配置首批重构`
- 审计信息：
  - repo: `root`
    branch: `011-linkfox-ui-redesign`
    commit: `9cd05fb`
    pr: `<TBD>`
    changed_files:
      - `frontend/src/views/dashboard/CockpitPage.vue`
      - `frontend/src/styles/main.css`

### Task T3: 重构项目列表与分区编辑表单

- [x] **状态**：完成

**代码仓范围：**
- 根项目：`/Users/melody/code/ai-workshop`
- 子仓：无

**文件：**
- 创建：无
- 修改：
  - `frontend/src/views/projects/ProjectListPage.vue`
  - `frontend/src/views/projects/ProjectFormPage.vue`
  - `frontend/src/components/projects/ProjectForm.vue`
  - `frontend/src/styles/main.css`
- 测试：无（使用构建与项目创建流程手动烟测）

**验收点：**
- `/projects` 的状态、调度语义、未来运行时间与操作入口更易扫描
- `/projects/new` 与 `/projects/:id/edit` 形成清晰的分区编辑体验
- 保留启停、立即执行、编辑、查看监控和保存路径
- 满足 `AC-004`、`AC-005`、`AC-011`、`AC-012`

**步骤 1：写失败测试（如适用）**
- Run: 不适用（当前无列表页/表单页自动化前端测试）
- Expected: 记录为 N/A，并在步骤 3 使用构建与手动任务录入验证
- Result: N/A（当前批次未补建列表页/表单页自动化测试）

**步骤 2：写最少实现**
- 修改点：
  - `frontend/src/views/projects/ProjectListPage.vue`
  - `frontend/src/views/projects/ProjectFormPage.vue`
  - `frontend/src/components/projects/ProjectForm.vue`
  - `frontend/src/styles/main.css`

**步骤 3：运行验证**
- Run: `cd /Users/melody/code/ai-workshop/frontend; npm run build`
- Expected: PASS（构建通过，表单与列表无模板/类型错误）
- Result: PASS（2026-07-10：`npm run build` 通过；项目列表页、项目表单页和分区编辑表单模板均编译成功）

**步骤 4：提交（频繁提交；commit message 必须中文）**
- Commit message: `完成前端骨架与任务配置首批重构`
- 审计信息：
  - repo: `root`
    branch: `011-linkfox-ui-redesign`
    commit: `9cd05fb`
    pr: `<TBD>`
    changed_files:
      - `frontend/src/views/projects/ProjectListPage.vue`
      - `frontend/src/views/projects/ProjectFormPage.vue`
      - `frontend/src/components/projects/ProjectForm.vue`
      - `frontend/src/styles/main.css`

### Task T4: 重构监控列表与报告详情阅读布局

- [ ] **状态**：未开始

**代码仓范围：**
- 根项目：`/Users/melody/code/ai-workshop`
- 子仓：无

**文件：**
- 创建：无
- 修改：
  - `frontend/src/views/reports/ReportListPage.vue`
  - `frontend/src/views/reports/ReportDetailPage.vue`
  - `frontend/src/components/reports/RatingForm.vue`
  - `frontend/src/styles/main.css`
- 测试：无（使用构建与多状态详情页手动烟测）

**验收点：**
- `/monitoring` 提升状态、摘要、时间和详情入口的可扫描性
- `/monitoring/:id` 形成更清晰的概览区、正文区、证据区、反馈/操作区
- `CHANGED`、`NO_CHANGE`、`ERROR_CRAWL` 三种状态都保持稳定阅读路径
- 保留评分、HTML 预览、MD 下载与返回监控入口
- 满足 `AC-006`、`AC-007`、`AC-008`、`AC-009`、`AC-010`

**步骤 1：写失败测试（如适用）**
- Run: 不适用（当前无报告列表/详情页自动化 UI 测试）
- Expected: 记录为 N/A，并在步骤 3 使用构建与多状态页面烟测

**步骤 2：写最少实现**
- 修改点：
  - `frontend/src/views/reports/ReportListPage.vue`
  - `frontend/src/views/reports/ReportDetailPage.vue`
  - `frontend/src/components/reports/RatingForm.vue`
  - `frontend/src/styles/main.css`

**步骤 3：运行验证**
- Run: `cd /Users/melody/code/ai-workshop/frontend; npm run build`
- Expected: PASS（构建通过，详情页多状态视图无模板/样式错误）

**步骤 4：提交（频繁提交；commit message 必须中文）**
- Commit message: `重构监控列表与报告详情布局`
- 审计信息：
  - repo: `root`
    branch: `011-linkfox-ui-redesign`
    commit: `<TBD>`
    pr: `<TBD>`
    changed_files:
      - `frontend/src/views/reports/ReportListPage.vue`
      - `frontend/src/views/reports/ReportDetailPage.vue`
      - `frontend/src/components/reports/RatingForm.vue`
      - `frontend/src/styles/main.css`

### Task T5: 做跨页面一致性收口与烟测

- [ ] **状态**：未开始

**代码仓范围：**
- 根项目：`/Users/melody/code/ai-workshop`
- 子仓：无

**文件：**
- 创建：无
- 修改：
  - `frontend/src/styles/main.css`
  - `frontend/src/components/common/AppShell.vue`
  - `frontend/src/views/dashboard/CockpitPage.vue`
  - `frontend/src/views/projects/ProjectListPage.vue`
  - `frontend/src/views/projects/ProjectFormPage.vue`
  - `frontend/src/components/projects/ProjectForm.vue`
  - `frontend/src/views/reports/ReportListPage.vue`
  - `frontend/src/views/reports/ReportDetailPage.vue`
- 测试：无专门测试文件；使用构建 + 本地路由烟测

**验收点：**
- 所有核心页面共享统一的标题区、区块层级、按钮语义和间距系统
- 常见窄屏宽度下无文本溢出、区块重叠、按钮丢失
- M0 范围内所有页面满足 `AC-001`~`AC-012`

**步骤 1：写失败测试（如适用）**
- Run: 不适用（当前无端到端 UI 自动化基线）
- Expected: 记录为 N/A，并在步骤 3 以构建和手动路由烟测替代

**步骤 2：写最少实现**
- 修改点：按烟测结果回收 `main.css` 与各页面残留不一致样式

**步骤 3：运行验证**
- Run:
  - `cd /Users/melody/code/ai-workshop/frontend; npm run build`
  - `cd /Users/melody/code/ai-workshop/frontend; npm run dev -- --host 127.0.0.1 --port 4173`
- Expected: PASS（构建通过；开发服务器正常启动；手动走查 `/cockpit`、`/projects`、`/projects/new`、`/monitoring`、`/monitoring/:id` 时主流程与布局均正常）

**步骤 4：提交（频繁提交；commit message 必须中文）**
- Commit message: `完成前端界面重构收口与烟测`
- 审计信息：
  - repo: `root`
    branch: `011-linkfox-ui-redesign`
    commit: `<TBD>`
    pr: `<TBD>`
    changed_files:
      - `frontend/src/styles/main.css`
      - `frontend/src/components/common/AppShell.vue`
      - `frontend/src/views/dashboard/CockpitPage.vue`
      - `frontend/src/views/projects/ProjectListPage.vue`
      - `frontend/src/views/projects/ProjectFormPage.vue`
      - `frontend/src/components/projects/ProjectForm.vue`
      - `frontend/src/views/reports/ReportListPage.vue`
      - `frontend/src/views/reports/ReportDetailPage.vue`

---

## Merge-back 待办清单（仅记录，不在本阶段执行）

- MB-001：把本次重构中沉淀出的前端设计 token、导航骨架规则和页面分区约束，回流到 project 级 `frontend-console` 模块 SSOT
- MB-002：补齐 `.aisdlc/project/components/frontend-console.md` 或等价 Discover 产物，避免后续前端需求继续依赖代码反推边界
