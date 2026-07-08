---
title: 调度任务与爬虫模块接入（Solutionate）
status: draft
---

> 目的：把"推荐决策 + 备选方案对比 + 决策依据 + 验证清单"落到一份可评审文档里，作为后续 `prd.md` 与 `prototype.md` 的**唯一决策入口**。
>
> 原则：结论先行；只保留支撑决策的最小信息；不写"待确认问题"清单——所有不确定性统一进入"验证清单"（Owner/截止/动作明确）。

## 0. 基本信息

- 需求标识（分支 / ID）：003-scheduler-crawler
- 作者 / 参与评审：FS（作者）；PM（待评审）
- 状态：draft
- 最后更新：2026-07-08
- 关联链接：`{FEATURE_DIR}/requirements/raw.md`（含 5 轮澄清记录）

## 1. 结论摘要（先给结论）

- 一句话目标：为现有 Django+Vue 骨架接入 django-apscheduler 定时调度与 httpx+BeautifulSoup+html2text 爬虫，使每个 MonitorProject 能按 cron 定时触发采集、规则去噪、写入 DataSnapshot。
- 本次 In / Out 的边界：In = django-apscheduler 集成、全局扫描 Job（每 5 分钟）、cron 窗口匹配、httpx 采集、BeautifulSoup 规则去噪、html2text 转 MD、Playwright 降级（markdown < 3 行）、DataSnapshot 入库（含失败空快照）；Out = LLM 降噪、diff 熔断、情报生成、飞书推送、IntelligenceFeed 写入、last_run_at 字段。
- 推荐方案：**"全局扫描 Job + httpx 采集 + BeautifulSoup 去噪 + html2text 转 MD + Playwright 兜底 + 空快照容错"最小闭环**——注册一个每 5 分钟触发的全局 Job，扫描所有 active 项目，用 5 分钟窗口匹配 cron，命中的项目逐 URL 采集去噪入库。
- 优先验证点：V-001（django-apscheduler 与 Django 进程集成）、V-003（cron 5 分钟窗口匹配正确性）、V-005（httpx 对目标站点的采集成功率）。

## 2. 推荐方案

- 方案名：**全局扫描 Job + 规则去噪爬虫（Global-Scan Scheduler + Rule-Based Crawler）**

- 主流程 / 关键机制：
  1. **调度注册（Django 启动时）**：在 Django `apps.py` 的 `ready()` 中向 django-apscheduler 注册一个全局 Job，cron 为 `*/5 * * * *`（每 5 分钟），该 Job 调用 `scheduler_service.run_scan()`。
  2. **全局扫描（每 5 分钟）**：`run_scan()` 查询所有 `is_active=True` 的 `MonitorProject`，对每个项目调用 `cron_matcher.is_due(project.cron, now)` 判断是否到期。
  3. **cron 窗口匹配**：`is_due(cron_expr, now)` 检查"当前时间所在的 5 分钟窗口是否匹配该 cron 表达式"——将 `now` 的分钟对齐到 5 分钟窗口起点，检查窗口内是否有分钟满足 cron。无需 `last_run_at` 字段。
  4. **逐 URL 采集（命中的项目）**：对 `competitor_urls` 中的每个 URL，调用 `crawler.fetch(url)` → httpx GET → BeautifulSoup 去噪（去 nav/footer/script/style）→ html2text 转 MD。
  5. **Playwright 降级**：若 httpx 产出的 markdown 行数 < 3，降级用 Playwright（JS 注入）重新采集，再走相同的去噪+html2text 链路。
  6. **入库（含失败容错）**：采集成功 → 写 `DataSnapshot(raw_markdown=原始HTML转MD, clean_markdown=去噪后MD, fetch_time=now)`；采集失败 → 写 `DataSnapshot(raw_markdown="", clean_markdown="", fetch_time=now)`（空快照，不抛异常，不中断其他 URL）。

- 关键边界 / 取舍：
  1. **全局扫描 Job，非每项目一 Job**：避免 cron 变更时的重注册复杂度；代价是需要自己实现 cron 窗口匹配逻辑。
  2. **cron 精度限于 5 分钟**：用户配置的 cron 分钟位会被对齐到 5 分钟窗口；不支持"第 3 分钟"这种非 5 的倍数的分钟配置。
  3. **BeautifulSoup 规则去噪，不用 LLM**：沿用 Spec 002 验证的策略，去 nav/footer/script/style；不在本 Spec 引入 LLM 降噪。
  4. **采集失败写空快照**：保证每次调度都有可追溯的快照记录；不写 IntelligenceFeed（维持范围约束）。
  5. **不补执行停机错过的调度**：单用户 MVP 容错策略，服务器重启后不追溯历史。
  6. **不新增 MonitorProject 字段**：不需要 `last_run_at`；cron 匹配基于时间窗口，不依赖历史执行记录。

