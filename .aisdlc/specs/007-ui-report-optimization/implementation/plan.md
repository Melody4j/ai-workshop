---
title: I1 Implementation Plan（SSOT）
status: draft
---

# 前端报告与任务管理优化 实现计划（SSOT）

> **必需技能：** `spec-execute`（按批次执行本计划）
> **上下文获取：** 必须先执行 `spec-context` 获取上下文，定位 `{FEATURE_DIR}`，失败即停止

**目标：** 优化前端报告详情页（HTML iframe 预览替代 PDF）、任务卡片启停操作（PATCH 统一切换）、移除多余文件路径、重新设计 HTML 报告模板为商务报告风。
**范围：** In = 前端 Vue 组件改动 + Jinja2 HTML 模板重写 + 前端 API 调用方式调整；Out = 后端 API 新增、数据库改动、新增后端业务逻辑。
**架构：** 复用已有后端端点（PATCH /api/projects/{id}、GET /api/feeds/{id}/preview_html、GET /api/feeds/{id}/download_md），前端定向重构 3 个 Vue 组件 + 1 个 API 文件 + 1 个 Jinja2 模板。零后端代码改动。
**验收口径：** `requirements/solution.md` Mini-PRD AC-001~AC-009。
**影响范围：** `requirements/solution.md#impact-analysis` → frontend-console（修改 UI）、report-service（修改渲染模板）、intelligence-api（仅读取）。
**需遵守的不变量：** 收件箱仅展示 CHANGED（不变量 6）；情报输出固定 4 字段（不变量 4）；competitor_urls JSON 数组（不变量 10）。
**子仓范围：** 无（仓库不含 `.gitmodules`）。

---

## TL;DR

- 一句话目标：前端 4 处 UI 优化 + Jinja2 模板重写，零后端改动。
- In：ReportDetailPage.vue（删 PDF + 加 iframe + 改 MD 下载 + 删路径）、ProjectListPage.vue（DELETE → PATCH el-switch）、report.html.j2（商务报告风重写）、projects.ts + reports.ts（新增辅助函数）。
- Out：后端 API 新增/修改、数据库改动、DELETE 端点移除。
- 关键路径：T1（API 层）→ T2（ReportDetailPage）→ T3（ProjectListPage）→ T4（HTML 模板）→ T5（测试验证）。
- 最大风险与优先验证点：V-001（iframe X-Frame-Options）、V-002（PATCH partial update 兼容性）。

---

## 范围与边界（In / Out）

- **In**：
  1. `frontend/src/views/reports/ReportDetailPage.vue`：删除 PDF 预览卡片 + `downloadPdfSummary()`；新增 HTML iframe 预览区 + "新窗口打开"按钮；"下载 MD"改为后端端点；移除 el-descriptions 中 html_report_path 和 md_table_path。
  2. `frontend/src/views/projects/ProjectListPage.vue`：将"停用任务"按钮替换为 el-switch 启停开关，调用 PATCH {is_active}。
  3. `backend/templates/reports/report.html.j2`：商务报告风重写（左色边+分级标题+排版留白+专业配色）。
  4. `frontend/src/api/projects.ts`：新增 `toggleProjectActive(id, is_active)` 便捷函数。
  5. `frontend/src/api/reports.ts`：新增 `downloadReportMd(id)` 和 `getReportHtmlPreviewUrl(id)` 辅助函数。
- **Out**：
  - 后端 API 新增或修改（views.py / serializers.py / urls.py 不改动）
  - 数据库改动 / migration
  - DELETE 端点移除（保留给 Admin 使用）
  - 新增报告字段
- **不变量/关键约束**：
  - iframe 预览仅对 CHANGED 状态 feed 展示（不变量 6）
  - HTML 模板保留 4 字段结构，不新增字段（不变量 4）
  - PATCH is_active 不涉及 competitor_urls 校验（不变量 10 无冲突）
- **影响面**：页面 `/monitoring/:id`、`/projects`；接口 PATCH /api/projects/{id}（已有）、GET /api/feeds/{id}/preview_html（已有）、GET /api/feeds/{id}/download_md（已有）；模板 report.html.j2（重写）。

## 代码工作区清单

无（仓库不含 `.gitmodules`）。

---

## 里程碑与节奏

- M0（MVP）：全部 5 个任务完成，测试通过，前端 build 成功。
  - 验收：AC-001~AC-009 全部满足；133+ 后端测试通过；`npm run build` 成功。

---

## 依赖与资源

- 环境/权限：开发环境（Django + Vite），无需外部权限。
- 外部系统/团队：无。
- 数据/样本：至少 1 条 CHANGED 状态的 IntelligenceFeed 数据用于验证 iframe 预览。
- 发布/变更窗口：无限制。

