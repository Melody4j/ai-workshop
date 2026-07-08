---
title: 产品需求方案决策（Solutionate）
status: draft
---

> 目的：把“推荐决策 + 备选方案对比 + 决策依据 + 验证清单”落到一份可评审文档里，作为后续 `prd.md` 与 `prototype.md` 的唯一决策入口。
>
> 原则：结论先行；只保留支撑决策的最小信息；不写“待确认问题”清单，所有不确定性统一进入“验证清单”（Owner/截止/动作明确）。

## 0. 基本信息

- 需求标识（分支 / ID）：001-competitive-intel-agent
- 作者 / 参与评审：PM（作者）；FS（待评审）；Leader（评审）
- 状态：draft
- 最后更新：2026-07-07
- 关联链接：`{FEATURE_DIR}/requirements/raw.md`（含 8 轮澄清记录、DB 裁决、前端架构调整修订）

## 1. 结论摘要（先给结论）

- 一句话目标：为个人产品经理/独立开发者构建一个自动化竞争情报监控代理，用户在 Vue 前端配置自有产品锚定文档与 5-10 个竞品 URL 后，系统日级采集官网与社媒信号，经 html2text + LLM 降噪后与历史快照 diff，有变化时用单次 LLM 解读战略意图并给出行动建议，随后推送飞书、沉淀报告；无变化则熔断退出。
- 本次 In / Out 的边界：In = Vue 任务配置、Vue 调度执行列表、Vue 收件箱 / 情报详情 / 报告预览、Django API + 调度后端、html2text + LLM 降噪、快照 diff + 单次 LLM 情报生成（4 字段）、有变化推飞书 + 报告产物落盘、无变化熔断、Negative Few-Shot 反馈注入； Out = 多租户、团队协作、第三方流量 API、AI 提及度、多信号交叉验证、3-Agent 多模型分层（P1）、Slack/邮件通知、实时/小时级监控。
- 推荐方案：**“Vue 前端 + Django API/调度后端 + 日级采集 + html2text/LLM 降噪 + diff 熔断 + 单次 LLM 情报生成 + 有变化推飞书”最小闭环**。产品前端页面统一由 Vue 承担；Django 只负责 API、调度、采集、LLM 编排、报告产物生成与飞书推送。
- 优先验证点：V-004（LLM prompt 模板与降噪/情报生成准确性）、V-007（API 契约与 Vue 页面消费）、V-019（Vue 与 Django Session/CSRF 集成）、V-017（产品锚定对建议质量提升）。

## 2. 推荐方案

- 方案名：**竞争情报前后端分离单体（Competitive Intel Split-Monolith）**
- 主流程 / 关键机制：
  1. **任务配置（Vue）**：用户在 Vue 前端创建/编辑 `MonitorProject`，填写项目名、自有产品锚定文档 `self_product_doc`、竞品 URL JSON 数组 `competitor_urls=[{url,title}]`、飞书 webhook、cron、启停状态；前端经 Django API 落库。
  2. **采集（django-apscheduler）**：调度器按日级 cron 触发任务，对每个 URL 使用 httpx 采集 HTML；若 httpx 拿不到有效内容且判断为 SPA，再按需降级 Playwright。
  3. **降噪与快照存储**：HTML 先做 html2text，再做独立的 LLM 语义降噪，产出 `raw_markdown` / `clean_markdown`；快照以 append-only 方式写入 `DataSnapshot`。
  4. **变化识别（diff + 熔断）**：将本次快照与上一条快照做 diff；diff 为空则写 `IntelligenceFeed(job_status=NO_CHANGE)` 并结束，不触发情报生成、不推送飞书。
  5. **情报生成（单次 LLM）**：仅在 diff 非空时触发一次 LLM，输入为 diff 片段 + `self_product_doc` + 最近 5 条 Negative Few-Shot，输出 4 字段：变化摘要 / 战略意图 / 行动建议 / 证据 diff（嵌入摘要或报告素材，不独立建列）。
  6. **报告与分发**：后端生成 HTML/MD 报告产物并落盘，保存路径索引；Vue 报告预览页通过 API 获取情报详情与报告元数据；飞书高级卡片跳转 Vue 报告预览路由。
  7. **消费与反馈（Vue）**：Vue 收件箱仅展示 `CHANGED`；Vue 调度执行列表展示 `CHANGED` / `NO_CHANGE` / `ERROR_CRAWL` 的全量执行记录；用户可在情报详情页点“毫无意义”并输入评语，下次推理前注入 Negative Few-Shot。