- 为什么选它（可追溯到证据）：
  1. `raw.md#R1-Q1`：范围裁定为止步于 DataSnapshot 入库，不包含 LLM/diff/情报/飞书。
  2. `raw.md#R1-Q2`：调度粒度选择全局扫描 Job，避免重注册。
  3. `raw.md#R1-Q3`：采集失败写空快照，不跳过不写 IntelligenceFeed。
  4. `raw.md#R1-Q4`：扫描频率每 5 分钟，cron 精度限于 5 分钟。
  5. `raw.md#R1-Q5`：不需要 last_run_at，cron 匹配基于 5 分钟窗口。
  6. Spec 002 `raw.md`：已验证 httpx + BeautifulSoup + html2text + Playwright 降级（markdown < 3 行）的可行性。

## 3. 备选方案

### 3.1 备选方案：每项目一 Job

- 核心机制：每个 `MonitorProject` 注册一个独立的 django-apscheduler Job，各自按自己的 cron 触发。
- 主流程：项目创建/更新时 → 注册/更新对应 Job → Job 到期时采集该项目所有 URL。
- 边界与取舍：cron 变更时需重注册对应 Job；项目删除时需注销 Job。
- 适用前提：每个项目需要独立的、精确到分钟的 cron 调度。
- 不选原因：`raw.md#R1-Q2` 已裁定选择全局扫描 Job，避免重注册复杂度；单用户场景下每项目一 Job 的灵活性过剩。

### 3.2 备选方案：全局日级 Job

- 核心机制：注册一个每天固定时间触发的全局 Job（如每天 9:00），一次遍历所有 active 项目。
- 主流程：每日 9:00 → 扫描所有 active 项目 → 逐 URL 采集入库。
- 边界与取舍：所有项目同一时间执行；无法各自定制 cron。
- 适用前提：所有项目都用相同的日级调度频率。
- 不选原因：`MonitorProject.cron` 字段已存在且默认 `"0 9 * * *"`，用户期望各自定制 cron；`raw.md#R1-Q2` 已选择全局扫描 Job 支持 per-project cron。

### 3.3 备选方案：采集失败仅记日志不入库

- 核心机制：采集失败的 URL 不写 DataSnapshot，仅写 Python logging 日志。
- 主流程：httpx/Playwright 失败 → 记日志 → 跳过该 URL → 其他 URL 正常入库。
- 边界与取舍：失败不可从 DB 追溯；需查日志才能排障。
- 适用前提：失败率极低且不关心历史失败记录。
- 不选原因：`raw.md#R1-Q3` 已裁定写空快照记录，保证每次调度都有可追溯的快照。

## 4. 决策依据（证据入口清单）

- `raw.md#需求描述`：调度任务接入 + 爬虫模块接入的原始需求。
- `raw.md#R1-Q1`：范围裁定为止步于 DataSnapshot 入库。
- `raw.md#R1-Q2`：调度粒度选择全局扫描 Job。
- `raw.md#R1-Q3`：采集失败写空快照记录。
- `raw.md#R1-Q4`：扫描频率每 5 分钟。
- `raw.md#R1-Q5`：不需要 last_run_at，cron 匹配基于 5 分钟窗口。
- `.aisdlc/specs/002-crawler-feasibility-test/requirements/raw.md`：已验证 httpx + BeautifulSoup + html2text + Playwright 降级（markdown < 3 行）的可行性。
- `backend/apps/intelligence/models.py`：现有 MonitorProject（含 cron 字段）与 DataSnapshot 模型。
- `.aisdlc/project/components/index.md`：现有模块地图（intelligence-api、intelligence-models）。

## 5. 验证清单（V-xxx，可执行）

- **V-001** django-apscheduler 与 Django 进程集成
  - 风险/假设：django-apscheduler 在 Django runserver 下能正常注册并触发 Job
  - 方法：在 `apps.py ready()` 中注册全局 Job，启动 `runserver`，观察日志确认每 5 分钟触发
  - 成功/失败信号：日志中每 5 分钟出现扫描记录，无重复触发
  - Owner：FS
  - 截止：I2
  - 触发动作：若 runserver 下不触发，检查是否需要 `--noreload` 或切换到 `runserver_plus`

