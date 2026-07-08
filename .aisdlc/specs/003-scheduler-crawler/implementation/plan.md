---
title: I1 Implementation Plan（SSOT）
status: draft
---

# 调度任务与爬虫模块接入 实现计划（SSOT）

> **必需技能：** `spec-execute`（按批次执行本计划）
> **上下文获取：** 必须先执行 `spec-context` 获取上下文，定位 `{FEATURE_DIR}`，失败即停止

**目标：** 为现有 Django+Vue 骨架接入 django-apscheduler 定时调度与 httpx+BeautifulSoup+html2text 爬虫，使每个 MonitorProject 能按 cron 定时触发采集、规则去噪、写入 DataSnapshot。
**范围：** In = django-apscheduler 集成、全局扫描 Job（每 5 分钟）、cron 窗口匹配、httpx 采集、BeautifulSoup 去噪、html2text 转 MD、Playwright 降级（markdown < 3 行）、DataSnapshot 入库（含失败空快照）；Out = LLM 降噪、diff 熔断、情报生成、飞书推送、IntelligenceFeed 写入、last_run_at 字段、多进程分布式锁、停机补执行
**架构：** Django 启动时注册全局扫描 Job（每 5 分钟）→ 扫描所有 active 项目 → cron 5 分钟窗口匹配 → 命中项目逐 URL 用 httpx 采集 → BeautifulSoup 去噪 → html2text 转 MD → markdown < 3 行降级 Playwright → 写入 DataSnapshot（失败写空快照）。不修改现有 API/views/serializers。
**验收口径：** `requirements/solution.md#8-mini-prd` AC-001 ~ AC-009
**影响范围：** `requirements/solution.md#7-impact-analysis` — intelligence-models（DataSnapshot 写入）、新增 services 层、config/settings.py、apps.py ready hook
**需遵守的不变量：**
1. 快照 append-only——DataSnapshot 禁止 UPDATE/DELETE（来源：CLAUDE.md 不变量 1）
2. httpx 优先，Playwright 仅 SPA 按需降级（来源：CLAUDE.md 不变量 7）
3. 调度限 django-apscheduler，不引入消息队列（来源：CLAUDE.md 不变量 8）
4. `competitor_urls` 必须为 JSON 数组，每项 `{"url":"...","title":"..."}`（来源：CLAUDE.md 不变量 10）
5. 本 Spec 不写 IntelligenceFeed（来源：raw.md#R1-Q1）
**子仓范围：** 无

---

## TL;DR

- 一句话目标：接入 django-apscheduler 全局扫描 Job + httpx/BeautifulSoup/html2text/Playwright 爬虫，实现定时采集入库
- In/Out：In = 调度+采集+清洗入库；Out = LLM/diff/情报/飞书
- 关键路径：T1 依赖安装 → T2 cron 匹配 → T3 采集服务 → T4 调度服务 → T5 集成注册 → T6 端到端测试
- 最大风险与优先验证点：R1（django-apscheduler 与 runserver 集成）、R3（httpx 采集成功率）、R5（Playwright 降级）

---

## 范围与边界（In / Out）

- **In**：
  - django-apscheduler 集成与全局扫描 Job（每 5 分钟）
  - cron 5 分钟窗口匹配逻辑
  - httpx 采集 HTML
  - BeautifulSoup 规则去噪（去 nav/footer/script/style）
  - html2text 转 MD
  - Playwright 降级（markdown < 3 行）
  - DataSnapshot 入库（含失败空快照）
- **Out**：
  - LLM 降噪、diff 熔断、情报生成、飞书推送
  - IntelligenceFeed 写入
  - last_run_at 字段
  - 多进程分布式锁
  - 停机补执行
- **不变量/关键约束**：
  - 快照 append-only，不 UPDATE/DELETE
  - httpx 优先，Playwright 按需降级
  - 不引入消息队列
  - 不写 IntelligenceFeed
- **影响面**：新增 services 层（scheduler_service + crawler_service）；修改 settings.py、apps.py、requirements/base.txt；不修改现有 API/views/serializers

## 代码工作区清单

无子仓。

---

## 里程碑与节奏

