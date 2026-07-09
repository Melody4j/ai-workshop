---
title: I1 Implementation Plan（SSOT）
status: draft
---

# 调度任务与爬虫模块接入 实现计划（SSOT）

> **必需技能：** `spec-execute`（按批次执行本计划）
> **上下文获取：** 必须先执行 `spec-context` 获取上下文，定位 `{FEATURE_DIR}`，失败即停止

**目标：** 为现有 Django+Vue 骨架接入 django-apscheduler 定时调度与 httpx+BeautifulSoup+html2text 爬虫，使每个 MonitorProject 能按 cron 定时触发采集、规则去噪、写入 DataSnapshot。
**范围：** In = django-apscheduler 集成、全局扫描 Job（每 5 分钟）、next_run_at 调度匹配、MonitorProject 新增 next_run_at 字段、httpx 采集、BeautifulSoup 去噪、html2text 转 MD、Playwright 降级（clean_markdown < 3 行）、DataSnapshot 入库（含失败空快照）；Out = LLM 降噪、diff 熔断、情报生成、飞书推送、IntelligenceFeed 写入、多进程分布式锁
**架构：** Django 启动时注册全局扫描 Job（每 5 分钟）→ 扫描所有 active 项目 → 检查 `now >= project.next_run_at` → 命中项目逐 URL 用 httpx 采集 → BeautifulSoup 去噪 → html2text 转 MD → clean_markdown < 3 行降级 Playwright → 写入 DataSnapshot（失败写空快照）→ 更新 next_run_at。不修改现有 API/views/serializers。
**验收口径：** `requirements/solution.md#8-mini-prd` AC-001 ~ AC-009（AC-009 由 next_run_at save 重算保证）
**影响范围：** `requirements/solution.md#7-impact-analysis` — intelligence-models（MonitorProject 新增字段 + DataSnapshot 写入）、新增 services 层、config/settings.py、apps.py ready hook
**需遵守的不变量：**
1. 快照 append-only——DataSnapshot 禁止 UPDATE/DELETE（来源：CLAUDE.md 不变量 1）
2. httpx 优先，Playwright 仅 SPA 按需降级（来源：CLAUDE.md 不变量 7）
3. 调度限 django-apscheduler，不引入消息队列（来源：CLAUDE.md 不变量 8）
4. `competitor_urls` 必须为 JSON 数组，每项 `{"url":"...","title":"..."}`（来源：CLAUDE.md 不变量 10）
5. 本 Spec 不写 IntelligenceFeed（来源：raw.md#R1-Q1）
6. raw_markdown = 原始 HTML；clean_markdown = 去噪后 MD（来源：raw.md#R1-Q6）
**子仓范围：** 无

---

## TL;DR

- 一句话目标：接入 django-apscheduler 全局扫描 Job + httpx/BeautifulSoup/html2text/Playwright 爬虫，实现定时采集入库
- In/Out：In = 调度+采集+清洗入库；Out = LLM/diff/情报/飞书
- 关键路径：T1 依赖安装 → T2 MonitorProject next_run_at + cron 匹配 → T3 采集服务 → T4 调度服务 → T5 集成注册 → T6 端到端测试
- 最大风险与优先验证点：R1（django-apscheduler 与 runserver autoreload）、R3（httpx 采集成功率）、R5（Playwright 降级）

---

## 范围与边界（In / Out）

- **In**：
  - django-apscheduler 集成与全局扫描 Job（每 5 分钟）
  - MonitorProject 新增 `next_run_at` 字段 + save() 重算逻辑
  - croniter 计算 next_run_at
  - httpx 采集 HTML
  - BeautifulSoup 规则去噪（去 nav/footer/script/style/noscript/iframe）
  - html2text 转 MD
  - Playwright 降级（clean_markdown < 3 行）
  - DataSnapshot 入库（raw_markdown=原始HTML, clean_markdown=去噪后MD, 含失败空快照）
