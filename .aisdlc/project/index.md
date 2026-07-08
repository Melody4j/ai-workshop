# Project Registry

## 状态

- 当前状态：`Active`
- 最近一次 merge-back：`003-scheduler-crawler`

## 已晋升资产

| type | entry | source_spec | status | note |
|---|---|---|---|---|
| ADR | [adr-001-vue-django-split-monolith.md](./adr/adr-001-vue-django-split-monolith.md) | `001-competitive-intel-agent` | Merged | 记录前后端分离单体的长期架构决策 |
| API Contract | [components/intelligence-api.md#api-contract](./components/intelligence-api.md#api-contract) | `001-competitive-intel-agent` | Merged | 任务/报告/评分 API 入口与护栏 |
| Data Contract | [components/intelligence-models.md#data-contract](./components/intelligence-models.md#data-contract) | `001-competitive-intel-agent` + `003-scheduler-crawler` | Merged | `MonitorProject`（含 next_run_at）/ `IntelligenceFeed` / `DataSnapshot`（路径字段）长期数据口径 |
| Service Contract | [components/intelligence-scheduler.md#service-contract](./components/intelligence-scheduler.md#service-contract) | `003-scheduler-crawler` | Merged | 调度服务+采集服务入口、不变量、运维限制 |
| Ops | [ops/index.md](./ops/index.md) | `001-competitive-intel-agent` + `003-scheduler-crawler` | Merged | 本地启动、构建、验证入口、依赖清单、scheduler 运维 |
| NFR | [nfr.md](./nfr.md) | `001-competitive-intel-agent` | Merged | 当前质量/安全门禁基线与缺口 |

## 未完成晋升项

- `DataSnapshot` append-only 触发器：代码尚未实现，保留在 spec 级待后续晋升
- 报告种子数据策略：当前仅用于骨架联调，不晋升为项目级规范
- Session/CSRF 同域写操作护栏：verification 阶段仍阻塞，待修复后再晋升
- 生产环境 scheduler 启动方案：RUN_MAIN 守卫仅适用 runserver，生产部署需另行处理
