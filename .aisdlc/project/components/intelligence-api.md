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

### Evidence

- [backend/apps/intelligence/urls.py](../../../backend/apps/intelligence/urls.py)
- [backend/apps/intelligence/views.py](../../../backend/apps/intelligence/views.py)
- [backend/apps/intelligence/serializers.py](../../../backend/apps/intelligence/serializers.py)
- [backend/apps/intelligence/tests/test_api.py](../../../backend/apps/intelligence/tests/test_api.py)

## Evidence Gaps

- 缺口：当前没有 OpenAPI / schema 导出入口
  - 影响：契约权威入口仍以代码和测试为主
- 缺口：同域 Session/CSRF 写操作护栏尚未闭环
  - 影响：`AC-016` 未满足，不能把写操作安全口径声明为稳定完成