- 关键边界 / 取舍：
  1. **前后端分离，但仍是单体项目**：一个仓库、一套业务模型；前端是 Vue，后端是 Django，不拆成多服务。
  2. **产品前端统一 Vue 化**：任务配置、调度执行列表、收件箱、情报详情、报告预览全部由 Vue 提供；Django Admin 不再作为产品主入口。
  3. **后端职责集中在业务编排**：Django 负责 API、调度、采集、LLM、报告产物、飞书推送，不承担产品页面渲染。
  4. **报告产物与前端展示分离**：前端页面由 Vue 展示；若保留 Jinja2，仅用于生成离线 HTML 报告文件，不承担页面 UI。
  5. **httpx 优先 + Playwright 兜底**：只对 SPA 按需降级，不能默认全量 Playwright。
  6. **两次 LLM 调用不可合并**：降噪 LLM 与情报生成 LLM 必须独立。
  7. **diff 非空才生成情报**：变化识别是成本熔断器，不能对全量快照做情报生成。
  8. **收件箱与执行列表职责分离**：收件箱只消费 `CHANGED`；执行列表面向监控与排障，展示所有状态。
  9. **Negative Few-Shot 最多最近 5 条**：反馈进入下一次生成，但要受 prompt 长度约束。
  10. **append-only 快照不变**：`DataSnapshot` 禁止 UPDATE/DELETE，DB 层强约束。

- 为什么选它（可追溯到证据）：
  1. raw.md 最新修订已明确：前端统一改为 Vue，且任务配置、调度执行列表必须进入产品前端。
  2. raw.md 原始目标仍然是“快速实现 MVP”，因此保留 Django 单体后端、SQLite、日级调度，不引入额外基础设施。
  3. UR-3 / UR-5 / UR-6 需要自动采集、可解释情报和主动推送，当前链路完整覆盖。
  4. Vue 化后，配置与执行状态对单用户更统一，避免后台页和消费页割裂。

## 3. 备选方案

### 3.1 备选方案：Django Admin + Jinja2 页面（旧方案）

- 核心机制：配置走 Django Admin，消费页走 Jinja2 或独立 HTML，后端同时承担 UI 渲染与业务编排。
- 适用前提：内部工具场景，UI 体验要求低，希望用最少前端开发完成闭环。
- 不选原因：用户已明确要求前端统一采用 Vue，且任务配置、调度执行列表也要前端化；继续沿用 Admin 作为主入口与最新裁决冲突。

### 3.2 备选方案：Vue 前端 + 多服务后端

- 核心机制：前端单独部署，后端拆为 API 服务、调度服务、采集服务、通知服务。
- 适用前提：多团队协作、高并发、多租户或需要独立扩缩容。
- 不选原因：当前是单用户 MVP，拆服务会显著增加部署、观测、测试和一致性成本。

### 3.3 备选方案：纯后端产物驱动，无交互前端

- 核心机制：只生成飞书卡片和 HTML/MD 报告文件，不做任务配置页、执行列表、收件箱等前端产品页面。
- 适用前提：只验证采集与推送价值，不关注长期使用体验。
- 不选原因：用户已明确要 Vue 页面覆盖配置与执行列表；同时 UR-4 也需要结构化消费入口。

## 4. 决策依据（证据入口清单）