- M0（MVP）：
  - 产物：调度服务 + 采集服务 + DataSnapshot 入库 + 端到端测试
  - 验收标准：AC-001 ~ AC-009 全部通过
  - 任务集合：T1 ~ T6

---

## 依赖与资源

- 环境/权限：Python 3.10+、`.venv` 虚拟环境、Playwright 浏览器（`playwright install`）
- 外部系统/团队：无
- 数据/样本：Spec 002 的 7 个目标站点（ihuiwa.com、x-design.com、piccopilot.com、weshop.ai、bandy.ai、thenewblack.ai、lovable.dev）
- 发布/变更窗口：无

---

## 风险与验证（可执行）

| # | 风险/假设 | 验证方式 | 成功信号 | 失败信号 | Owner | 截止 | 下一步动作 |
|---|---|---|---|---|---|---|---|
| R1 | django-apscheduler 在 runserver 下可能不触发 | 启动 runserver，观察日志 | 每 5 分钟出现扫描记录 | 无扫描记录 | FS | I2 | 检查是否需 --noreload 或切换 APScheduler 配置 |
| R2 | cron 5 分钟窗口匹配逻辑可能遗漏/重复 | 单元测试覆盖典型 cron | 所有测试通过 | 测试失败 | FS | I2 | 改用 croniter 库做区间匹配 |
| R3 | httpx 对部分站点可能被反爬 | 对 7 个目标站点逐一测试 | >= 5 个站点直接成功 | < 5 个站点成功 | FS | I2 | 评估默认启用 Playwright |
| R4 | BeautifulSoup 去噪可能误删正文 | 对比去噪前后 markdown | 正文核心内容保留 | 正文被误删 | FS | I2 | 补充 CSS selector 精确定位 |
| R5 | Playwright 降级后仍可能拿不到内容 | 对 httpx 失败站点测试 Playwright | markdown >= 3 行 | markdown < 3 行 | FS | I2 | 写空快照记录失败 |
| R6 | 多 URL 串行采集耗时过长 | 测量 10 URL 串行总耗时 | < 60s | >= 60s | FS | I2 | 引入 httpx async 或线程池 |

---

## 验收口径（可追溯）

- 追溯：`requirements/solution.md#8-mini-prd` AC-001 ~ AC-009
- 关键验收点：
  - AC-001：全局扫描 Job 每 5 分钟触发
  - AC-002：active 且 cron 匹配的项目被触发
  - AC-003：is_active=False 的项目不触发
  - AC-004：每个 URL 生成一条 DataSnapshot
  - AC-005：markdown < 3 行自动降级 Playwright
  - AC-006：采集失败写空快照，不中断其他 URL
  - AC-007：BeautifulSoup 去噪移除 nav/footer/script/style
  - AC-008：不写 IntelligenceFeed
  - AC-009：cron 变更后无需重启即生效

---

## NEEDS CLARIFICATION（未消除前不得进入 I2）

无。所有关键不确定项已在 R1 澄清中消除。

---

## 任务清单（SSOT）

### Task T1: 安装依赖与配置 settings.py

- [ ] **状态**：未开始

**代码仓范围：**
- 根项目：`backend/requirements/base.txt`、`backend/config/settings.py`
- 子仓：无

**文件：**
- 修改：`backend/requirements/base.txt`
- 修改：`backend/config/settings.py`
- 测试：无

**验收点：**
- `pip install -r backend/requirements/base.txt` 成功
- `python backend/manage.py check` 无错误
- `settings.INSTALLED_APPS` 包含 `django_apscheduler`
- `settings.APSCHEDULER_RUN_NOW_TIMEOUT` 已配置

**步骤 1：添加依赖到 base.txt**
- 修改点：`backend/requirements/base.txt`，追加以下行：
  ```
  django-apscheduler>=0.7.0,<0.8.0
  httpx>=0.27.0,<0.28.0
  html2text>=2024.2.26
  beautifulsoup4>=4.12.0,<5.0.0
  playwright>=1.40.0,<2.0.0
  ```

**步骤 2：安装依赖**
- Run: `pip install -r backend/requirements/base.txt`
- Expected: 所有包安装成功

