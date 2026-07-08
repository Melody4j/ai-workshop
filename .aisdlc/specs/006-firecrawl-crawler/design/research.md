---
title: D1 Research — Firecrawl 爬虫接入技术调研
status: draft
---

## 基本信息

- Date：2026-07-08
- Feature：Firecrawl 爬虫接入（替换 Playwright）
- Spec（分支 / ID）：006-firecrawl-crawler
- 作者：AI + 用户

## TL;DR

- **最大风险**：firecrawl-py SDK 的 `crawl_url` 方法**不支持 prompt 参数**（`_validate_kwargs` 白名单不含 prompt），与 raw.md 需求 3"crawl_hint 作为 Firecrawl prompt 传入"存在冲突。REST API 文档（WebSearch）称 crawl 支持 prompt，但未实测。
- **推荐方向**：优先用 `requests` 直调 Firecrawl REST API（POST /v1/crawl 传 prompt + 轮询 GET /v1/crawl/{id}），绕过 SDK 限制；若 REST API 实测不支持 prompt，降级为 `include_paths` 路径过滤或 crawl_hint 仅作日志。
- crawl 返回 `List[V1FirecrawlDocument]`，每页含 `url` + `markdown` + `html`，按 url 排序拼接后可映射到 `raw_html_path` + `clean_md_path`。
- SDK `crawl_url` 同步轮询（`poll_interval=2s`），无显式超时 → 需加超时保护。

## Research Tasks Completed

### T1. Firecrawl crawl API 是否支持 prompt 参数（V-005，最高优先）

**Task**：针对 006 推荐方案依赖 crawl_hint 作为 crawl prompt 传入，研究 Firecrawl crawl API（SDK + REST）是否支持 prompt。

**研究发现**：
- firecrawl-py 4.31.0 的 `V1FirecrawlApp.crawl_url` 方法签名**不含 prompt 参数**
- `_validate_kwargs` 白名单中 crawl_url 允许的 kwargs：`include_paths, exclude_paths, max_depth, max_discovery_depth, limit, allow_backward_links, allow_external_links, ignore_sitemap, scrape_options, webhook, deduplicate_similar_urls, ignore_query_parameters, regex_on_full_url, integration` — **不含 prompt**
- prompt 仅出现在 `extract` 方法的 kwargs 白名单中（`{"prompt", "schema", "system_prompt", ...}`）
- `V1ScrapeOptions` 字段不含 extract/json_options（无法通过 scrapeOptions 间接传 prompt）
- WebSearch 返回的 Firecrawl REST API 文档称 crawl 支持 `prompt`（string, optional）："A natural language prompt that describes what you want to extract/find. This guides the crawler to focus on specific content or page types." — 但此为搜索结果摘要，**未用真实 API key 实测**
- SDK 内部 `crawl_params.update(kwargs)` 会透传 kwargs，但 `_validate_kwargs` 在前拦截

**Decision**：推荐用 `requests` 直调 Firecrawl REST API（POST /v1/crawl 传 prompt + GET /v1/crawl/{id} 轮询），绕过 SDK crawl_url 的 prompt 限制。若 REST API 实测不支持 prompt，降级为 include_paths 路径过滤。

**Rationale**：
- 用户需求（raw.md 需求 3）明确要求 crawl_hint 作为 prompt 传入
- SDK crawl_url 确定不支持 prompt（源码证据确凿）
- REST API 文档称支持 prompt（虽未实测，但 SDK 落后于 API 是常见情况）
- `requests` 是 firecrawl-py 的已有依赖，不引入新依赖
- raw.md 需求 1"移除 httpx"指移除 httpx 爬虫流程，用 requests 调 API 不违反此约束

