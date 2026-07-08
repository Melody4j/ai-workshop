---
title: PRD
status: draft
---

目的：把 `requirements/solution.md` 的推荐决策转为可交付、可验收、可测试的规格。文档中不写“待确认问题”；所有未知统一写入第 8 节验证清单。

## 0. 基本信息

- 需求标识（分支 / ID）：001-competitive-intel-agent
- 作者：PM
- 评审人：FS（待评审）；Leader（评审）
- 状态：draft
- 最后更新：2026-07-07
- 关联链接：`requirements/solution.md`（唯一决策入口）；`requirements/raw.md`（含前端架构调整修订）

## 1. 结论摘要（3-7 行）

- **目标（要解决什么）**：为个人产品经理/独立开发者构建自动化竞争情报监控代理。用户在 Vue 前端配置自有产品锚定文档与 5-10 个竞品 URL 后，系统日级采集、降噪、diff 熔断、生成情报，并把有变化结果推送飞书并沉淀报告。
- **In / Out 边界**：In = Vue 任务配置页、Vue 调度执行列表、Vue 收件箱 / 情报详情 / 报告预览、Django API/调度后端、html2text + LLM 降噪、单次 LLM 情报生成、飞书推送、反馈注入； Out = 多租户、团队协作、第三方流量 API、AI 提及度、多信号交叉验证、Slack/邮件、实时监控。
- **MVP 边界**：① 前后端分离但仍是单体项目；② 前端全部采用 Vue；③ 有变化即推送，无变化熔断；④ 调度执行列表展示全量状态，但收件箱只展示 `CHANGED`。
- **推荐方案**：Vue 前端 + Django API/调度后端 + 日级采集 + html2text/LLM 降噪 + diff 熔断 + 单次 LLM 情报生成 + 有变化推飞书。
- **优先验证点**：V-007（API 契约）、V-019（Session/CSRF 集成）、V-004（LLM prompt 准确性）、V-017（产品锚定对建议质量提升）。

## 2. 范围与里程碑

### 2.1 MVP 范围（In / Out）

**In**：
1. Vue 任务配置页：创建/编辑 `MonitorProject`，配置项目名、`competitor_urls`、`self_product_doc`、飞书 webhook、cron、启停状态
2. Django API + 调度后端：保存配置、执行采集、调用 LLM、落快照、生成情报、记录执行状态
3. 日级采集：httpx GET → html2text → LLM 语义降噪 → append-only 快照；必要时 Playwright 兜底
4. 变化识别：diff 为空写 `NO_CHANGE` 并熔断；diff 非空进入单次情报生成
5. 情报生成：输入 diff + `self_product_doc` + 最近 5 条负反馈，输出 4 字段
6. 报告与分发：落盘 HTML/MD 报告产物；飞书高级卡片跳到 Vue 报告预览页
7. Vue 调度执行列表：展示 `CHANGED` / `NO_CHANGE` / `ERROR_CRAWL`
8. Vue 收件箱 / 详情 / 报告预览：收件箱仅展示 `CHANGED`；详情页支持反馈

**Out**：
- 多租户 / 团队协作 / 权限分层
- 第三方流量 API / AI 提及度采集
- 多信号交叉验证
- 3-Agent 多模型分层（P1）
- Slack / 邮件通知
- 实时 / 小时级监控
- `refined_rules` 自动提炼（P1）
- 存储归档策略（P1）

### 2.2 里程碑

| 里程碑 | 目标 | 范围 | 产出物 | 出关标准 |
|---|---|---|---|---|
| M0 需求冻结 | 冻结产品范围、关键页面、主链路与口径 | PRD / 原型 / 设计 RFC | `requirements/prd.md`、`requirements/prototype.md`、`design/design.md` | 范围、页面、AC、里程碑获得评审确认；不再新增 P0 需求 |
| M1 MVP 可用版本 | 打通真实后端最小闭环 | 配置 API、日级调度、采集、降噪、diff、情报生成、飞书推送、反馈写回 | 可运行应用、基础部署说明、最小验证结果 | 用户可创建任务并收到首条真实情报；执行列表与收件箱可消费真实数据 |
| M2 P1 增强 | 提升可维护性与长期使用体验 | `refined_rules`、存储归档、更多运营/观测能力、多模型优化 | 增强版需求 / 设计 / 验证产物 | 核心性能、稳定性、可维护性满足长期使用要求 |

