---
title: Firecrawl 爬虫接入方案决策（Solutionate）
status: draft
---

> 目的：把"推荐决策 + 备选方案对比 + 决策依据 + 验证清单"落到一份可评审文档里，作为后续 `prd.md` 与实现的唯一决策入口。

## 0. 基本信息

- 需求标识（分支）：`006-firecrawl-crawler`
- 作者 / 参与评审：AI + 用户
- 状态：draft
- 最后更新：2026-07-08
- 关联链接：raw.md（4 点需求 + R1-Q1~Q6 澄清记录）

## 1. 结论摘要

- **一句话目标**：将采集层从 httpx+playwright+BeautifulSoup+html2text 迁移到 Firecrawl 云端 crawl API，支持 AI 爬虫建议（crawl_hint）+ 多页爬取，输出干净 html/md 直接落盘。
- **In/Out 边界**：In = 后端 crawler_service 重写 + serializer 放宽 + 配置/依赖替换 + 前端表单加 crawl_hint + 清理历史快照命令；Out = 调度器逻辑/数据模型 schema/LLM 链路/飞书推送/diff 熔断逻辑。
- **推荐方案**：Firecrawl crawl 多页 + crawl_hint prompt + 合并单快照——每个竞品 URL 调 Firecrawl crawl API 爬取子页，crawl_hint 非空时作为 prompt 传入，多页结果按 URL 排序拼接为一个快照，保留 raw_html_path + clean_md_path 双字段落盘。
- **优先验证点**：V-005（Firecrawl crawl API 是否支持 prompt 参数）、V-001（异步轮询超时策略）、V-006（crawl 子页范围 limit 控制）。

## 2. 推荐方案

- **方案名**：Firecrawl crawl 多页 + crawl_hint prompt + 合并单快照

- **主流程（6 步）**：
  1. `scheduler_service.run_scan()` 遍历 `competitor_urls`，每项取 `url` + `crawl_hint`（可选）
  2. `crawler_service.fetch_with_firecrawl(url, crawl_hint)` 调用 firecrawl-py 的 crawl API；crawl_hint 非空时作为 prompt 参数传入
  3. 轮询 crawl job 直到完成（轮询间隔 5s，超时 120s → 失败）
  4. 收集所有子页的 markdown + html，按子页 URL 字典序排序，分别拼接为一个 clean_md 和一个 raw_html
  5. `file_storage.save_raw_html()` / `file_storage.save_clean_md()` 落盘（逻辑不变）
  6. `DataSnapshot.objects.create()` 入库（一 URL 一快照，source_url=竞品 URL）；失败返回 ("","") → scheduler 记 ERROR

- **关键边界/取舍（5 条）**：
  1. **crawl 多页而非 scrape 单页**——raw.md 需求 2 明确要求"爬取一个网页中的所有子网页"（如主页+定价页）
  2. **合并单快照而非每子页一快照**——保持现有"一 URL 一快照"架构，diff 熔断与 LLM 情报生成均基于整体 clean_md，改动最小
  3. **crawl_hint 可选**——兼容现有 `{url,title}` 数据，为空时不传 prompt，Firecrawl crawl 爬取默认子页
  4. **清理历史快照**——Firecrawl markdown 格式与 html2text 不同，删除旧格式快照避免虚假 diff，首次 Firecrawl 采集作为新基线
  5. **两字段都保留（raw_html_path + clean_md_path）**——不改 DataSnapshot 模型 schema，raw_html 可用于调试

- **为什么选它（3 条）**：
  1. 完整满足 raw.md 需求 1-4：移除 httpx/playwright/BS/html2text → Firecrawl 云 API；AI 爬虫能力；crawl_hint 配置；简化流程（直接用 Firecrawl 输出）——证据：`raw.md` 需求 1-4
  2. 改动最小：不改数据模型 schema（JSONField 兼容 crawl_hint）、不改 file_storage、不改 scheduler、不改 diff 熔断逻辑——证据：Explore 报告 003 代码结构
  3. 兼容现有数据：crawl_hint 可选，旧项目 `{url,title}` 无需迁移——证据：R1-Q3 澄清

