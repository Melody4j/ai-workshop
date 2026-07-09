---
title: Merge-back 清单（Spec 007）
status: done
---

# Spec 007 Merge-back 清单

> 来源：`implementation/plan.md#merge-back-待办清单` + 实现期补充项

## 晋升项汇总

| # | 类别 | project 落点 | 状态 | 代码来源 |
|---|---|---|---|---|
| MB-001 | Service Contract | `components/report-service.md` | Done | 根项目 |
| MB-002 | Service Contract | `components/frontend-console.md` | Not Done | 根项目 |
| MB-003 | API Contract | `components/intelligence-api.md` | Done | 根项目 |
| MB-004 | Registry | `index.md` | Done | 根项目 |

---

## MB-001: report-service 模板描述更新

- **project 落点**：`.aisdlc/project/components/report-service.md`
- **变更内容**：
  - HTML 报告模板从基础排版重写为商务报告风（左色边 #2c3e50 + 分级标题 #3498db + 排版留白 + 证据 Diff 红色左边框 #e74c3c + 等宽字体）
  - 模板路径修正：`backend/templates/reports/report.html.j2`（原 Evidence 引用路径 `backend/apps/intelligence/templates/report.html` 不准确）
  - 内联 CSS 自包含，无外部依赖
  - Jinja2 变量引用不变（feed.project.project_name / feed.published_at / feed.job_status / feed.change_summary / feed.strategic_intent / feed.action_suggestion / feed.evidence_diff）
- **不变量摘要**：
  1. HTML 模板为商务报告风（左色边+分级标题+排版留白+专业配色）
  2. 内联 CSS 自包含，无外部依赖
  3. 4 字段结构不变（变化摘要/战略意图/行动建议/证据Diff）
- **证据入口**：
  - `backend/templates/reports/report.html.j2`
  - `backend/apps/intelligence/tests/test_report_service.py`（5 tests OK）
- **状态**：Done

## MB-002: frontend-console 组件文档

- **project 落点**：`.aisdlc/project/components/frontend-console.md`（尚未建立）
- **变更内容**：
  - ReportDetailPage.vue：删除 PDF 预览，新增 HTML iframe 预览（`/api/feeds/{id}/preview_html`）+ 新窗口打开（`/view/html/{id}`）+ 后端端点 MD 下载，移除文件路径展示
  - ProjectListPage.vue：停用按钮改为 el-switch 启停开关（PATCH `{is_active}` 统一切换），支持直接启停
  - API 层新增：`toggleProjectActive()` / `downloadReportMd()` / `getReportHtmlPreviewUrl()`
- **状态**：Not Done — `frontend-console.md` 组件文档尚未建立
- **计划**：待 frontend-console 组件文档建立时，一并补入 ReportDetailPage 和 ProjectListPage 的页面结构与 API 调用入口

## MB-003: intelligence-api 契约更新

- **project 落点**：`.aisdlc/project/components/intelligence-api.md`
- **变更内容**：
  - `FeedHtmlPreviewView` 添加 `@xframe_options_exempt` 装饰器，豁免 Django 默认 `X-Frame-Options: DENY` 限制，允许 iframe 嵌入预览
  - `PATCH /api/projects/{id}` 正式作为任务启停的统一切换端点（前端已从 DELETE 改为 PATCH `{is_active: true/false}`）
- **不变量摘要**：
  1. `FeedHtmlPreviewView`（`/api/feeds/{id}/preview_html` 和 `/view/html/{id}`）豁免 X-Frame-Options，允许同源 iframe 嵌入
  2. 任务启停统一使用 `PATCH /api/projects/{id}` + `{is_active}`，DELETE 保留给 Admin 使用
- **证据入口**：
  - `backend/apps/intelligence/views.py`（`@method_decorator(xframe_options_exempt, name="dispatch")`）
  - `frontend/src/api/projects.ts`（`toggleProjectActive`）
  - `frontend/src/api/reports.ts`（`downloadReportMd` / `getReportHtmlPreviewUrl`）
- **状态**：Done

## MB-004: Registry 更新

- **project 落点**：`.aisdlc/project/index.md`
- **变更内容**：
  - `report-service` 行 source_spec 追加 `007-ui-report-optimization`
  - `intelligence-api` 行 source_spec 追加 `007-ui-report-optimization`
  - 最近一次 merge-back 更新为 `007-ui-report-optimization`
- **状态**：Done