- **V-002** cron 窗口匹配正确性
  - 风险/假设：5 分钟窗口匹配逻辑可能遗漏或重复匹配 cron 表达式
  - 方法：编写单元测试，覆盖 `*/5`、`0 9 * * *`、`*/30 * * * *` 等典型 cron，验证在多个时间点的匹配结果
  - 成功/失败信号：所有测试用例通过，无遗漏/重复
  - Owner：FS
  - 截止：I2
  - 触发动作：若匹配逻辑有误，改用 `croniter` 库做区间匹配

- **V-003** httpx 对目标站点的采集成功率
  - 风险/假设：部分目标站点可能反爬或需特定 headers
  - 方法：对 Spec 002 的 7 个目标站点逐一测试 httpx 采集，记录成功率与 markdown 行数
  - 成功/失败信号：>= 5 个站点 httpx 直接成功（markdown >= 3 行）；剩余站点 Playwright 降级成功
  - Owner：FS
  - 截止：I2
  - 触发动作：若 httpx 成功率 < 50%，评估是否默认启用 Playwright

- **V-004** BeautifulSoup 去噪后 markdown 质量
  - 风险/假设：规则去噪可能误删正文内容或残留噪音
  - 方法：对比去噪前后的 markdown，检查是否保留正文核心内容
  - 成功/失败信号：去噪后 markdown 保留正文核心内容，nav/footer/script/style 已移除
  - Owner：FS
  - 截止：I2
  - 触发动作：若去噪质量不足，补充 CSS selector 精确定位正文区域

- **V-005** Playwright 降级触发与成功率
  - 风险/假设：markdown < 3 行时 Playwright 能拿到有效内容
  - 方法：对 httpx 失败的站点测试 Playwright 降级，记录成功率和内容质量
  - 成功/失败信号：Playwright 降级后 markdown >= 3 行
  - Owner：FS
  - 截止：I2
  - 触发动作：若 Playwright 仍失败，写空快照并记录失败原因

- **V-006** 采集失败空快照可追溯性
  - 风险/假设：空快照（raw_markdown/clean_markdown 为空）能否从 DB 查询中区分"失败"与"正常空页面"
  - 方法：在 DataSnapshot 查询中过滤 `clean_markdown=""` 的记录，验证可追溯失败
  - 成功/失败信号：能从 DB 查出失败记录并关联到具体项目/URL/时间
  - Owner：FS
  - 截止：I2
  - 触发动作：若区分困难，考虑在 DataSnapshot 增加 `fetch_status` 字段（P1 优化）

- **V-007** 多 URL 并发采集性能
  - 风险/假设：单项目 5-10 个 URL 串行采集可能耗时过长
  - 方法：测量单项目 10 个 URL 的串行采集总耗时
  - 成功/失败信号：总耗时 < 60s（单用户日级场景可接受）
  - Owner：FS
  - 截止：I2
  - 触发动作：若 > 60s，引入 httpx async 或线程池并发

- **V-008** django-apscheduler 在多进程下的行为
  - 风险/假设：若未来用 gunicorn 多 worker 部署，Job 可能被多进程重复触发
  - 方法：查阅 django-apscheduler 文档，确认多进程下的行为
  - 成功/失败信号：单 worker 部署（runserver）下无重复触发
  - Owner：FS
  - 截止：I2
  - 触发动作：若多进程重复触发，引入分布式锁或限制单 worker

## 6. Context Gaps

- `.aisdlc/project/components/intelligence-api.md`：未读取，标记 `CONTEXT GAP`——该模块页可能包含 API 契约的权威定义，本 Spec 新增调度服务不直接修改 API 层，但需确认无冲突。
- `.aisdlc/project/components/intelligence-models.md`：未读取，标记 `CONTEXT GAP`——该模块页可能包含数据模型的权威定义与不变量，本 Spec 新增 DataSnapshot 写入逻辑需遵守其约束。
- Spec 002 的实现代码：`raw.md` 提到验证 httpx + BeautifulSoup + html2text 的可行性，但实现代码位置未确认，标记 `CONTEXT GAP`——需在 I1 确认是否可复用 Spec 002 的脚本代码。

## 7. Impact Analysis

### 7.1 受影响模块

| 模块 | 影响类型 | 关键不变量 | stale? |
|------|----------|-----------|--------|
| intelligence-models | 新增能力（DataSnapshot 写入） | 快照 append-only；DataSnapshot 不做 UPDATE/DELETE | no |
| apps.intelligence（新增 services 层） | 新增能力 | 调度服务与采集服务为新增模块，不修改现有 API/views | no |
| config/settings.py | 新增依赖 | 新增 django-apscheduler、httpx、html2text、beautifulsoup4、playwright 到 INSTALLED_APPS 与 requirements | no |
| config/apps.py（ready hook） | 新增能力 | Django 启动时注册全局 Job，不影响现有请求链路 | no |