**步骤 3：安装 Playwright 浏览器**
- Run: `playwright install chromium`
- Expected: chromium 下载安装成功

**步骤 4：配置 settings.py**
- 修改点：`backend/config/settings.py`
  - 在 `INSTALLED_APPS` 追加 `"django_apscheduler"`
  - 在文件末尾追加：
    ```python
    # django-apscheduler 配置
    APSCHEDULER_RUN_NOW_TIMEOUT = 25  # seconds
    ```

**步骤 5：运行验证**
- Run: `python backend/manage.py check`
- Expected: 无错误，输出 "System check identified no issues"

**步骤 6：提交（AUTO_COMMIT=true）**
- Commit message: `安装调度与爬虫依赖并配置 settings`
- 审计信息：
  - repo: `root`
    branch: `003-scheduler-crawler`
    commit: `<TBD>`
    pr: `<TBD>`
    changed_files:
      - `backend/requirements/base.txt`
      - `backend/config/settings.py`

---

### Task T2: 实现 cron 5 分钟窗口匹配逻辑

- [ ] **状态**：未开始

**代码仓范围：**
- 根项目：`backend/apps/intelligence/services/`
- 子仓：无

**文件：**
- 创建：`backend/apps/intelligence/services/__init__.py`（如不存在）
- 创建：`backend/apps/intelligence/services/cron_matcher.py`
- 创建：`backend/apps/intelligence/tests/test_cron_matcher.py`

**验收点：**
- `is_due("*/5 * * * *", now)` 在任意时间返回 True
- `is_due("0 9 * * *", now)` 在 9:00 窗口返回 True，其他窗口返回 False
- `is_due("*/30 * * * *", now)` 在 00 分和 30 分窗口返回 True，其他返回 False
- `is_due("0 9 * * 1", now)` 在周一 9:00 窗口返回 True，其他返回 False

**步骤 1：写失败测试**
- 修改点：`backend/apps/intelligence/tests/test_cron_matcher.py`
- 写入测试：
  - `test_every_5_minutes`：`is_due("*/5 * * * *", datetime(2026, 7, 8, 14, 3))` → True
  - `test_daily_9am_hit`：`is_due("0 9 * * *", datetime(2026, 7, 8, 9, 2))` → True（9:00 窗口 9:00-9:04）
  - `test_daily_9am_miss`：`is_due("0 9 * * *", datetime(2026, 7, 8, 10, 3))` → False
  - `test_every_30min_hit`：`is_due("*/30 * * * *", datetime(2026, 7, 8, 14, 32))` → True（30 分窗口 14:30-14:34）
  - `test_every_30min_miss`：`is_due("*/30 * * * *", datetime(2026, 7, 8, 14, 17))` → False
  - `test_weekly_monday_9am`：`is_due("0 9 * * 1", datetime(2026, 7, 6, 9, 3))` → True（2026-07-06 是周一）
  - `test_weekly_monday_9am_miss`：`is_due("0 9 * * 1", datetime(2026, 7, 7, 9, 3))` → False（周二）
- Run: `python backend/manage.py test apps.intelligence.tests.test_cron_matcher`
- Expected: FAIL（模块不存在）

**步骤 2：写最少实现**
- 修改点：`backend/apps/intelligence/services/cron_matcher.py`
- 实现逻辑：
  - 使用 `croniter` 库（如果可用）或自己实现 5 分钟窗口匹配
  - 核心逻辑：将 `now` 的分钟对齐到 5 分钟窗口起点（`window_start = now.replace(minute=now.minute - now.minute % 5, second=0, microsecond=0)`）
  - 检查从 `window_start` 到 `now` 的区间内是否有分钟满足 cron 表达式
  - 简化方案：检查 `window_start` 是否匹配 cron（因为 5 分钟窗口只有起点需要检查，cron 精度也限 5 分钟）
  - 使用 `croniter` 的 `is_match` 方法检查 `window_start`

**步骤 3：运行验证**
- Run: `python backend/manage.py test apps.intelligence.tests.test_cron_matcher`
- Expected: PASS（所有测试通过）

