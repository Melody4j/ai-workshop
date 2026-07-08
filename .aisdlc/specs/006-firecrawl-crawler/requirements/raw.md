# Firecrawl 爬虫接入（替换 Playwright）

## 背景

当前系统（Spec 003 已实现）的爬虫方案为 httpx 优先 + Playwright（SPA 兜底）+ BeautifulSoup 去噪 + html2text 转 MD。后续系统计划部署到 Vercel，Playwright 在 Vercel 无服务器环境下不适用（需要浏览器二进制、长时运行受限）。因此需要将爬虫技术栈迁移到 Firecrawl。

## 需求

### 1. 爬虫技术栈迁移：Playwright → Firecrawl（云端 API）

- 移除现有的 httpx + Playwright + BeautifulSoup + html2text 多步流程
- 改为直接调用 Firecrawl 云端 API，使用其输出的 html/md 作为干净数据
- Firecrawl 部署方式：云端 API 接入（不自建、不本地部署）

### 2. 利用 Firecrawl 的 AI 爬虫能力

- Firecrawl 提供 AI 驱动的爬虫功能，能够根据给 AI 的建议（prompt）定向爬取目标内容
- 支持爬取一个网页中的所有子网页（如主页 + 定价页 + 功能页）

### 3. 任务配置调整：竞品 URL 结构变更

- 将 `competitor_urls` 中每项的"给 AI 的建议"字段改为"爬虫建议"（crawl hint）
- 示例：帮我爬取网页的主页数据和定价数据
- 该爬虫建议会作为 Firecrawl 的 prompt 传入，指导 AI 爬虫定向抓取

### 4. 简化采集流程

- 不再需要 httpx/playwright + BeautifulSoup + html2text 这种多步去噪流程
- 直接采用 Firecrawl 输出的 html/md 作为干净数据，存入快照

## 澄清记录

### R1-Q1：Firecrawl 调用模式
- 本轮结论：每个竞品 URL 使用 Firecrawl **crawl** API（多页爬取），从竞品 URL 出发爬取子页，crawl_hint 指导爬取范围。
- 新增约束：crawl 为异步任务（返回 job_id 需轮询）；返回多页数据需决定合并策略与快照粒度。
- 关键决策：选 crawl 多页而非 scrape 单页，依据 raw.md「爬取一个网页中的所有子网页」+「主页数据+定价数据」多页需求。
- 遗留歧义：crawl 异步轮询超时与多页合并策略 → V-001（轮询）、V-002（合并）

### R1-Q2：多页快照粒度
- 本轮结论：crawl 多页结果**合并为单个快照**。所有子页 markdown 拼接为一个 clean_md，存一个 DataSnapshot（source_url=竞品 URL）。
- 新增约束：保持一 URL 一快照不变；diff 熔断基于合并后整体 clean_md；拼接需有确定性顺序（按子页 URL 排序）。
- 关键决策：合并单快照 > 每子页一快照，因当前 diff 熔断与 LLM 情报生成均基于整体，改动最小。
- 遗留歧义：拼接顺序与子页来源标记 → V-003

### R1-Q3：crawl_hint 必填性
- 本轮结论：crawl_hint **可选**，为空时 Firecrawl crawl 不传 prompt，爬取默认子页。兼容现有 {url,title} 数据。
- 新增约束：serializer 校验 crawl_hint 可选；crawler_service 调用时 crawl_hint 非空才传 prompt 参数。
- 关键决策：可选 > 必填，因需兼容现有无 crawl_hint 的项目数据。
- 遗留歧义：无

### R1-Q4：快照存储映射
- 本轮结论：raw_html_path 和 clean_md_path **两字段都保留**。raw_html_path 存拼接的 Firecrawl html，clean_md_path 存拼接的 Firecrawl markdown。与当前结构一致，改动最小。
- 新增约束：Firecrawl crawl 返回多页，需按子页 URL 排序拼接 html 和 md 分别落盘；file_storage.py 落盘逻辑保留。
- 关键决策：两字段都保留 > 只用 clean_md，因 raw_html 可用于调试且不改模型。
- 遗留歧义：无

### R1-Q5：前端范围
- 本轮结论：006 **含前端改动**。competitor_urls 编辑表单需加 crawl_hint 输入框。
- 新增约束：需调查 frontend/ 中 competitor_urls 编辑组件并新增 crawl_hint 输入；API serializer 需放宽校验允许 crawl_hint。
- 关键决策：含前端 > 只改后端，因用户希望一站式完成 crawl_hint 的配置闭环。
- 遗留歧义：前端编辑组件具体位置与结构 → V-004

### R1-Q6：diff 基线
- 本轮结论：**清理历史快照**，从零开始。删除旧格式（html2text）快照，避免格式不连续导致虚假 diff。
- 新增约束：迁移时提供清理历史快照的方式（管理命令或脚本）；首次 Firecrawl 采集作为新基线，无 diff 不触发 LLM/飞书。
- 关键决策：清理历史 > 接受首次触发 > 重置基线逻辑，因单用户场景历史快照无需保留，最简单干净。
- 遗留歧义：清理方式（管理命令 vs 手动 SQL）→ V-005
