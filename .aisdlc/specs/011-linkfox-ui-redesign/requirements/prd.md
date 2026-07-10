---
title: PRD
status: draft
---

目的：把 `requirements/solution.md` 的推荐决策转为可交付规格。文档中不写“待确认问题”；未知统一写入第 8 节验证清单。

## 0. 基本信息

- 需求标识（分支 / ID）：`011-linkfox-ui-redesign`
- 作者：Codex
- 评审人：Melody
- 状态：draft
- 最后更新：2026-07-10
- 关联链接：
  - [requirements/solution.md](./solution.md)
  - [requirements/raw.md](./raw.md)
  - [frontend/src/router/index.ts](/Users/melody/code/ai-workshop/frontend/src/router/index.ts)

---

## 1. 结论摘要（3-7 行）

- 目标（要解决什么）：把当前前端从黑白极简后台样式重构为高保真参考 LinkFox AI 官网视觉语言的品牌化工作台，同时保持现有业务功能、路由与 API 契约稳定。
- In / Out 边界：In = 全局导航骨架、页面布局、配色体系、卡片/表格/表单/详情页的视觉与结构重构；Out = 后端业务逻辑、接口语义、页面路由、任务执行流程与数据模型变更。
- MVP 边界（1-3 条）：
  - 所有核心页面统一应用新设计语言：`/cockpit`、`/projects`、`/projects/new`、`/projects/:id/edit`、`/monitoring`、`/monitoring/:id`
  - `/cockpit` 保持工作台首页定位，不改造成营销首页
  - 列表、详情、表单允许明显重排结构，但需维持中等信息密度与后台扫描效率
- 推荐方案（引用 `requirements/solution.md`）：采用“品牌化工作台高保真重构方案”，在现有后台工作台骨架上重构导航、色板、页面层级和关键页面布局。
- 优先验证点（引用第 8 节条目编号，1-3 个）：`V-001`、`V-002`、`V-004`

---

## 2. 范围与里程碑

### 2.1 MVP 范围（In / Out）

- **In**：
  - 重构全局 `AppShell`，升级品牌区、侧边导航、顶部辅助信息区与统一页面容器
  - 重构全局设计 token：颜色、背景层、边框、阴影、圆角、按钮、标签、空状态、表格与表单样式
  - 重构 `/cockpit` 为品牌化但仍以任务数据和操作入口为核心的工作台首页
  - 重构 `/projects` 为更清晰的信息分区列表页
  - 重构 `/projects/new`、`/projects/:id/edit` 为更产品化的分区编辑页
  - 重构 `/monitoring` 为更高可扫描性的执行记录页
  - 重构 `/monitoring/:id` 为概览区更强、允许双栏 / 分区阅读的详情页
  - 统一页面标题区、分区标题、主要 CTA、状态表达与反馈区样式
- **Out**：
  - 新增业务路由、删除现有功能入口
  - 调整后端 API 结构、DTO 字段或接口语义
  - 改动任务执行、报告生成、评分写回、下载、预览等业务流程
  - 引入与当前技术栈不一致的全新前端框架或设计系统替换

### 2.2 里程碑（尽量精简）

- MVP：
  - 完成统一设计 token 与全局骨架重构
  - 完成核心页面 UI 改造并保证交互能力不回退
  - 完成关键流程走查：任务浏览、任务编辑、执行监控、报告阅读、评分反馈
- M1（可选）：
  - 继续收敛视觉细节、动效、响应式边界与组件一致性
  - 补充前端设计原则 / token 说明沉淀，便于后续 merge-back

---

## 3. 核心场景（建议 ≤ 3 个）

### 3.1 场景 S-001：用户在新仪表盘中快速进入主要工作流

- **触发**：用户打开 `/cockpit`
- **参与者**：用户；前端导航骨架；仪表盘页面
- **目标**：在具备更强品牌感的前提下，用户仍能快速理解当前系统状态并进入任务管理或监控详情
- **成功标准（1-3 条）**：
  - 用户可在首屏识别系统品牌、当前关键状态和主要入口
  - 进入 `/projects`、`/monitoring`、单个详情页的路径不比当前更深
  - 仪表盘首屏仍以工作台信息和操作入口为主

### 3.2 场景 S-002：用户在重构后的列表页中快速扫描状态并执行操作

- **触发**：用户打开 `/projects` 或 `/monitoring`
- **参与者**：用户；项目列表页；监控列表页
- **目标**：用户能在更清晰的布局与新视觉体系下快速定位状态、时间、摘要与主要操作
- **成功标准（1-3 条）**：
  - 状态、时间、摘要和操作按钮在首屏或一次滚动内可稳定识别
  - 列表结构更清晰，但不降低后台扫描效率
  - 启停、立即执行、编辑、查看详情等操作可直接触达

### 3.3 场景 S-003：用户在重构后的详情页与表单页完成深度阅读与配置

