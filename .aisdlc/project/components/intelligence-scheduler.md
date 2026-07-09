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
4. 命中项目逐 URL 调用 `_process_url(project, url, title, now)` 执行 12 步链路
5. 项目执行后更新 `next_run_at = cron_matcher.get_next_run(cron, now)`

### `_process_url` 12 步链路（含稳定 diff 语义）

1. **采集**：`crawler_service.fetch_and_clean(url)` → 返回 `raw_html` + Firecrawl Markdown；失败写 ERROR_CRAWL，不创建快照
2. **保存原始文件**：保存 `raw_html` + Firecrawl Markdown（`raw_md_path` 指向 Firecrawl 版本）
3. **LLM 语义降噪**（第 1 次 LLM）：`llm_service.denoise(clean_md)` → 失败写 ERROR_CRAWL，不创建快照
4. **快照入库**：保存 LLM 降噪 MD（`llm_` 前缀），创建 DataSnapshot（`clean_md_path` 指向 LLM 版本）
5. **获取上一条快照**：排除当前条；无上一条或旧格式快照 → 跳过 diff，`diff_text=llm_clean_md`
6. **原始证据 diff**：读取当前/上一条 `raw_md_path`，计算 `raw_diff_text = diff_service.text_diff(curr_raw_md, prev_raw_md)`
7. **原始内容熔断**：`raw_diff_text == ""` → 写 NO_CHANGE，跳过 `judge_diff` / `generate_intel`
8. **规则归一化 diff**：`diff_text = diff_service.canonical_text_diff(curr_raw_md, prev_raw_md)`
9. **稳定 diff 熔断**：`diff_text == ""` → 写 NO_CHANGE（保留 `raw_diff_text`），跳过 `judge_diff` / `generate_intel`
10. **LLM diff 判断**（第 2 次 LLM）：仅 `diff_text != ""` 时调用 `llm_service.judge_diff(diff_text, self_doc)`；无意义写 NO_CHANGE
11. **LLM 情报生成**（第 3 次 LLM）：`llm_service.generate_intel(diff_text, self_doc, few_shots)` → 失败写 ERROR_CRAWL
12. **情报入库 + 报告 + 推送**：写 IntelligenceFeed(CHANGED, 4 字段) → `report_service.render_html/render_md` → `feishu_service.push_intelligence(feed.id)`（异常不中断主流程）

### Invariants

1. 全局扫描 Job 由 `apps.py ready()` 在 `RUN_MAIN=true` 时启动，非 autoreload 进程不启动
2. `run_scan()` 只处理 `is_active=True` 且 `next_run_at <= now`（或 `next_run_at is None`）的项目；无活跃项目时直接 return（来源：Spec 006 优化）
3. 当前采集链路以 Firecrawl 返回的 `raw_html` + Markdown 为准；采集失败写 ERROR_CRAWL（不创建快照），不中断其他 URL
4. 本模块串接 LLM 链路后写 IntelligenceFeed（12 步链路：采集→降噪→raw diff→canonical diff→熔断/判断→情报生成→入库→报告→推送）
5. 3 次 LLM 调用独立，不合并（denoise / judge_diff / generate_intel）（Spec 004 新增）
6. 首次爬取或旧格式快照（缺少 `raw_md_path`，或 `clean_md_path` 无 `llm_` 前缀）跳过稳定 diff，直接情报生成
7. `raw_diff_text` 是 Firecrawl Markdown 的原始 diff 证据；为空时直接写 NO_CHANGE，不调用 `judge_diff` / `generate_intel`
8. `diff_text` 是 Firecrawl Markdown 经 `canonicalize_markdown()` 规则归一化后的稳定 diff，不再来自 `llm_clean_md`
9. `llm_clean_md` 仍保存到 `clean_md_path`，并用于页面理解/首次抓取兼容路径；它不是变化真相源
10. 当 `raw_diff_text != ""` 且 `diff_text == ""` 时，仍写 NO_CHANGE，并保留 `raw_diff_text` 作为排障证据
11. LLM 降噪/情报生成失败 → ERROR_CRAWL；若失败发生在 diff 已生成之后，应保留 `raw_diff_text`
12. 飞书推送异常不中断主流程（try-except 隔离）（Spec 004 新增）
13. `competitor_urls` 中的空 URL 被跳过，不写快照
14. `next_run_at` 更新使用 `save(update_fields=["next_run_at"])`，不触发 save() 中的 cron 重算
15. 所有 `IntelligenceFeed.objects.create()` 调用必须写入 `diff_text`；在稳定 diff 场景下，CHANGED/NO_CHANGE 记录的 `diff_text` 均以 canonical diff 语义为准

### Evidence

- [backend/apps/intelligence/scheduler.py](../../../backend/apps/intelligence/scheduler.py)
- [backend/apps/intelligence/apps.py](../../../backend/apps/intelligence/apps.py)
- [backend/apps/intelligence/services/scheduler_service.py](../../../backend/apps/intelligence/services/scheduler_service.py)
- [backend/apps/intelligence/services/prompt_optimizer_service.py](../../../backend/apps/intelligence/services/prompt_optimizer_service.py)
- [backend/apps/intelligence/services/crawler_service.py](../../../backend/apps/intelligence/services/crawler_service.py)
- [backend/apps/intelligence/services/cron_matcher.py](../../../backend/apps/intelligence/services/cron_matcher.py)
- [backend/apps/intelligence/services/file_storage.py](../../../backend/apps/intelligence/services/file_storage.py)
- [backend/apps/intelligence/services/llm_service.py](../../../backend/apps/intelligence/services/llm_service.py)
- [backend/apps/intelligence/services/diff_service.py](../../../backend/apps/intelligence/services/diff_service.py)
- [backend/apps/intelligence/services/report_service.py](../../../backend/apps/intelligence/services/report_service.py)
- [backend/apps/intelligence/services/feishu_service.py](../../../backend/apps/intelligence/services/feishu_service.py)
- [backend/apps/intelligence/tests/test_scheduler_service.py](../../../backend/apps/intelligence/tests/test_scheduler_service.py)
- [backend/apps/intelligence/tests/test_llm_pipeline_e2e.py](../../../backend/apps/intelligence/tests/test_llm_pipeline_e2e.py)
- [backend/apps/intelligence/tests/test_fixture_report_flow_e2e.py](../../../backend/apps/intelligence/tests/test_fixture_report_flow_e2e.py)
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
- 缺口：当前仍会在计算稳定 diff 前执行一次 `denoise()`
  - 影响：即使 `raw_diff_text == ""`，仍会产生一次 LLM 成本
  - 建议动作：后续单开 Spec，将 raw diff 熔断前移到 denoise 之前