**步骤 4：提交（AUTO_COMMIT=true）**
- Commit message: `实现 cron 5 分钟窗口匹配逻辑与单元测试`
- 审计信息：
  - repo: `root`
    branch: `003-scheduler-crawler`
    commit: `<TBD>`
    pr: `<TBD>`
    changed_files:
      - `backend/apps/intelligence/services/__init__.py`
      - `backend/apps/intelligence/services/cron_matcher.py`
      - `backend/apps/intelligence/tests/test_cron_matcher.py`

---

### Task T3: 实现采集服务（crawler_service）

- [ ] **状态**：未开始

**代码仓范围：**
- 根项目：`backend/apps/intelligence/services/`
- 子仓：无

**文件：**
- 创建：`backend/apps/intelligence/services/crawler_service.py`
- 创建：`backend/apps/intelligence/tests/test_crawler_service.py`

**验收点：**
- `fetch_and_clean(url)` 返回 `(raw_markdown, clean_markdown)` 元组
- httpx 成功时 raw_markdown 非空，clean_markdown 已去噪
- markdown < 3 行时自动降级 Playwright
- 采集失败时返回 `("", "")`（空字符串元组）
- BeautifulSoup 去噪移除了 nav/footer/script/style 标签

**步骤 1：写失败测试**
- 修改点：`backend/apps/intelligence/tests/test_crawler_service.py`
- 写入测试：
  - `test_fetch_success`：mock httpx 返回正常 HTML，验证 raw_markdown 非空、clean_markdown 不含 nav/footer 内容
  - `test_fetch_degrade_to_playwright`：mock httpx 返回极少内容（< 3 行 markdown），mock Playwright 返回正常内容，验证降级触发
  - `test_fetch_failure_returns_empty`：mock httpx 抛异常，验证返回 `("", "")`
  - `test_dedup_removes_nav_footer`：给定含 nav/footer/script/style 的 HTML，验证 clean_markdown 不含这些标签内容
- Run: `python backend/manage.py test apps.intelligence.tests.test_crawler_service`
- Expected: FAIL（模块不存在）

**步骤 2：写最少实现**
- 修改点：`backend/apps/intelligence/services/crawler_service.py`
- 实现逻辑：
  ```python
  def fetch_and_clean(url: str) -> tuple[str, str]:
      """
      采集 URL 并清洗为 markdown。
      返回 (raw_markdown, clean_markdown)。
      失败返回 ("", "")。
      """
      # 1. httpx GET
      # 2. BeautifulSoup 去噪（去 nav/footer/script/style）
      # 3. html2text 转 MD
      # 4. 检查行数 < 3 → Playwright 降级
      # 5. 返回 (raw_markdown, clean_markdown)
  ```
  - httpx 超时设 30s，headers 含 User-Agent
  - BeautifulSoup 用 `html.parser`，移除 `nav`, `footer`, `script`, `style`, `noscript`, `iframe` 标签
  - html2text 配置：`body_width=0`（不折行）
  - Playwright：`sync_playwright()` → chromium → `page.goto(url)` → `page.content()`
  - 异常捕获：httpx.RequestError / PlaywrightError → 返回 `("", "")`

**步骤 3：运行验证**
- Run: `python backend/manage.py test apps.intelligence.tests.test_crawler_service`
- Expected: PASS（所有测试通过）

**步骤 4：提交（AUTO_COMMIT=true）**
- Commit message: `实现采集服务：httpx+BeautifulSoup+html2text+Playwright 降级`
- 审计信息：
  - repo: `root`
    branch: `003-scheduler-crawler`
    commit: `<TBD>`
    pr: `<TBD>`
    changed_files:
      - `backend/apps/intelligence/services/crawler_service.py`
      - `backend/apps/intelligence/tests/test_crawler_service.py`

---

### Task T4: 实现调度服务（scheduler_service）

- [ ] **状态**：未开始

**代码仓范围：**
- 根项目：`backend/apps/intelligence/services/`
- 子仓：无

**文件：**
- 创建：`backend/apps/intelligence/services/scheduler_service.py`
- 创建：`backend/apps/intelligence/tests/test_scheduler_service.py`