- **触发**：用户打开 `/monitoring/:id` 或 `/projects/new`、`/projects/:id/edit`
- **参与者**：用户；报告详情页；项目表单页
- **目标**：详情页更适合分析阅读，表单页更适合模块化配置，但都不牺牲效率
- **成功标准（1-3 条）**：
  - 详情页的概览区、正文区、证据区、评分操作区层级清晰
  - 表单页的配置模块分组合理，字段查找路径更清晰
  - 报告评分、下载、预览、项目保存等核心动作仍然顺畅

---

## 4. 功能清单（与优先级/里程碑对齐）

| 功能项 | 优先级（P0/P1/P2 或 Must/Should/Could/Won't） | 里程碑 | 说明/依赖 |
|---|---|---|---|
| F-01 全局导航骨架重构 | P0 | MVP | 重构 `AppShell`、品牌区、侧边导航、顶部辅助区 |
| F-02 全局设计 token 重构 | P0 | MVP | 统一色板、背景、阴影、圆角、按钮、标签、表格、表单样式 |
| F-03 仪表盘页面重构 | P0 | MVP | `/cockpit` 保持工作台定位，强化层级与品牌表达 |
| F-04 项目列表页重构 | P0 | MVP | `/projects` 信息分区优化，保留任务操作效率 |
| F-05 项目表单页分区编辑重构 | P0 | MVP | `/projects/new`、`/projects/:id/edit` 按配置模块分组 |
| F-06 监控列表页重构 | P0 | MVP | `/monitoring` 提升扫描效率与层级表达 |
| F-07 报告详情页双栏/分区重构 | P0 | MVP | `/monitoring/:id` 概览区、正文区、diff 区、反馈区重组 |
| F-08 通用标题区与空状态重构 | P0 | MVP | 统一页面头部、空状态、区块标题与卡片样式 |
| F-09 响应式与窄屏适配修正 | P1 | MVP | 保证常见窄屏宽度下布局不崩坏 |
| F-10 设计原则/Token 文档沉淀 | P1 | M1 | 用于后续 merge-back 和持续维护 |

---

## 5. 业务规则与口径（只写影响 AC 的）

- 规则-1：不得修改现有业务路由语义，核心入口仍为 `/cockpit`、`/projects`、`/projects/new`、`/projects/:id/edit`、`/monitoring`、`/monitoring/:id`。
- 规则-2：不得修改现有后端 API 的字段语义与调用方式，前端重构仅限 UI 层和信息组织层。
- 规则-3：`/cockpit` 必须保持工作台首页属性，不能演变为营销首页或官网式展示首页。
- 规则-4：整体信息密度采用中等密度策略，禁止极端稀疏或极端高密度。
- 规则-5：全局导航可以品牌化升级，但仍以侧边导航为主，不移除主要工作台入口。
- 规则-6：列表页、详情页、表单页都允许明显重排结构，但必须保留高频扫描与高频操作效率。
- 规则-7：报告详情页允许双栏/分区布局，但仍以分析阅读与反馈操作为主，不做展示型沉浸页面。
- 规则-8：项目表单页允许升级为更产品化的分区编辑页，但保存与填写效率不能明显下降。

---

## 6. 验收标准（AC，可测试）

### 6.1 场景 S-001 的 AC

- AC-001：用户打开 `/cockpit`。预期：首屏可同时识别品牌区、核心指标区与主要工作台入口。
- AC-002：用户从 `/cockpit` 进入 `/projects` 或 `/monitoring`。预期：主要入口在首屏或单次导航层级内可直接到达。
- AC-003：仪表盘重构后仍保留任务数据、执行状态和操作入口为核心内容。预期：不存在以营销文案或展示内容主导首屏的情况。

### 6.2 场景 S-002 的 AC

- AC-004：用户打开 `/projects`。预期：可快速识别项目名称、状态、调度语义、竞品数量和主要操作按钮。
- AC-005：用户在 `/projects` 执行启停、立即执行、编辑、查看监控。预期：所有操作入口保持存在且清晰可见。
- AC-006：用户打开 `/monitoring`。预期：可快速识别执行状态、变化摘要、执行时间和详情入口。
- AC-007：列表页视觉升级后仍能完成高频扫描。预期：状态、摘要、时间和操作不需要跨多个视觉层级反复查找。

### 6.3 场景 S-003 的 AC

- AC-008：用户打开 `/monitoring/:id`。预期：页面存在更强的概览区，并把概览、正文、证据 diff、评分反馈区做清晰分层。
- AC-009：在 `CHANGED`、`NO_CHANGE`、`ERROR_CRAWL` 三种状态下查看详情页。预期：不同状态下的阅读路径依旧清晰，没有布局断裂。
- AC-010：用户在详情页执行评分、下载 MD、打开 HTML 预览。预期：这些操作仍保留且可直接触达。
- AC-011：用户打开 `/projects/new` 或 `/projects/:id/edit`。预期：表单按配置模块分组展示，而不是无层次的单一长表单。
- AC-012：用户填写项目名称、竞品 URL、crawl_hint、补充文档、cron、webhook 并保存。预期：字段路径更清晰，保存路径不比当前版本明显更长。