## 3. 备选方案

### 3.1 备选方案：scrape 单页 + crawl_hint 作为 AI 提取 prompt

- **核心机制**：用 Firecrawl scrape API 抓取单个 URL，crawl_hint 作为 scrape 的 prompt 参数指导 AI 提取重点内容
- **主流程**：scheduler 取 url+crawl_hint → crawler_service 调 scrape API（同步）→ 返回单页 md+html → 落盘 → DataSnapshot 入库
- **边界与取舍**：同步调用无需轮询；只覆盖单页内容；crawl_hint 作为 AI 提取 prompt 明确支持
- **适用前提**：只需单页内容（如只看主页）；需要 scrape 的 AI 提取能力
- **不选原因**：raw.md 需求 2 明确要求"爬取所有子网页"（主页+定价页+功能页），scrape 只覆盖单页，无法满足多页需求

### 3.2 备选方案：crawl 多页 + 每子页一快照

- **核心机制**：crawl 多页但每个子页单独存一个 DataSnapshot（source_url=子页 URL），diff 逐页对比
- **边界与取舍**：粒度细，能定位具体哪个子页变化；但快照数量倍增，diff 熔断逻辑需从"单 diff"改为"任一子页 diff 非空即触发"
- **适用前提**：需要精确定位变化子页；接受 diff 熔断逻辑重构
- **不选原因**：需重构 diff 熔断 + LLM 情报生成逻辑（当前基于整体 clean_md），改动面大且与 004 LLM 分支冲突风险高——证据：R1-Q2 澄清

### 3.3 备选方案：只用 clean_md_path，移除 raw_html_path

- **核心机制**：Firecrawl 已输出干净数据，移除 DataSnapshot.raw_html_path 字段，只存 clean_md_path
- **边界与取舍**：简化存储；但需 DB 迁移（删字段）；失去 raw_html 调试能力
- **适用前提**：确定不需要原始 HTML；接受 DB schema 变更
- **不选原因**：需改模型 schema（迁移文件），与 004/005 并行分支冲突风险高；raw_html 用于调试有价值——证据：R1-Q4 澄清

## 4. 决策依据（证据入口清单）

- `raw.md` 需求 1：爬虫技术栈迁移 Playwright → Firecrawl 云端 API
- `raw.md` 需求 2：Firecrawl AI 爬虫能力，爬取所有子网页
- `raw.md` 需求 3：competitor_urls 新增 crawl_hint（爬虫建议）字段
- `raw.md` 需求 4：简化采集流程，直接用 Firecrawl 输出 html/md
- `raw.md` R1-Q1：Firecrawl 调用模式 = crawl 多页
- `raw.md` R1-Q2：多页快照粒度 = 合并单快照
- `raw.md` R1-Q3：crawl_hint 必填性 = 可选，空不传 prompt
- `raw.md` R1-Q4：快照存储映射 = 两字段都保留
- `raw.md` R1-Q5：前端范围 = 含前端改动
- `raw.md` R1-Q6：diff 基线 = 清理历史快照
- Explore 报告（后端）：`backend/apps/intelligence/services/crawler_service.py`（85 行，整文件替换）、`scheduler_service.py` L39 调用点、`serializers.py` L37-47 校验、`base.txt` L4-7 依赖、`settings.py` 配置
- Explore 报告（前端）：`frontend/src/components/projects/ProjectForm.vue`（CompetitorFormRow 接口 + 表单 + 提交逻辑）、`frontend/src/api/projects.ts`（CompetitorInput 类型）
- 项目知识库：`.aisdlc/project/components/index.md`（4 模块地图）、`.aisdlc/project/memory/glossary.md`（competitor_urls 定义）

## 5. 验证清单（V-xxx，可执行）

