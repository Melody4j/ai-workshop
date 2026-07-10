---
title: LinkFox 风格前端 UI 重构方案决策
status: draft
---

## 0. 基本信息

- 需求标识（分支 / ID）：`011-linkfox-ui-redesign`
- 作者 / 参与评审：Codex / Melody
- 状态：draft
- 最后更新：2026-07-10
- 关联链接：
  - [requirements/raw.md](./raw.md)
  - [frontend/src/router/index.ts](/Users/melody/code/ai-workshop/frontend/src/router/index.ts)
  - [frontend/src/components/common/AppShell.vue](/Users/melody/code/ai-workshop/frontend/src/components/common/AppShell.vue)
  - [frontend/src/styles/main.css](/Users/melody/code/ai-workshop/frontend/src/styles/main.css)

## 1. 结论摘要

- 一句话目标：在不改动现有业务功能、路由与 API 契约的前提下，将当前 Vue 管理台重构为高保真参考 LinkFox AI 官网视觉语言的品牌化工作台。
- 本次 In / Out 的边界：In 为前端信息架构、全局骨架、页面布局、色彩、组件视觉与交互层次重构；Out 为后端模型、接口语义、路由能力、任务执行链路与报告生成逻辑变更。
- 推荐方案：**品牌化工作台高保真重构方案**，以现有后台工作台为骨架，重构导航框架、页面层级、色板与关键页面布局，使 `/cockpit`、`/projects`、`/monitoring`、详情页和表单页形成统一的新设计语言。
- 优先验证点：`V-001`、`V-002`、`V-004`

## 2. 推荐方案

- 方案名：品牌化工作台高保真重构方案
- 主流程 / 关键机制：
  1. 保留现有路由与业务入口不变，以 [frontend/src/router/index.ts](/Users/melody/code/ai-workshop/frontend/src/router/index.ts) 为稳定信息架构边界。
  2. 重构 [frontend/src/components/common/AppShell.vue](/Users/melody/code/ai-workshop/frontend/src/components/common/AppShell.vue) 与全局样式层，建立新的品牌区、导航层级、顶部辅助区和统一页面容器。
  3. 用一套新的设计 token 重写 [frontend/src/styles/main.css](/Users/melody/code/ai-workshop/frontend/src/styles/main.css) 中的颜色、背景层次、圆角、边框、阴影、间距和状态样式。
  4. 对 `/cockpit` 保持纯工作台定位，但重构为更强层次的品牌化仪表盘；对 `/projects`、`/monitoring`、详情页、表单页允许明显重排结构。
  5. 把报告详情页重构为概览区 + 分栏正文区 + 证据区 + 反馈操作区，把项目表单重构为按配置模块分组的分区编辑页。
  6. 使用现有 Element Plus 组件和已有 API 调用层，优先重写版式、状态、视觉语义与信息排序，不引入新的业务流程。
- 关键边界/取舍：
  - 保持工作台属性：即使高保真参考 LinkFox，`/cockpit` 也不能变成营销首页，详情页也不能演变为展示型沉浸页面。
  - 保持契约稳定：不修改项目 CRUD、报告查看、评分、下载、执行等接口行为，只调整前端展示与交互组织方式。
  - 中等密度优先：避免当前后台过于朴素，也避免官网化留白过大导致扫描效率下降。
  - 导航品牌化但不去侧栏：允许增加品牌区和顶部辅助信息，但仍以侧边导航为主，不改成完全不同的导航范式。
  - 页面统一升级：没有“必须保守”的核心页面，因此采用统一设计语言替代局部补丁式修修补补。
