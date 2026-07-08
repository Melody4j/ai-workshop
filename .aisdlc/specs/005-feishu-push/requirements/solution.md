---
title: 产品需求方案决策（Solutionate）
status: draft
---

> 目的：把"推荐决策 + 备选方案对比 + 决策依据 + 验证清单"落到一份可评审文档里，作为后续 `prd.md` 与 `prototype.md` 的**唯一决策入口**。
>
> 原则：结论先行；只保留支撑决策的最小信息；不写"待确认问题"清单——所有不确定性统一进入"验证清单"（Owner/截止/动作明确）。

## 0. 基本信息

- 需求标识（分支 / ID）：005-feishu-push
- 作者 / 参与评审：AI Agent / PM
- 状态：draft
- 最后更新：2026-07-08
- 关联链接：`requirements/raw.md`（原始需求 + R1-Q1~Q4 澄清裁决）

## 1. 结论摘要（先给结论，3–7 行）

- **一句话目标**：在 LLM 情报生成完成后，根据任务配置的飞书 webhook 构建高级卡片消息推送，推送成功后更新 push_status 为 PUSHED。
- **In / Out 边界**：In = 飞书推送服务（卡片模板构建 + HTTP 推送 + 重试 + 状态更新）+ 手动触发 API + MD 下载接口 + push_status 字段迁移；Out = LLM 情报生成链路（Spec 004）、调度链路修改、飞书消息回调处理。
- **推荐方案**：独立 `feishu_service` 推送服务——构建飞书交互式卡片 JSON → httpx POST 推送 → 2 次重试间隔 30s → 更新 push_status；提供 `push_intelligence(feed_id)` 函数接口供 Spec 004 调用 + REST API 手动触发。
- **优先验证点**：V-001（飞书卡片 JSON 格式正确性）、V-002（推送成功率与重试）、V-005（卡片链接可访问性）。

## 2. 推荐方案（必须 1 个）

- **方案名**：独立 feishu_service + httpx 推送 + push_status 状态追踪

- **主流程 / 关键机制**（6 步）：
  1. **调用入口**：`feishu_service.push_intelligence(feed_id)` 接收 IntelligenceFeed ID，查库获取 feed 及关联的 MonitorProject
  2. **前置校验**：检查 `feed.job_status == CHANGED` 且 `project.feishu_webhook` 非空；不满足则跳过推送（push_status 保持 NOT_PUSHED，记日志）
  3. **卡片构建**：构建飞书交互式卡片 JSON（标题"竞品情报速报 · {project_name}" + change_summary 正文 + strategic_intent 正文 + "在线预览"按钮跳转 `{SITE_BASE_URL}/view/html/{feed_id}` + "下载 MD"按钮跳转 `{SITE_BASE_URL}/api/feeds/{feed_id}/download_md`）
  4. **HTTP 推送**：httpx POST 到 `project.feishu_webhook`，body 为卡片 JSON，Content-Type `application/json`
  5. **重试机制**：推送失败（HTTP 非 2xx 或异常）→ 等待 30s → 重试，最多重试 2 次（总共 3 次尝试）
  6. **状态更新**：推送成功 → `push_status=PUSHED`；3 次均失败 → `push_status=PUSH_FAILED`（情报和报告仍保留，AC-015）

- **关键边界/取舍**（≥ 3 条）：
  1. **不修改 scheduler_service**：推送服务独立存在，自动触发调用点由 Spec 004 在情报生成完成后集成，Spec 005 不侵入调度链路（R1-Q2 裁决）
  2. **push_status 与 job_status 正交**：job_status 标识情报结果，push_status 标识推送结果，两者独立演进不互相覆盖（R1-Q1 裁决）
  3. **同步重试不引入异步队列**：重试使用 `time.sleep(30)`，遵循项目不变量"不引入消息队列"；重试期间 push_status 保持 NOT_PUSHED，仅最终失败才标记 PUSH_FAILED
  4. **卡片正文仅含 change_summary + strategic_intent**：action_suggestion 和 evidence_diff 留给详情页/报告页，保持卡片简洁（R1-Q3 裁决）

- **为什么选它**（1–3 条）：
  1. 职责单一：feishu_service 只做推送，不依赖 Spec 004 代码，可在 dev 分支独立开发和测试（R1-Q2 约束）
  2. 接口清晰：`push_intelligence(feed_id)` 是 Spec 004 唯一需要调用的入口，集成成本最低
  3. 与现有技术栈一致：httpx 已是项目依赖（采集层使用），无需引入新 HTTP 库

## 3. 备选方案（2–3 个，差异明显）

### 3.1 备选方案：调度末尾扫描推送

