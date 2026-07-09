---
title: 前端报告与任务管理优化方案决策（Solutionate）
status: draft
---

> 目的：把"推荐决策 + 备选方案对比 + 决策依据 + 验证清单"落到一份可评审文档里，作为后续 `prd.md` 与 `prototype.md` 的**唯一决策入口**。

## 0. 基本信息

- 需求标识：007-ui-report-optimization
- 作者 / 参与评审：Claude / FS
- 状态：draft
- 最后更新：2026-07-09
- 关联链接：`requirements/raw.md`（含 4 条澄清记录 R1-Q1~Q4）

## 1. 结论摘要（先给结论）

- 一句话目标：优化前端报告详情页（HTML 预览替代 PDF）、任务卡片启停操作（PATCH 统一切换）、移除多余文件路径、重新设计 HTML 报告模板为商务报告风。
- 本次 In / Out 的边界：In = 前端 Vue 组件改动 + Jinja2 HTML 模板重写 + 前端 API 调用方式调整；Out = 后端 API 新增（复用已有端点）、数据库改动、新增后端业务逻辑。
- 推荐方案：前端 4 处定向修改 + Jinja2 模板重写，零后端 API 新增（复用 PATCH + preview_html + download_md）。
- 优先验证点：V-001（iframe 跨域预览）、V-002（PATCH is_active 兼容性）、V-003（商务报告风模板视觉效果）。

## 2. 推荐方案：复用已有端点 + 前端定向重构

- 方案名：复用已有端点的前端定向重构
- 主流程 / 关键机制：
  1. **ReportDetailPage.vue 改造**：删除 PDF 预览卡片 + `downloadPdfSummary()` 函数；将"下载 MD"改为调用 `GET /api/feeds/{id}/download_md`（Blob 下载）；新增 HTML 报告 iframe 预览区（`src=/api/feeds/{id}/preview_html`，高度 600px）+ "在新窗口打开"按钮（链接 `/view/html/{id}`）；删除 `el-descriptions` 中的 `html_report_path` 和 `md_table_path` 两项。
  2. **ProjectListPage.vue 改造**：将"停用任务"按钮替换为 `el-switch` 启停开关，调用 `PATCH /api/projects/{id} {is_active: true/false}`；移除 `disableProject` (DELETE) 调用，改用 `updateProject` (PATCH)。
  3. **report.html.j2 重写**：商务报告风——左色边 + 分级标题 + 排版留白 + 专业配色；保留 4 字段结构但增加视觉层次（标题区/元信息区/正文区/证据区）；内联 CSS 保持自包含。
  4. **前端 API 层微调**：`projects.ts` 新增 `toggleProjectActive(id, is_active)` 便捷函数（内部调 `patchJson`）；`reports.ts` 新增 `downloadReportMd(id)` 和 `getReportHtmlPreviewUrl(id)` 辅助函数。
- 关键边界/取舍：
  1. **零后端 API 新增**：PATCH is_active 已可用（serializer fields 含 is_active 且非 read-only）；preview_html 和 download_md 端点已存在。不引入新端点降低复杂度。
  2. **iframe 预览而非组件内渲染**：HTML 报告是自包含 HTML 文档（含 `<html><head><body>`），无法直接用 `v-html` 渲染；iframe 是唯一安全且简单的嵌入方式。
  3. **el-switch 而非按钮对**：单一切换开关比"启动"+"停用"两个按钮更直观，且与卡片状态标签语义一致。
  4. **保留 MD 预览区**：客户端拼接的 MD 预览仍保留（快速浏览），仅下载改为后端端点（获取完整 Jinja2 渲染版本）。
- 为什么选它：
  1. 后端端点全部就绪，零后端工作量，降低交付风险（证据：`views.py` FeedHtmlPreviewView L215-237、FeedDownloadMdView L191-212；`serializers.py` is_active 在 fields 列表 L21、不在 read_only_fields L26）
  2. 前端改动范围明确（3 个 Vue 文件 + 1 个 API 文件 + 1 个 Jinja2 模板），无跨模块依赖
  3. 商务报告风模板为纯 CSS/HTML 改动，不影响 Jinja2 渲染逻辑和 report_service.py（证据：`report.html.j2` 当前为自包含内联 CSS）

## 3. 备选方案

### 3.1 备选方案：新增 toggle 专用端点

- 核心机制：后端新增 `POST /api/projects/{id}/toggle` 端点，切换 is_active 状态
- 主流程：前端调用 toggle 端点 → 后端读取当前 is_active → 取反 → 保存 → 返回新状态
- 边界与取舍：语义明确但增加后端代码；与 RESTful PATCH 语义重叠
- 适用前提：需要审计切换操作、或 PATCH 权限控制较复杂时
- 不选原因：PATCH 已支持 is_active 更新，新增端点为过度设计（证据：`serializers.py` L21 is_active 在 fields 中）

### 3.2 备选方案：HTML 报告用组件内渲染（v-html）