- **V-001**：crawl 异步轮询超时策略
  - 风险/假设：Firecrawl crawl 是异步任务，轮询间隔过长拖慢采集、过短浪费 API 调用；超时过短导致大站点采不全
  - 方法：用 2-3 个竞品 URL 实测 crawl 耗时；测试轮询间隔 5s + 超时 120s 是否够用
  - 成功/失败信号：所有测试 URL 在 120s 内完成 → 成立；超时 → 不成立，需调大超时或改用 webhook 回调
  - Owner：DEV
  - 截止：I2 实现前
  - 触发动作：不成立则调整为 webhook 回调模式或增大超时至 300s

- **V-002**：crawl 多页合并拼接确定性
  - 风险/假设：多页拼接顺序不确定会导致 diff 误报（相同内容不同顺序 = diff 非空）
  - 方法：对同一 URL 连续 crawl 两次，对比拼接后 clean_md 是否一致
  - 成功/失败信号：两次拼接结果一致 → 成立；不一致 → 不成立，需固定排序
  - Owner：DEV
  - 截止：I2 实现中
  - 触发动作：不成立则在拼接前按子页 URL 字典序排序

- **V-003**：拼接内容含子页来源标记
  - 风险/假设：拼接后无法区分哪段内容来自哪个子页，影响 LLM 情报生成的证据定位
  - 方法：在拼接时插入分隔标记（如 `\n\n---\nsource: {sub_url}\n\n`），验证 LLM 能否引用
  - 成功/失败信号：LLM 输出证据 diff 可定位子页 → 成立；无法定位 → 不成立
  - Owner：DEV
  - 截止：I2 实现后验证
  - 触发动作：不成立则调整分隔标记格式

- **V-004**：前端 crawl_hint 输入框改动
  - 风险/假设：前端 ProjectForm.vue 改动可能遗漏回填/提交/校验环节
  - 方法：按 Explore 报告改动 3 文件 8 处；手动测试新建/编辑项目时 crawl_hint 的保存与回显
  - 成功/失败信号：crawl_hint 在新建、编辑、回填三个场景均正确 → 成立；任一场景丢失 → 不成立
  - Owner：DEV
  - 截止：I2 实现中
  - 触发动作：不成立则排查 mergeCompetitors / onSubmit / ProjectFormPage 回填逻辑

- **V-005**：Firecrawl crawl API 是否支持 prompt 参数（**最高优先**）
  - 风险/假设：推荐方案依赖 crawl_hint 作为 crawl 的 prompt 传入；但 Firecrawl crawl API 可能不支持 prompt（仅 scrape 支持），需验证
  - 方法：查阅 Firecrawl 官方文档 + 用 firecrawl-py 实测 crawl_url 是否接受 prompt 参数；若不支持，测试 includes/excludes 路径过滤是否能替代
  - 成功/失败信号：crawl 支持 prompt → 成立；不支持但 includes/excludes 可替代 → 成立（方案微调）；均不可行 → 不成立，需改用 scrape+prompt 或 crawl 后 LLM 筛选
  - Owner：DEV
  - 截止：I2 实现前（阻塞实现）
  - 触发动作：不成立则切换备选方案 3.1（scrape+prompt）或混合方案

- **V-006**：crawl 子页范围控制（limit 参数）
  - 风险/假设：crawl 默认可能爬取过多子页（整站），导致 API 耗时长、内容过多、token 超限
  - 方法：测试 crawl 的 limit 参数（如 limit=10）；验证 crawl_hint 含"定价"时是否能限定到 /pricing 等路径
  - 成功/失败信号：limit 可控且 crawl_hint 能缩小范围 → 成立；无法控制 → 不成立，需后处理裁剪
  - Owner：DEV
  - 截止：I2 实现前
  - 触发动作：不成立则在 crawler_service 中对返回结果按相关性裁剪

- **V-007**：firecrawl-py SDK 兼容性与 API 稳定性
  - 风险/假设：firecrawl-py 可能有版本变更、API 签名不稳定、或 crawl 返回结构与预期不符
  - 方法：安装 firecrawl-py 最新版，用真实 API key 调通 crawl；确认返回字段含 markdown + html
  - 成功/失败信号：SDK 可用且返回 markdown+html → 成立；字段缺失或不稳定 → 不成立
  - Owner：DEV
  - 截止：I2 实现前
  - 触发动作：不成立则改用直接 httpx 调 Firecrawl REST API（不依赖 SDK）

