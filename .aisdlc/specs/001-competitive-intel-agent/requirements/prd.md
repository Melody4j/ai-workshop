---
title: PRD
status: draft
---

目的：把 `requirements/solution.md` 的推荐决策转为**可交付规格**。不写"待确认问题"；未知统一写入第 8 节验证清单。

## 0. 基本信息

- 需求标识（分支 / ID）：001-competitive-intel-agent
- 作者：PM
- 评审人：FS（待评审）；Leader（评审）
- 状态：draft
- 最后更新：2026-07-07
- 关联链接：`requirements/solution.md` v3（唯一决策入口）；`requirements/raw.md`（8 轮澄清 + 技术设计文档冲突修订）

---

## 1. 结论摘要（3–7 行）

- **目标（要解决什么）**：为个人产品经理/独立开发者构建自动化竞争情报监控代理——用户配置自有产品锚定文档 + 5-10 个竞品 URL 后，系统日级采集 → html2text+LLM 降噪 → diff 熔断 → 单次 LLM 情报生成（注入产品锚定）→ 有变化推飞书+存报告 / 无变化熔断。
- **In / Out 边界**：In = 监控配置（竞品 URL JSON 数组/飞书 webhook/产品锚定文档/调度 cron）、日级采集（httpx 优先 + Playwright 可选兜底）、html2text + LLM 降噪、快照 diff + 单次 LLM 情报生成（4 字段）、有变化→飞书推送+HTML/MD 报告、无变化→熔断、情报反馈（Negative Few-Shot 注入）；Out = 多租户、团队协作、第三方流量 API、AI 提及度、多信号交叉验证、3-Agent 多模型分层（P1）、Slack/邮件、实时/小时级、价值度分级推送。
- **MVP 边界（1–3 条）**：① 单用户 Django 单体，无多租户；② 单次 LLM 直出情报（非 3-Agent）；③ 有变化即推送无分级，无变化即熔断。
- **推荐方案（引用 solution.md）**："Django 单体 + 日级采集 + html2text/LLM 降噪 + diff 熔断 + 单次 LLM 直出情报 + 有变化推飞书"最小闭环（solution.md §2）。
- **优先验证点**：V-004（LLM prompt 准确性）、V-016（产品锚定解析与注入）、V-017（产品锚定对建议质量提升）。

---

## 2. 范围与里程碑

### 2.1 MVP 范围（In / Out）

**In**：
1. 配置管理（Django Admin）：监控项目（项目名 / `competitor_urls` JSON 数组 `{"url","title"}` / `manual_txt_source` / `imported_md_file` / `self_product_doc` Nullable / `feishu_webhook` / `cron` / `refined_rules` P1 占位 / `is_active`）
2. 日级采集（django-apscheduler cron 触发）：httpx GET → html2text 转 MD → LLM 语义降噪 → 存快照（append-only）；httpx 失败时可选 Playwright 兜底
3. 变化识别（diff + 熔断）：取上一条快照 diff；diff 为空 → 熔断（写 `IntelligenceFeed.job_status=NO_CHANGE`）；diff 非空 → 进情报生成
4. 情报生成（单次 LLM 直出）：prompt = diff 片段 + `self_product_doc` + Negative Few-Shot（最近 5 条）；输出 4 字段（变化摘要/战略意图/行动建议/证据diff 嵌入 change_summary）
5. 渲染与分发：Jinja2 渲染 HTML 网页报告 + MD 表格文档（落盘，DB 存 `html_report_path`/`md_table_path` 路径索引）；推送飞书高级卡片（变化摘要 + 预览/下载按钮）
6. 消费与反馈：独立 HTML 网页 + Django Admin 浏览（收件箱仅展示 `job_status=CHANGED`）；用户点"毫无意义"+评语 → `user_feedback=-1` + `user_comment` → 下次情报生成注入 Negative Few-Shot

**Out**：
- 多租户 / 团队协作 / 权限
- 第三方流量 API / AI 提及度采集
- 多信号交叉验证
- 3-Agent 多模型分层（P1）
- Slack / 邮件通知
- 实时 / 小时级监控
- 价值度分级推送
- `refined_rules` AI 自精进（P1 占位，MVP 不写入）
- 存储清理归档策略（P1）

### 2.2 里程碑

- **MVP**：6 步执行链路全打通（配置→采集→降噪→diff熔断→情报生成→渲染分发→反馈），单用户可本地运行，飞书卡片可收到有变化的情报。
- **M1（可选，P1 候选）**：3-Agent 分层 / `refined_rules` 周级提炼 / 多信号交叉验证 / 存储归档。