**Alternatives considered**：
- 方案 A：用 SDK crawl_url，不传 prompt，crawl_hint 仅作日志 — 不选，因不满足用户需求 3
- 方案 B：用 SDK crawl_url + include_paths 替代 prompt — 不选，因 include_paths 需用户填路径模式（如 `/pricing`），不如自然语言 prompt 友好；可作为降级方案
- 方案 C：修改 SDK _validate_kwargs 白名单加入 prompt — 不选，因 hack 第三方 SDK 不可维护

**Evidence**：
- firecrawl-py 4.31.0 源码：`V1FirecrawlApp._validate_kwargs` 白名单（本地安装后 `inspect.getsource` 确认）
- `V1FirecrawlApp.crawl_url` 签名（本地安装后 `inspect.signature` 确认）
- WebSearch："Firecrawl v1 crawl API body parameters prompt scrapeOptions formats documentation"

### T2. crawl 子页范围控制（V-006）

**Task**：查找 Firecrawl crawl API 中子页范围控制的最佳实践（limit / include_paths / max_depth）。

**研究发现**：
- `crawl_url` 支持 `limit`（最大页数，SDK 无默认值，REST API 文档称默认 10）
- `crawl_url` 支持 `include_paths` / `exclude_paths`（URL 路径模式过滤，如 `["*/pricing*"]`）
- `crawl_url` 支持 `max_depth`（爬取深度）、`max_discovery_depth`（发现新 URL 深度）
- `crawl_url` 支持 `ignore_sitemap`（跳过 sitemap.xml）、`crawl_entire_domain`（爬整个域名）

**Decision**：limit 设为可配置（默认 10），include_paths 可选（用户可通过 crawl_hint 暗示路径，系统尝试转化为 include_paths 作为补充）。max_depth 不设（让 Firecrawl 默认）。

**Rationale**：
- limit=10 平衡覆盖度与 API 耗时/费用
- include_paths 可选，用于降级方案（当 prompt 不可用时）
- 不限 max_depth，让 Firecrawl 智能决定爬取范围

**Alternatives considered**：
- 不设 limit（无限爬）— 不选，可能爬整站导致超时/超费
- limit=1（退化为单页）— 不选，失去 crawl 多页意义

**Evidence**：
- firecrawl-py 4.31.0 `crawl_url` 签名（本地 inspect 确认）
- WebSearch Firecrawl crawl API 文档

### T3. firecrawl-py SDK 兼容性与 API 稳定性（V-007）

**Task**：查找 firecrawl-py SDK 的版本、API 签名、返回结构，验证是否可用于 006 实现。

**研究发现**：
- firecrawl-py 4.31.0 安装成功（Python 3.12，macOS arm64）
- 主类为 `V1FirecrawlApp`（非旧版 `FirecrawlApp`，旧版仅含 `parse` 方法）
- `crawl_url(url, ...)` → 同步返回 `V1CrawlStatusResponse`
- `async_crawl_url(url, ...)` → 异步返回 `V1CrawlResponse`（含 job_id），配合 `check_crawl_status(id)` 轮询
- `V1CrawlStatusResponse` 字段：`success: bool`, `status: Literal['scraping','completed','failed','cancelled']`, `completed: int`, `total: int`, `data: List[V1FirecrawlDocument]`
- `V1FirecrawlDocument` 字段：`url`, `markdown`, `html`, `rawHtml`, `metadata`, `title`, `description`, `links`, `extract`, `screenshot`

**Decision**：SDK 可用，但因 crawl_url 不支持 prompt（T1），推荐用 requests 直调 REST API。SDK 的 `V1FirecrawlDocument` 结构定义了返回数据的契约（即使直调 REST API，返回结构应一致）。

**Rationale**：
- SDK 安装成功且 API 结构清晰
- V1FirecrawlDocument 含 markdown+html+url，满足拼接需求
- 但 SDK crawl_url 限制 prompt → 直调 REST API 更灵活
- SDK 的 Pydantic 模型可作为返回数据的类型参考

**Alternatives considered**：
- 纯用 SDK crawl_url — 不选，因不支持 prompt（T1）
- 不用 SDK，纯 requests + 手写 Pydantic 模型 — 可选，但 SDK 的模型可复用作类型参考

