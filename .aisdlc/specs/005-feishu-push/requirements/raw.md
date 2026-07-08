飞书推送接入

对接 LLM 系统，在 LLM 输出完成分析时，根据任务配置的 webhook 数据，构建飞书卡片消息，推送到飞书机器人。当推送成功后，更新本次执行的状态为已推送。同时设计合理的飞书消息卡片模板，包含：标题、分析摘要、HTML/MD 分析跳转链接、下载链接。

## 澄清记录

### R1-Q1：推送状态字段设计（2026-07-08）

- 本轮结论：IntelligenceFeed 新增 `push_status` 字段（枚举：NOT_PUSHED / PUSHED / PUSH_FAILED），独立于 job_status。默认 NOT_PUSHED。
- 本轮约束：
  1. push_status 与 job_status 正交——job_status 标识情报结果（CHANGED/NO_CHANGE/ERROR_CRAWL），push_status 标识推送结果
  2. 仅 job_status=CHANGED 的记录会触发推送，推送成功后 push_status=PUSHED
  3. 推送失败标记 PUSH_FAILED，支持失败重试追踪
  4. 需新增 Django migration（0005）
- 关键决策：推送状态记录 → 选择"新增 push_status 字段"；放弃"feishu_pushed_at 时间戳"和"扩展 job_status"
- 遗留歧义：推送失败重试策略、Spec 004 集成边界、卡片模板细节（待后续澄清）

### R1-Q2：Spec 005 与 Spec 004 集成边界（2026-07-08）

- 本轮结论：Spec 005 实现独立 feishu_service 推送服务接口，自动触发调用点留给 Spec 004 在 LLM 情报生成完成后调用。
- 本轮约束：
  1. Spec 005 核心产物是 feishu_service（卡片模板构建 + HTTP 推送 + push_status 状态更新）
  2. 提供清晰函数接口供 Spec 004 调用（如 `feishu_service.push_intelligence(feed_id)`）
  3. 不修改 scheduler_service 的调度链路
  4. 提供手动触发 API 便于独立测试（POST /api/feeds/{id}/push）
- 关键决策：集成边界 → 选择"独立服务接口，自动触发留给 004"；放弃"调度末尾扫描"和"Django 信号"
- 遗留歧义：卡片模板细节、webhook 为空处理、失败重试策略（待后续澄清）

### R1-Q3：飞书卡片正文内容映射（2026-07-08）

- 本轮结论：飞书卡片正文"分析摘要"包含 change_summary（变化摘要）+ strategic_intent（战略意图）。
- 本轮约束：
  1. 卡片正文展示变化摘要 + 战略意图两个模块
  2. action_suggestion（行动建议）和 evidence_diff（证据 diff）留给详情页/报告页
  3. 摘要文本如过长需截断（飞书卡片内容块有长度限制），截断后追加"…"并引导点击查看详情
- 关键决策：卡片正文内容映射 → 选择"change_summary + strategic_intent"
- 遗留歧义：跳转 URL base 配置、webhook 为空处理、失败重试策略（待后续澄清）

### R1-Q4：推送失败重试策略（2026-07-08）

- 本轮结论：推送失败重试 2 次，间隔 30s（总共 3 次尝试），最终失败标记 push_status=PUSH_FAILED。
- 本轮约束：
  1. 首次推送失败后，间隔 30s 重试，最多重试 2 次
  2. 3 次尝试全部失败 → push_status=PUSH_FAILED，情报和报告仍保留（AC-015）
  3. 重试期间 push_status 保持 NOT_PUSHED（仅最终失败才标记 PUSH_FAILED）
  4. 重试使用同步等待（time.sleep），不引入异步任务队列（遵循不变量：不引入消息队列）
- 关键决策：失败重试策略 → 选择"重试 2 次，间隔 30s"；放弃"1 次"和"不重试"
- 遗留歧义：无（所有需求裁决点已澄清）

### R1 附加确认（无分歧，直接结论）

- **webhook 为空处理**：MonitorProject.feishu_webhook 为空时，跳过推送，push_status 保持 NOT_PUSHED，记录日志"webhook 未配置，跳过推送"。
- **跳转 URL base 配置**：settings.py 新增 SITE_BASE_URL 配置项（.env 可覆盖），开发环境默认 http://localhost:5173。飞书卡片按钮链接 = SITE_BASE_URL + 路径。
- **卡片标题**：使用动态标题"竞品情报速报 · {project_name}"，包含项目名让用户识别来源。
- **下载接口**：需新增 GET /api/feeds/{id}/download_md 端点，返回 md_table_path 指向的 MD 文件下载流。
