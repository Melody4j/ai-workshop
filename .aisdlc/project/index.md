# Project Registry

## 状态

- 当前状态：`Active`
- 最近一次 merge-back：`007-ui-report-optimization`

## 已晋升资产

| type | entry | source_spec | status | note |
|---|---|---|---|---|
| ADR | [adr-001-vue-django-split-monolith.md](./adr/adr-001-vue-django-split-monolith.md) | `001-competitive-intel-agent` | Merged | 记录前后端分离单体的长期架构决策 |
| API Contract | [components/intelligence-api.md#api-contract](./components/intelligence-api.md#api-contract) | `001-competitive-intel-agent` + `005-feishu-push` + `004-llm-intel-pipeline` + `006-prompt-optimization` + `007-ui-report-optimization` | Merged | 任务/报告/评分 API + 飞书推送/MD 下载/HTML 预览/prompt 优化端点入口与护栏 + X-Frame-Options 豁免 + PATCH 启停 |
| Data Contract | [components/intelligence-models.md#data-contract](./components/intelligence-models.md#data-contract) | `001-competitive-intel-agent` + `003-scheduler-crawler` + `005-feishu-push` + `004-llm-intel-pipeline` + `006-prompt-optimization` | Merged | `MonitorProject` / `IntelligenceFeed`（含 push_status / diff_text）/ `DataSnapshot` / `PromptVersion` 长期数据口径 |
| Service Contract | [components/intelligence-scheduler.md#service-contract](./components/intelligence-scheduler.md#service-contract) | `003-scheduler-crawler` + `004-llm-intel-pipeline` + `006-prompt-optimization` | Merged | 调度服务 11 步链路（采集→LLM 降噪→diff 熔断→情报生成→入库→报告→飞书推送）+ diff_text 存储入口、不变量、运维限制 |
| Service Contract | [components/llm-service.md#service-contract](./components/llm-service.md#service-contract) | `004-llm-intel-pipeline` + `006-prompt-optimization` | Merged | 4 次独立 LLM 调用（denoise/judge_diff/generate_intel/optimize_prompts）+ instructor + 重试机制 + prompt_loader save_prompt |
| Service Contract | [components/report-service.md#service-contract](./components/report-service.md#service-contract) | `004-llm-intel-pipeline` + `007-ui-report-optimization` | Merged | Jinja2 离线渲染 HTML/MD 报告（商务报告风模板） |
| Ops | [ops/index.md](./ops/index.md) | `001-competitive-intel-agent` + `003-scheduler-crawler` + `005-feishu-push` + `004-llm-intel-pipeline` + `006-prompt-optimization` | Merged | 本地启动、构建、验证入口、依赖清单、scheduler/LLM/飞书推送/prompt 优化运维 |
| NFR | [nfr.md](./nfr.md) | `001-competitive-intel-agent` | Merged | 当前质量/安全门禁基线与缺口（LLM 延迟/成本基线待 V 阶段实测） |

## 未完成晋升项

- `DataSnapshot` append-only 触发器：代码尚未实现，保留在 spec 级待后续晋升
- 报告种子数据策略：当前仅用于骨架联调，不晋升为项目级规范
- Session/CSRF 同域写操作护栏：verification 阶段仍阻塞，待修复后再晋升
- 生产环境 scheduler 启动方案：RUN_MAIN 守卫仅适用 runserver，生产部署需另行处理
- LLM 延迟/成本 NFR 基线：V 阶段未执行，待实测后晋升（Spec 004 MB-005）
- `frontend-console.md` 组件文档：尚未建立，ReportDetailPage 和 ProjectListPage 的页面结构与 API 调用入口待补入（Spec 007 MB-002）