- **核心机制**（1–2 句）：在 `scheduler_service.run_scan()` 末尾，扫描当前项目下所有 `job_status=CHANGED` 且 `push_status=NOT_PUSHED` 的 IntelligenceFeed 记录，逐条推送。
- **主流程**（4 步）：
  1. run_scan() 采集入库后，查询 CHANGED + NOT_PUSHED 的 feed
  2. 逐条调用 feishu_service.push_intelligence(feed_id)
  3. 推送结果更新 push_status
  4. 继续下一个项目
- **边界与取舍**：
  1. 需修改 scheduler_service，侵入调度链路
  2. dev 分支上 scheduler_service 不写 IntelligenceFeed（不变量 5），扫描结果为空，无法独立验证
- **适用前提**（何时会选它）：
  1. 如果 Spec 004 不存在或无限期推迟，需要调度层自行触发推送
- **不选原因**：
  1. 违反 R1-Q2 裁决（Spec 005 不修改调度链路）
  2. dev 分支上 scheduler_service 不产出 IntelligenceFeed，集成点无意义

### 3.2 备选方案：Django post_save 信号触发

- **核心机制**（1–2 句）：监听 IntelligenceFeed 的 `post_save` 信号，当 `job_status=CHANGED` 且 `push_status=NOT_PUSHED` 时自动触发推送。
- **主流程**（3 步）：
  1. 注册 post_save 信号处理器
  2. IntelligenceFeed 保存时检查 job_status
  3. CHANGED 时自动调用 feishu_service.push_intelligence
- **边界与取舍**：
  1. 隐式触发，调试困难——推送失败时不易定位是信号处理器问题还是推送服务问题
  2. 信号处理器在同一个事务/请求中执行，推送重试 30s×2 会阻塞保存操作
- **适用前提**（何时会选它）：
  1. 需要完全解耦、无需任何调用方显式触发推送
- **不选原因**：
  1. 信号隐式触发违反可调试性原则
  2. 同步重试 60s+ 会阻塞 IntelligenceFeed 保存，影响调度链路性能

## 4. 决策依据（证据入口清单）

- `raw.md` R1-Q1：push_status 字段设计裁决 → 推荐方案第 6 步状态更新
- `raw.md` R1-Q2：集成边界裁决（独立服务，不侵入调度） → 推荐方案边界 1
- `raw.md` R1-Q3：卡片正文内容映射（change_summary + strategic_intent） → 推荐方案第 3 步卡片构建
- `raw.md` R1-Q4：失败重试策略（2 次，间隔 30s） → 推荐方案第 5 步重试机制
- `raw.md` R1 附加确认：webhook 为空跳过、SITE_BASE_URL 配置、卡片标题、下载接口 → 推荐方案第 2/3 步
- `.aisdlc/specs/001-competitive-intel-agent/requirements/prd.md` F-10/F-17/AC-005/AC-015 → 推送需求与失败处理约定
- `.aisdlc/project/components/intelligence-models.md` 不变量 6 → job_status 枚举兼容
- `.aisdlc/project/components/intelligence-scheduler.md` 不变量 5 → 本模块不写 IntelligenceFeed（确认 Spec 005 不依赖调度层产出 feed）
- `backend/apps/intelligence/models.py` → IntelligenceFeed 当前字段（无 push_status，需新增）
- `backend/apps/intelligence/views.py` / `urls.py` → 当前 API 结构（需新增推送和下载端点）

## 5. 验证清单（V-xxx，可执行）

- **V-001** 飞书卡片 JSON 格式正确性
  - 风险/假设：飞书交互式卡片 JSON schema 有严格校验，格式错误会被飞书 API 拒绝
  - 方法：构建卡片 JSON 后用飞书 API 校验或发送测试消息到测试群
  - 成功/失败信号：飞书 API 返回 200 + `{"StatusCode":0}` 为成立；返回非 0 或 4xx 为不成立
  - Owner：DEV
  - 截止：I2 实现后 1 天
  - 触发动作：不成立则对照飞书卡片文档修正 JSON 结构

- **V-002** 推送成功率与重试逻辑
  - 风险/假设：飞书 webhook 可能因网络抖动暂时不可达，重试 2 次间隔 30s 可覆盖大部分临时故障
  - 方法：模拟 webhook 返回 500 / 超时 / 网络断开，验证重试次数和间隔
  - 成功/失败信号：3 次尝试后 push_status=PUSH_FAILED 为成立；未重试或重试次数不对为不成立
  - Owner：DEV
  - 截止：I2 实现后 1 天
  - 触发动作：不成立则修正重试逻辑

- **V-003** push_status 状态流转正确性
  - 风险/假设：push_status 需在 NOT_PUSHED → PUSHED / PUSH_FAILED 之间正确流转
  - 方法：单元测试覆盖 3 种场景——推送成功、推送失败、webhook 为空跳过
  - 成功/失败信号：成功时 PUSHED，失败时 PUSH_FAILED，跳过时 NOT_PUSHED 为成立
  - Owner：DEV
  - 截止：I2 实现后 1 天
  - 触发动作：不成立则修正状态更新逻辑