**验收点：**
- `run_scan()` 查询所有 `is_active=True` 的项目
- 对每个项目调用 `cron_matcher.is_due(project.cron, now)` 判断是否到期
- 命中项目逐 URL 调用 `crawler_service.fetch_and_clean(url)`
- 每个 URL（无论成功/失败）写入一条 DataSnapshot
- 不写 IntelligenceFeed
- 失败的 URL 写空快照（raw_markdown="" / clean_markdown=""）
- 单个 URL 失败不中断其他 URL

**步骤 1：写失败测试**
- 修改点：`backend/apps/intelligence/tests/test_scheduler_service.py`
- 写入测试：
  - `test_run_scan_active_project_matched`：创建 active 项目 + cron 匹配当前时间，mock `fetch_and_clean` 返回正常内容，验证 DataSnapshot 写入
  - `test_run_scan_inactive_project_skipped`：创建 inactive 项目，验证不触发采集
  - `test_run_scan_cron_not_matched`：创建 active 项目但 cron 不匹配当前时间，验证不触发采集
  - `test_run_scan_fetch_failure_writes_empty_snapshot`：mock `fetch_and_clean` 返回 `("", "")`，验证写入空快照
  - `test_run_scan_does_not_write_intelligence_feed`：执行后 IntelligenceFeed 数量为 0
  - `test_run_scan_partial_failure_continues`：项目有 3 个 URL，第 1 个失败，验证第 2/3 个仍被采集并写入
- Run: `python backend/manage.py test apps.intelligence.tests.test_scheduler_service`
- Expected: FAIL（模块不存在）

**步骤 2：写最少实现**
- 修改点：`backend/apps/intelligence/services/scheduler_service.py`
- 实现逻辑：
  ```python
  def run_scan():
      now = timezone.now()
      active_projects = MonitorProject.objects.filter(is_active=True)
      for project in active_projects:
          if not cron_matcher.is_due(project.cron, now):
              continue
          for item in project.competitor_urls:
              url = item.get("url", "")
              title = item.get("title", "")
              try:
                  raw_md, clean_md = crawler_service.fetch_and_clean(url)
              except Exception:
                  raw_md, clean_md = "", ""
              DataSnapshot.objects.create(
                  project=project,
                  source_url=url,
                  source_title=title,
                  raw_markdown=raw_md,
                  clean_markdown=clean_md,
                  fetch_time=now,
              )
  ```
  - 注意：`fetch_and_clean` 内部已捕获异常返回空字符串，外层 try/except 是防御性兜底

**步骤 3：运行验证**
- Run: `python backend/manage.py test apps.intelligence.tests.test_scheduler_service`
- Expected: PASS（所有测试通过）

**步骤 4：提交（AUTO_COMMIT=true）**
- Commit message: `实现调度服务：全局扫描+cron 匹配+逐 URL 采集入库`
- 审计信息：
  - repo: `root`
    branch: `003-scheduler-crawler`
    commit: `<TBD>`
    pr: `<TBD>`
    changed_files:
      - `backend/apps/intelligence/services/scheduler_service.py`
      - `backend/apps/intelligence/tests/test_scheduler_service.py`

---

### Task T5: 集成 django-apscheduler 与 Django 启动注册

- [ ] **状态**：未开始

**代码仓范围：**
- 根项目：`backend/apps/intelligence/apps.py`
- 子仓：无

**文件：**
- 修改：`backend/apps/intelligence/apps.py`
- 创建：`backend/apps/intelligence/scheduler.py`

**验收点：**
- Django 启动后全局扫描 Job 注册成功
- Job cron 为 `*/5 * * * *`（每 5 分钟）
- Job 调用 `scheduler_service.run_scan()`
- `python backend/manage.py runserver` 启动后日志中无 APScheduler 错误

