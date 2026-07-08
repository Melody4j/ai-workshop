---
title: D2 Design — Firecrawl 爬虫接入设计决策（RFC）
status: draft
---

> 目的：基于 R1（solution.md）+ D1（research.md）+ 项目知识库，产出可评审的技术决策文档。只写决策与对外承诺要点，不写实现步骤/字段清单/DDL。

## 0. 基本信息

- 需求标识（分支）：`006-firecrawl-crawler`
- 作者：AI + 用户
- 状态：draft
- 最后更新：2026-07-08
- 关联文档：`requirements/solution.md`、`design/research.md`、`requirements/raw.md`

## 1. In/Out（追溯 solution.md）

- **In**：
  - crawler_service.py 整文件重写为 Firecrawl REST API 调用（crawl 多页 + prompt + 轮询 + 拼接）
  - scheduler_service.py 调用点修改（传 crawl_hint）
  - serializers.py validate_competitor_urls 放宽（允许 crawl_hint 可选）
  - settings.py 新增 FIRECRAWL_API_KEY + python-dotenv 加载
  - base.txt 依赖替换（移除 httpx/playwright/BS/html2text，新增 firecrawl-py）
  - 前端 ProjectForm.vue + projects.ts + ProjectFormPage.vue 新增 crawl_hint 输入
  - 清理历史快照管理命令
  - 测试重写
- **Out**：
  - 数据模型 schema 变更（JSONField 兼容，无需迁移）
  - diff 熔断逻辑变更（基于合并后 clean_md，逻辑不变）
  - LLM 链路（004 负责）/ 飞书推送（005 负责）/ 调度器（scheduler.py 不变）

## 2. 推荐方案（C4 L1-L3）

### 2.1 C4 L1：系统上下文

```
[用户] → [Vue SPA: ProjectForm] → [Django API] → [SQLite]
                                          ↓
                              [调度器 scheduler_service]
                                          ↓
                              [crawler_service] → [Firecrawl Cloud API]
                                          ↓
                              [文件系统 data/] ← 落盘 raw_html + clean_md
```

用户在 Vue SPA 配置竞品 URL + crawl_hint → Django API 存储 → 调度器触发 → crawler_service 调 Firecrawl 云端 API → 返回多页 markdown+html → 落盘 + DataSnapshot 入库。

### 2.2 C4 L2：容器

| 容器 | 改动 | 职责 |
|---|---|---|
| Vue SPA（frontend/） | 修改 | ProjectForm.vue 新增 crawl_hint 输入框，提交时传入 competitor_urls |
| Django Backend（backend/） | 修改 | crawler_service 重写 + scheduler_service 调用修改 + serializer 放宽 + settings 配置 |
| Firecrawl Cloud API（外部） | 新增对接 | POST /v1/crawl（启动爬取+prompt）→ GET /v1/crawl/{id}（轮询状态+数据） |
| SQLite | 不变 | DataSnapshot 表结构不变（raw_html_path + clean_md_path） |
| 文件系统（data/） | 不变 | file_storage.py 落盘逻辑保留 |

### 2.3 C4 L3：组件（crawler_service 内部）

```
crawler_service.py
├── fetch_with_firecrawl(url, crawl_hint, limit=10) → (raw_html, clean_md) | ("", "")
│   ├── _start_crawl(url, crawl_hint, limit) → job_id
│   │   └── POST /v1/crawl {url, prompt: crawl_hint, limit, scrapeOptions:{formats:[markdown,html]}}
│   ├── _poll_crawl(job_id, poll_interval=5, timeout=120) → V1CrawlStatusResponse
│   │   └── GET /v1/crawl/{id} 循环直到 status=completed/failed 或超时
│   └── _merge_documents(documents) → (raw_html, clean_md)
│       └── 按 document.url 字典序排序 → 拼接 markdown（含 source 标记）+ 拼接 html
```

## 3. 关键决策

### D-001：用 requests 直调 Firecrawl REST API，不用 SDK crawl_url

- **决策**：crawler_service 用 `requests` 库直接调 Firecrawl REST API（POST /v1/crawl + GET /v1/crawl/{id}），不使用 firecrawl-py SDK 的 `crawl_url` 方法。
- **原因**：D1 调研（research.md T1）确认 SDK `crawl_url` 的 `_validate_kwargs` 白名单**不含 prompt**，无法传 crawl_hint。REST API 文档称支持 prompt 参数。
- **备选**：SDK crawl_url（不传 prompt）— 不选，因不满足 raw.md 需求 3。

### D-002：crawl_hint 作为 prompt 传入 POST /v1/crawl body

