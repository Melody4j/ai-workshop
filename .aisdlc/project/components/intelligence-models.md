# intelligence-models

## Module

- 代码入口：[backend/apps/intelligence/models.py](../../../backend/apps/intelligence/models.py)
- 迁移入口：[backend/apps/intelligence/migrations/0001_initial.py](../../../backend/apps/intelligence/migrations/0001_initial.py)、[backend/apps/intelligence/migrations/0002_monitorproject_competitor_contexts_and_more.py](../../../backend/apps/intelligence/migrations/0002_monitorproject_competitor_contexts_and_more.py)

## Data Contract

- 权威入口：
  - 模型：[backend/apps/intelligence/models.py](../../../backend/apps/intelligence/models.py)
  - 结构校验：[backend/apps/intelligence/serializers.py](../../../backend/apps/intelligence/serializers.py)

### Invariants

1. `MonitorProject.competitor_urls` 必须是对象数组，单项至少含 `title` 与 `url`
2. `MonitorProject.competitor_contexts` 与 `competitor_urls` 在数量上必须对齐
3. `MonitorProject.self_product_doc` 与 `self_product_doc_name` 允许为空
4. `IntelligenceFeed.job_status` 保持兼容 `CHANGED` / `NO_CHANGE` / `ERROR_CRAWL`
5. `IntelligenceFeed.user_feedback` 仅允许 `-1` / `1` / `null`
6. 当前任务停用不清理历史报告记录

### Evidence

- [backend/apps/intelligence/models.py](../../../backend/apps/intelligence/models.py)
- [backend/apps/intelligence/serializers.py](../../../backend/apps/intelligence/serializers.py)
- [backend/apps/intelligence/tests/test_api.py](../../../backend/apps/intelligence/tests/test_api.py)
- [backend/apps/intelligence/tests/test_models.py](../../../backend/apps/intelligence/tests/test_models.py)

## Evidence Gaps

- 缺口：`DataSnapshot` append-only 触发器尚未实现
  - 影响：快照表当前只有模型占位，尚未形成数据库级长期护栏
- 缺口：真实执行链路（调度/采集/diff）未落地
  - 影响：`IntelligenceFeed` 的全状态流转仍以骨架兼容为主
