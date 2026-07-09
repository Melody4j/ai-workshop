# intelligence-api

## Module

- 代码入口：[backend/apps/intelligence/views.py](../../../backend/apps/intelligence/views.py)
- 路由入口：[backend/apps/intelligence/urls.py](../../../backend/apps/intelligence/urls.py)
- DTO / 校验入口：[backend/apps/intelligence/serializers.py](../../../backend/apps/intelligence/serializers.py)

## API Contract

- 权威入口：
  - 路由：[backend/apps/intelligence/urls.py](../../../backend/apps/intelligence/urls.py)
  - 视图：[backend/apps/intelligence/views.py](../../../backend/apps/intelligence/views.py)
  - 序列化：[backend/apps/intelligence/serializers.py](../../../backend/apps/intelligence/serializers.py)

### Invariants

1. 任务接口提供列表、创建、详情、更新、停用能力
2. 任务“删除”语义固定为停用：`DELETE /api/projects/{id}` 仅将 `is_active=false`
3. 报告接口提供列表、详情、评分 CRUD
4. 报告列表入口支持 `project` / `status` / `date_from` / `date_to` 过滤
5. 评分写入仅接受 `user_feedback=-1|1`
6. `POST /api/feeds/{id}/push`：手动触发飞书推送，非 `CHANGED` feed 返回 400（来源：Spec 005）
7. `GET /api/feeds/{id}/download_md`：返回 MD 文件下载流（`Content-Type: text/markdown`），文件不存在返回 404（来源：Spec 005）
8. 推送服务入口为 `feishu_service.push_intelligence(feed_id)`，返回 `"pushed"` / `"push_failed"` / `"skipped"` / `"skipped_no_webhook"` / `"not_found"`（来源：Spec 005）
9. `GET /view/html/{id}`：HTML 报告在线预览（inline，`Content-Type: text/html`），读取 `feed.html_report_path` 文件返回；文件不存在或 path 为空返回 404（来源：Spec 004）
10. `GET /api/feeds/{id}/preview_html`：同上 API 路由入口（来源：Spec 004）
11. `POST /api/feeds/{id}/optimize_prompt`：手动触发 prompt 优化，同步返回 `{"intel_system_version": N, "intel_user_version": M}`（来源：Spec 006）
12. 评分=-1 通过 POST 或 PATCH 均触发异步 prompt 优化（threading.Thread, daemon=True）（来源：Spec 006）
13. 评分=+1 不触发优化（来源：Spec 006）
14. 异步优化失败不影响评分保存（threading 内 try-except，仅 logger.error）（来源：Spec 006）
15. 前端已完成评分（有评分+有评语）时禁用评分控件，需清空后才能重新评分（来源：Spec 006）

### Evidence

- [backend/apps/intelligence/urls.py](../../../backend/apps/intelligence/urls.py)
- [backend/apps/intelligence/views.py](../../../backend/apps/intelligence/views.py)
- [backend/config/urls.py](../../../backend/config/urls.py)
- [backend/apps/intelligence/serializers.py](../../../backend/apps/intelligence/serializers.py)
- [backend/apps/intelligence/services/feishu_service.py](../../../backend/apps/intelligence/services/feishu_service.py)
- [backend/apps/intelligence/services/prompt_optimizer_service.py](../../../backend/apps/intelligence/services/prompt_optimizer_service.py)
- [frontend/src/components/reports/RatingForm.vue](../../../frontend/src/components/reports/RatingForm.vue)
- [backend/apps/intelligence/tests/test_api.py](../../../backend/apps/intelligence/tests/test_api.py)
- [backend/apps/intelligence/tests/test_feishu_service.py](../../../backend/apps/intelligence/tests/test_feishu_service.py)

## Evidence Gaps

- 缺口：当前没有 OpenAPI / schema 导出入口
  - 影响：契约权威入口仍以代码和测试为主
- 缺口：同域 Session/CSRF 写操作护栏尚未闭环
  - 影响：`AC-016` 未满足，不能把写操作安全口径声明为稳定完成