- `raw.md#需求描述`：产品愿景与核心价值链（采集 → 变化 → 意图 → 建议 → 推送）。
- `raw.md#用户需求` UR-1 ～ UR-7：快速配置、持续自动采集、结构化情报消费、主动通知、反馈改进。
- `raw.md#R1-修订：前端架构调整裁决（新增）`：前端统一改为 Vue，任务配置与调度执行列表也进入前端。
- `raw.md#R1-修订：数据库设计审查裁决（4 项）`：`competitor_urls` JSON、`self_product_doc` Nullable、`NO_CHANGE` 同表、`refined_rules` 占位。
- `raw.md#R1-修订：技术设计文档冲突裁决（5 项）`：httpx 优先 + Playwright 兜底、降噪与情报生成两次 LLM、产品锚定为 P0。

## 5. 验证清单（V-xxx，可执行）

- **V-001** 社媒平台 JS 渲染兜底
  - 风险/假设：社媒平台多为 SPA，httpx 拿不到内容
  - 方法：httpx 失败时降级 Playwright 验证
  - 成功/失败信号：Playwright 能拿到有效内容
  - Owner：FS
  - 截止：I2
  - 触发动作：若仍失败，标记该平台不可采集

- **V-002** Vue 配置页支持多 URL 录入的可用性
  - 风险/假设：`competitor_urls` 是 JSON 数组，直接文本输入可用性差
  - 方法：实现时优先用“动态表单行 + title/url 双字段”交互，而非裸 JSON 文本框
  - 成功/失败信号：用户能完成 5-10 个竞品 URL 录入，错误率低
  - Owner：PM + FS
  - 截止：R3 / I1
  - 触发动作：若仍需裸 JSON，则补导入/校验辅助

- **V-003** diff 粒度
  - 风险/假设：全文文本 diff 仍可能引入布局噪音
  - 方法：先用降噪文本做全文 diff，用真实站点样本验证
  - 成功/失败信号：噪音 diff 过滤率 >80%
  - Owner：FS
  - 截止：I2
  - 触发动作：不足则升级关键区域 diff

- **V-004** LLM prompt 准确性（降噪 + 情报生成）
  - 风险/假设：降噪误删、情报建议空泛
  - 方法：两套 prompt 分别用 10-20 个真实样本测试
  - 成功/失败信号：降噪保留核心 >90%；情报判定准确率 >80%
  - Owner：FS + PM
  - 截止：I2
  - 触发动作：3 轮不达标则补规则预过滤

- **V-005** cron 配置前端化
  - 风险/假设：cron 表达式直接输入对用户不友好
  - 方法：Vue 端优先提供日级调度表单或预设选项，再转换为 cron
  - 成功/失败信号：用户无需手写复杂 cron 也能完成配置
  - Owner：PM + FS
  - 截止：R3 / I1
  - 触发动作：若复杂度仍高，限制 MVP 为“每天固定时间”

- **V-006** 采集失败重试策略
  - 风险/假设：目标站临时不可达
  - 方法：默认重试 1-2 次（间隔 30s），记录执行日志
  - 成功/失败信号：单任务失败不阻塞其他任务
  - Owner：FS
  - 截止：I2
  - 触发动作：失败率 >20% 时升级退避策略

- **V-007** API 契约与 Vue 页面消费
  - 风险/假设：任务配置、执行列表、收件箱、详情、报告预览都依赖清晰 API
  - 方法：在 I1 定义统一 API 契约，覆盖分页、过滤、详情、反馈、预览元数据
  - 成功/失败信号：Vue 页面不依赖后端模板即可完整消费数据
  - Owner：FS
  - 截止：I1
  - 触发动作：若页面字段反复变更，先冻结 BFF / DTO

- **V-008** 飞书高级卡片格式
  - 风险/假设：卡片按钮要跳到 Vue 预览路由且保持可访问
  - 方法：对接卡片 API，按钮链接指向前端报告预览路由
  - 成功/失败信号：飞书可读，按钮可打开报告页
  - Owner：FS
  - 截止：I2
  - 触发动作：如卡片复杂度过高，降级文本消息