---

## 3. 核心场景（建议 ≤ 3 个）

### 3.1 场景 S-001：首次配置并触发首次采集

- **触发**：用户在 Django Admin 新建 MonitorProject，填入项目名、竞品 URL（JSON 数组）、`self_product_doc`（或上传 .md 文件）、飞书 webhook、cron 表达式，保存并启用。
- **参与者**：用户（配置者）；系统（django-apscheduler 调度器 + 采集器 + 降噪引擎 + 情报生成 + 渲染 + 飞书推送）
- **目标**：系统按 cron 日级触发首次采集，因无历史快照（首采），直接生成情报并推送飞书。
- **成功标准（1–3 条）**：
  1. 配置保存后，django-apscheduler 按 cron 在下一个调度时间点触发采集。
  2. 首采无上一条快照，不熔断，直接进入情报生成，产出 4 字段情报并写 `IntelligenceFeed.job_status=CHANGED`。
  3. 飞书群收到高级卡片，含变化摘要 + 预览/下载按钮可跳转。

### 3.2 场景 S-002：日常日级采集 + 无变化熔断

- **触发**：cron 日级触发，对某竞品 URL 采集 → 降噪 → diff。
- **参与者**：系统（调度器 + 采集器 + 降噪 + diff 引擎）
- **目标**：diff 为空时熔断退出，不推送不生成情报，但写 `IntelligenceFeed.job_status=NO_CHANGE` 记录调度痕迹。
- **成功标准（1–3 条）**：
  1. diff 为空 → 不调用情报生成 LLM（不变量4，成本约束）。
  2. 写 `IntelligenceFeed(job_status=NO_CHANGE, execution_time=now)`，收件箱不展示。
  3. 飞书群无推送。

### 3.3 场景 S-003：有变化 + 反馈注入下次推理

- **触发**：cron 日级触发，diff 非空 → 情报生成 → 推送 → 用户点"毫无意义"+评语 → 下次 cron 触发时注入 Negative Few-Shot。
- **参与者**：用户；系统（调度 + 采集 + 降噪 + diff + 情报生成 + 飞书 + 反馈系统）
- **目标**：验证反馈闭环——用户负反馈直接影响下次 LLM 推理。
- **成功标准（1–3 条）**：
  1. diff 非空 → 单次 LLM 调用产出 4 字段，`job_status=CHANGED`，飞书推送，报告落盘。
  2. 用户点"毫无意义"+评语 → `user_feedback=-1` + `user_comment` 持久化。
  3. 下次情报生成 LLM 启动前，取最近 5 条 `user_feedback=-1` 的 `user_comment` 注入 prompt 底部。

---

## 4. 功能清单（与优先级/里程碑对齐）

| 功能项 | 优先级 | 里程碑 | 说明/依赖 |
|---|---|---|---|
| F-01 配置管理（Django Admin，MonitorProject CRUD） | P0 | MVP | 3 张表落地；`competitor_urls` JSON 数组；`self_product_doc` Nullable |
| F-02 日级调度（django-apscheduler + cron） | P0 | MVP | 不变量9：日级，无消息队列 |
| F-03 采集器（httpx 优先 + Playwright 可选兜底） | P0 | MVP | 不变量8：httpx 优先，SPA 按需 Playwright |
| F-04 html2text 转 MD | P0 | MVP | 采集后初步过滤 |
| F-05 LLM 语义降噪（独立 prompt） | P0 | MVP | 不变量3：独立于情报生成 LLM |
| F-06 快照存储（append-only + clean_markdown） | P0 | MVP | 不变量1/2：append-only + 降噪后 Markdown |
| F-07 diff 引擎 + 熔断 | P0 | MVP | 不变量4/6：diff 为空熔断，不调 LLM |
| F-08 情报生成（单次 LLM + instructor/Pydantic） | P0 | MVP | 不变量5：4 字段；注入 self_product_doc |
| F-09 Negative Few-Shot 注入（最近 5 条） | P0 | MVP | 不变量12：上限 5 条 |
| F-10 Jinja2 渲染 HTML 报告 + MD 表格 | P0 | MVP | 报告落盘，DB 存路径索引 |
| F-11 飞书高级卡片推送 | P0 | MVP | 不变量6：有变化即推送；含预览/下载按钮 |
| F-12 收件箱（独立 HTML 网页，仅 CHANGED） | P0 | MVP | 不变量7：仅展示 CHANGED |
| F-13 反馈接口（user_feedback + user_comment） | P0 | MVP | 不变量12：负反馈注入数据源 |
| F-14 Django Admin 调度日志视图 | P1 | MVP | 展示 NO_CHANGE/ERROR_CRAWL 记录 |
| F-15 采集失败重试（1-2 次，间隔 30s） | P1 | MVP | V-006：失败率 >20% 升级 |
| F-16 飞书推送失败重试（1-2 次） | P1 | MVP | V-010：失败率 >10% 检查 webhook |
| F-17 `refined_rules` P1 占位字段 | P2 | M1 | MVP 不写入 |
| F-18 3-Agent 多模型分层 | P2 | M1 | P1 候选 |
| F-19 存储归档策略 | P2 | M1 | P1 候选 |

