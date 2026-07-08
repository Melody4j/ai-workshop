# report-service

## Module

- 服务入口：[backend/apps/intelligence/services/report_service.py](../../../backend/apps/intelligence/services/report_service.py)
- 模板目录：[backend/apps/intelligence/templates/](../../../backend/apps/intelligence/templates/)

## Service Contract

### 渲染函数

1. **render_html(feed) → str**：Jinja2 渲染 HTML 报告，返回文件绝对路径
2. **render_md(feed) → str**：Jinja2 渲染 MD 表格报告，返回文件绝对路径

### Invariants

1. Jinja2 离线渲染 HTML + MD 报告（模板：`report.html` / `report.md`）
2. 渲染后路径回写 `IntelligenceFeed.html_report_path` / `md_table_path`
3. 渲染失败不中断主流程（scheduler try-except 隔离）
4. 报告产物存储在 `data/reports/` 目录

### Evidence

- [backend/apps/intelligence/services/report_service.py](../../../backend/apps/intelligence/services/report_service.py)
- [backend/apps/intelligence/templates/report.html](../../../backend/apps/intelligence/templates/report.html)
- [backend/apps/intelligence/templates/report.md](../../../backend/apps/intelligence/templates/report.md)
- [backend/apps/intelligence/tests/test_report_service.py](../../../backend/apps/intelligence/tests/test_report_service.py)

## Evidence Gaps

（无）