- **决策**：crawl_hint 非空时，作为 `prompt` 字段传入 POST /v1/crawl 请求体，引导 Firecrawl AI 爬虫聚焦内容。crawl_hint 为空时不传 prompt。
- **原因**：满足 raw.md 需求 3"crawl_hint 作为 Firecrawl prompt 传入"。D1 调研确认 REST API 文档支持 prompt（V-005-REST 需实测确认）。
- **降级**：若 V-005-REST 实测发现 REST API 不支持 prompt，降级为 include_paths 路径过滤或 crawl_hint 仅作日志。

### D-003：手动轮询，间隔 5s，总超时 120s

- **决策**：POST /v1/crawl 返回 job_id 后，每 5 秒 GET /v1/crawl/{id} 查询状态，总超时 120s。超时后返回 ("","") 失败。
- **原因**：D1 调研（research.md T4）确认 SDK crawl_url 无显式超时保护。手动轮询可控制总超时，避免无限等待。
- **备选**：SDK crawl_url（poll_interval=2s）— 不选，因无超时保护且不支持 prompt。

### D-004：多页结果按 url 字典序拼接为单快照

- **决策**：crawl 返回的 `List[document]` 按 `document.url` 字典序排序，markdown 用 `\n\n---\nsource: {url}\n\n` 分隔拼接，html 用 `\n<!-- {url} -->\n` 分隔拼接。
- **原因**：R1-Q2 决策合并单快照；字典序确保拼接确定性（V-002）；分隔标记含 url 确保可追溯（V-003）。

### D-005：清理历史快照管理命令

- **决策**：新增 Django management command `clear_snapshots`，删除指定项目（或全部）的 DataSnapshot 记录 + 关联文件。
- **原因**：R1-Q6 决策清理历史快照，避免 Firecrawl markdown 与 html2text 格式不连续导致虚假 diff。
- **风险**：与不变量 10（DataSnapshot append-only）冲突，但 DB 触发器尚未实现（Evidence Gap），当前 DELETE 可行。

## 4. 备选方案

### 4.1 SDK crawl_url + 不传 prompt

- **核心**：用 firecrawl-py SDK crawl_url（同步），crawl_hint 不传 Firecrawl 仅作日志
- **不选原因**：不满足 raw.md 需求 3（crawl_hint 作为 prompt）；SDK crawl_url 无超时保护

### 4.2 scrape 单页 + extract prompt

- **核心**：用 scrape API 单页抓取，crawl_hint 作为 extract 的 prompt 做结构化提取
- **不选原因**：单页抓取无法覆盖子页（raw.md 需求 2 要求爬取所有子网页）

### 4.3 SDK crawl_url + include_paths 替代 prompt

- **核心**：用 SDK crawl_url，crawl_hint 转化为 include_paths 路径模式
- **不选原因**：include_paths 需用户填路径模式（如 `/pricing`），不如自然语言 prompt 友好；且转化逻辑复杂

## 5. 与现有系统的对齐

### 5.1 契约兼容性声明

| 模块 | 变更类型 | 不变量影响 | 兼容性 | 组件页引用 |
|---|---|---|---|---|
| intelligence-models | 扩展 | 不变量1扩展：competitor_urls 单项新增可选 crawl_hint | **兼容**（JSONField，无需迁移） | `intelligence-models.md#data-contract` Invariant 1 |
| intelligence-models | 不变 | 不变量9：DataSnapshot 只存路径 | 兼容（保留 raw_html_path + clean_md_path） | `intelligence-models.md#data-contract` Invariant 9 |
| intelligence-scheduler | **破坏性变更** | 不变量3修订：httpx+playwright → Firecrawl REST API | **破坏性**（采集方式变更） | `intelligence-scheduler.md#service-contract` Invariant 3 |
| intelligence-scheduler | 不变 | 不变量4：采集失败写空快照 | 兼容（Firecrawl 失败同样返回 ("","")） | `intelligence-scheduler.md#service-contract` Invariant 4 |
| intelligence-scheduler | 不变 | 不变量5：不写 IntelligenceFeed | 兼容（006 范围止步 DataSnapshot） | `intelligence-scheduler.md#service-contract` Invariant 5 |
| intelligence-scheduler | 不变 | 不变量6：空 URL 跳过 | 兼容 | `intelligence-scheduler.md#service-contract` Invariant 6 |
| intelligence-api | 扩展 | 不变量1-5 均不变 | **兼容**（API 接口不变，serializer 放宽校验） | `intelligence-api.md#api-contract` Invariants 1-5 |
| intelligence-crawler | 新模块 | 无现有不变量 | **CONTEXT GAP**（无组件页） | 无 |

### 5.2 ADR 合规声明

| ADR | 合规状态 | 说明 |
|---|---|---|
| ADR-001（Vue SPA + Django split-monolith） | **遵守** | 006 前端改动在 Vue SPA 内（ProjectForm.vue），后端改动在 Django 内（crawler_service 等），不引入新服务/基础设施。不变量1（产品主入口不回退 Django Admin）遵守。不变量2（前后端职责分离）遵守。 |