---

## 5. 业务规则与口径（只写影响 AC 的）

- **规则-1（不变量1）**：快照存储 append-only，不得覆盖/轮替历史版本。DB 层用 SQLite 触发器 `RAISE(ABORT) on UPDATE/DELETE` 硬约束。
- **规则-2（不变量2）**：快照存 LLM 降噪后干净 Markdown（`clean_markdown`）+ 原始 html2text 文本（`raw_markdown`），不存原始 HTML。
- **规则-3（不变量3）**：降噪 LLM 调用与情报生成 LLM 调用是独立两次调用，不得合并。
- **规则-4（不变量4）**：情报生成 LLM 仅在 diff 非空时触发，不得全量调用。
- **规则-5（不变量5）**：情报输出 4 字段（变化摘要/意图/建议/证据diff），不含价值度字段。证据 diff 嵌入 `change_summary` 或报告渲染素材，不独立为 DB 字段（DB-1 裁决）。
- **规则-6（不变量6）**：has_change=True → 推飞书+存报告；has_change=False → 熔断退出。熔断记录写 `IntelligenceFeed.job_status=NO_CHANGE`，不独立 JobLog 表（DB-3 裁决）。
- **规则-7（不变量7）**：收件箱仅展示 `job_status=CHANGED`；`NO_CHANGE`/`ERROR_CRAWL` 仅 Django Admin 可见。
- **规则-8（不变量8）**：httpx 优先，Playwright 仅 SPA 按需降级，不得默认全量 Playwright。
- **规则-9（不变量9）**：调度限 django-apscheduler 日级，不引入消息队列。
- **规则-10（不变量10）**：每个监控任务必须关联 `self_product_doc`（Nullable 允许只上传文件），情报生成时注入 prompt。
- **规则-11（不变量11）**：`competitor_urls` 必须为 JSON 数组，每项 `{"url":"...","title":"..."}`，title 作为爬取数据标题标识来源。
- **规则-12（不变量12）**：Negative Few-Shot 注入上限最近 5 条，超过取最近 5 条。
- **规则-13（不变量13）**：`refined_rules` P1 占位，MVP 不写入。

---

## 6. 验收标准（AC，可测试）

### 6.1 场景 S-001 的 AC（首次配置 + 首采）

- **AC-001**：在 Django Admin 新建 MonitorProject，填入项目名"AI IDE 监控"、2 个竞品 URL（JSON 数组 `[{"url":"https://a.com","title":"A官网"},{"url":"https://b.com","title":"B官网"}]`）、`self_product_doc` 文本、飞书 webhook、cron `0 9 * * *`，保存。预期：记录入库，`is_active=TRUE`，django-apscheduler 注册该 cron 任务。
- **AC-002**：到达 cron 触发时间（或手动触发），系统对每个 competitor_url 执行 httpx GET → html2text 转 MD → LLM 降噪 → 写 DataSnapshot（`raw_markdown` + `clean_markdown` + `fetch_time`）。预期：DataSnapshot 新增 2 条记录，append-only（UPDATE/DELETE 触发 RAISE ABORT）。
- **AC-003**：首采无上一条快照，不熔断，直接进入情报生成。单次 LLM 调用产出 4 字段（change_summary/strategic_intent/action_suggestions/evidence_diff 嵌入 change_summary）。预期：IntelligenceFeed 新增记录 `job_status=CHANGED`，4 字段非空。
- **AC-004**：Jinja2 渲染 HTML 报告 + MD 表格，落盘到 `storage/html/{project_id}/{date}.html` 与 `storage/md/{project_id}/{date}.md`。预期：IntelligenceFeed 的 `html_report_path`/`md_table_path` 存储相对路径，文件实际存在。
- **AC-005**：飞书群收到高级卡片，正文含 change_summary，按钮"在线预览"跳转 HTML 报告 URL（`/view/html/{intelligence_id}`），"下载 MD"触发下载。预期：飞书 API 返回成功状态码。

