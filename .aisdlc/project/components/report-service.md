# report-service

## Module

- 服务入口：[backend/apps/intelligence/services/report_service.py](../../../backend/apps/intelligence/services/report_service.py)
- 模板目录：[backend/templates/reports/](../../../backend/templates/reports/)

## Service Contract

### 渲染函数

1. **render_html(feed) → str**：Jinja2 渲染 HTML 报告，返回文件绝对路径
2. **render_md(feed) → str**：Jinja2 渲染 MD 表格报告，返回文件绝对路径

### Invariants

1. Jinja2 离线渲染 HTML + MD 报告（模板：`report.html.j2` / `report.md.j2`）
2. HTML 模板为商务报告风（左色边 #2c3e50 + 分级标题 #3498db + 证据 Diff 红色左边框 #e74c3c + 内联 CSS 自包含，无外部依赖）（来源：Spec 007）
3. 渲染后路径回写 `IntelligenceFeed.html_report_path` / `md_table_path`
4. 渲染失败不中断主流程（scheduler try-except 隔离）
5. 报告产物存储在 `data/reports/` 目录

### Evidence

- [backend/apps/intelligence/services/report_service.py](../../../backend/apps/intelligence/services/report_service.py)
- [backend/templates/reports/report.html.j2](../../../backend/templates/reports/report.html.j2)
- [backend/templates/reports/report.md.j2](../../../backend/templates/reports/report.md.j2)
- [backend/apps/intelligence/tests/test_report_service.py](../../../backend/apps/intelligence/tests/test_report_service.py)

## Evidence Gaps

（无）