- 核心机制：后端返回 HTML 报告片段（非完整文档），前端用 `v-html` 渲染
- 主流程：新增 API 端点返回 HTML 片段 → 前端 v-html 渲染 → 样式由前端框架控制
- 边界与取舍：需要后端拆分模板为片段版+完整版；XSS 风险需处理
- 适用前提：需要前端完全控制报告样式、或需要交互式报告
- 不选原因：HTML 报告是自包含文档（含完整 `<html>` 结构），拆分为片段增加复杂度且破坏报告独立性（证据：`report.html.j2` 包含完整 DOCTYPE + html + head + body）

### 3.3 备选方案：卡片用按钮对（启动+停用）

- 核心机制：卡片上根据 is_active 状态显示"启用"或"停用"按钮
- 主流程：is_active=true → 显示"停用"按钮 → 点击 PATCH {is_active: false}；is_active=false → 显示"启用"按钮 → 点击 PATCH {is_active: true}
- 边界与取舍：两个互斥按钮 vs 一个开关；占用更多卡片空间
- 适用前提：需要更明确的操作语义、或按钮需要携带确认弹窗
- 不选原因：el-switch 更紧凑直观，且与卡片已有状态标签语义一致（证据：`ProjectListPage.vue` L98-100 已有 is_active 状态标签）

## 4. 决策依据（证据入口清单）

- `raw.md` 需求 1：任务报告详情页缺少 HTML 在线预览，PDF 预览多余 → 删除 PDF + 新增 iframe 预览
- `raw.md` 需求 2：任务卡片需直接启动/停用 → el-switch + PATCH 统一切换
- `raw.md` 需求 3：执行详情页 HTML/MD 文件路径多余 → 移除 el-descriptions 中的路径项
- `raw.md` 需求 4：HTML 报告排版不精美、内容空泛 → 商务报告风重写模板
- `raw.md` R1-Q1 澄清：商务报告风（左色边+分级标题+排版留白+专业感）
- `raw.md` R1-Q2 澄清：PATCH 统一切换（不用 DELETE）
- `raw.md` R1-Q3 澄清：内嵌 iframe + 新窗口打开按钮
- `raw.md` R1-Q4 澄清：MD 下载改为后端端点
- 代码证据：
  - `serializers.py` L21: `is_active` 在 fields 列表中
  - `serializers.py` L26: `is_active` 不在 `read_only_fields` 中
  - `views.py` L215-237: `FeedHtmlPreviewView` 已存在
  - `views.py` L191-212: `FeedDownloadMdView` 已存在
  - `projects.ts` L46-48: `updateProject` (PATCH) 已存在
  - `report.html.j2`: 当前模板为自包含内联 CSS

## 5. 验证清单（V-xxx，可执行）

- V-001：iframe 跨域预览兼容性
  - 风险/假设：iframe 嵌入 `/api/feeds/{id}/preview_html` 可能因 X-Frame-Options 或 CSP 被浏览器拦截
  - 方法：在开发环境用 Chrome/Safari/Firefox 打开详情页，检查 iframe 是否正常渲染 HTML 报告
  - 成功/失败信号：iframe 内显示完整 HTML 报告内容为成功；显示空白或错误页为失败
  - Owner：DEV
  - 截止：实现后 1 天
  - 触发动作：失败则检查 Django 中间件 X-Frame-Options 设置，必要时调整为 SAMEORIGIN

- V-002：PATCH is_active 兼容性
  - 风险/假设：PATCH /api/projects/{id} {is_active: false} 可能因 serializer validate() 拦截（如 competitor_contexts 校验）
  - 方法：在开发环境用 curl 发送 `PATCH /api/projects/1 -d '{"is_active": false}'`，检查返回 200 且 is_active 已变更
  - 成功/失败信号：HTTP 200 + response.is_active == false 为成功；400/500 为失败
  - Owner：DEV
  - 截止：实现后 1 天
  - 触发动作：失败则检查 serializer.validate() 是否对 partial update 做了过严校验，必要时在 validate() 中跳过 partial update 的字段一致性检查

- V-003：商务报告风模板视觉效果
  - 风险/假设：重新设计的 HTML 模板可能在不同浏览器下排版不一致，或信息密度不满足用户预期
  - 方法：用已有 CHANGED feed 数据渲染 HTML 报告，在 Chrome/Safari 打开检查排版、留白、色边、字体层次
  - 成功/失败信号：左色边+分级标题清晰可见、4 字段信息层次分明、排版留白适中为成功；字段堆叠无层次或过于拥挤/空泛为失败
  - Owner：DEV + FS
  - 截止：实现后 2 天
  - 触发动作：失败则根据 FS 反馈调整 CSS（间距/配色/字号）

- V-004：MD 下载端点文件名正确性
  - 风险/假设：后端 Content-Disposition 中的文件名可能含中文或特殊字符导致浏览器解析异常
  - 方法：点击"下载 MD"按钮，检查下载的文件名和内容
  - 成功/失败信号：文件名合理（如 `1.md` 或含项目名）、内容为 Jinja2 渲染的完整 MD 为成功；文件名乱码或内容为空为失败
  - Owner：DEV
  - 截止：实现后 1 天
  - 触发动作：失败则检查 `FeedDownloadMdView` 的 Content-Disposition header 编码

## 6. 迭代记录