### 7.2 需遵守的不变量

1. 快照 append-only——DataSnapshot 禁止 UPDATE/DELETE（来源：CLAUDE.md 不变量 1）
2. httpx 优先，Playwright 仅 SPA 按需降级，不得默认全量 Playwright（来源：CLAUDE.md 不变量 7）
3. 调度限 django-apscheduler，不引入消息队列（来源：CLAUDE.md 不变量 8）
4. `competitor_urls` 必须为 JSON 数组，每项 `{"url":"...","title":"..."}`（来源：CLAUDE.md 不变量 10）
5. 本 Spec 不写 IntelligenceFeed（来源：raw.md#R1-Q1 范围裁定）

### 7.3 跨模块影响

- 新增 services 层（scheduler_service + crawler_service）→ 不修改现有 views/serializers/urls，不影响前端 API 契约。
- DataSnapshot 写入 → 需确认 append-only 约束是否已有 DB 触发器；当前 migration 中未发现触发器，本 Spec 不新增触发器（留待 Spec 001 完整闭环）。
- `settings.py` 新增 INSTALLED_APPS → 需加 `django_apscheduler`，不影响现有 app。

### 7.4 Context Gaps

- `CONTEXT GAP`：`.aisdlc/project/components/intelligence-models.md` 未读取 → 建议动作：I1 阶段读取该模块页确认 DataSnapshot 的不变量与契约。
- `CONTEXT GAP`：`.aisdlc/project/components/intelligence-api.md` 未读取 → 建议动作：I1 阶段读取确认无 API 层冲突。
- `CONTEXT GAP`：Spec 002 实现代码位置未确认 → 建议动作：I1 阶段确认是否可复用 Spec 002 的爬虫脚本。

## 8. Mini-PRD

- **MVP 范围**：
  - In：django-apscheduler 集成（全局扫描 Job 每 5 分钟）、cron 5 分钟窗口匹配、httpx 采集、BeautifulSoup 去噪（去 nav/footer/script/style）、html2text 转 MD、Playwright 降级（markdown < 3 行）、DataSnapshot 入库（含失败空快照）
  - Out：LLM 降噪、diff 熔断、情报生成、飞书推送、IntelligenceFeed 写入、last_run_at 字段、多进程分布式锁、停机补执行

- **验收标准（AC）**：
  - AC-001：Django 启动后，全局扫描 Job 每 5 分钟触发一次（可从日志验证）
  - AC-002：`is_active=True` 且 cron 匹配当前 5 分钟窗口的项目会被触发采集
  - AC-003：`is_active=False` 的项目不会被触发
  - AC-004：每个 URL 采集后生成一条 DataSnapshot 记录（raw_markdown + clean_markdown + fetch_time + source_url + source_title）
  - AC-005：httpx 产出的 markdown < 3 行时，自动降级 Playwright 重新采集
  - AC-006：采集失败的 URL 写入空快照（raw_markdown="" / clean_markdown=""），不抛异常，不中断其他 URL
  - AC-007：BeautifulSoup 去噪移除了 nav/footer/script/style 标签
  - AC-008：不写 IntelligenceFeed 表
  - AC-009：cron 变更后无需重启即生效（下一个扫描窗口自动匹配新 cron）

- **交互变化结论**：无前端交互变化。调度与采集均为后端服务，不涉及前端页面。

- **影响面**：
  - `backend/config/settings.py`：新增 INSTALLED_APPS（django_apscheduler）+ 依赖
  - `backend/config/apps.py` 或 `backend/apps/intelligence/apps.py`：ready() 中注册 Job
  - `backend/apps/intelligence/services/`：新增 scheduler_service.py + crawler_service.py
  - `backend/apps/intelligence/models.py`：不修改（复用现有 DataSnapshot）
  - `backend/requirements/base.txt`：新增 django-apscheduler、httpx、html2text、beautifulsoup4、playwright

## 9. 迭代记录

- 2026-07-08：R1 澄清初始化，5 轮澄清完成范围裁定、调度粒度、采集失败处理、扫描频率、上次执行时间存储位置裁决。
- 2026-07-08：产出 solution.md，推荐"全局扫描 Job + 规则去噪爬虫"方案，含 3 个备选方案、8 条验证清单、Mini-PRD 9 条 AC。