### 6.2 场景 S-002 的 AC（无变化熔断）

- **AC-006**：对某竞品 URL 日级采集，降噪后 `clean_markdown` 与上一条快照 diff 为空。预期：不调用情报生成 LLM（TaskLog 或日志可证零 LLM 调用）。
- **AC-007**：写 `IntelligenceFeed(job_status=NO_CHANGE, execution_time=now)`，4 字段（change_summary 等）为 Nullable/空。预期：收件箱（独立 HTML 网页）不展示该记录。
- **AC-008**：Django Admin 调度日志视图可查看 `NO_CHANGE` 记录。预期：Admin 列表含该记录，可筛选 `job_status=NO_CHANGE`。
- **AC-009**：飞书群无推送。预期：飞书 webhook 无调用记录。

### 6.3 场景 S-003 的 AC（有变化 + 反馈注入）

- **AC-010**：diff 非空 → 单次 LLM 调用产出 4 字段，`job_status=CHANGED`，飞书推送，报告落盘（同 AC-003/004/005）。
- **AC-011**：用户在独立 HTML 网页点"毫无意义"按钮，输入评语"这条情报没有可执行性"。预期：IntelligenceFeed 记录 `user_feedback=-1` + `user_comment="这条情报没有可执行性"`。
- **AC-012**：下次 cron 触发且 diff 非空时，情报生成 LLM 启动前，系统取最近 5 条 `user_feedback=-1` 的 `user_comment` 注入 prompt 底部。预期：LLM 调用日志或 IntelligenceFeed 记录可证注入条数 ≤5；prompt 不超模型上下文窗口。
- **AC-013**：注入后 LLM 不再产出类似被标记"毫无意义"的情报（V-018 成功信号）。

### 6.4 异常路径 AC

- **AC-014（采集失败）**：httpx GET 返回 403/超时，重试 1-2 次（间隔 30s）仍失败。预期：写 `IntelligenceFeed(job_status=ERROR_CRAWL, log_message=<错误详情>)`，不阻塞其他竞品 URL 采集；收件箱不展示；Admin 可查。
- **AC-015（飞书推送失败）**：飞书 webhook 返回错误或超时，重试 1-2 次仍失败。预期：IntelligenceFeed 的 `job_status` 仍为 `CHANGED`（情报已生成），报告已落盘不丢失；Admin 可查推送失败日志。
- **AC-016（SPA 兜底）**：httpx 拿不到有效内容（如社媒 SPA），降级 Playwright 兜底。预期：Playwright 拿到内容后正常走降噪→快照→diff 链路；若 Playwright 仍失败，按 AC-014 处理。
- **AC-017（append-only 硬约束）**：直接对 DataSnapshot 执行 SQL `UPDATE` 或 `DELETE`。预期：SQLite 触发器 `RAISE(ABORT)` 阻止操作，报错 "Snapshot is append-only"。

---

## 7. 异常与边界（只覆盖影响 AC 的关键异常）

- **异常-1**：采集目标临时不可达/限流（403/429/超时）→ 重试 1-2 次间隔 30s，仍失败写 `ERROR_CRAWL`，不阻塞其他 URL。
- **异常-2**：飞书 webhook 不可达/返回错误 → 重试 1-2 次，情报报告仍落盘不丢失。
- **异常-3**：社媒 SPA httpx 拿不到内容 → 降级 Playwright；仍失败按异常-1 处理。
- **异常-4**：产品锚定文档过长（超 prompt 上下文窗口）→ 截断到合理长度（如 2000 token），取产品定位/核心功能/定价段落。
- **异常-5**：Negative Few-Shot 累积超 5 条 → 取最近 5 条，不全量注入。
- **异常-6**：LLM 调用失败/超时 → 记录错误日志，该次情报生成标记失败，不推送；下次 cron 重试。
- **边界-1**：首采无上一条快照 → 不熔断，直接进情报生成。
- **边界-2**：`self_product_doc` 为空且未上传文件 → 情报生成 prompt 不注入产品锚定段（不影响链路，但建议 V-017 验证质量差异）。

---

## 8. 风险/依赖与验证清单（可执行；所有不确定性仅写在此处）

