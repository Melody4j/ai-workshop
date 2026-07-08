调度任务接入，爬虫模块接入：

1. 接入django的apsscheduler，能够根据任务表的cron表达式，定时调度任务去执行
2. 爬虫系统能够根据任务的urls去爬去数据并作清洗入库

里程碑：任务表的任务能够被定时调度；爬虫系统能够根据任务的urls去爬去数据并作清洗入库。

## 澄清记录

### R1-Q1：范围边界（2026-07-08）

- 本轮结论：本 Spec 003 范围止步于"调度+采集+清洗入库"——即 django-apscheduler 定时触发 → httpx 采集 → BeautifulSoup 规则去噪 → html2text 转 MD → 写入 DataSnapshot（raw_markdown + clean_markdown）。不包含 LLM 降噪、diff 熔断、情报生成、飞书推送。
- 本轮约束：
  1. 降噪策略沿用 Spec 002 验证的 BeautifulSoup 规则去噪（去 nav/footer/script/style），不使用 LLM
  2. httpx 优先，markdown < 3 行时降级 Playwright（沿用 Spec 002 阈值）
  3. 产物为 DataSnapshot 记录入库，不写 IntelligenceFeed
- 关键决策：范围裁定 → 选择"调度+采集+清洗入库"；Spec 001 的 LLM 降噪/diff/情报/飞书不在本 Spec 范围
- 遗留歧义：全局扫描频率、上次执行时间存储位置、采集失败处理、调度执行记录（待后续澄清）

### R1-Q2：调度任务粒度（2026-07-08）

- 本轮结论：采用"全局扫描 Job"模式——注册一个全局 Job 定期扫描所有 `is_active=True` 的项目，检查是否到达 cron 执行时间。
- 本轮约束：
  1. 无需在 cron 变更时重注册 Job，cron 变更立即生效
  2. 需要实现 cron 匹配逻辑（判断"当前时间是否匹配该项目的 cron 表达式"）
  3. 需要记录每个项目的"上次执行时间"以避免重复触发
- 关键决策：调度粒度 → 选择"全局扫描 Job"；放弃"每项目一 Job"的独立注册模式
- 遗留歧义：全局扫描频率、上次执行时间存储位置、采集失败处理、调度执行记录（待后续澄清）

### R1-Q3：采集失败处理（2026-07-08）

- 本轮结论：某 URL 采集失败时，仍写一条 DataSnapshot（raw_markdown / clean_markdown 为空或标记 error），保证每次调度都有快照记录。
- 本轮约束：
  1. 失败的 URL 写空快照（不跳过），保证可追溯
  2. 其他 URL 正常采集入库，不因单个 URL 失败而中断整个项目
  3. 不写 IntelligenceFeed（维持 Q1 约束）
- 关键决策：采集失败处理 → 选择"写空快照记录"；放弃"仅记日志"和"写 ERROR_CRAWL"
- 遗留歧义：全局扫描频率、上次执行时间存储位置（待后续澄清）

### R1-Q4：全局扫描频率（2026-07-08）

- 本轮结论：全局扫描 Job 每 5 分钟触发一次，检查所有 `is_active=True` 的项目是否匹配 cron 表达式。
- 本轮约束：
  1. cron 精度限于 5 分钟——用户配置的 cron 分钟位会被对齐到 5 分钟窗口
  2. cron 匹配逻辑需检查"在过去 5 分钟窗口内是否匹配"，而非精确到分钟
  3. 单用户场景下每 5 分钟一次 DB 查询开销可忽略
- 关键决策：扫描频率 → 选择"每 5 分钟"；放弃"每分钟"和"每小时"
- 遗留歧义：上次执行时间存储位置（待后续澄清）

### R1-Q5：上次执行时间存储位置（2026-07-08）

- 本轮结论：不需要记录"上次执行时间"来避免重复触发。cron 匹配逻辑基于"在过去 5 分钟窗口内是否匹配 cron 表达式"，每 5 分钟只扫描一次，每个窗口只会匹配一次，自然不会重复触发。
- 本轮修正：撤销 Q2 中"需要记录每个项目的上次执行时间以避免重复触发"的假设。
- 本轮约束：
  1. cron 匹配逻辑：检查"当前时间所在的 5 分钟窗口是否匹配该项目的 cron 表达式"
  2. 无需在 MonitorProject 上新增 last_run_at 字段
  3. 服务器停机期间错过的调度不补执行（单用户 MVP 容错策略）
- 关键决策：上次执行时间 → 选择"不需要"；撤销"加字段"和"从快照推断"
- 遗留歧义：无

### R1-修订-1：调度匹配策略改为 next_run_at（2026-07-08，plan 评审触发）

- 本轮结论：撤销 R1-Q4 的"5 分钟窗口匹配"和 R1-Q5 的"不需要字段"。改为：MonitorProject 新增 `next_run_at` 字段，用 croniter 计算下次执行时间；全局扫描 Job 每 5 分钟检查 `now >= project.next_run_at`，命中则执行并更新 `next_run_at` 为下一个未来匹配时间。
- 本轮约束：
  1. MonitorProject 新增 `next_run_at = DateTimeField(null=True, blank=True)`
  2. 项目创建/更新时（save 调用）重算 next_run_at（cron 变更立即生效）
  3. 执行后更新 next_run_at = croniter.get_next(cron, now)
  4. cron 精度仍限 5 分钟（扫描间隔），但 cron 表达式分钟位无需对齐到 5 的倍数
  5. 服务器停机后重启，若 next_run_at 已过，下一个扫描周期会执行一次（非补执行所有错过次数）
- 本轮修正：撤销 Q4 约束 1-2（5 分钟窗口对齐与匹配逻辑）；撤销 Q5 约束 2-3（不加字段、不补执行）
- 关键决策：调度匹配 → next_run_at 字段 + croniter 计算；放弃 5 分钟窗口匹配
- 遗留歧义：无

### R1-Q6：raw_markdown 与 clean_markdown 语义（2026-07-08，plan 评审触发）

- 本轮结论：raw_markdown = httpx/Playwright 返回的原始 HTML（不做 html2text）；clean_markdown = BeautifulSoup 去噪后 HTML 经 html2text 转换的 MD。
- 本轮约束：
  1. raw_markdown 存原始 HTML 字符串
  2. clean_markdown 存去噪后 MD 字符串
  3. Playwright 降级时，raw_markdown 和 clean_markdown 都基于 Playwright 的 HTML 重新生成
  4. markdown 行数判断（< 3 行降级）基于 clean_markdown
- 关键决策：raw/clean 语义 → raw=原始HTML, clean=去噪后MD
- 遗留歧义：无