- **V-008**：API Key 配置与 dotenv 加载
  - 风险/假设：settings.py 当前无 env 加载机制；引入 python-dotenv 需确保 .env 不入库
  - 方法：创建 .env.example 模板；settings.py 加 dotenv 加载；确认 .gitignore 含 .env
  - 成功/失败信号：FIRECRAWL_API_KEY 从环境变量正确读取 → 成立；读取失败 → 不成立
  - Owner：DEV
  - 截止：I2 实现中
  - 触发动作：不成立则检查 dotenv 路径与 .gitignore

## 6. 迭代记录

- 2026-07-08：初始版本。基于 raw.md 4 点需求 + R1-Q1~Q6 六轮澄清 + 后端/前端 Explore 报告产出。核心决策：crawl 多页 + 合并单快照 + crawl_hint 可选 + 两字段保留 + 含前端 + 清理历史快照。识别 V-005 为最高优先验证项（crawl API prompt 支持性）。

## 7. Impact Analysis

### 7.1 受影响模块

| 模块 | 影响类型 | 关键不变量 | stale? |
|------|----------|-----------|--------|
| intelligence-crawler（crawler_service.py） | **重写** | 不变量 7 修订（httpx+playwright → Firecrawl） | yes（无模块页） |
| intelligence-scheduler（scheduler_service.py） | 修改调用 | 调用签名变更：fetch_and_clean(url) → fetch_with_firecrawl(url, crawl_hint) | no |
| intelligence-api（serializers.py） | 修改校验 | 不变量 10 扩展：competitor_urls 每项 {url,title} → {url,title,crawl_hint?} | no |
| intelligence-models（models.py） | 无 schema 改动 | JSONField 兼容 crawl_hint，无需迁移 | no |
| frontend-console（ProjectForm.vue） | 新增输入 | competitor_urls 编辑表单加 crawl_hint | no |
| config（settings.py） | 新增配置 | FIRECRAWL_API_KEY + dotenv 加载 | no |
| dependencies（base.txt） | 依赖替换 | 移除 httpx/playwright/BS/html2text，新增 firecrawl-py | no |

### 7.2 需遵守的不变量（含修订）

**修订-6**：不变量 7 修订
- 原文（Spec 001）：httpx 优先，Playwright 仅对 SPA 按需降级，不得默认全量 Playwright
- 修订为：采集统一使用 Firecrawl 云端 crawl API，不再使用 httpx/Playwright/BeautifulSoup/html2text；crawl_hint 可选作为 prompt 传入
- 来源：raw.md 需求 1 + R1-Q1

**修订-7**：不变量 10 扩展
- 原文（Spec 001）：competitor_urls 必须为 JSON 数组，每项 {"url":"...","title":"..."}，title 标识内容来源
- 修订为：competitor_urls 必须为 JSON 数组，每项 {"url":"...","title":"...","crawl_hint":"..."}，title 标识内容来源，crawl_hint 为可选的爬虫建议（作为 Firecrawl prompt）
- 来源：raw.md 需求 3 + R1-Q3

**不受影响的不变量**：1（append-only）、2（两次独立 LLM 调用）、3（仅 diff 非空触发 LLM）、4（4 字段输出）、5（has_change 推飞书）、6（收件箱仅 CHANGED）、8（调度限日级）、9（self_product_doc 关联）、11（Negative Few-Shot 上限 5）、12（refined_rules 占位）、13（证据 diff 嵌入 change_summary）

### 7.3 跨模块影响

- **crawler_service 重写 → scheduler_service 调用变更**：scheduler_service.py L39 `fetch_and_clean(url)` 需改为 `fetch_with_firecrawl(url, crawl_hint)`，并从 `item` 中取 `crawl_hint` 字段
- **serializer 放宽 → 前端表单配合**：serializers.py validate_competitor_urls 允许 crawl_hint 可选；前端 ProjectForm.vue 需新增 crawl_hint 输入框并在提交时传入 competitor_urls
- **依赖移除 → 测试重写**：test_crawler_service.py（6 个用例 mock httpx/playwright）需全部重写为 mock firecrawl-py；test_e2e_crawl.py（真实网络测试）需改用 Firecrawl API
- **与 004（LLM）分支的合并风险**：004 改 settings.py（LLM 配置），006 也改 settings.py（Firecrawl 配置），合并时需手动整合两者配置块
- **与 005（飞书）分支无冲突**：005 改飞书推送，006 改采集，模块隔离