- **Out**：
  - LLM 降噪、diff 熔断、情报生成、飞书推送
  - IntelligenceFeed 写入
  - 多进程分布式锁
- **不变量/关键约束**：
  - 快照 append-only，不 UPDATE/DELETE
  - httpx 优先，Playwright 按需降级
  - 不引入消息队列
  - 不写 IntelligenceFeed
  - raw_markdown = 原始 HTML，clean_markdown = 去噪后 MD
- **影响面**：新增 services 层（scheduler_service + crawler_service + cron_matcher）；修改 settings.py、apps.py、models.py（新增字段）、requirements/base.txt；不修改现有 API/views/serializers

## 代码工作区清单

无子仓。

---

## 里程碑与节奏

- M0（MVP）：
  - 产物：调度服务 + 采集服务 + MonitorProject next_run_at + DataSnapshot 入库 + 端到端测试
  - 验收标准：AC-001 ~ AC-009 全部通过
  - 任务集合：T1 ~ T6

---

## 依赖与资源

- 环境/权限：Python 3.10+、`.venv` 虚拟环境、Playwright 浏览器（`playwright install chromium`）
- 外部系统/团队：无
- 数据/样本：Spec 002 的 7 个目标站点（ihuiwa.com、x-design.com、piccopilot.com、weshop.ai、bandy.ai、thenewblack.ai、lovable.dev）
- 发布/变更窗口：无

---

## 风险与验证（可执行）

| # | 风险/假设 | 验证方式 | 成功信号 | 失败信号 | Owner | 截止 | 下一步动作 |
|---|---|---|---|---|---|---|---|
| R1 | django-apscheduler 在 runserver autoreload 下双重启动 | 用 RUN_MAIN 守卫，启动 runserver 观察日志 | 仅一个 scheduler 实例 | 两个 scheduler 实例 | FS | I2 | 改用 `--noreload` 或条件检测 |
| R2 | croniter next_run_at 计算错误 | 单元测试覆盖典型 cron | 所有测试通过 | 测试失败 | FS | I2 | 检查 croniter API 用法 |
| R3 | httpx 对部分站点可能被反爬 | 对 7 个目标站点逐一测试 | >= 5 个站点直接成功 | < 5 个站点成功 | FS | I2 | 评估默认启用 Playwright |
| R4 | BeautifulSoup 去噪可能误删正文 | 对比去噪前后 markdown | 正文核心内容保留 | 正文被误删 | FS | I2 | 补充 CSS selector 精确定位 |
| R5 | Playwright 降级后仍可能拿不到内容 | 对 httpx 失败站点测试 Playwright | markdown >= 3 行 | markdown < 3 行 | FS | I2 | 写空快照记录失败 |
| R6 | 多 URL 串行采集耗时过长 | 测量 10 URL 串行总耗时 | < 60s | >= 60s | FS | I2 | 引入 httpx async 或线程池 |

---

## 验收口径（可追溯）

- 追溯：`requirements/solution.md#8-mini-prd` AC-001 ~ AC-009
- 关键验收点：
  - AC-001：全局扫描 Job 每 5 分钟触发（T5 手动验证 + T6 间接验证）
  - AC-002：active 且 next_run_at <= now 的项目被触发
  - AC-003：is_active=False 的项目不触发
  - AC-004：每个 URL 生成一条 DataSnapshot（raw_markdown=HTML, clean_markdown=MD）
  - AC-005：clean_markdown < 3 行自动降级 Playwright
  - AC-006：采集失败写空快照，不中断其他 URL
  - AC-007：BeautifulSoup 去噪移除 nav/footer/script/style
  - AC-008：不写 IntelligenceFeed
  - AC-009：cron 变更后 save() 重算 next_run_at，无需重启即生效

---

## NEEDS CLARIFICATION（未消除前不得进入 I2）

无。所有关键不确定项已在 R1 澄清 + plan 评审澄清中消除。

---

## 任务清单（SSOT）

### Task T1: 安装依赖与配置 settings.py