**步骤 1：创建 scheduler 注册模块**
- 修改点：`backend/apps/intelligence/scheduler.py`
- 实现逻辑：
  ```python
  from apscheduler.schedulers.background import BackgroundScheduler
  from apscheduler.triggers.cron import CronTrigger
  from django_apscheduler.jobstores import DjangoJobStore

  def start_scheduler():
      scheduler = BackgroundScheduler()
      scheduler.add_jobstore(DjangoJobStore(), "default")
      scheduler.add_job(
          run_scan_job,
          trigger=CronTrigger(minute="*/5"),
          id="scan_all_projects",
          name="Scan all active projects",
          replace_existing=True,
      )
      scheduler.start()

  def run_scan_job():
      from apps.intelligence.services import scheduler_service
      scheduler_service.run_scan()
  ```

**步骤 2：在 apps.py 的 ready() 中注册**
- 修改点：`backend/apps/intelligence/apps.py`
- 修改为：
  ```python
  class IntelligenceConfig(AppConfig):
      default_auto_field = "django.db.models.BigAutoField"
      name = "apps.intelligence"
      verbose_name = "Competitive Intelligence"

      def ready(self):
          from apps.intelligence.scheduler import start_scheduler
          start_scheduler()
  ```

**步骤 3：运行验证**
- Run: `python backend/manage.py runserver`（启动后观察 5 秒后 Ctrl+C）
- Expected: 日志中无 APScheduler 错误，出现 Job 注册信息

**步骤 4：提交（AUTO_COMMIT=true）**
- Commit message: `集成 django-apscheduler 全局扫描 Job 注册`
- 审计信息：
  - repo: `root`
    branch: `003-scheduler-crawler`
    commit: `<TBD>`
    pr: `<TBD>`
    changed_files:
      - `backend/apps/intelligence/scheduler.py`
      - `backend/apps/intelligence/apps.py`

---

### Task T6: 端到端验证与真实站点测试

- [ ] **状态**：未开始

**代码仓范围：**
- 根项目：`backend/`
- 子仓：无

**文件：**
- 创建：`backend/apps/intelligence/tests/test_e2e_crawl.py`

**验收点：**
- 对 Spec 002 的 7 个目标站点，httpx 采集成功率 >= 5 个（或 Playwright 降级后成功）
- 每个成功站点生成的 DataSnapshot 的 clean_markdown 行数 >= 3
- 去噪后的 clean_markdown 不含 nav/footer/script/style 标签内容
- 采集失败的站点写入空快照
- 整体流程不写 IntelligenceFeed

**步骤 1：写端到端测试**
- 修改点：`backend/apps/intelligence/tests/test_e2e_crawl.py`
- 写入测试：
  - `test_e2e_real_sites`：创建一个 active 项目，`competitor_urls` 含 7 个目标站点 URL，cron 设为 `*/5 * * * *`，手动调用 `scheduler_service.run_scan()`，验证：
    - DataSnapshot 生成 7 条记录
    - 成功采集的记录 clean_markdown 行数 >= 3
    - 失败的记录 clean_markdown 为空
    - IntelligenceFeed 记录数为 0
- 注意：此测试依赖网络，标记 `@tag("e2e")` 或跳过网络不可用时的断言

**步骤 2：运行测试**
- Run: `python backend/manage.py test apps.intelligence.tests.test_e2e_crawl`
- Expected: PASS（7 条 DataSnapshot，>= 5 条 clean_markdown 非空）

**步骤 3：运行全量测试确保无回归**
- Run: `python backend/manage.py test`
- Expected: PASS（所有测试通过，无回归）

**步骤 4：提交（AUTO_COMMIT=true）**
- Commit message: `端到端验证：7 站点采集入库测试通过`
- 审计信息：
  - repo: `root`
    branch: `003-scheduler-crawler`
    commit: `<TBD>`
    pr: `<TBD>`
    changed_files:
      - `backend/apps/intelligence/tests/test_e2e_crawl.py`

---

## Merge-back 待办清单（仅记录，不在本阶段执行）

- MB-001：调度服务与采集服务的模块页（`.aisdlc/project/components/`）需在实现完成后补齐，包含服务入口、依赖关系、运维方式
- MB-002：`backend/requirements/base.txt` 新增依赖需 merge-back 到项目级依赖清单
- MB-003：cron 匹配逻辑的不变量（5 分钟窗口精度）需记录到项目知识库