### 7.4 Context Gaps

- `CONTEXT GAP`：`.aisdlc/project/components/` 无 crawler_service 模块页（components/index.md 只列了 frontend-console / intelligence-api / intelligence-models / intelligence-scheduler，未含 crawler） → 建议动作：I2 实现后补 Delta Discover，新增 intelligence-crawler 模块页
- `CONTEXT GAP`：`.aisdlc/project/memory/glossary.md` competitor_urls 定义为"每项必须含 title 与 url"，未含 crawl_hint → 建议动作：merge-back 时更新 glossary

## 8. Mini-PRD

- **MVP 范围**：
  - In：
    - crawler_service.py 整文件重写为 Firecrawl crawl API 调用（crawl_hint 可选 prompt、异步轮询、多页拼接）
    - scheduler_service.py 调用点修改（传 crawl_hint）
    - serializers.py validate_competitor_urls 放宽（允许 crawl_hint 可选）
    - settings.py 新增 FIRECRAWL_API_KEY + python-dotenv 加载
    - base.txt 移除 httpx/playwright/beautifulsoup4/html2text，新增 firecrawl-py
    - .env.example 新增 FIRECRAWL_API_KEY 模板
    - ProjectForm.vue + projects.ts + ProjectFormPage.vue 新增 crawl_hint 输入框
    - 清理历史快照管理命令（django management command）
    - 测试重写（crawler_service 单测 + e2e）
  - Out：
    - 数据模型 schema 变更（JSONField 兼容，无需迁移）
    - diff 熔断逻辑变更（基于合并后 clean_md，逻辑不变）
    - LLM 链路变更（004 负责）
    - 飞书推送变更（005 负责）
    - 调度器变更（scheduler.py 不变）

- **验收标准（AC）**：
  1. AC-001：crawler_service 调用 Firecrawl crawl API，返回拼接后的 (raw_html, clean_md)；crawl_hint 非空时作为 prompt 传入
  2. AC-002：crawl_hint 为空时 Firecrawl crawl 不传 prompt，正常爬取默认子页
  3. AC-003：crawl 异步轮询在 120s 内完成，超时返回 ("","") 并记 ERROR
  4. AC-004：多页结果按子页 URL 字典序拼接为一个 clean_md + 一个 raw_html
  5. AC-005：DataSnapshot 一 URL 一快照，raw_html_path + clean_md_path 双字段落盘
  6. AC-006：competitor_urls 每项支持可选 crawl_hint 字段，serializer 校验通过
  7. AC-007：前端 ProjectForm 新增 crawl_hint 输入框，新建/编辑/回填均正确
  8. AC-008：管理命令 `python manage.py clear_snapshots` 可清理历史快照
  9. AC-009：httpx/playwright/beautifulsoup4/html2text 依赖从 base.txt 移除，firecrawl-py 新增
  10. AC-010：FIRECRAWL_API_KEY 从环境变量读取，.env.example 提供模板

- **交互变化结论**：有但简单——前端竞品编辑表单新增 1 个 crawl_hint 输入框（textarea），模式与现有 supplement_doc_content 一致，无新增页面/路由/状态分支

- **影响面**：
  - 后端：crawler_service.py（重写）、scheduler_service.py（L31-39 修改）、serializers.py（L37-47 修改）、settings.py（新增配置）、base.txt（依赖替换）
  - 前端：ProjectForm.vue（8 处小改）、projects.ts（类型扩展）、ProjectFormPage.vue（初始值+回填）
  - 管理：新增 clear_snapshots 管理命令
  - 不变量：修订-6（不变量 7）、修订-7（不变量 10）
