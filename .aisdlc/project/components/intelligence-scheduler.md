# intelligence-scheduler

## Module

- 代码入口：[backend/apps/intelligence/scheduler.py](../../../backend/apps/intelligence/scheduler.py)
- 调度注册：[backend/apps/intelligence/apps.py](../../../backend/apps/intelligence/apps.py)（ready hook）
- 服务入口：
  - 调度服务：[backend/apps/intelligence/services/scheduler_service.py](../../../backend/apps/intelligence/services/scheduler_service.py)
  - 采集服务：[backend/apps/intelligence/services/crawler_service.py](../../../backend/apps/intelligence/services/crawler_service.py)
  - cron 匹配：[backend/apps/intelligence/services/cron_matcher.py](../../../backend/apps/intelligence/services/cron_matcher.py)
  - 文件存储：[backend/apps/intelligence/services/file_storage.py](../../../backend/apps/intelligence/services/file_storage.py)

## Service Contract

### 调度链路

1. Django 启动 → `apps.py ready()` → `RUN_MAIN=true` 时调用 `scheduler.start_scheduler()`
2. `start_scheduler()` 注册全局 Job（`scan_all_projects`），调用 `scheduler_service.run_scan()`
3. `run_scan()` 遍历 `is_active=True` 且 `next_run_at <= now`（或 `next_run_at is None`）的项目
4. 命中项目逐 URL 调用 `crawler_service.fetch_and_clean(url)` 采集
5. 采集结果经 `file_storage` 落盘，路径写入 `DataSnapshot`
6. 项目执行后更新 `next_run_at = cron_matcher.get_next_run(cron, now)`

### Invariants

1. 全局扫描 Job 由 `apps.py ready()` 在 `RUN_MAIN=true` 时启动，非 autoreload 进程不启动
2. `run_scan()` 只处理 `is_active=True` 且 `next_run_at <= now`（或 `next_run_at is None`）的项目
3. httpx 优先采集，`clean_markdown < 3 行` 时降级 Playwright
4. 采集失败写空快照（path=""），不中断其他 URL
5. 本模块不写 IntelligenceFeed（范围止步于 DataSnapshot 入库）
6. `competitor_urls` 中的空 URL 被跳过，不写快照
7. `next_run_at` 更新使用 `save(update_fields=["next_run_at"])`，不触发 save() 中的 cron 重算

### Evidence

- [backend/apps/intelligence/scheduler.py](../../../backend/apps/intelligence/scheduler.py)
- [backend/apps/intelligence/apps.py](../../../backend/apps/intelligence/apps.py)
- [backend/apps/intelligence/services/scheduler_service.py](../../../backend/apps/intelligence/services/scheduler_service.py)
- [backend/apps/intelligence/services/crawler_service.py](../../../backend/apps/intelligence/services/crawler_service.py)
- [backend/apps/intelligence/services/cron_matcher.py](../../../backend/apps/intelligence/services/cron_matcher.py)
- [backend/apps/intelligence/services/file_storage.py](../../../backend/apps/intelligence/services/file_storage.py)
- [backend/apps/intelligence/tests/test_scheduler_service.py](../../../backend/apps/intelligence/tests/test_scheduler_service.py)
- [backend/apps/intelligence/tests/test_crawler_service.py](../../../backend/apps/intelligence/tests/test_crawler_service.py)
- [backend/apps/intelligence/tests/test_cron_matcher.py](../../../backend/apps/intelligence/tests/test_cron_matcher.py)
- [backend/apps/intelligence/tests/test_e2e_crawl.py](../../../backend/apps/intelligence/tests/test_e2e_crawl.py)

## Evidence Gaps

- 缺口：`scheduler.py` 中 CronTrigger 使用 `second="*/5"`（每 5 秒），与 plan.md 设计的 `minute="*/5"`（每 5 分钟）不符
  - 影响：调度频率高于设计预期，可能导致更频繁的 DB 查询
  - 建议动作：后续 Spec 中修正为 `minute="*/5"`
- 缺口：生产环境（gunicorn/uwsgi）下 `RUN_MAIN` 未设，scheduler 不会启动
  - 影响：MVP 阶段仅支持 runserver 本地开发
  - 建议动作：生产部署时需另行处理 scheduler 启动