- 为什么选它：
  - `raw.md` 中已明确裁决需要高保真参考 LinkFox 官网，同时又多次强调保留后台工作台效率；该方案是唯一同时满足两者的折中解。见 [requirements/raw.md](./raw.md)。
  - 当前前端整体样式高度依赖单一黑白主题，层级、品牌区分和页面骨架都较弱，适合做一轮系统性重构，而不是局部皮肤替换。见 [frontend/src/styles/main.css](/Users/melody/code/ai-workshop/frontend/src/styles/main.css) 与 [frontend/src/components/common/AppShell.vue](/Users/melody/code/ai-workshop/frontend/src/components/common/AppShell.vue)。
  - 业务边界文档要求保留任务 CRUD、报告查看、评分 CRUD 和前后端分离工作台骨架，这与“只改 UI 层，不改业务功能”的方案天然一致。见 [.aisdlc/project/memory/product.md](/Users/melody/code/ai-workshop/.aisdlc/project/memory/product.md)。

## 3. 备选方案

### 3.1 备选方案：视觉换肤保守方案

- 核心机制：保留现有页面结构与组件编排，仅更换色板、字重、圆角和部分卡片样式。
- 主流程：
  1. 修改全局 token。
  2. 小幅调整侧栏和页面标题区。
  3. 保留现有卡片网格、表格、表单结构。
  4. 用新按钮、标签和背景色覆盖旧样式。
- 边界与取舍：
  - 风险小，交付快。
  - 页面信息结构和导航骨架几乎不变。
  - 无法真正体现高保真参考站点的布局语言。
- 适用前提：
  - 用户要求“只换颜色，不动结构”。
  - 实施时间极短，只允许低风险 UI 更新。
- 不选原因：已明确允许多数页面做明显结构重排，也没有必须保守的页面；仅换肤达不到这次重构目标。

### 3.2 备选方案：官网化展示主导方案

- 核心机制：把管理台大量页面改造成更接近官网首页的展示结构，强化 hero、品牌内容区、沉浸布局与低密度排版。
- 主流程：
  1. 重做全局导航与首屏结构。
  2. 将 `/cockpit` 改为品牌首页式信息编排。
  3. 列表页和详情页进一步视觉化与低密度化。
  4. 弱化后台表格和表单的传统工作台体验。
- 边界与取舍：
  - 品牌表达最强。
  - 视觉冲击最好。
  - 高概率损失扫描效率和配置效率。
- 适用前提：
  - 用户更重视对外展示而不是内部工作台效率。
  - 产品目标转向展示型产品控制台。
- 不选原因：用户已经明确要求 `/cockpit` 保持纯工作台首页，信息密度采用中等密度，详情页和表单页都不走沉浸式展示路线。

### 3.3 备选方案：分阶段页面分批重构方案

- 核心机制：先重构 `/cockpit` 和导航，再逐步重构项目、监控、详情、表单页。
- 主流程：
  1. 第一阶段重构全局骨架与仪表盘。
  2. 第二阶段改造列表页。
  3. 第三阶段改造详情页和表单页。
  4. 多阶段保持旧新样式并存。
- 边界与取舍：
  - 风险可控，回滚简单。
  - 容易出现一段时间内风格不统一。
  - 需要额外处理新旧样式共存成本。
- 适用前提：
  - 需要非常细粒度发布或跨多个迭代上线。
  - 团队无法接受一次性前端视觉整体替换。
- 不选原因：本次需求强调统一设计语言和整体一致性，且没有被标记为需要保守处理的页面，更适合直接走系统性重构。

## 4. 决策依据

- `requirements/raw.md` 引用点位：
  - “全面参考 LinkFox AI 官网首页的 UI 设计和布局，重构当前前端的整体视觉风格、页面布局和配色体系”
  - “在不破坏现有业务功能、路由和数据接口的前提下，完成前端 UI 层重构”
  - 澄清记录中的关键决策：
    - 参考强度：B（高保真参考）
    - `/cockpit` 首页形态：A（纯工作台首页）
    - 颜色改造幅度：B（整体换成接近 LinkFox 的色彩体系）
    - 其他页面版式改造：B（允许明显重排结构）
    - 全局导航改造：B（品牌化升级，但仍以侧边导航为主）
    - 信息密度：B（中等密度）
    - 无必须保守页面
    - 报告详情页：B（双栏 / 分区布局）
    - 项目表单页：B（分区编辑页）
