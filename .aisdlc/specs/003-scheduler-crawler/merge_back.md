---
title: Merge-back 清单与证据
status: draft
spec: 003-scheduler-crawler
---

# Merge-back 清单与证据

> 主入口：`implementation/plan.md#Merge-back 待办清单`（MB-001 ~ MB-004）
> 本次 merge-back 范围：ADR / Data Contract / API Contract（无变更） / Ops / NFR / Registry

## 晋升清单总览

| # | 类型 | 条目 | project 落点 | 状态 | 代码来源 |
|---|---|---|---|---|---|
| MB-001 | Component | 调度服务与采集服务模块页 | `.aisdlc/project/components/intelligence-scheduler.md`（新建） | Done | 根项目 |
| MB-002 | Ops | 依赖清单更新 | `.aisdlc/project/ops/index.md`（更新） | Done | 根项目 |
| MB-003 | Data Contract | next_run_at 字段与 croniter 匹配逻辑 | `.aisdlc/project/components/intelligence-models.md#data-contract`（更新） | Done | 根项目 |
| MB-004 | Ops | RUN_MAIN 守卫局限性 | `.aisdlc/project/ops/index.md`（更新） | Done | 根项目 |
| MB-005 | Data Contract | DataSnapshot 字段重构（TextField→路径字段） | `.aisdlc/project/components/intelligence-models.md#data-contract`（更新） | Done | 根项目 |
| MB-006 | Component Index | 新增 intelligence-scheduler 模块到地图 | `.aisdlc/project/components/index.md`（更新） | Done | 根项目 |

---

## MB-001：调度服务与采集服务模块页

- **project 落点**：`.aisdlc/project/components/intelligence-scheduler.md`（新建）
- **不变量摘要**：
  1. 全局扫描 Job 由 `apps.py ready()` 在 `RUN_MAIN=true` 时启动，非 autoreload 进程不启动
  2. `run_scan()` 遍历 `is_active=True` 且 `next_run_at <= now`（或 `next_run_at is None`）的项目
  3. httpx 优先，clean_markdown < 3 行降级 Playwright
  4. 采集失败写空快照（path=""），不中断其他 URL
  5. 本 Spec 不写 IntelligenceFeed
- **证据入口**：
  - 代码：`backend/apps/intelligence/services/scheduler_service.py`
  - 代码：`backend/apps/intelligence/services/crawler_service.py`
  - 代码：`backend/apps/intelligence/services/cron_matcher.py`
  - 代码：`backend/apps/intelligence/scheduler.py`
  - 代码：`backend/apps/intelligence/apps.py`
  - 测试：`backend/apps/intelligence/tests/test_scheduler_service.py`
  - 测试：`backend/apps/intelligence/tests/test_crawler_service.py`
  - 测试：`backend/apps/intelligence/tests/test_cron_matcher.py`
- **状态**：Done

---

## MB-002：依赖清单更新

- **project 落点**：`.aisdlc/project/ops/index.md`（Run/Verify 部分更新）
- **变更内容**：`backend/requirements/base.txt` 新增 6 个依赖包：
  - `django-apscheduler>=0.7.0,<0.8.0`
  - `httpx>=0.27.0,<0.28.0`
  - `html2text>=2024.2.26`
  - `beautifulsoup4>=4.12.0,<5.0.0`
  - `playwright>=1.40.0,<2.0.0`
  - `croniter>=2.0.0,<3.0.0`
- **运维注意**：Playwright 需额外执行 `playwright install chromium` 下载浏览器
- **证据入口**：`backend/requirements/base.txt`
- **状态**：Done

---

## MB-003：next_run_at 字段与 croniter 匹配逻辑