- **V-004** webhook 为空时跳过推送
  - 风险/假设：用户未配置飞书 webhook 时不应尝试推送，也不应标记为失败
  - 方法：创建 feishu_webhook="" 的 MonitorProject + CHANGED feed，调用 push_intelligence
  - 成功/失败信号：push_status 保持 NOT_PUSHED，日志含"webhook 未配置"，无 HTTP 请求发出 为成立
  - Owner：DEV
  - 截止：I2 实现后 1 天
  - 触发动作：不成立则修正前置校验逻辑

- **V-005** 飞书卡片链接可访问性
  - 风险/假设：卡片中"在线预览"和"下载 MD"按钮的绝对 URL 需要可访问
  - 方法：发送测试卡片到飞书群，点击按钮验证跳转
  - 成功/失败信号：在线预览打开报告页面，下载 MD 触发文件下载 为成立；链接 404 或无法打开为不成立
  - Owner：DEV
  - 截止：I2 实现后 2 天
  - 触发动作：不成立则检查 SITE_BASE_URL 配置和路由注册

- **V-006** MD 下载接口正确性
  - 风险/假设：md_table_path 指向的文件可能不存在或路径无效
  - 方法：调用 GET /api/feeds/{id}/download_md，验证返回 Content-Type 和文件内容
  - 成功/失败信号：返回 `text/markdown` Content-Disposition attachment 为成立；404 或 500 为不成立
  - Owner：DEV
  - 截止：I2 实现后 1 天
  - 触发动作：不成立则检查文件路径和 FileResponse 实现

- **V-007** 手动触发推送 API 正确性
  - 风险/假设：POST /api/feeds/{id}/push 需正确触发推送并返回结果
  - 方法：调用 API 后检查返回的 push_status 和数据库状态
  - 成功/失败信号：返回 200 + push_status 更新为 PUSHED 为成立；返回 500 或状态未更新为不成立
  - Owner：DEV
  - 截止：I2 实现后 1 天
  - 触发动作：不成立则检查 API 视图和 feishu_service 调用链

- **V-008** Spec 004 集成兼容性
  - 风险/假设：Spec 004 merge 后在情报生成完成处调用 feishu_service.push_intelligence(feed_id) 能正常工作
  - 方法：Spec 004 merge 后端到端测试——创建 CHANGED feed → 自动推送 → 飞书收到卡片
  - 成功/失败信号：feishu_service 被正确调用且 push_status=PUSHED 为成立；调用失败或遗漏为不成立
  - Owner：DEV
  - 截止：Spec 004 merge 后 2 天
  - 触发动作：不成立则检查 Spec 004 集成点是否正确调用推送接口

## 6. 迭代记录（追加，不覆盖）

- 2026-07-08：R1 澄清完成，产出 solution.md 初版。4 轮澄清（push_status 字段 / 集成边界 / 卡片正文 / 失败重试）+ 4 项附加确认（webhook 为空 / SITE_BASE_URL / 标题 / 下载接口）。推荐方案为独立 feishu_service，2 个备选（调度末尾扫描 / Django 信号）已排除。

## 7. Impact Analysis（需求影响分析）

### 7.1 受影响模块

| 模块 | 影响类型 | 关键不变量 | stale? |
|------|----------|-----------|--------|
| intelligence-models | 新增字段（push_status） | push_status 与 job_status 正交；默认 NOT_PUSHED | no |
| intelligence-api | 新增端点（push / download_md） | 现有端点不变；新增 POST /api/feeds/{id}/push + GET /api/feeds/{id}/download_md | no |
| intelligence-scheduler | 不修改 | 不变量 5：本模块不写 IntelligenceFeed（Spec 005 不侵入） | no |
| feishu-push（新增） | 新增服务模块 | feishu_service.push_intelligence(feed_id) 为唯一入口 | n/a |

### 7.2 需遵守的不变量

- job_status 保持 CHANGED / NO_CHANGE / ERROR_CRAWL 三态，不扩展（来源：`.aisdlc/project/components/intelligence-models.md#不变量6`）
- 仅 job_status=CHANGED 的记录触发推送（来源：`001 prd.md#规则-5`）
- push_status 与 job_status 正交，不互相覆盖（来源：`raw.md R1-Q1`）
- 不引入消息队列，重试用同步 sleep（来源：`001 prd.md#规则-9`，`raw.md R1-Q4`）
- httpx 优先用于 HTTP 调用（来源：`001 solution.md` 技术栈）
- 推送失败情报和报告仍保留（来源：`001 prd.md#AC-015`）