- **V-010** 飞书推送失败降级
  - 风险/假设：webhook 不可达时情报丢失
  - 方法：重试 1-2 次；报告产物与记录仍保留
  - 成功/失败信号：推送失败可从执行列表追溯
  - Owner：FS
  - 截止：I2
  - 触发动作：失败率 >10% 时检查网络 / webhook

- **V-011** 快照存储格式
  - 风险/假设：只存降噪文本可能损失结构信息
  - 方法：MVP 保存 `raw_markdown + clean_markdown + meta`
  - 成功/失败信号：diff 质量可接受，存储量可控
  - Owner：FS
  - 截止：I1
  - 触发动作：质量不足则增加原始文本辅助

- **V-012** 存储清理策略
  - 风险/假设：append-only 快照与报告长期累积
  - 方法：MVP 默认永久保留，P1 定归档
  - 成功/失败信号：年存储量可接受
  - Owner：FS
  - 截止：P1
  - 触发动作：超限则定义归档策略

- **V-015** 项目知识库缺失影响 Impact Analysis
  - 风险/假设：`.aisdlc/project/` 为空，无法引用存量模块页
  - 方法：按“全新仓库”口径记录，无现有模块冲突
  - 成功/失败信号：当前实现无 stale 风险
  - Owner：PM + Leader
  - 截止：本阶段不阻塞
  - 触发动作：后续有存量代码时补 discover

- **V-016** 产品锚定文档解析与注入
  - 风险/假设：上传文档格式杂乱
  - 方法：支持 `.md/.html`，解析后注入 prompt，必要时截断
  - 成功/失败信号：建议中体现“对照我方定位”
  - Owner：FS + PM
  - 截止：I2
  - 触发动作：过长则做摘要/截断

- **V-017** 产品锚定对建议质量提升
  - 风险/假设：增加上下文未必提升建议质量
  - 方法：有锚定 / 无锚定 A/B 盲评
  - 成功/失败信号：有锚定建议“更相关/更可执行” >60%
  - Owner：PM + 用户
  - 截止：I2 首批情报后
  - 触发动作：不显著则简化注入策略

- **V-018** Negative Few-Shot 注入策略
  - 风险/假设：反馈积累后 prompt 膨胀
  - 方法：默认最近 5 条，超过则截断
  - 成功/失败信号：注入后无意义情报减少
  - Owner：FS + PM
  - 截止：I2
  - 触发动作：频繁失败则升级相似度检索

- **V-019** Vue 与 Django Session/CSRF 集成
  - 风险/假设：前后端分离后写操作需要处理登录态、CSRF、Cookie 同域问题
  - 方法：MVP 采用同域部署 + Django Session/CSRF；前端统一封装 API Client
  - 成功/失败信号：配置、反馈等写操作稳定成功，无跨域/CSRF 误报
  - Owner：FS
  - 截止：I1
  - 触发动作：若同域不可行，再评估 token 方案

## 6. Context Gaps

- `project/memory/product.md`：缺失，标记 `CONTEXT GAP`
- `project/memory/glossary.md`：缺失，标记 `CONTEXT GAP`
- `project/products/index.md`：缺失，标记 `CONTEXT GAP`
- `project/components/index.md`：缺失，标记 `CONTEXT GAP`

当前仓库为空仓库首次开发，上述缺口不阻塞本轮方案决策，但已通过 V-015 记录。

## 7. Impact Analysis

### 7.1 受影响模块