- **阶段约束**：
  - M0 前不进入代码实现。
  - 不再单列“高保真 Demo 工程”交付；页面与交互走查以 `requirements/prototype.md` 为准。
  - M1 直接接入真实采集、调度、LLM 与飞书通知，验证最小闭环。
  - M2 仅处理 P1/P2 增强项，不回头扩大 M1 的 P0 范围。

## 3. 核心场景（建议 ≤ 3 个）

### 3.1 场景 S-001：通过 Vue 页面配置监控任务并触发首采

- **触发**：用户打开 Vue 任务配置页，录入项目名、竞品 URL、产品锚定文档、飞书 webhook、cron 并保存启用。
- **参与者**：用户；Vue 前端；Django API；django-apscheduler；采集器；LLM；飞书机器人。
- **目标**：首采能够从配置成功进入完整监控闭环。
- **成功标准**：
  1. 配置保存成功并注册调度。
  2. 首采无历史快照时直接生成 `CHANGED` 情报。
  3. 飞书卡片与 Vue 报告预览页可打开。

### 3.2 场景 S-002：用户在 Vue 调度执行列表查看全量运行结果

- **触发**：任务按日级 cron 运行后，用户进入调度执行列表筛选最近执行状态。
- **参与者**：用户；Vue 前端；Django API。
- **目标**：用户能够区分有变化、无变化、采集失败三种执行结果，并可追溯错误。
- **成功标准**：
  1. 列表可查看 `CHANGED` / `NO_CHANGE` / `ERROR_CRAWL`。
  2. 收件箱不混入 `NO_CHANGE` / `ERROR_CRAWL`。
  3. 错误记录可查看 `log_message` 或失败原因摘要。

### 3.3 场景 S-003：用户消费情报并把负反馈注入下次推理

- **触发**：某次运行 diff 非空，系统生成情报并推送飞书；用户在 Vue 情报详情页反馈“毫无意义”。
- **参与者**：用户；Vue 前端；Django API；LLM；飞书机器人。
- **目标**：验证收件箱消费与反馈闭环。
- **成功标准**：
  1. `CHANGED` 情报进入收件箱和详情页。
  2. 负反馈被持久化。
  3. 下次生成情报时自动注入最近 5 条负反馈。

## 4. 功能清单（与优先级 / 里程碑对齐）

| 功能项 | 优先级 | 里程碑 | 说明 / 依赖 |
|---|---|---|---|
| F-01 Vue 任务配置页 | P0 | MVP | 创建 / 编辑 `MonitorProject`；支持 URL + title 录入 |
| F-02 Django 配置 API | P0 | MVP | 保存配置、校验字段、注册 / 更新调度 |
| F-03 日级调度（django-apscheduler） | P0 | MVP | 日级 cron，无消息队列 |
| F-04 采集器（httpx 优先 + Playwright 兜底） | P0 | MVP | SPA 按需降级 |
| F-05 html2text + LLM 降噪 | P0 | MVP | 独立于情报生成 LLM |
| F-06 快照存储（append-only） | P0 | MVP | `raw_markdown` + `clean_markdown` |
| F-07 diff 引擎 + 熔断 | P0 | MVP | diff 为空不调情报生成 |
| F-08 情报生成（单次 LLM + instructor/Pydantic） | P0 | MVP | 注入 `self_product_doc` + 最近 5 条负反馈 |
| F-09 报告产物生成（HTML / MD） | P0 | MVP | 落盘并保存路径索引 |
| F-10 飞书高级卡片推送 | P0 | MVP | 预览按钮跳 Vue 报告页 |
| F-11 Vue 调度执行列表 | P0 | MVP | 展示 `CHANGED` / `NO_CHANGE` / `ERROR_CRAWL` |
| F-12 Vue 收件箱（仅 `CHANGED`） | P0 | MVP | 与执行列表分离 |
| F-13 Vue 情报详情 + 反馈 | P0 | MVP | 反馈写回 `user_feedback` / `user_comment` |
| F-14 Vue 报告预览页 | P0 | MVP | 预览报告内容和下载链接 |
| F-15 Django 执行记录 / 详情 API | P1 | MVP | 支持筛选、分页、错误追溯 |
| F-16 采集失败重试（1-2 次） | P1 | MVP | 间隔 30s |
| F-17 飞书推送失败重试（1-2 次） | P1 | MVP | 失败不丢情报 |
| F-18 `refined_rules` 占位 | P2 | M2 | MVP 不写入 |
| F-19 归档 / 清理策略 | P2 | M2 | P1 候选 |