---

## 风险与验证

| # | 风险/假设 | 验证方式 | 成功信号 | 失败信号 | Owner | 截止 | 下一步动作 |
|---|---|---|---|---|---|---|---|
| R1 | iframe 被 X-Frame-Options 拦截 | 开发环境打开详情页检查 iframe | iframe 显示报告内容 | iframe 空白 | DEV | T2 完成后 | 调整 Django X-Frame-Options 为 SAMEORIGIN |
| R2 | PATCH partial update 被 serializer validate() 拦截 | curl PATCH {is_active: false} | HTTP 200 + is_active 变更 | HTTP 400/500 | DEV | T3 完成后 | 在 validate() 中跳过 partial update 的字段一致性检查 |
| R3 | 商务报告风模板视觉效果不达标 | FS 人工审查渲染报告 | 左色边+分级标题清晰、层次分明 | 过于拥挤或空泛 | DEV+FS | T4 完成后 | 根据 FS 反馈调整 CSS |

---

## 验收口径（可追溯）

- 追溯：`requirements/solution.md` Mini-PRD AC-001~AC-009。
- 关键验收点：
  - AC-001：ReportDetailPage 无 PDF 预览卡片和"下载 PDF"按钮
  - AC-002：ReportDetailPage 有 HTML iframe 预览区，CHANGED 状态下显示报告
  - AC-003：ReportDetailPage 有"在新窗口打开"按钮，跳转 /view/html/{id}
  - AC-004：点击"下载 MD"下载后端 Jinja2 渲染的 MD（非前端拼接）
  - AC-005：el-descriptions 不再显示 html_report_path 和 md_table_path
  - AC-006：卡片有 el-switch 启停开关，切换后 PATCH 并刷新列表
  - AC-007：停用项目可通过开关重新启用
  - AC-008：HTML 报告模板为商务报告风（左色边+分级标题+排版留白）
  - AC-009：133+ 后端测试通过，前端 build 成功

---

## NEEDS CLARIFICATION

无。所有需求已在 R1 澄清中解决（R1-Q1~Q4），无遗留不确定项。

---

## 任务清单（SSOT）

### Task T1: 前端 API 层新增辅助函数

- [ ] **状态**：未开始

**代码仓范围：**
- 根项目：`/Users/melody/code/ai-workshop-007`

**文件：**
- 修改：`frontend/src/api/projects.ts`
- 修改：`frontend/src/api/reports.ts`

**验收点：**
- `projects.ts` 导出 `toggleProjectActive(id: number, is_active: boolean): Promise<Project>`
- `reports.ts` 导出 `downloadReportMd(id: number): Promise<Blob>`
- `reports.ts` 导出 `getReportHtmlPreviewUrl(id: number): string`
- TypeScript 编译无错误

**步骤 1：修改 `projects.ts`**
- 在 `disableProject` 函数后新增：
```typescript
export function toggleProjectActive(id: number, is_active: boolean): Promise<Project> {
  return patchJson<Project>(`/api/projects/${id}`, { is_active })
}
```

**步骤 2：修改 `reports.ts`**
- 在文件末尾新增：
```typescript
export function downloadReportMd(id: number): Promise<Blob> {
  return fetch(`/api/feeds/${id}/download_md`).then((res) => {
    if (!res.ok) throw new Error("MD 下载失败")
    return res.blob()
  })
}

export function getReportHtmlPreviewUrl(id: number): string {
  return `/api/feeds/${id}/preview_html`
}
```

**步骤 3：运行验证**
- Run: `cd /Users/melody/code/ai-workshop-007/frontend && npx tsc --noEmit 2>&1 | head -20`
- Expected: 无错误输出

**步骤 4：提交**
- Commit message: `feat: 前端 API 层新增 toggleProjectActive / downloadReportMd / getReportHtmlPreviewUrl 辅助函数`
- 审计信息：
  - repo: `root`
    branch: `007-ui-report-optimization`
    commit: `<TBD>`
    pr: `<TBD>`
    changed_files:
      - `frontend/src/api/projects.ts`
      - `frontend/src/api/reports.ts`

---

### Task T2: ReportDetailPage.vue 改造（删 PDF + 加 iframe + 改 MD 下载 + 删路径）

- [ ] **状态**：未开始

**代码仓范围：**
- 根项目：`/Users/melody/code/ai-workshop-007`

**文件：**
- 修改：`frontend/src/views/reports/ReportDetailPage.vue`

