# Components Index（地图层：只导航）

| module | priority | owner | code_entry | api_contract | data_contract | ops_entry | status |
|--------|----------|-------|------------|--------------|---------------|-----------|--------|
| frontend-console | P0 | FS | [frontend/src/](../../../frontend/src/) | - | - | [ops](../ops/index.md) | - [ ] |
| intelligence-api | P0 | FS | [backend/apps/intelligence/views.py](../../../backend/apps/intelligence/views.py) | [api](./intelligence-api.md#api-contract) | - | [ops](../ops/index.md) | - [x] |
| intelligence-models | P0 | FS | [backend/apps/intelligence/models.py](../../../backend/apps/intelligence/models.py) | - | [data](./intelligence-models.md#data-contract) | [ops](../ops/index.md) | - [x] |

## Dependencies（direct only）

```mermaid
graph LR
  frontend_console["frontend-console"] -->|HTTP API| intelligence_api["intelligence-api"]
  intelligence_api -->|ORM| intelligence_models["intelligence-models"]
```