## 5. 业务规则与口径（只写影响 AC 的）

- **规则-1**：`DataSnapshot` append-only，数据库层禁止 UPDATE / DELETE。
- **规则-2**：降噪 LLM 与情报生成 LLM 是独立两次调用，不得合并。
- **规则-3**：情报生成只在 diff 非空时触发。
- **规则-4**：情报输出固定 4 字段，不含价值度字段。
- **规则-5**：`has_change=True` → 推飞书 + 存报告；`has_change=False` → 熔断退出。
- **规则-6**：收件箱仅展示 `job_status=CHANGED`。
- **规则-7**：调度执行列表展示 `CHANGED` / `NO_CHANGE` / `ERROR_CRAWL` 全量执行记录。
- **规则-8**：httpx 优先，Playwright 仅 SPA 按需降级。
- **规则-9**：调度限 django-apscheduler 日级，不引入消息队列。
- **规则-10**：`competitor_urls` 必须为 JSON 数组，每项为 `{"url":"...","title":"..."}`。
- **规则-11**：Negative Few-Shot 注入上限最近 5 条。
- **规则-12**：任务配置、调度执行列表、收件箱、详情、报告预览全部由 Vue 承担。

## 6. 验收标准（AC，可测试）

### 6.1 场景 S-001 的 AC（Vue 配置 + 首采）

- **AC-001**：用户在 Vue 任务配置页填写项目名“AI IDE 监控”、2 个竞品 URL、`self_product_doc` 文本、飞书 webhook、cron `0 9 * * *` 并保存。预期：后端创建 `MonitorProject`，返回成功，调度注册完成。
- **AC-002**：首采触发后，系统对每个 URL 执行 httpx GET → html2text → LLM 降噪 → 写 `DataSnapshot`。预期：新增快照记录，且 append-only 约束有效。
- **AC-003**：首采无上一条快照时直接进入情报生成。预期：`IntelligenceFeed.job_status=CHANGED`，4 字段非空。
- **AC-004**：后端生成 HTML/MD 报告产物并保存路径索引。预期：`html_report_path` / `md_table_path` 可访问或可下载。
- **AC-005**：飞书卡片正文含变化摘要，“在线预览”按钮跳转 Vue 报告预览页。预期：链接可打开。

### 6.2 场景 S-002 的 AC（执行列表）

- **AC-006**：某任务 diff 为空。预期：不调用情报生成 LLM，并写 `IntelligenceFeed(job_status=NO_CHANGE)`。
- **AC-007**：用户打开 Vue 调度执行列表。预期：可看到 `NO_CHANGE` 记录，但收件箱中不展示该记录。
- **AC-008**：某任务采集失败。预期：写 `IntelligenceFeed(job_status=ERROR_CRAWL, log_message=...)`，执行列表可筛选该记录并查看失败原因摘要。
- **AC-009**：执行列表支持按项目、状态、时间范围过滤。预期：筛选结果正确返回。

### 6.3 场景 S-003 的 AC（收件箱 + 反馈）

- **AC-010**：某任务 diff 非空。预期：单次 LLM 生成 4 字段，记录为 `CHANGED`，进入收件箱。
- **AC-011**：用户在 Vue 收件箱点击某条情报进入详情页。预期：能查看变化摘要、战略意图、行动建议、报告预览入口。
- **AC-012**：用户点击“毫无意义”并输入评语“这条情报没有可执行性”。预期：记录 `user_feedback=-1` 与 `user_comment`。
- **AC-013**：下次 diff 非空时，系统在情报生成前注入最近 5 条负反馈。预期：日志或记录可证注入条数 ≤5。

### 6.4 异常路径 AC