- 2026-07-09：初始版本。基于 raw.md 4 条需求 + 4 条澄清记录（R1-Q1~Q4），产出推荐方案（复用已有端点 + 前端定向重构）+ 3 个备选方案 + 4 条验证清单。

## 7. Impact Analysis

### 7.1 受影响模块

| 模块 | 影响类型 | 关键不变量 | stale? |
|------|----------|-----------|--------|
| frontend-console | 修改 UI 组件 | ReportDetailPage.vue 删除 PDF + 新增 HTML iframe；ProjectListPage.vue 替换 DELETE 为 PATCH toggle | no |
| report-service | 修改渲染模板 | report.html.j2 重写为商务报告风；report_service.py 渲染逻辑不变 | no |
| intelligence-api | 仅读取（无修改） | PATCH /api/projects/{id} 已支持 is_active；preview_html / download_md 端点已存在 | no |

### 7.2 需遵守的不变量

- 收件箱仅展示 `job_status=CHANGED`（来源：CLAUDE.md 不变量 6）→ iframe 预览仅对 CHANGED feed 展示
- 情报输出固定 4 字段（来源：CLAUDE.md 不变量 4）→ HTML 模板保留 4 字段结构，不新增字段
- `competitor_urls` 必须为 JSON 数组（来源：CLAUDE.md 不变量 10）→ PATCH is_active 不涉及 competitor_urls，无冲突

### 7.3 跨模块影响

- 改了 `report.html.j2` → 需关注 `report_service.py`（渲染逻辑引用模板文件，模板路径不变，无代码改动）
- 改了 `ProjectListPage.vue`（DELETE → PATCH）→ 需关注 `ProjectDetailView.perform_destroy`（DELETE 软删除逻辑保留但前端不再调用，不影响 Admin 后台的 DELETE 操作）
- 改了 `ReportDetailPage.vue`（新增 iframe）→ 需关注 `FeedHtmlPreviewView`（已有端点，无改动）

### 7.4 Context Gaps

- `CONTEXT GAP`：`.aisdlc/project/components/frontend-console.md` 未建立模块页 → 当前只能从代码直接分析影响面。建议动作：后续按需补齐 Delta Discover。
- `CONTEXT GAP`：`.aisdlc/project/components/report-service.md` 已有但可能 stale（Spec 004 之后未更新）→ 建议动作：实现完成后更新模块页中模板相关的描述。

## 8. Mini-PRD

- **MVP 范围**：
  - In：
    1. ReportDetailPage.vue：删除 PDF 预览卡片 + downloadPdfSummary()；新增 HTML iframe 预览区 + "新窗口打开"按钮；"下载 MD"改为调用后端端点；移除 el-descriptions 中 html_report_path 和 md_table_path
    2. ProjectListPage.vue：将"停用任务"按钮替换为 el-switch 启停开关，调用 PATCH {is_active}
    3. report.html.j2：商务报告风重写（左色边+分级标题+排版留白+专业配色）
    4. projects.ts：新增 toggleProjectActive() 便捷函数
    5. reports.ts：新增 downloadReportMd() 和 getReportHtmlPreviewUrl() 辅助函数
  - Out：
    - 后端 API 新增或修改
    - 数据库改动
    - DELETE 端点移除（保留给 Admin 使用）
    - 新增报告字段

- **验收标准（AC）**：
  1. AC-001：ReportDetailPage 无 PDF 预览卡片和"下载 PDF"按钮
  2. AC-002：ReportDetailPage 有 HTML 报告 iframe 预览区，CHANGED 状态下显示报告内容
  3. AC-003：ReportDetailPage 有"在新窗口打开"按钮，点击跳转 `/view/html/{id}`
  4. AC-004：点击"下载 MD"按钮下载的文件内容为后端 Jinja2 渲染的 MD（非前端拼接）
  5. AC-005：ReportDetailPage 的 el-descriptions 不再显示 html_report_path 和 md_table_path
  6. AC-006：ProjectListPage 卡片有启停开关（el-switch），切换后立即调用 PATCH 并刷新列表
  7. AC-007：停用的项目可通过开关重新启用，无需进入编辑页
  8. AC-008：HTML 报告模板为商务报告风（左色边+分级标题+排版留白），4 字段信息层次分明
  9. AC-009：现有测试全部通过（133+ tests），前端 build 成功

- **交互变化结论**：有但简单。
  1. ReportDetailPage：PDF 卡片 → HTML iframe 卡片（位置不变，右侧列替换）
  2. ProjectListPage：文字按钮 → 开关组件（同一位置，交互更直接）
  3. 详情页 el-descriptions 从 4 项减为 2 项（移除文件路径，保留发布时间和反馈状态）

- **影响面**：
  - 页面：`/monitoring/:id`（ReportDetailPage）、`/projects`（ProjectListPage）
  - 接口：`GET /api/feeds/{id}/preview_html`（已有，前端新调用）、`GET /api/feeds/{id}/download_md`（已有，前端新调用）、`PATCH /api/projects/{id}`（已有，前端新调用）
  - 模板：`backend/templates/reports/report.html.j2`（重写）
