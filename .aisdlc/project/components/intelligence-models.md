# intelligence-models

## Module

- 代码入口：[backend/apps/intelligence/models.py](../../../backend/apps/intelligence/models.py)
- 迁移入口：
  - [0001_initial.py](../../../backend/apps/intelligence/migrations/0001_initial.py)
  - [0002_monitorproject_competitor_contexts_and_more.py](../../../backend/apps/intelligence/migrations/0002_monitorproject_competitor_contexts_and_more.py)
  - [0003_monitorproject_next_run_at.py](../../../backend/apps/intelligence/migrations/0003_monitorproject_next_run_at.py)
  - [0004_remove_datasnapshot_clean_markdown_and_more.py](../../../backend/apps/intelligence/migrations/0004_remove_datasnapshot_clean_markdown_and_more.py)
  - [0005_intelligencefeed_push_status.py](../../../backend/apps/intelligence/migrations/0005_intelligencefeed_push_status.py)

## Data Contract

- 权威入口：
  - 模型：[backend/apps/intelligence/models.py](../../../backend/apps/intelligence/models.py)
  - 结构校验：[backend/apps/intelligence/serializers.py](../../../backend/apps/intelligence/serializers.py)

### Invariants

1. `MonitorProject.competitor_urls` 必须是对象数组，单项至少含 `title` 与 `url`
2. `MonitorProject.competitor_contexts` 与 `competitor_urls` 在数量上必须对齐
3. `MonitorProject.self_product_doc` 与 `self_product_doc_name` 允许为空
4. `MonitorProject.next_run_at`（DateTimeField, nullable）记录下次调度时间；项目新建或 cron 变更时 `save()` 调用 `cron_matcher.get_next_run(cron, now)` 重算
5. `MonitorProject.next_run_at=None` 的项目在首次扫描时被触发执行
6. `IntelligenceFeed.job_status` 保持兼容 `CHANGED` / `NO_CHANGE` / `ERROR_CRAWL`
7. `IntelligenceFeed.user_feedback` 仅允许 `-1` / `1` / `null`
8. 当前任务停用不清理历史报告记录
9. `DataSnapshot` 数据库字段只存绝对文件路径（`raw_html_path` / `clean_md_path`），不存内容；内容为空时路径为空字符串
10. `DataSnapshot` append-only——禁止 UPDATE/DELETE（DB 触发器尚未实现，见 Evidence Gaps）
11. `IntelligenceFeed.push_status` 保持兼容 `NOT_PUSHED` / `PUSHED` / `PUSH_FAILED`，默认 `NOT_PUSHED`（来源：Spec 005）
12. `push_status` 与 `job_status` 正交——`job_status` 标识情报结果，`push_status` 标识推送结果，不互相覆盖（来源：Spec 005）
13. 仅 `job_status=CHANGED` 的记录触发推送（来源：Spec 005）

### Evidence

- [backend/apps/intelligence/models.py](../../../backend/apps/intelligence/models.py)
- [backend/apps/intelligence/serializers.py](../../../backend/apps/intelligence/serializers.py)
- [backend/apps/intelligence/services/cron_matcher.py](../../../backend/apps/intelligence/services/cron_matcher.py)
- [backend/apps/intelligence/services/file_storage.py](../../../backend/apps/intelligence/services/file_storage.py)
- [backend/apps/intelligence/tests/test_api.py](../../../backend/apps/intelligence/tests/test_api.py)
- [backend/apps/intelligence/tests/test_models.py](../../../backend/apps/intelligence/tests/test_models.py)
- [backend/apps/intelligence/tests/test_cron_matcher.py](../../../backend/apps/intelligence/tests/test_cron_matcher.py)
- [backend/apps/intelligence/tests/test_scheduler_service.py](../../../backend/apps/intelligence/tests/test_scheduler_service.py)
- [backend/apps/intelligence/tests/test_feishu_service.py](../../../backend/apps/intelligence/tests/test_feishu_service.py)

## Evidence Gaps

- 缺口：`DataSnapshot` append-only 触发器尚未实现
  - 影响：快照表当前只有模型层约束，尚未形成数据库级硬约束（UPDATE/DELETE 未被 RAISE 阻止）
- 缺口：`DataSnapshot` 字段从 TextField 重构为路径字段（migration 0004），旧数据未迁移
  - 影响：如有历史快照数据，raw_markdown/clean_markdown 内容将丢失（开发环境无影响）