### 7.3 跨模块影响

- **Spec 004 → Spec 005**：Spec 004 在 LLM 情报生成完成后（IntelligenceFeed 创建为 CHANGED 后）需调用 `feishu_service.push_intelligence(feed_id)`。Spec 005 提供函数接口，Spec 004 负责集成调用点。
- **intelligence-models → migration**：新增 push_status 字段需要 migration 0005，所有现有 IntelligenceFeed 记录默认 NOT_PUSHED。
- **intelligence-api → serializers**：IntelligenceFeedListSerializer 和 IntelligenceFeedDetailSerializer 需新增 push_status 字段到 fields 列表。
- **前端 reports 页面**：push_status 可用于展示推送状态（P0 范围外，但字段预留）。

### 7.4 Context Gaps

- `CONTEXT GAP`：Spec 004 的 `requirements/raw.md` 不在 dev 分支（worktree 基于 dev，004 分支未 merge）。Spec 005 无法读取 Spec 004 的详细设计来确认集成点精确位置。
  - 建议动作：Spec 004 merge 后进行端到端集成验证（V-008）
- `CONTEXT GAP`：飞书交互式卡片 JSON schema 的精确格式需对照飞书开放平台文档确认。
  - 建议动作：实现阶段查阅飞书卡片消息文档，用测试群验证 JSON 格式（V-001）

## 8. Mini-PRD（跳过 `requirements/prd.md`，在此补齐）

### MVP 范围

**In**：
1. IntelligenceFeed 新增 `push_status` 字段（NOT_PUSHED / PUSHED / PUSH_FAILED）+ migration 0005
2. `feishu_service.py` 推送服务：`push_intelligence(feed_id)` 函数接口
3. 飞书交互式卡片模板构建：标题 + change_summary + strategic_intent + 在线预览按钮 + 下载 MD 按钮
4. httpx POST 推送到飞书 webhook + 2 次重试间隔 30s
5. push_status 状态更新（成功 → PUSHED，失败 → PUSH_FAILED，webhook 空 → 保持 NOT_PUSHED）
6. REST API：POST /api/feeds/{id}/push（手动触发推送）
7. REST API：GET /api/feeds/{id}/download_md（下载 MD 报告文件）
8. settings.py 新增 SITE_BASE_URL 配置项
9. serializers 新增 push_status 字段

**Out**：
- LLM 情报生成链路（Spec 004 负责）
- 调度链路修改（Spec 005 不侵入 scheduler_service）
- 飞书消息回调/交互回调处理
- 飞书推送频率限制/限流
- 前端 push_status 展示（P1 候选）

### 验收标准（AC）

- **AC-001**：IntelligenceFeed 新增 push_status 字段，默认 NOT_PUSHED，migration 0005 执行成功
- **AC-002**：调用 `feishu_service.push_intelligence(feed_id)` 对 CHANGED + webhook 非空的 feed 推送成功后，push_status 更新为 PUSHED
- **AC-003**：飞书卡片含标题"竞品情报速报 · {project_name}"、change_summary 正文、strategic_intent 正文、"在线预览"按钮、"下载 MD"按钮
- **AC-004**：推送失败时重试 2 次间隔 30s，3 次均失败后 push_status=PUSH_FAILED，情报和报告仍保留
- **AC-005**：webhook 为空时跳过推送，push_status 保持 NOT_PUSHED，日志记录"webhook 未配置"
- **AC-006**：POST /api/feeds/{id}/push 返回推送结果（push_status），非 CHANGED feed 返回 400
- **AC-007**：GET /api/feeds/{id}/download_md 返回 MD 文件下载流（Content-Type: text/markdown）
- **AC-008**：卡片中"在线预览"按钮链接为 `{SITE_BASE_URL}/view/html/{feed_id}`，"下载 MD"按钮链接为 `{SITE_BASE_URL}/api/feeds/{feed_id}/download_md`
- **AC-009**：IntelligenceFeedListSerializer 和 DetailSerializer 包含 push_status 字段

### 交互变化结论

无前端交互变化。飞书卡片是推送产物（D-001 的实现），不属于前端页面交互。手动触发 API 供调试/运维使用，无 UI 界面。

### 影响面

- **数据模型**：IntelligenceFeed 新增 push_status 字段（migration 0005）
- **服务层**：新增 `backend/apps/intelligence/services/feishu_service.py`
- **API 端点**：新增 `POST /api/feeds/{id}/push` + `GET /api/feeds/{id}/download_md`
- **配置**：settings.py 新增 `SITE_BASE_URL`
- **序列化器**：IntelligenceFeedListSerializer / IntelligenceFeedDetailSerializer 新增 push_status
- **跨 Spec 依赖**：Spec 004 需在情报生成后调用 `feishu_service.push_intelligence(feed_id)`