**验收点：**
- 无 PDF 预览卡片和"下载 PDF"按钮（AC-001）
- 有 HTML iframe 预览区，CHANGED 状态下 src 指向 `/api/feeds/{id}/preview_html`（AC-002）
- 有"在新窗口打开"按钮，链接 `/view/html/{id}`（AC-003）
- "下载 MD"按钮调用 `downloadReportMd(id)` 下载 Blob（AC-004）
- el-descriptions 无 html_report_path 和 md_table_path（AC-005）
- `downloadPdfSummary()` 函数和 `markdownPreview` computed 均已删除

**步骤 1：删除 PDF 相关代码**
- 删除 `downloadPdfSummary()` 函数（L49-93）
- 删除 PDF 预览卡片（L179-196 el-col 第二列）
- 删除 `markdownPreview` computed（L15-35）

**步骤 2：修改 MD 下载函数**
- 将 `downloadMarkdown()` 改为调用 `downloadReportMd(report.value.id)`，Blob 下载，文件名从 Content-Disposition 获取或默认 `{id}.md`
- import `downloadReportMd` from `../../api/reports`

**步骤 3：新增 HTML iframe 预览区**
- 在 MD 预览卡片下方（原 PDF 卡片位置）新增 HTML 预览卡片：
  - 卡片标题："HTML 报告预览"
  - iframe：`v-if="report.job_status === 'CHANGED'"`，`:src="getReportHtmlPreviewUrl(report.id)"`，高度 600px，宽度 100%，border none
  - "在新窗口打开"按钮：`<a :href="`/view/html/${report.id}`" target="_blank">`
  - "下载 MD"按钮移到此卡片头部
- import `getReportHtmlPreviewUrl` from `../../api/reports`

**步骤 4：修改 MD 预览区**
- 将 MD 预览卡片改为显示 4 字段的简单文本预览（保留 `<pre>` 但内容改为直接显示 `report.change_summary` 等字段），或直接移除 MD 预览卡片（因 iframe 已展示完整 HTML 报告）
- 推荐方案：移除 MD 预览卡片，保留 iframe + 下载按钮即可

**步骤 5：删除 el-descriptions 中的文件路径**
- 删除 `el-descriptions-item label="HTML 报告"` 和 `el-descriptions-item label="MD 报告"` 两项
- 保留"发布时间"和"反馈状态"两项

**步骤 6：运行验证**
- Run: `cd /Users/melody/code/ai-workshop-007/frontend && npm run build 2>&1 | tail -5`
- Expected: `✓ built` 无错误

**步骤 7：提交**
- Commit message: `feat: ReportDetailPage 删除 PDF 预览，新增 HTML iframe 预览，MD 下载改为后端端点，移除文件路径展示`
- 审计信息：
  - repo: `root`
    branch: `007-ui-report-optimization`
    commit: `<TBD>`
    pr: `<TBD>`
    changed_files:
      - `frontend/src/views/reports/ReportDetailPage.vue`

---

### Task T3: ProjectListPage.vue 改造（DELETE → PATCH el-switch）

- [ ] **状态**：未开始

**代码仓范围：**
- 根项目：`/Users/melody/code/ai-workshop-007`

**文件：**
- 修改：`frontend/src/views/projects/ProjectListPage.vue`

**验收点：**
- 卡片有 el-switch 启停开关（AC-006）
- 切换后调用 `toggleProjectActive(id, is_active)` 并刷新列表（AC-006）
- 停用项目可通过开关重新启用（AC-007）
- 不再调用 `disableProject` (DELETE)

**步骤 1：修改 import**
- 将 `import { disableProject, executeProject, listProjects, type Project }` 改为 `import { executeProject, listProjects, toggleProjectActive, type Project }`

**步骤 2：替换 archiveProject 函数**
- 删除 `archiveProject(id: number)` 函数
- 新增 `toggleProjectActiveHandler(project: Project)` 函数：
```typescript
async function toggleProjectActiveHandler(project: Project) {
  const newActive = !project.is_active
  try {
    await toggleProjectActive(project.id, newActive)
    ElMessage.success(newActive ? "任务已启用" : "任务已停用")
    await loadProjects()
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : "操作失败")
  }
}
```

**步骤 3：替换模板中的停用按钮**
- 将"停用任务" el-button 替换为 el-switch：
```html
<el-switch
  :model-value="project.is_active"
  @change="toggleProjectActiveHandler(project)"
  active-text="启用"
  inactive-text="停用"
  inline-prompt
/>
```

**步骤 4：运行验证**
- Run: `cd /Users/melody/code/ai-workshop-007/frontend && npm run build 2>&1 | tail -5`
- Expected: `✓ built` 无错误