- 数据/约束来源：
  - [.aisdlc/project/memory/product.md](/Users/melody/code/ai-workshop/.aisdlc/project/memory/product.md)
  - [.aisdlc/project/components/index.md](/Users/melody/code/ai-workshop/.aisdlc/project/components/index.md)
  - [frontend/src/router/index.ts](/Users/melody/code/ai-workshop/frontend/src/router/index.ts)
  - [frontend/src/views/dashboard/CockpitPage.vue](/Users/melody/code/ai-workshop/frontend/src/views/dashboard/CockpitPage.vue)
  - [frontend/src/views/projects/ProjectListPage.vue](/Users/melody/code/ai-workshop/frontend/src/views/projects/ProjectListPage.vue)
  - [frontend/src/views/reports/ReportDetailPage.vue](/Users/melody/code/ai-workshop/frontend/src/views/reports/ReportDetailPage.vue)
- 若缺少证据：见 “验证清单”中的 `V-004`、`V-005`

## 5. 验证清单

- V-001 导航与首屏品牌化升级是否仍保持高效可达
  - 风险/假设：品牌区与新增顶部辅助区可能削弱用户对主要任务入口的识别速度。
  - 方法：完成高保真稿或实现后，使用现有用户任务流做 5 个关键操作走查：进入仪表盘、进入项目管理、创建任务、查看监控、查看详情；记录首屏完成路径和点击层级。
  - 成功/失败信号：5 个关键操作在首屏或单次导航层级内可达且路径更清晰为成立；若出现入口被遮蔽、理解成本明显上升则不成立。
  - Owner：Design + FE
  - 截止：方案评审后 2 天
  - 触发动作：不成立则缩减品牌区体积，优先恢复侧栏与一级操作入口显著性。

- V-002 中等密度改造后是否仍具备后台扫描效率
  - 风险/假设：新样式可能因为卡片化、留白增加而降低列表和详情页的快速扫描能力。
  - 方法：对 `/projects`、`/monitoring`、`/monitoring/:id` 做任务型走查，检查用户是否能在 10 秒内定位状态、时间、操作按钮和主要摘要。
  - 成功/失败信号：任务型走查中关键信息定位稳定且不比当前版本更慢为成立；若多处需要滚动或二次查找才能定位核心信息则不成立。
  - Owner：FE
  - 截止：页面实现完成后 1 天
  - 触发动作：不成立则提高表格/摘要信息密度，压缩装饰性留白与非必要品牌层。

- V-003 详情页双栏布局是否改善阅读与反馈效率
  - 风险/假设：双栏布局可能在不同状态（CHANGED / NO_CHANGE / ERROR_CRAWL）下出现内容割裂或移动端阅读困难。
  - 方法：分别以三种状态构造详情页场景，检查概览区、正文区、diff 区和评分区的阅读顺序与操作顺序。
  - 成功/失败信号：不同状态下都能形成稳定阅读路径且评分/下载/预览操作清晰为成立；若某一状态出现强烈布局断裂则不成立。
  - Owner：FE
  - 截止：详情页实现完成后 1 天
  - 触发动作：不成立则退回单主栏 + 次栏摘要的简化结构。

- V-004 LinkFox 视觉参考是否足够一致且未流于局部模仿
  - 风险/假设：若没有清晰设计 token 和骨架原则，最终可能只形成散乱的局部借鉴。
  - 方法：在实现前输出一份设计原则清单，明确色板、背景层、标题层级、导航骨架、卡片语义、按钮语义和分区规则，并对照各页面检查覆盖情况。
  - 成功/失败信号：所有核心页面均能映射到统一规则集为成立；若页面间仍各自为战则不成立。
  - Owner：FE
  - 截止：方案进入实现前
  - 触发动作：不成立则先补统一设计 token 与页面骨架规范，再开始页面改造。