**Evidence**：
- 本地安装 firecrawl-py 4.31.0，`inspect.signature` + `model_fields` 确认
- pip 安装日志确认版本号

### T4. crawl 异步轮询策略（V-001）

**Task**：梳理 Firecrawl crawl 异步轮询机制与超时控制。

**研究发现**：
- SDK `crawl_url` 是同步方法：内部启动 crawl job → 轮询 `check_crawl_status` → 直到 status=completed/failed
- `poll_interval` 默认 2 秒（可配置）
- **无显式超时参数**：SDK crawl_url 会一直轮询直到 job 完成/失败，无总超时限制
- REST API 模式：POST /v1/crawl 返回 job_id → GET /v1/crawl/{id} 轮询 → 手动控制超时
- `V1CrawlStatusResponse.status` 含 `scraping`（进行中）、`completed`、`failed`、`cancelled`

**Decision**：用 requests 直调 REST API，手动轮询（间隔 5s，总超时 120s）。超时后取消 job（POST /v1/crawl/{id}/cancel）并返回失败。

**Rationale**：
- 手动轮询可控制总超时（SDK crawl_url 无超时保护，可能无限等待）
- 间隔 5s 平衡 API 调用频率与响应速度
- 超时 120s 覆盖 limit=10 的小型站点爬取
- 超时取消 job 避免浪费 API 额度

**Alternatives considered**：
- 用 SDK crawl_url（poll_interval=2s）+ threading.Timer 超时 — 不选，因线程超时不优雅且 SDK 不支持取消
- 用 SDK async_crawl_url + check_crawl_status 手动轮询 — 可选，但同样因 prompt 限制倾向直调 REST API

**Evidence**：
- firecrawl-py 4.31.0 `crawl_url` 源码（`poll_interval` 参数，无 timeout 参数）
- `V1CrawlStatusResponse.status` 枚举值
- WebSearch Firecrawl crawl API 文档（job_id + GET 轮询）

### T5. crawl 返回数据结构映射到 DataSnapshot

**Task**：梳理 crawl 返回的 `List[V1FirecrawlDocument]` 如何映射到 DataSnapshot 的 `raw_html_path` + `clean_md_path`。

**研究发现**：
- `V1CrawlStatusResponse.data` 是 `List[V1FirecrawlDocument]`
- 每个 V1FirecrawlDocument 含：`url`（子页 URL）、`markdown`（Firecrawl 生成的干净 MD）、`html`（Firecrawl 生成的干净 HTML）
- 多页需合并为单快照（R1-Q2 决策）

**Decision**：
- 按 `document.url` 字典序排序所有子页
- clean_md = `"\n\n---\nsource: {url}\n\n" + document.markdown` 拼接所有子页
- raw_html = `"\n<!-- {url} -->\n" + document.html` 拼接所有子页
- 分别通过 `file_storage.save_raw_html()` / `file_storage.save_clean_md()` 落盘
- 分隔标记含子页 URL，便于 LLM 情报生成时定位证据来源

**Rationale**：
- 按字典序排序确保拼接确定性（V-002）
- 分隔标记含 URL 确保可追溯（V-003）
- 保留 file_storage 逻辑不变，改动最小

**Alternatives considered**：
- 不加分隔标记，纯拼接 — 不选，因无法区分子页来源
- 按 Firecrawl 返回顺序拼接 — 不选，因返回顺序可能不确定

**Evidence**：
- `V1FirecrawlDocument.model_fields` 确认含 url + markdown + html
- R1-Q2 澄清（合并单快照）

### T6. crawl_hint 与 Firecrawl prompt 的映射方案

**Task**：梳理 crawl_hint（用户填写的爬虫建议）如何映射到 Firecrawl API 参数。