- **project 落点**：`.aisdlc/project/components/intelligence-models.md#data-contract`（Invariants + Evidence 更新）
- **不变量摘要**：
  1. `MonitorProject.next_run_at`（DateTimeField, nullable）记录下次调度时间
  2. 项目新建或 cron 变更时，`save()` 调用 `cron_matcher.get_next_run(cron, now)` 重算 next_run_at
  3. `scheduler_service.run_scan()` 执行后用 `save(update_fields=["next_run_at"])` 更新，不触发 save() 重算
  4. `next_run_at=None` 的项目在首次扫描时被触发执行
  5. croniter 精度不限 5 的倍数，实际触发取决于扫描周期
- **证据入口**：
  - 模型：`backend/apps/intelligence/models.py`（MonitorProject.save 覆盖）
  - 服务：`backend/apps/intelligence/services/cron_matcher.py`
  - 迁移：`backend/apps/intelligence/migrations/0003_monitorproject_next_run_at.py`
  - 测试：`backend/apps/intelligence/tests/test_cron_matcher.py`
- **状态**：Done

---

## MB-004：RUN_MAIN 守卫局限性

- **project 落点**：`.aisdlc/project/ops/index.md`（Evidence Gaps 更新）
- **不变量摘要**：
  1. `apps.py ready()` 使用 `os.environ.get("RUN_MAIN") == "true"` 守卫，仅在 runserver worker 进程启动 scheduler
  2. 生产环境（gunicorn/uwsgi）不设 `RUN_MAIN`，scheduler 不会启动——需另行处理
  3. BackgroundScheduler 为进程内调度，多 worker 部署会重复触发——需分布式锁或单 worker 约束
- **证据入口**：
  - 代码：`backend/apps/intelligence/apps.py`
  - 代码：`backend/apps/intelligence/scheduler.py`
- **状态**：Done

---

## MB-005：DataSnapshot 字段重构（文件存储）

- **project 落点**：`.aisdlc/project/components/intelligence-models.md#data-contract`（Invariants + Evidence 更新）
- **变更内容**：
  - `raw_markdown`（TextField）→ `raw_html_path`（CharField(512)）
  - `clean_markdown`（TextField）→ `clean_md_path`（CharField(512)）
  - 新增 `file_storage.py` 服务模块，负责文件落盘与路径返回
  - 新增 `settings.SNAPSHOT_STORAGE_DIR` 配置项，指向项目根 `data/` 目录
  - 文件路径格式：`{SNAPSHOT_STORAGE_DIR}/snapshots/{project_id}/{YYYYMMDD}/{HHMMSS}_{domain}.{ext}`
- **不变量摘要**：
  1. DataSnapshot 数据库字段只存绝对文件路径，不存内容
  2. 内容为空时路径字段为空字符串（不写文件）
  3. 文件存储服务 `file_storage.save_raw_html()` / `save_clean_md()` 为唯一落盘入口
- **证据入口**：
  - 模型：`backend/apps/intelligence/models.py`（DataSnapshot 字段）
  - 服务：`backend/apps/intelligence/services/file_storage.py`
  - 配置：`backend/config/settings.py`（SNAPSHOT_STORAGE_DIR）
  - 迁移：`backend/apps/intelligence/migrations/0004_remove_datasnapshot_clean_markdown_and_more.py`
  - 测试：`backend/apps/intelligence/tests/test_scheduler_service.py`
- **状态**：Done

---

## MB-006：Component Index 地图更新

- **project 落点**：`.aisdlc/project/components/index.md`（表格 + 依赖图更新）
- **变更内容**：新增 `intelligence-scheduler` 模块行
- **状态**：Done

---

## 不晋升项（留痕）

| 条目 | 原因 |
|---|---|
| Spec 002 爬虫验证脚本 | 一次性验证产物，非长期资产 |
| E2E 测试（test_e2e_crawl.py） | 测试代码本身不晋升，通过 Evidence 入口引用 |
| `scheduler.py` 中 CronTrigger(second="*/5") 与 plan.md 中 minute="*/5" 的差异 | 实现偏差，需在后续 Spec 中修正；不作为不变量晋升 |

---

## CONTEXT GAP（本次未消除）

- `DataSnapshot` append-only 触发器仍未实现——沿用 project index.md 中的未完成晋升项记录，不在本次 merge-back 消除