- V-005 项目表单分区编辑页是否仍保持配置效率
  - 风险/假设：表单分区与说明性增强可能增加填写路径长度，拖慢高频配置。
  - 方法：以“创建一个包含 crawl_hint、补充文档、cron 和 webhook 的任务”为基准流程，记录字段查找、填写与提交路径。
  - 成功/失败信号：字段路径更清晰且总流程不明显变长为成立；若录入链路明显更重则不成立。
  - Owner：FE
  - 截止：表单页实现完成后 1 天
  - 触发动作：不成立则减少说明块体积，恢复更紧凑的输入布局。

## 6. 迭代记录

- 2026-07-10：基于 raw 需求与多轮裁决，明确本次为高保真参考 LinkFox 的品牌化工作台重构；补齐了导航、色彩、信息密度、详情页与表单页的关键边界，并产出推荐方案、备选方案和验证清单。

## 7. Impact Analysis

### 7.1 受影响模块

| 模块 | 影响类型 | 关键不变量 | stale? |
|------|----------|-----------|--------|
| frontend-console | 页面骨架重构、设计 token 重构、页面布局重构 | 必须保留任务 CRUD、报告列表/详情、评分 CRUD 的前端消费入口，不得改掉现有核心工作台能力（来源：`.aisdlc/project/memory/product.md`） | yes |
| intelligence-api | 只读消费契约稳定性校验 | 前端允许重构 UI，但不应变更现有项目、报告、评分接口的语义与调用方式（来源：`.aisdlc/project/memory/product.md` 与现有 `frontend/src/api/*.ts`） | no |
| report-service | 报告预览与下载入口继续可见 | 详情页重构不能破坏 HTML 预览、MD 下载、评分等既有阅读/反馈路径（来源：`frontend/src/views/reports/ReportDetailPage.vue`） | no |

### 7.2 需遵守的不变量

- 保留任务 CRUD、报告列表 / 详情查看、评分 CRUD 和前后端分离的产品管理台骨架（来源：[.aisdlc/project/memory/product.md](/Users/melody/code/ai-workshop/.aisdlc/project/memory/product.md)）。
- 路由入口继续覆盖 `/cockpit`、`/projects`、`/projects/new`、`/projects/:id/edit`、`/monitoring`、`/monitoring/:id`，不在本次需求中引入新的业务路由语义（来源：[frontend/src/router/index.ts](/Users/melody/code/ai-workshop/frontend/src/router/index.ts)）。
- 评分、报告预览、MD 下载、项目启停、立即执行等用户操作必须继续保留（来源：[frontend/src/views/reports/ReportDetailPage.vue](/Users/melody/code/ai-workshop/frontend/src/views/reports/ReportDetailPage.vue) 与 [frontend/src/views/projects/ProjectListPage.vue](/Users/melody/code/ai-workshop/frontend/src/views/projects/ProjectListPage.vue)）。

### 7.3 跨模块影响

- 改 `AppShell` 与全局 token → 需要同步检查所有页面标题区、卡片、按钮、表格、表单与空状态，否则会出现新旧视觉骨架混杂。
- 改 `/monitoring/:id` 详情结构 → 需要同时关注评分组件、diff 展示区、报告预览 iframe 与下载按钮的布局适配。
- 改项目表单页分区结构 → 需要同步关注 `ProjectForm.vue` 中竞争对手列表、补充文档上传、cron 配置器与 webhook 输入区的节奏关系。

### 7.4 Context Gaps

- `CONTEXT GAP`：`.aisdlc/project/components/` 中没有 `frontend-console` 的独立模块页，当前只能从代码和 products/index 反推前端边界。→ 建议动作：后续 merge-back 前补齐 `frontend-console` 模块页或以 Delta Discover 形式补前端模块 SSOT。
- `CONTEXT GAP`：项目知识库中没有现成的品牌设计 token、页面骨架规范或 LinkFox 对标拆解文档。→ 建议动作：在实现前先补一页前端设计原则或在 implementation/plan 中固化设计 token 与布局规则。

