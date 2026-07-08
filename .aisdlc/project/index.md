# Project Registry

## 状态

- 当前状态：`Active`
- 最近一次 merge-back：`001-competitive-intel-agent`

## 已晋升资产

| type | entry | source_spec | status | note |
|---|---|---|---|---|
| ADR | [adr-001-vue-django-split-monolith.md](./adr/adr-001-vue-django-split-monolith.md) | `001-competitive-intel-agent` | Merged | 记录前后端分离单体的长期架构决策 |
| API Contract | [components/intelligence-api.md#api-contract](./components/intelligence-api.md#api-contract) | `001-competitive-intel-agent` | Merged | 任务/报告/评分 API 入口与护栏 |
| Data Contract | [components/intelligence-models.md#data-contract](./components/intelligence-models.md#data-contract) | `001-competitive-intel-agent` | Merged | `MonitorProject` / `IntelligenceFeed` 长期数据口径 |
| Ops | [ops/index.md](./ops/index.md) | `001-competitive-intel-agent` | Merged | 本地启动、构建、验证入口 |
| NFR | [nfr.md](./nfr.md) | `001-competitive-intel-agent` | Merged | 当前质量/安全门禁基线与缺口 |

## 未完成晋升项

- `DataSnapshot` append-only 触发器：代码尚未实现，保留在 spec 级待后续晋升
- 报告种子数据策略：当前仅用于骨架联调，不晋升为项目级规范
- Session/CSRF 同域写操作护栏：verification 阶段仍阻塞，待修复后再晋升