**研究发现**：
- SDK crawl_url 不支持 prompt（T1）
- REST API 文档称支持 prompt（未实测）
- include_paths 可做路径过滤（如 `["*/pricing*"]`）
- scrapeOptions.formats 可指定输出格式

**Decision**：
- 主路径：requests 直调 REST API，crawl_hint 作为 `prompt` 参数传入 POST /v1/crawl body
- 降级路径：若 REST API 实测不支持 prompt，crawl_hint 转化为 `include_paths`（简单关键词匹配，如"定价"→ `["*/pricing*"]`）
- 兜底路径：若转化不可行，crawl_hint 仅作日志，Firecrawl crawl 爬取默认子页

**Rationale**：
- 主路径满足用户需求 3（crawl_hint 作为 prompt）
- 降级路径保留 crawl_hint 的指导价值
- 兜底路径确保系统可用

**Alternatives considered**：
- crawl_hint 不传 Firecrawl，仅日志 — 不选，因不满足用户需求 3
- crawl_hint 用 scrape+extract prompt — 不选，因是单页提取不是多页 crawl

**Evidence**：
- T1 调研结论（SDK 不支持 prompt，REST API 文档称支持）
- raw.md 需求 3（crawl_hint 作为 Firecrawl prompt 传入）

## 风险与验证清单（未关闭项）

- **V-005-REST**：REST API crawl prompt 支持性实测（**阻塞实现**）
  - 风险/假设：REST API 文档称 crawl 支持 prompt，但 SDK 不支持；若 REST API 也不支持，推荐方案需调整
  - 方法：用真实 Firecrawl API key，curl POST /v1/crawl 带 prompt 参数，验证是否被接受 + 是否影响爬取范围
  - 成功/失败信号：REST API 接受 prompt 且爬取结果聚焦于 prompt 描述的内容 → 成立；不接受或无效果 → 不成立
  - Owner：DEV
  - 截止：I2 实现前
  - 触发动作：成立则用 requests 直调 REST API 传 prompt；不成立则降级为 include_paths 路径过滤（T6 降级路径）

- **V-001-TIMEOUT**：crawl 轮询超时实测
  - 风险/假设：limit=10 的站点 120s 内可能无法完成
  - 方法：用 2-3 个竞品 URL 实测 crawl 耗时
  - 成功/失败信号：所有测试 URL 在 120s 内完成 → 成立；超时 → 不成立
  - Owner：DEV
  - 截止：I2 实现中
  - 触发动作：不成立则增大超时至 300s 或减小 limit

- **V-003-MARKER**：分隔标记对 LLM 的影响
  - 风险/假设：`---\nsource: {url}` 分隔标记可能干扰 004 LLM 链路（降噪/diff/情报生成）
  - 方法：用含分隔标记的 clean_md 走一遍 LLM 链路，检查输出质量
  - 成功/失败信号：LLM 输出正常且能引用子页来源 → 成立；LLM 输出异常 → 不成立
  - Owner：DEV
  - 截止：I2 实现后验证
  - 触发动作：不成立则调整分隔标记格式或移除

- **V-009**：Firecrawl API 额度与费用
  - 风险/假设：crawl 按页计费，limit=10 × 多竞品 × 日级调度可能快速消耗额度
  - 方法：查阅 Firecrawl 定价；估算日级消耗
  - 成功/失败信号：日级消耗在可接受范围 → 成立；超出预算 → 不成立
  - Owner：DEV/用户
  - 截止：I2 实现前
  - 触发动作：不成立则减小 limit 或降低调度频率

## 迭代记录

- 2026-07-08：初始版本。安装 firecrawl-py 4.31.0 实测 SDK API 结构，WebSearch 查阅 REST API 文档。核心发现：SDK crawl_url 不支持 prompt（_validate_kwargs 白名单不含），与用户需求 3 冲突。推荐用 requests 直调 REST API 传 prompt，降级方案 include_paths。识别 V-005-REST 为阻塞性验证项（需真实 API key 实测）。
