# Spec 004: LLM 系统接入与竞品分析全流程

## 背景

Spec 001 设计了完整 LLM 链路（降噪 → diff 熔断 → 情报生成 → 入库），Spec 003 完成了采集与调度层（httpx + BeautifulSoup 规则去噪 + django-apscheduler 日级调度），但 LLM 层完全未实现。当前 DataSnapshot.clean_markdown 由 BeautifulSoup 规则去噪产出，IntelligenceFeed 的 4 个情报字段为空。本 Spec 补齐从"采集后原始 markdown"到"情报入库"的完整 LLM 链路。

## 功能需求

### 1. LLM 服务抽象层

- 仅支持 OpenAI 兼容 API（覆盖 OpenAI / DeepSeek / 通义 / Moonshot 等兼容接口）
- 配置来源：Django settings.py + .env 文件（环境变量管理密钥，不得硬编码）
- 配置项：api_key、base_url、model、temperature、max_tokens
- 情报生成使用 instructor + Pydantic 做结构化输出
- 降噪与 diff 判断使用普通文本补全
- 服务层可被 scheduler_service 与手动触发两种方式调用

### 2. Prompt 体系（文件系统存储，prompts/ 目录）

5 套 Prompt 模板：

1. 数据清洗 prompt：输入原始 markdown，输出降噪后的结构化 markdown（去广告/导航/模板噪音，保留核心内容语义）
2. diff 判断 prompt：输入文本 diff 片段 + self_product_doc 上下文，输出是否有实质变化（结构化 JSON：{has_meaningful_change: bool, reason: str}）
3. 自家产品系统 prompt：system role，注入 self_product_doc 作为分析锚定上下文
4. 竞品分析系统 prompt：user/task role，注入有意义的 diff 片段 + Negative Few-Shot，引导产出 4 字段分析
5. 输出结果 prompt：instructor Pydantic schema 约束，固定 4 字段输出格式

### 3. 混合 Diff 熔断（方案 C）

1. 文本 diff（difflib）：新 clean_markdown vs 上一条 clean_markdown
2. 文本 diff 为空 → 直接熔断（NO_CHANGE），零 LLM 调用
3. 文本 diff 非空 → 调用 LLM diff 判断 prompt，结合 self_product_doc 判断变化是否有分析价值
4. LLM 判断无意义 → 熔断（NO_CHANGE）
5. LLM 判断有意义 → 进入情报生成

### 4. 情报生成（单次 LLM 直出）

- 输入：有意义的 diff 片段 + self_product_doc + 最近 5 条 Negative Few-Shot（取 user_feedback = -1 的记录）
- 输出：4 字段（变化摘要 / 战略意图 / 行动建议 / 证据 diff）
- 使用 instructor + Pydantic 确保结构化输出
- Negative Few-Shot 注入上限 5 条，超过取最近 5 条

### 5. 分析结果产出入库

- 4 字段写入 IntelligenceFeed 表，job_status = CHANGED
- 渲染 HTML 网页报告 + MD 表格，落盘到文件系统
- html_report_path / md_table_path 写入 IntelligenceFeed

### 6. 与现有调度服务集成

- scheduler_service.run_scan() 在写入 DataSnapshot 后，串接 LLM 链路
- 首次爬取（无上一条快照）→ 跳过 diff，直接情报生成
- 采集失败 → job_status = ERROR_CRAWL，不进入 LLM 链路

## 与 Spec 001 不变量的变更（需 R1 裁决记录）

- Invariant #2 变更：原"降噪 LLM 与情报生成 LLM 是独立两次调用"→ 现增加 diff 判断 LLM 为第 3 次独立调用，三次不得合并
- Invariant #3 变更：原"情报生成 LLM 仅 diff 非空时触发"→ 现为"情报生成 LLM 仅在 LLM diff 判断为有意义变化时触发"

## 约束

- 降噪 LLM、diff 判断 LLM、情报生成 LLM 是 3 次独立调用，各自独立计费
- 情报输出固定 4 字段，不含价值度字段
- LLM 密钥必须从 .env 读取，不得硬编码或入库
- Prompt 模板文件存放在项目文件系统 prompts/ 目录，不存 DB
- 不引入消息队列，LLM 调用同步执行（在调度任务内串行完成）