### 5.3 跨模块影响确认

- **crawler_service 重写 → scheduler_service 调用变更**：scheduler_service.py L39 `fetch_and_clean(url)` → `fetch_with_firecrawl(url, crawl_hint)`，从 `item` 取 `crawl_hint`
- **serializer 放宽 → 前端表单配合**：serializers.py validate_competitor_urls 允许 crawl_hint 可选；前端 ProjectForm.vue 新增 crawl_hint 输入并在 onSubmit 传入
- **依赖移除 → 测试重写**：test_crawler_service.py（6 用例 mock httpx/playwright）重写为 mock requests；test_e2e_crawl.py（真实网络）改用 Firecrawl API
- **与 004（LLM）合并风险**：004 改 settings.py（LLM 配置），006 也改 settings.py（Firecrawl 配置），合并时需手动整合
- **与 005（飞书）无冲突**：模块隔离

### 5.4 不变量修订记录

**修订-6**：intelligence-scheduler 不变量3
- 原文：httpx 优先采集，clean_markdown < 3 行时降级 Playwright
- 修订为：采集统一使用 Firecrawl 云端 crawl API（requests 直调 REST API），不再使用 httpx/Playwright/BeautifulSoup/html2text；crawl_hint 非空时作为 prompt 传入

**修订-7**：intelligence-models 不变量1
- 原文：competitor_urls 必须是对象数组，单项至少含 title 与 url
- 修订为：competitor_urls 必须是对象数组，单项至少含 title 与 url，可选含 crawl_hint（爬虫建议，作为 Firecrawl prompt）

## 6. 风险与验证清单

| ID | 风险/假设 | 方法 | 成功信号 | Owner | 截止 | 触发动作 |
|---|---|---|---|---|---|---|
| V-005-REST | REST API crawl prompt 支持性（**阻塞**） | 用真实 API key curl POST /v1/crawl 带 prompt | API 接受 prompt 且爬取聚焦 | DEV | I2 前 | 不成立→降级 include_paths |
| V-001-T | crawl 轮询 120s 超时是否够 | 2-3 个竞品 URL 实测 crawl 耗时 | 全部 120s 内完成 | DEV | I2 中 | 不成立→增大至 300s |
| V-002 | 拼接确定性（同 URL 两次 crawl 拼接一致） | 同 URL 连续 crawl 两次对比 clean_md | 两次一致 | DEV | I2 中 | 不成立→固定字典序 |
| V-003-M | 分隔标记对 004 LLM 链路的影响 | 含标记的 clean_md 走 LLM 链路 | LLM 输出正常 | DEV | I2 后 | 不成立→调标记格式 |
| V-009 | Firecrawl 额度消耗（limit×竞品×日级） | 查定价 + 估算日消耗 | 在可接受范围 | DEV/用户 | I2 前 | 不成立→减 limit/降频 |
| V-010 | clear_snapshots 与 append-only 触发器冲突 | 确认触发器未实现；未来实现时清理命令需特殊处理 | 当前可 DELETE | DEV | I2 中 | 触发器实现后→用 raw SQL 绕过 |

## 7. Context Gaps

- `CONTEXT GAP`：`project/components/` 无 intelligence-crawler 模块页 → crawler_service 是 006 的核心重写对象，但项目知识库中无其契约/不变量记录 → 补齐路径：I2 实现后 merge-back 时新增 `intelligence-crawler.md` 模块页
- `CONTEXT GAP`：`project/components/` 无 frontend-console 模块页（components/index.md 列了但无链接） → 006 改动 ProjectForm.vue 但无前端契约参考 → 补齐路径：merge-back 时补齐
- `CONTEXT GAP`：`project/memory/glossary.md` competitor_urls 定义为"每项必须含 title 与 url"，未含 crawl_hint → 补齐路径：merge-back 时更新 glossary

> DoD 声明：因上述 CONTEXT GAP 存在，"与现有系统的对齐已完成"**未完全通过**。intelligence-crawler 和 frontend-console 的契约对齐基于 Explore 代码调查（非组件页 SSOT），在 merge-back 时需补齐模块页。

## 8. 迭代记录

- 2026-07-08：初始版本。基于 solution.md + research.md + 3 组件页全文 + ADR-001 全文产出。核心决策：requests 直调 REST API 传 prompt（D-001/D-002），手动轮询 120s 超时（D-003），合并单快照按 url 排序（D-004），清理历史快照命令（D-005）。识别 2 个 CONTEXT GAP（intelligence-crawler / frontend-console 无组件页）。V-005-REST 为阻塞性验证项。