- **AC-014（SPA 兜底）**：httpx 拿不到有效内容时降级 Playwright。预期：若 Playwright 成功，链路继续；若失败，按 `ERROR_CRAWL` 记录。
- **AC-015（飞书失败）**：飞书 webhook 错误或超时。预期：重试 1-2 次；`CHANGED` 情报和报告仍保留。
- **AC-016（Session/CSRF）**：Vue 发起配置保存或反馈提交。预期：同域 Session/CSRF 校验通过，写操作成功。
- **AC-017（append-only）**：直接对快照执行 SQL UPDATE / DELETE。预期：SQLite 触发器阻止操作，报错 “Snapshot is append-only”。

## 7. 异常与边界（只覆盖影响 AC 的关键异常）

- **异常-1**：采集目标 403 / 429 / 超时 → 重试 1-2 次，仍失败写 `ERROR_CRAWL`。
- **异常-2**：飞书 webhook 不可达 → 重试，报告与情报记录仍保留。
- **异常-3**：SPA 页面 httpx 无法获取正文 → Playwright 兜底。
- **异常-4**：`self_product_doc` 过长 → 截断到合理长度，优先保留产品定位 / 核心功能 / 定价。
- **异常-5**：负反馈超过 5 条 → 只取最近 5 条。
- **边界-1**：首采无上一条快照 → 不熔断，直接生成首条情报。
- **边界-2**：用户不配置 `self_product_doc` 仅上传文件或保持为空 → 生成链路不阻塞，但建议质量可能下降。

## 8. 风险 / 依赖与验证清单（可执行）

| 风险/假设/依赖 | 验证信号 | 方法 | Owner | 截止 | 触发动作 |
|---|---|---|---|---|---|
| V-002 Vue 配置页的多 URL 录入可用性 | 用户能顺畅录入 5-10 个 URL | 动态表单交互测试 | PM+FS | R3/I1 | 仍难用则增加导入能力 |
| V-004 LLM prompt 准确性 | 降噪保留核心 >90%；情报判定 >80% | 真实样本测试 | FS+PM | I2 | 继续迭代 prompt |
| V-005 cron 前端化可用性 | 用户无需手写复杂表达式 | 预设时间选择交互 | PM+FS | R3/I1 | 简化为固定日级时间 |
| V-007 API 契约稳定 | Vue 页面无需依赖模板渲染 | 先定义 DTO / API 契约 | FS | I1 | 冻结 BFF / DTO |
| V-008 飞书卡片跳 Vue 预览 | 卡片按钮可直接打开报告页 | 联调卡片链接 | FS | I2 | 降级纯文本消息 |
| V-010 飞书失败降级 | 推送失败但情报可查 | 模拟失败场景 | FS | I2 | 检查网络 / webhook |
| V-016 产品锚定注入有效 | 建议体现我方定位 | A/B 对比输出 | FS+PM | I2 | 调整注入策略 |
| V-017 锚定是否提升建议质量 | 用户盲评“更相关” >60% | A/B 盲评 | PM+用户 | I2 | 精简锚定内容 |
| V-018 Negative Few-Shot 策略 | prompt 不超限，坏结果减少 | 取最近 5 条实测 | FS+PM | I2 | 改成 top-K 检索 |
| V-019 Session/CSRF 集成 | Vue 写操作稳定成功 | 同域部署联调 | FS | I1 | 改 token 方案 |

## 9. 原型产出判定

- **交互变化结论**：需要原型。原因：配置、执行列表、收件箱、详情、报告预览全部转为 Vue 页面，且“收件箱只看变更 / 执行列表看全量状态”的信息架构发生变化。
- **页面与入口**：
  - Vue：任务配置页、调度执行列表、收件箱、情报详情、报告预览
  - 飞书卡片：变化摘要 + “在线预览” + “下载 MD”
- **关键控件 / 字段与校验**：
  - 竞品 URL 与标题成对录入
  - cron / 日级执行时间的前端化输入
  - 执行列表的状态筛选
  - 反馈按钮与评语输入

## 10. 追溯链接

- `requirements/solution.md`：推荐方案、验证清单、Impact Analysis、不变量
- `requirements/raw.md`：需求原文、修订-1～修订-6、DB-1～DB-4
- `requirements/prototype.md`：Vue 页面与任务流原型说明
