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
4. 命中项目逐 URL 调用 `_process_url(project, url, title, now)` 执行 11 步链路
5. 项目执行后更新 `next_run_at = cron_matcher.get_next_run(cron, now)`

### `_process_url` 11 步链路（Spec 004 修订）

1. **采集**：`crawler_service.fetch_and_clean(url)` → 失败写 ERROR_CRAWL，不创建快照
2. **保存原始文件**：raw_html + BS clean_md（BS 版本仅存文件不入 DB）
3. **LLM 语义降噪**（第 1 次 LLM）：`llm_service.denoise(clean_md)` → 失败写 ERROR_CRAWL，不创建快照
4. **快照入库**：保存 LLM 降噪 MD（`llm_` 前缀），创建 DataSnapshot（`clean_md_path` 指向 LLM 版本）
5. **获取上一条快照**：排除当前条；无上一条 → 首次爬取跳过 diff
6. **文本 diff**：`diff_service.text_diff(new_md, prev_md)` → 为空写 NO_CHANGE 熔断
7. **LLM diff 判断**（第 2 次 LLM）：`llm_service.judge_diff(diff_text, self_doc)` → 无意义写 NO_CHANGE 熔断
8. **LLM 情报生成**（第 3 次 LLM）：`llm_service.generate_intel(diff, self_doc, few_shots)` → 失败写 ERROR_CRAWL
9. **情报入库**：写 IntelligenceFeed(CHANGED, 4 字段)
10. **报告渲染**：`report_service.render_html/render_md` → 路径回写 feed
11. **飞书推送**：`feishu_service.push_intelligence(feed.id)` → 异常不中断主流程

### Invariants

1. 全局扫描 Job 由 `apps.py ready()` 在 `RUN_MAIN=true` 时启动，非 autoreload 进程不启动
2. `run_scan()` 只处理 `is_active=True` 且 `next_run_at <= now`（或 `next_run_at is None`）的项目
3. httpx 优先采集，`clean_markdown < 3 行` 时降级 Playwright
4. 采集失败写 ERROR_CRAWL（不创建快照），不中断其他 URL
5. 本模块串接 LLM 链路后写 IntelligenceFeed（11 步链路：采集→降噪→diff熔断→情报生成→入库→报告→推送）（Spec 004 修订）
6. 3 次 LLM 调用独立，不合并（denoise / judge_diff / generate_intel）（Spec 004 新增）
7. 首次爬取或旧格式快照（`clean_md_path` 无 `llm_` 前缀）跳过 diff，直接情报生成（Spec 004 新增）
8. LLM 降噪/情报生成失败 → ERROR_CRAWL，不创建快照（Spec 004 新增）
9. 飞书推送异常不中断主流程（try-except 隔离）（Spec 004 新增）
10. `competitor_urls` 中的空 URL 被跳过，不写快照
11. `next_run_at` 更新使用 `save(update_fields=["next_run_at"])`，不触发 save() 中的 cron 重算

### Evidence

- [backend/apps/intelligence/scheduler.py](../../../backend/apps/intelligence/scheduler.py)
- [backend/apps/intelligence/apps.py](../../../backend/apps/intelligence/apps.py)
- [backend/apps/intelligence/services/scheduler_service.py](../../../backend/apps/intelligence/services/scheduler_service.py)
- [backend/apps/intelligence/services/crawler_service.py](../../../backend/apps/intelligence/services/crawler_service.py)
- [backend/apps/intelligence/services/cron_matcher.py](../../../backend/apps/intelligence/services/cron_matcher.py)
- [backend/apps/intelligence/services/file_storage.py](../../../backend/apps/intelligence/services/file_storage.py)
- [backend/apps/intelligence/services/llm_service.py](../../../backend/apps/intelligence/services/llm_service.py)
- [backend/apps/intelligence/services/diff_service.py](../../../backend/apps/intelligence/services/diff_service.py)
- [backend/apps/intelligence/services/report_service.py](../../../backend/apps/intelligence/services/report_service.py)
- [backend/apps/intelligence/services/feishu_service.py](../../../backend/apps/intelligence/services/feishu_service.py)
- [backend/apps/intelligence/tests/test_scheduler_service.py](../../../backend/apps/intelligence/tests/test_scheduler_service.py)
- [backend/apps/intelligence/tests/test_llm_pipeline_e2e.py](../../../backend/apps/intelligence/tests/test_llm_pipeline_e2e.py)
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