| 模块 | 影响类型 | 关键不变量 | stale? |
|---|---|---|---|
| Vue 前端壳层 / 路由 | 新增能力 | 产品页面统一由 Vue 承担；不再依赖 Django Admin / Jinja2 页面 | N/A（全新） |
| 任务配置页 | 新增能力 | `competitor_urls` 录入必须满足 `{url,title}`；cron 配置需转后端合法表达 | N/A（全新） |
| 调度执行列表 | 新增能力 | 展示 `CHANGED` / `NO_CHANGE` / `ERROR_CRAWL`；支持筛选、追溯错误 | N/A（全新） |
| 收件箱 / 情报详情 / 报告预览 | 新增能力 | 收件箱仅展示 `CHANGED`；反馈入口写回 Negative Few-Shot 数据源 | N/A（全新） |
| Django API 层 | 新增能力 | 对前端暴露稳定 DTO / 过滤 / 分页 / 详情接口 | N/A（全新） |
| 调度器（django-apscheduler） | 新增能力 | 日级 cron；无消息队列 | N/A（全新） |
| 采集器（httpx + Playwright） | 新增能力 | httpx 优先，Playwright 按需兜底 | N/A（全新） |
| 降噪引擎（html2text + LLM） | 新增能力 | 与情报生成是两次独立 LLM 调用 | N/A（全新） |
| diff / 熔断引擎 | 新增能力 | diff 为空即熔断，不触发情报生成 | N/A（全新） |
| 报告产物生成 | 新增能力 | HTML/MD 报告落盘；若用 Jinja2，仅承担离线产物 | N/A（全新） |
| 飞书通知 | 新增能力 | 有变化即推送；按钮打开 Vue 预览页 | N/A（全新） |

### 7.2 需遵守的不变量

1. 快照 append-only，DB 层阻止 UPDATE / DELETE。
2. 降噪 LLM 与情报生成 LLM 必须是独立两次调用。
3. 情报生成仅在 diff 非空时触发。
4. 情报输出固定 4 字段，不含价值度字段。
5. `has_change=True` → 推飞书 + 存报告；`has_change=False` → 熔断退出。
6. 收件箱仅展示 `CHANGED`；调度执行列表展示 `CHANGED` / `NO_CHANGE` / `ERROR_CRAWL`。
7. httpx 优先，Playwright 仅 SPA 按需降级。
8. 调度仅使用 django-apscheduler 日级执行，不引入消息队列。
9. 每个监控任务都要关联 `self_product_doc`（Nullable，允许只上传文件）。
10. `competitor_urls` 必须为 JSON 数组，每项 `{"url":"...","title":"..."}`。
11. Negative Few-Shot 只取最近 5 条。
12. `refined_rules` 仅为 P1 占位，MVP 不写入。
13. 产品功能页面统一由 Vue 承担，Django Admin 不再作为产品主入口。

### 7.3 跨模块影响

- 配置入口改为 Vue 后，后端必须补稳定 API，而不能依赖 Django ModelForm 页面。
- 执行状态对前端开放后，`NO_CHANGE` / `ERROR_CRAWL` 的可见性从“仅后台”调整为“执行列表可见、收件箱不可见”。
- 飞书卡片的“在线预览”按钮需要从旧的 HTML 页面路由改为 Vue 报告预览路由。
- 报告预览页不再依赖服务端页面渲染，前后端要通过 API 或报告元数据衔接。

## 8. 迭代记录

- 2026-07-07：R1 澄清初始化，完成目标用户、信号源、变化判定、频率、情报生成、通知、持久化、部署形态等裁决。
- 2026-07-07：技术设计冲突修订，确认 httpx 优先 + Playwright 兜底、取消价值度分级、加入产品锚定与独立降噪 LLM。
- 2026-07-07：数据库设计审查裁决，确认 `self_product_doc`、`competitor_urls` JSON、`NO_CHANGE` 入 `IntelligenceFeed`、`refined_rules` 占位。
- 2026-07-07：前端架构调整修订，明确前端统一改为 Vue，任务配置与调度执行列表进入产品前端；Django 收敛为 API/调度后端。
- 2026-07-07：重写 solution.md，使 UI 入口、状态可见性、报告预览和技术栈与最新裁决一致。
