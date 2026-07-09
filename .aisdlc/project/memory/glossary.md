# 术语表（短）

| 术语 | 一句话定义 | 权威出处 |
|---|---|---|
| Competitive Intel Agent | 当前仓库要交付的竞争情报监控产品骨架 | [README.md](../../../README.md) |
| MonitorProject | 监控任务配置实体，承载项目名、竞品 URL、产品文档、cron、webhook、启停状态 | [backend/apps/intelligence/models.py](../../../backend/apps/intelligence/models.py) |
| DataSnapshot | 监控采集快照实体，为后续 append-only 快照链路预留 | [backend/apps/intelligence/models.py](../../../backend/apps/intelligence/models.py) |
| IntelligenceFeed | 报告/执行记录实体，承载状态、情报字段、评分、报告路径 | [backend/apps/intelligence/models.py](../../../backend/apps/intelligence/models.py) |
| CHANGED | 有变化的报告状态，会进入前端消费路径 | [backend/apps/intelligence/models.py](../../../backend/apps/intelligence/models.py) |
| NO_CHANGE | 无变化的报告状态，当前仅在监控列表/API 结构中兼容 | [backend/apps/intelligence/models.py](../../../backend/apps/intelligence/models.py) |
| ERROR_CRAWL | 采集失败状态，当前仅在模型/API 结构中兼容 | [backend/apps/intelligence/models.py](../../../backend/apps/intelligence/models.py) |
| competitor_urls | 监控任务中的竞品来源数组，每项必须含 `title` 与 `url` | [backend/apps/intelligence/serializers.py](../../../backend/apps/intelligence/serializers.py) |