**步骤 5：提交**
- Commit message: `feat: ProjectListPage 卡片停用按钮改为 el-switch 启停开关，调用 PATCH 统一切换`
- 审计信息：
  - repo: `root`
    branch: `007-ui-report-optimization`
    commit: `<TBD>`
    pr: `<TBD>`
    changed_files:
      - `frontend/src/views/projects/ProjectListPage.vue`

---

### Task T4: report.html.j2 商务报告风重写

- [ ] **状态**：未开始

**代码仓范围：**
- 根项目：`/Users/melody/code/ai-workshop-007`

**文件：**
- 修改：`backend/templates/reports/report.html.j2`

**验收点：**
- 左色边+分级标题视觉层次分明（AC-008）
- 4 字段（变化摘要/战略意图/行动建议/证据Diff）信息层次清晰
- 排版留白适中，专业配色
- 内联 CSS 自包含，无外部依赖
- Jinja2 变量引用不变（feed.project.project_name / feed.published_at / feed.job_status / feed.change_summary / feed.strategic_intent / feed.action_suggestion / feed.evidence_diff）

**步骤 1：重写 report.html.j2**
- 商务报告风设计要点：
  - 整体：白底，max-width 820px，居中，padding 40px
  - 标题区：h1 带左色边（border-left: 4px solid #2c3e50），字号 24px，深色 #1a1a1a
  - 元信息区：flex 布局，项目名/时间/状态分列，字号 13px，色 #666，底部 1px 分隔线
  - 正文区：每个字段用 `.section` 容器，h2 带 left border accent（3px solid #3498db），字号 16px，margin-top 28px
  - 段落：line-height 1.8，color #333，white-space pre-wrap
  - 证据 Diff：浅灰背景 #f8f9fa，左色边 3px solid #e74c3c，monospace 13px，padding 16px，border-radius 4px
  - 底部：版权/生成时间，字号 12px，色 #999
  - 配色方案：主色 #2c3e50（深蓝灰）、强调色 #3498db（蓝）、证据色 #e74c3c（红橙）
  - 字体：-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif

**步骤 2：运行验证**
- Run: `cd /Users/melody/code/ai-workshop-007/backend && /Users/melody/code/ai-workshop/.venv/bin/python manage.py test apps.intelligence.tests.test_report_service --verbosity=1 2>&1 | tail -5`
- Expected: 报告渲染测试通过（模板变量引用未变）
- Run: 手动渲染检查（可选）：用已有 CHANGED feed 数据渲染 HTML，在浏览器中打开检查排版

**步骤 3：提交**
- Commit message: `feat: HTML 报告模板重写为商务报告风（左色边+分级标题+排版留白+专业配色）`
- 审计信息：
  - repo: `root`
    branch: `007-ui-report-optimization`
    commit: `<TBD>`
    pr: `<TBD>`
    changed_files:
      - `backend/templates/reports/report.html.j2`

---

### Task T5: 全量测试验证 + 前端 build

- [ ] **状态**：未开始

**代码仓范围：**
- 根项目：`/Users/melody/code/ai-workshop-007`

**文件：**
- 无新增/修改文件（纯验证任务）

**验收点：**
- 133+ 后端测试全部通过（AC-009）
- 前端 build 成功（AC-009）
- Django check 无问题

**步骤 1：后端测试**
- Run: `cd /Users/melody/code/ai-workshop-007/backend && /Users/melody/code/ai-workshop/.venv/bin/python manage.py test apps.intelligence.tests --exclude-tag=e2e --verbosity=1 2>&1 | tail -5`
- Expected: `Ran 133+ tests` + `OK`

**步骤 2：Django check**
- Run: `cd /Users/melody/code/ai-workshop-007/backend && /Users/melody/code/ai-workshop/.venv/bin/python manage.py check 2>&1`
- Expected: `System check identified no issues`

**步骤 3：前端 build**
- Run: `cd /Users/melody/code/ai-workshop-007/frontend && npm run build 2>&1 | tail -5`
- Expected: `✓ built` 无错误

**步骤 4：提交（如有修复）**
- 若测试或 build 发现问题需修复，修复后提交
- Commit message: `fix: 全量验证修复`（如适用）
- 审计信息：
  - repo: `root`
    branch: `007-ui-report-optimization`
    commit: `<TBD>`
    pr: `<TBD>`
    changed_files: `<TBD>`

---

## Merge-back 待办清单

- MB-001：实现完成后，更新 `.aisdlc/project/components/report-service.md` 中模板相关描述（商务报告风重写）。
- MB-002：实现完成后，更新 `.aisdlc/project/components/frontend-console.md`（如已建立）中 ReportDetailPage 和 ProjectListPage 的描述。