- [x] **状态**：完成

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
- `python backend/manage.py migrate` 无报错（django_apscheduler 表创建）

**步骤 1：添加依赖到 base.txt**
- 修改点：`backend/requirements/base.txt`，追加以下行：
  ```
  django-apscheduler>=0.7.0,<0.8.0
  httpx>=0.27.0,<0.28.0
  html2text>=2024.2.26
  beautifulsoup4>=4.12.0,<5.0.0
  playwright>=1.40.0,<2.0.0
  croniter>=2.0.0,<3.0.0
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

**步骤 5：执行 migrate（创建 django_apscheduler 表）**
- Run: `python backend/manage.py migrate`
- Expected: 无报错，输出中包含 django_apscheduler 相关 migration

**步骤 6：运行验证**
- Run: `python backend/manage.py check`
- Expected: 无错误，输出 "System check identified no issues"

**步骤 7：提交（AUTO_COMMIT=true）**
- Commit message: `安装调度与爬虫依赖并配置 settings`
- 审计信息：
  - repo: `root`
    branch: `003-scheduler-crawler`
    commit: `cfe3e4c`

---

### Task T2: MonitorProject 新增 next_run_at 字段 + cron 匹配逻辑

- [x] **状态**：完成

**代码仓范围：**
- 根项目：`backend/apps/intelligence/models.py`、`backend/apps/intelligence/services/`
- 子仓：无

**文件：**
- 修改：`backend/apps/intelligence/models.py`（MonitorProject 新增字段 + save 重算）
- 创建：`backend/apps/intelligence/migrations/0003_monitorproject_next_run_at.py`（或 makemigrations 生成）
- 确认：`backend/apps/intelligence/services/__init__.py`（已存在，当前目录含 report_seed.py）
- 创建：`backend/apps/intelligence/services/cron_matcher.py`
- 创建：`backend/apps/intelligence/tests/test_cron_matcher.py`

**验收点：**
- `get_next_run(cron_expr, after)` 返回 after 之后的下一个 cron 匹配时间
- `get_next_run("*/5 * * * *", datetime(2026, 7, 8, 14, 3))` → `datetime(2026, 7, 8, 14, 5)`
- `get_next_run("0 9 * * *", datetime(2026, 7, 8, 9, 2))` → `datetime(2026, 7, 9, 9, 0)`（今天 9:00 已过）
- `get_next_run("0 9 * * 1", datetime(2026, 7, 7, 9, 3))` → `datetime(2026, 7, 13, 9, 0)`（下周一）
- MonitorProject 新增 `next_run_at = DateTimeField(null=True, blank=True)`
- MonitorProject.save() 中 cron 变更时重算 next_run_at
- migration 生成并执行成功

**步骤 1：写失败测试**
- 修改点：`backend/apps/intelligence/tests/test_cron_matcher.py`
- 写入测试：
  - `test_every_5_minutes`：`get_next_run("*/5 * * * *", datetime(2026, 7, 8, 14, 3))` → `datetime(2026, 7, 8, 14, 5)`
  - `test_daily_9am_same_day_before`：`get_next_run("0 9 * * *", datetime(2026, 7, 8, 8, 30))` → `datetime(2026, 7, 8, 9, 0)`（今天 9:00 未到）
  - `test_daily_9am_same_day_after`：`get_next_run("0 9 * * *", datetime(2026, 7, 8, 9, 2))` → `datetime(2026, 7, 9, 9, 0)`（今天 9:00 已过，明天）
  - `test_every_30min`：`get_next_run("*/30 * * * *", datetime(2026, 7, 8, 14, 17))` → `datetime(2026, 7, 8, 14, 30)`
  - `test_weekly_monday_9am`：`get_next_run("0 9 * * 1", datetime(2026, 7, 7, 9, 3))` → `datetime(2026, 7, 13, 9, 0)`（2026-07-07 是周二，下周一 7/13）
  - `test_non_5_multiple_minute`：`get_next_run("3 9 * * *", datetime(2026, 7, 8, 9, 0))` → `datetime(2026, 7, 8, 9, 3)`（非 5 倍数分钟也能计算，实际触发在最近 5 分钟扫描周期）
- Run: `python backend/manage.py test apps.intelligence.tests.test_cron_matcher`
- Expected: FAIL（模块不存在）

**步骤 2：写 cron_matcher 实现**
- 修改点：`backend/apps/intelligence/services/cron_matcher.py`
- 实现逻辑：
  ```python
  from croniter import croniter
  from datetime import datetime

  def get_next_run(cron_expr: str, after: datetime) -> datetime:
      """计算 after 之后的下一个 cron 匹配时间。"""
      return croniter(cron_expr, after).get_next(datetime)
  ```

**步骤 3：修改 MonitorProject 模型**
- 修改点：`backend/apps/intelligence/models.py`
  - MonitorProject 新增字段：`next_run_at = models.DateTimeField(null=True, blank=True)`
  - 覆盖 `save()`：当 pk 不存在（新建）或 cron 字段变更时，重算 next_run_at
    ```python
    def save(self, *args, **kwargs):
        from apps.intelligence.services.cron_matcher import get_next_run
        if not self.pk or self._state.adding:
            # 新建项目
            self.next_run_at = get_next_run(self.cron, timezone.now())
        else:
            # 更新：检查 cron 是否变更
            old = MonitorProject.objects.filter(pk=self.pk).values_list("cron", flat=True).first()
            if old != self.cron:
                self.next_run_at = get_next_run(self.cron, timezone.now())
        super().save(*args, **kwargs)
    ```

**步骤 4：生成并执行 migration**
- Run: `python backend/manage.py makemigrations intelligence`
- Expected: 生成 `0003_monitorproject_next_run_at.py`
- Run: `python backend/manage.py migrate`
- Expected: 无报错

**步骤 5：运行验证**
- Run: `python backend/manage.py test apps.intelligence.tests.test_cron_matcher`
- Expected: PASS（所有测试通过）

**步骤 6：提交（AUTO_COMMIT=true）**
- Commit message: `新增 next_run_at 字段与 croniter 匹配逻辑`
- 审计信息：
  - repo: `root`
    branch: `003-scheduler-crawler`
    commit: `a0d0aba`

- [x] **状态**：完成

**代码仓范围：**
- 根项目：`backend/apps/intelligence/services/`
- 子仓：无

**文件：**
- 创建：`backend/apps/intelligence/services/crawler_service.py`
- 创建：`backend/apps/intelligence/tests/test_crawler_service.py`

**验收点：**
- `fetch_and_clean(url)` 返回 `(raw_markdown, clean_markdown)` 元组
- raw_markdown = httpx/Playwright 返回的原始 HTML 字符串
- clean_markdown = BeautifulSoup 去噪后 HTML 经 html2text 转换的 MD 字符串
- clean_markdown 行数 < 3 时自动降级 Playwright
- Playwright 降级时 raw_markdown 和 clean_markdown 都基于 Playwright 的 HTML 重新生成
- httpx 采集失败时降级 Playwright
- httpx + Playwright 都失败时返回 `("", "")`
- BeautifulSoup 去噪移除了 nav/footer/script/style/noscript/iframe 标签

**步骤 1：写失败测试**
- 修改点：`backend/apps/intelligence/tests/test_crawler_service.py`
- 写入测试：
  - `test_fetch_success`：mock httpx 返回正常 HTML（含 nav/footer），验证 raw_markdown=原始HTML、clean_markdown 不含 nav/footer 内容且行数 >= 3
  - `test_dedup_removes_nav_footer`：给定含 nav/footer/script/style/noscript/iframe 的 HTML，验证 clean_markdown 不含这些标签内容
  - `test_fetch_degrade_to_playwright`：mock httpx 返回极少内容（clean_markdown < 3 行），mock Playwright 返回正常内容，验证降级触发且 raw/clean 基于 Playwright HTML
  - `test_fetch_httpx_error_degrades_to_playwright`：mock httpx 抛 RequestError，mock Playwright 返回正常内容，验证降级触发
  - `test_playwright_also_fails_returns_empty`：mock httpx 返回 < 3 行，mock Playwright 也抛异常，验证返回 `("", "")`
  - `test_fetch_completely_fails_returns_empty`：mock httpx 抛异常 + mock Playwright 抛异常，验证返回 `("", "")`
- Run: `python backend/manage.py test apps.intelligence.tests.test_crawler_service`
- Expected: FAIL（模块不存在）

**步骤 2：写最少实现**
- 修改点：`backend/apps/intelligence/services/crawler_service.py`
- 实现逻辑：
  ```python
  import logging
  import httpx
  from bs4 import BeautifulSoup
  import html2text
  from playwright.sync_api import sync_playwright, Error as PlaywrightError

  logger = logging.getLogger(__name__)

  def fetch_and_clean(url: str) -> tuple[str, str]:
      """
      采集 URL 并清洗为 markdown。
      返回 (raw_markdown, clean_markdown)。
      raw_markdown = 原始 HTML 字符串。
      clean_markdown = BeautifulSoup 去噪后 HTML 经 html2text 转换的 MD。
      失败返回 ("", "")。
      """
      # 1. httpx 采集
      raw_html = _fetch_with_httpx(url)
      if raw_html:
          clean_md = _clean_html_to_md(raw_html)
          if clean_md.strip().count("\n") >= 2:  # >= 3 行
              logger.info(f"httpx 采集成功: {url}")
              return (raw_html, clean_md)
          logger.warning(f"httpx 采集内容不足 3 行，降级 Playwright: {url}")

      # 2. Playwright 降级
      raw_html_pw = _fetch_with_playwright(url)
      if raw_html_pw:
          clean_md_pw = _clean_html_to_md(raw_html_pw)
          logger.info(f"Playwright 采集成功: {url}")
          return (raw_html_pw, clean_md_pw)

      # 3. 全部失败
      logger.error(f"采集失败: {url}")
      return ("", "")

  def _fetch_with_httpx(url: str) -> str:
      """httpx GET，返回 HTML 字符串，失败返回空字符串。"""
      try:
          resp = httpx.get(url, timeout=30, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0"})
          resp.raise_for_status()
          return resp.text
      except httpx.RequestError as e:
          logger.warning(f"httpx 请求失败: {url} - {e}")
          return ""
      except httpx.HTTPStatusError as e:
          logger.warning(f"httpx 状态码异常: {url} - {e}")
          return ""

  def _fetch_with_playwright(url: str) -> str:
      """Playwright 采集，返回 HTML 字符串，失败返回空字符串。"""
      try:
          with sync_playwright() as p:
              browser = p.chromium.launch()
              page = browser.new_page()
              page.goto(url, timeout=30)
              html = page.content()
              browser.close()
              return html
      except PlaywrightError as e:
          logger.warning(f"Playwright 采集失败: {url} - {e}")
          return ""
      except Exception as e:
          logger.warning(f"Playwright 未知异常: {url} - {e}")
          return ""

  def _clean_html_to_md(html: str) -> str:
      """BeautifulSoup 去噪 + html2text 转 MD。"""
      soup = BeautifulSoup(html, "html.parser")
      for tag in soup.find_all(["nav", "footer", "script", "style", "noscript", "iframe"]):
          tag.decompose()
      h = html2text.HTML2Text()
      h.body_width = 0  # 不折行
      return h.handle(str(soup))
  ```

**步骤 3：运行验证**
- Run: `python backend/manage.py test apps.intelligence.tests.test_crawler_service`
- Expected: PASS（所有测试通过）

**步骤 4：提交（AUTO_COMMIT=true）**
- Commit message: `实现采集服务：httpx+BeautifulSoup+html2text+Playwright 降级`
- 审计信息：
  - repo: `root`
    branch: `003-scheduler-crawler`
    commit: `a37df06`

---

### Task T4: 实现调度服务（scheduler_service）

- [x] **状态**：完成

**代码仓范围：**
- 根项目：`backend/apps/intelligence/services/`
- 子仓：无

**文件：**
- 创建：`backend/apps/intelligence/services/scheduler_service.py`
- 创建：`backend/apps/intelligence/tests/test_scheduler_service.py`

**验收点：**
- `run_scan()` 查询所有 `is_active=True` 且 `next_run_at <= now`（或 `next_run_at is None`）的项目
- 命中项目逐 URL 调用 `crawler_service.fetch_and_clean(url)`
- 空 URL 被跳过，不写快照
- 每个 URL（无论成功/失败）写入一条 DataSnapshot
- 不写 IntelligenceFeed
- 失败的 URL 写空快照（raw_markdown="" / clean_markdown=""）
- 单个 URL 失败不中断其他 URL
- 项目执行后更新 `next_run_at = get_next_run(cron, now)`

**步骤 1：写失败测试**
- 修改点：`backend/apps/intelligence/tests/test_scheduler_service.py`
- 写入测试：
  - `test_run_scan_active_project_due`：创建 active 项目 + next_run_at 设为过去时间，mock `fetch_and_clean` 返回正常内容，验证 DataSnapshot 写入 + next_run_at 更新
  - `test_run_scan_active_project_not_due`：创建 active 项目 + next_run_at 设为未来时间，验证不触发采集
  - `test_run_scan_inactive_project_skipped`：创建 inactive 项目，验证不触发采集
  - `test_run_scan_next_run_at_none_triggers`：创建 active 项目 + next_run_at=None，验证触发采集并更新 next_run_at
  - `test_run_scan_fetch_failure_writes_empty_snapshot`：mock `fetch_and_clean` 返回 `("", "")`，验证写入空快照
  - `test_run_scan_does_not_write_intelligence_feed`：执行后 IntelligenceFeed 数量为 0
  - `test_run_scan_partial_failure_continues`：项目有 3 个 URL，第 1 个 mock 失败，验证第 2/3 个仍被采集并写入
  - `test_run_scan_empty_url_skipped`：项目含空 URL 的 competitor_urls 项，验证跳过不写快照
  - `test_run_scan_updates_next_run_at`：执行后 next_run_at 被更新为未来时间
- Run: `python backend/manage.py test apps.intelligence.tests.test_scheduler_service`
- Expected: FAIL（模块不存在）

**步骤 2：写最少实现**
- 修改点：`backend/apps/intelligence/services/scheduler_service.py`
- 实现逻辑：
  ```python
  import logging
  from django.utils import timezone
  from apps.intelligence.models import MonitorProject, DataSnapshot
  from apps.intelligence.services import crawler_service
  from apps.intelligence.services.cron_matcher import get_next_run

  logger = logging.getLogger(__name__)

  def run_scan():
      now = timezone.now()
      active_projects = MonitorProject.objects.filter(is_active=True)
      for project in active_projects:
          if project.next_run_at is not None and project.next_run_at > now:
              logger.debug(f"项目未到期: {project.project_name} (next: {project.next_run_at})")
              continue
          logger.info(f"开始执行项目: {project.project_name}")
          urls = project.competitor_urls or []
          for item in urls:
              url = (item or {}).get("url", "")
              if not url:
                  logger.warning(f"跳过空 URL: {project.project_name}")
                  continue
              title = (item or {}).get("title", "")
              try:
                  raw_md, clean_md = crawler_service.fetch_and_clean(url)
              except Exception as e:
                  logger.error(f"采集异常: {url} - {e}")
                  raw_md, clean_md = "", ""
              DataSnapshot.objects.create(
                  project=project,
                  source_url=url,
                  source_title=title,
                  raw_markdown=raw_md,
                  clean_markdown=clean_md,
                  fetch_time=now,
              )
          # 更新 next_run_at
          project.next_run_at = get_next_run(project.cron, now)
          project.save(update_fields=["next_run_at"])
          logger.info(f"项目执行完成: {project.project_name} (next: {project.next_run_at})")
  ```
  - 注意：`save(update_fields=["next_run_at"])` 只更新 next_run_at，不触发 save() 中的 cron 重算逻辑

**步骤 3：运行验证**
- Run: `python backend/manage.py test apps.intelligence.tests.test_scheduler_service`
- Expected: PASS（所有测试通过）

**步骤 4：提交（AUTO_COMMIT=true）**
- Commit message: `实现调度服务：全局扫描+next_run_at 匹配+逐 URL 采集入库`
- 审计信息：
  - repo: `root`
    branch: `003-scheduler-crawler`
    commit: `c472319` 集成 django-apscheduler 与 Django 启动注册

- [x] **状态**：完成

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
- runserver autoreload 下仅启动一个 scheduler 实例（RUN_MAIN 守卫）
- scheduler 在进程退出时优雅关闭（atexit）
- `python backend/manage.py runserver` 启动后日志中无 APScheduler 错误
- 日志中出现 Job 注册成功信息

**步骤 1：创建 scheduler 注册模块**
- 修改点：`backend/apps/intelligence/scheduler.py`
- 实现逻辑：
  ```python
  import atexit
  import logging
  from apscheduler.schedulers.background import BackgroundScheduler
  from apscheduler.triggers.cron import CronTrigger
  from django_apscheduler.jobstores import DjangoJobStore

  logger = logging.getLogger(__name__)
  _scheduler = None

  def start_scheduler():
      global _scheduler
      if _scheduler is not None:
          return  # 防止重复启动
      _scheduler = BackgroundScheduler()
      _scheduler.add_jobstore(DjangoJobStore(), "default")
      _scheduler.add_job(
          run_scan_job,
          trigger=CronTrigger(minute="*/5"),
          id="scan_all_projects",
          name="Scan all active projects",
          replace_existing=True,
      )
      _scheduler.start()
      atexit.register(lambda: _scheduler.shutdown(wait=False))
      logger.info("APScheduler 已启动，全局扫描 Job 已注册 (每 5 分钟)")

  def run_scan_job():
      from apps.intelligence.services import scheduler_service
      scheduler_service.run_scan()
  ```

**步骤 2：在 apps.py 的 ready() 中注册（含 RUN_MAIN 守卫）**
- 修改点：`backend/apps/intelligence/apps.py`
- 修改为：
  ```python
  import os
  from django.apps import AppConfig

  class IntelligenceConfig(AppConfig):
      default_auto_field = "django.db.models.BigAutoField"
      name = "apps.intelligence"
      verbose_name = "Competitive Intelligence"

      def ready(self):
          # runserver autoreload 下仅在 worker 进程启动 scheduler
          if os.environ.get("RUN_MAIN") == "true":
              from apps.intelligence.scheduler import start_scheduler
              start_scheduler()
  ```
  - 说明：`runserver` 默认 autoreload 会启动两个进程（watcher + worker），`RUN_MAIN=true` 仅在 worker 进程中设置。生产环境（gunicorn/uwsgi）不设 `RUN_MAIN`，此时需另行处理——MVP 阶段仅支持 runserver。

**步骤 3：运行验证**
- Run: `python backend/manage.py runserver`（启动后观察 5 秒后 Ctrl+C）
- Expected: 日志中出现 "APScheduler 已启动" 信息，无重复启动、无 APScheduler 错误

**步骤 4：提交（AUTO_COMMIT=true）**
- Commit message: `集成 django-apscheduler 全局扫描 Job 注册（含 autoreload 守卫与优雅关闭）`
- 审计信息：
  - repo: `root`
    branch: `003-scheduler-crawler`
    commit: `b4842b4`

---

### Task T6: 端到端验证与真实站点测试

- [x] **状态**：完成

**代码仓范围：**
- 根项目：`backend/`
- 子仓：无

**文件：**
- 创建：`backend/apps/intelligence/tests/test_e2e_crawl.py`

**验收点：**
- 对 Spec 002 的 7 个目标站点，httpx 采集成功率 >= 5 个（或 Playwright 降级后成功）
- 每个成功站点生成的 DataSnapshot 的 clean_markdown 行数 >= 3
- raw_markdown 为原始 HTML 字符串（非空时）
- 去噪后的 clean_markdown 不含 nav/footer/script/style 标签内容
- 采集失败的站点写入空快照（raw_markdown="" / clean_markdown=""）
- 整体流程不写 IntelligenceFeed
- next_run_at 执行后被更新为未来时间

**步骤 1：写端到端测试**
- 修改点：`backend/apps/intelligence/tests/test_e2e_crawl.py`
- 写入测试：
  ```python
  from django.test import TestCase, tag
  from apps.intelligence.models import MonitorProject, DataSnapshot, IntelligenceFeed
  from apps.intelligence.services import scheduler_service
  from django.utils import timezone
  from datetime import timedelta

  @tag("e2e", "network")
  class E2ECrawlTest(TestCase):
      def test_e2e_real_sites(self):
          project = MonitorProject.objects.create(
              project_name="E2E Test",
              competitor_urls=[
                  {"url": "https://www.ihuiwa.com/", "title": "ihuiwa"},
                  {"url": "https://www.x-design.com/", "title": "x-design"},
                  {"url": "https://www.piccopilot.com/", "title": "piccopilot"},
                  {"url": "https://www.weshop.ai/", "title": "weshop"},
                  {"url": "https://bandy.ai/", "title": "bandy"},
                  {"url": "https://thenewblack.ai/", "title": "thenewblack"},
                  {"url": "https://lovable.dev/", "title": "lovable"},
              ],
              cron="*/5 * * * *",
              is_active=True,
          )
          # 绕过 save() 覆盖，手动设 next_run_at 为过去时间触发执行
          MonitorProject.objects.filter(pk=project.pk).update(
              next_run_at=timezone.now() - timedelta(minutes=1)
          )
          project.refresh_from_db()
          scheduler_service.run_scan()
          # 7 条 DataSnapshot
          self.assertEqual(DataSnapshot.objects.filter(project=project).count(), 7)
          # >= 5 条 clean_markdown 非空
          success_count = DataSnapshot.objects.filter(
              project=project, clean_markdown__gt=""
          ).count()
          self.assertGreaterEqual(success_count, 5)
          # 不写 IntelligenceFeed
          self.assertEqual(IntelligenceFeed.objects.filter(project=project).count(), 0)
          # next_run_at 已更新为未来
          project.refresh_from_db()
          self.assertGreater(project.next_run_at, timezone.now())
  ```

**步骤 2：运行 E2E 测试（需网络）**
- Run: `python backend/manage.py test apps.intelligence.tests.test_e2e_crawl --tag=e2e`
- Expected: PASS（7 条 DataSnapshot，>= 5 条 clean_markdown 非空）

**步骤 3：运行全量测试（排除 E2E）确保无回归**
- Run: `python backend/manage.py test --exclude-tag=e2e`
- Expected: PASS（所有非 E2E 测试通过，无回归）

**步骤 4：提交（AUTO_COMMIT=true）**
- Commit message: `端到端验证：7 站点采集入库测试通过`
- 审计信息：
  - repo: `root`
    branch: `003-scheduler-crawler`
    commit: `fc7be76`

---

## Merge-back 待办清单（仅记录，不在本阶段执行）

- MB-001：调度服务与采集服务的模块页（`.aisdlc/project/components/`）需在实现完成后补齐，包含服务入口、依赖关系、运维方式
- MB-002：`backend/requirements/base.txt` 新增依赖需 merge-back 到项目级依赖清单
- MB-003：next_run_at 字段与 croniter 匹配逻辑需记录到项目知识库（含"cron 变更 save 重算"不变量）
- MB-004：runserver RUN_MAIN 守卫的局限性需记录（生产环境需另行处理）