---

## 7. 异常与边界（只覆盖影响 AC 的关键异常）

- 异常/边界-1：窄屏或较小桌面宽度下访问页面。预期：导航、列表、表单和详情布局仍可用，不出现主要内容重叠或主要按钮丢失。
- 异常/边界-2：`NO_CHANGE` 与 `ERROR_CRAWL` 报告详情内容较少。预期：详情页分区仍清晰，不因内容不足导致布局空洞失衡。
- 异常/边界-3：项目表单中竞品行数较多。预期：分区设计仍支持连续录入，不因视觉分层过强导致操作变慢。
- 异常/边界-4：状态标签、长摘要、diff 内容较长。预期：组件样式与容器尺寸能稳定承载，不出现文本溢出破坏结构。

---

## 8. 风险/依赖与验证清单（可执行；所有不确定性仅写在此处）

| 风险/假设/依赖 | 验证信号（看到什么算成立/不成立） | 方法（怎么验证） | Owner | 截止 | 触发动作（成立/不成立怎么做） |
|---|---|---|---|---|---|
| V-001 品牌化导航升级后仍保持高效可达 | 5 个核心操作入口都在首屏或单次导航层级内可达 | 对 `/cockpit`、导航与首屏做任务走查 | FE | 方案评审后 2 天 | 不成立则压缩品牌区体积，提升导航主入口显著性 |
| V-002 中等密度是否仍保持后台扫描效率 | 状态、摘要、时间、操作在 10 秒内可稳定定位 | 对 `/projects`、`/monitoring`、`/monitoring/:id` 做走查 | FE | 页面实现完成后 1 天 | 不成立则提高信息密度，减少装饰性留白 |
| V-003 详情页双栏/分区布局是否稳定 | `CHANGED` / `NO_CHANGE` / `ERROR_CRAWL` 下阅读路径一致 | 构造三种详情场景做对比检查 | FE | 详情页实现完成后 1 天 | 不成立则简化为单主栏 + 次栏摘要结构 |
| V-004 LinkFox 风格是否形成统一规则而非局部模仿 | 所有核心页面都能映射到统一色板、骨架、分区规则 | 在实现前输出 token 与布局原则清单并逐页核对 | FE | 实现前 | 不成立则先补设计 token 与页面骨架规范 |
| V-005 分区表单页是否仍保持配置效率 | 创建任务流程总路径未明显变长，字段定位更清晰 | 以完整任务创建流程进行录入走查 | FE | 表单页实现完成后 1 天 | 不成立则压缩说明区与分区层级，恢复更紧凑布局 |

---

## 9. 原型产出判定（可选）

- **交互变化结论**：需要原型。原因：本次不只是换视觉，而是重构全局导航骨架、仪表盘结构、列表信息分区、详情页双栏布局和表单分区编辑结构。
- **页面与入口**：
  - `/cockpit`
  - `/projects`
  - `/projects/new`
  - `/projects/:id/edit`
  - `/monitoring`
  - `/monitoring/:id`
- **关键控件/字段与校验**：
  - 侧边导航与顶部辅助信息区
  - 项目列表卡片 / 信息分区 / 操作按钮
  - 监控列表状态表达、摘要、时间和详情入口
  - 详情页概览区、diff 区、评分反馈区
  - 项目表单中的竞品分组、文档上传、cron 配置与 webhook 区

---

## 10. 追溯链接

- [requirements/solution.md](./solution.md)：推荐决策、验证清单、Impact Analysis
- [requirements/raw.md](./raw.md)：原始需求与澄清记录
- 术语与口径：[.aisdlc/project/memory/glossary.md](/Users/melody/code/ai-workshop/.aisdlc/project/memory/glossary.md)
- 当前页面证据：
  - [frontend/src/components/common/AppShell.vue](/Users/melody/code/ai-workshop/frontend/src/components/common/AppShell.vue)
  - [frontend/src/views/dashboard/CockpitPage.vue](/Users/melody/code/ai-workshop/frontend/src/views/dashboard/CockpitPage.vue)
  - [frontend/src/views/projects/ProjectListPage.vue](/Users/melody/code/ai-workshop/frontend/src/views/projects/ProjectListPage.vue)
  - [frontend/src/components/projects/ProjectForm.vue](/Users/melody/code/ai-workshop/frontend/src/components/projects/ProjectForm.vue)
  - [frontend/src/views/reports/ReportListPage.vue](/Users/melody/code/ai-workshop/frontend/src/views/reports/ReportListPage.vue)
  - [frontend/src/views/reports/ReportDetailPage.vue](/Users/melody/code/ai-workshop/frontend/src/views/reports/ReportDetailPage.vue)
