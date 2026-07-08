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