| 风险/假设/依赖 | 验证信号 | 方法 | Owner | 截止 | 触发动作 |
|---|---|---|---|---|---|
| V-001 社媒 SPA httpx 拿不到内容 | Playwright 兜底可拿到有效内容 | httpx 失败时降级 Playwright 测试 | FS | I2 | Playwright 仍拿不到→标记不可采集 |
| V-002 官网关键页面选择策略 | 用户可配置 1-N 个 URL | Django Admin 配置测试 | PM+FS | R2 完成时 | 配置困难→P1 智能推荐 |
| V-003 diff 粒度（全文文本） | 噪音 diff 过滤率 >80% | 3-5 真实竞品页面验证 | FS | I2 首批采集后 | 不足 80%→升级 CSS 选择器区域 diff |
| V-004 LLM prompt 准确性（降噪+情报生成） | 降噪保留核心 >90%；情报判定 >80% | 10-20 真实样本测试 | FS+PM | I2 | 不达标→迭代 prompt；3 轮后引入规则预过滤 |
| V-006 采集失败重试策略 | 单任务失败不影响其他；有日志 | 实测失败场景 | FS | I2 | 失败率 >20%→指数退避/P1 告警 |
| V-007 情报输出 schema 字段定义 | schema 可被 Jinja2 消费渲染 HTML/MD | FS 定义 JSON schema + PM 确认语义 | FS | I1（api.md 定义时） | 渲染需求变→更新 schema + api.md |
| V-008 飞书高级卡片格式 | 群收到可读卡片，按钮可跳转 | 对接飞书卡片 API | FS | I2 | 困难→降级 Markdown 纯文本 |
| V-010 飞书推送失败降级 | 推送失败有日志；报告可查 | 实测推送失败场景 | FS | I2 | 失败率 >10%→检查 webhook/网络 |
| V-011 快照存储格式 | diff 基于降噪文本可识别变化；存储量可控 | 实测 diff 质量 | FS | I1（数据模型定义时） | 质量不足→同时存降噪前 html2text 文本 |
| V-012 存储清理策略 | 年累积快照 <10GB；报告 <5GB | 监控存储量 | FS | P1 | 超限→定义 N 天归档策略 |
| V-016 产品锚定文档解析与注入 | 可解析为干净文本；注入后建议含"对照我方定位" | .md/.html 解析测试 | FS+PM | I2 | 超长→截断；解析失败→提示重新上传 |
| V-017 产品锚定对建议质量提升 | 有锚定建议被盲评"更相关"比例 >60% | A/B 对比盲评 | PM+用户 | I2 首批情报后 | 不显著→简化锚定注入 |
| V-018 Negative Few-Shot 注入策略 | 注入后不产出类似无意义情报；prompt 不超窗口 | 实测注入最近 5 条 | FS+PM | I2 | 超限→减少条数；频繁无意义→升级相似度检索 top-K |

---

## 9. 原型产出判定（可选）

- **交互变化结论**：需要原型（原因：独立 HTML 消费页 + 飞书卡片 + Django Admin 三端交互，需走查信息流与按钮跳转）
- **页面与入口**：
  - Django Admin：MonitorProject 配置页（新增/编辑）、IntelligenceFeed 列表页（调度日志，含 NO_CHANGE/ERROR_CRAWL 筛选）
  - 独立 HTML 网页：收件箱列表页（仅 CHANGED）、情报详情页（`/view/html/{id}`，含"毫无意义"反馈按钮 + 评语输入框）、HTML 报告预览页
  - 飞书卡片：变化摘要正文 + "在线预览"按钮（跳转 `/view/html/{id}`）+ "下载 MD"按钮
- **关键控件/字段与校验**：
  - `competitor_urls` JSON 数组校验（每项必有 url + title）
  - `cron` 表达式格式校验（django-apscheduler cron 语法）
  - `feishu_webhook` URL 格式校验
  - 反馈评语 `user_comment` 可空（点"毫无意义"即可，评语可选）

---

## 10. 追溯链接

- `requirements/solution.md`：§2 推荐方案 / §5 验证清单 V-001~V-018 / §7.2 不变量 1-13 / §6 迭代记录 DB-1~DB-4b 裁决
- `requirements/raw.md`：UR-1~UR-7 用户需求 / Q1-Q8 澄清裁决 / 修订-1~修订-5 技术设计冲突
- 术语与口径：`project/memory/glossary.md`（无，标注为 CONTEXT GAP，solution.md 内自定义）
- `requirements/prototype.md`：待 R3 产出
