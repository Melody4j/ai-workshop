# 测试计划模板（verification/test-plan.md）

> 本模板用于在 Spec Pack 的 verification 阶段冻结：范围、策略、环境、准入/准出标准、风险与验证清单，并为用例/套件/报告提供口径。

---

## 1. 基本信息

- **Spec / Feature**：`/Users/melody/code/ai-workshop/.aisdlc/specs/001-competitive-intel-agent`
- **版本/构建**：`unknown`
- **环境**：`Dev`
- **测试负责人**：`Codex / FS`
- **计划日期**：`2026-07-08`

---

## 2. 执行摘要

- **待测能力**：`Competitive Intel Agent 当前骨架版本：任务 CRUD、报告列表/详情、评分 CRUD，以及近期的 Element Plus / Cron 表单收尾调整`
- **目标**：`验证 implementation/plan.md 当前批次承诺的 AC-001、AC-004、AC-009、AC-011、AC-012、AC-016 是否达到可交付口径`
- **关键风险**：
  - `Vue 写操作链路未体现同域 Session/CSRF 集成，AC-016 可能不成立`
  - `README 默认后端测试命令实际返回 0 tests，容易误判完成度`
  - `前端缺少独立 lint/typecheck 门禁，UI 收尾回归覆盖不足`
  - `Cron 组件已切换为 vue3-cron-plus-picker，存在 6/7 段到 5 段表达式转换风险`
- **结论门槛（预告）**：见“准出标准”

---

## 3. 测试范围

### 3.1 范围内（In Scope）

- `MonitorProject` 创建、编辑、停用相关 API 与前端配置表单字段
- 报告列表查询、状态筛选、详情查询、评分 CRUD
- Vue 仪表盘、任务管理、任务监控、执行详情页的构建可用性与基础导航
- `vue3-cron-plus-picker` 接入后的表达式填写与保存口径
- 当前批次对齐的 AC：`AC-001`、`AC-004`、`AC-009`、`AC-011`、`AC-012`、`AC-016`

### 3.2 范围外（Out of Scope）

- `django-apscheduler` 调度执行
- `httpx` / `Playwright` / `html2text` 采集与降噪
- LLM 情报生成、Negative Few-Shot 注入
- 飞书推送与真实 HTML/MD 报告文件落盘联调
- append-only 快照触发器（`AC-017`）与真实执行状态流转

---

## 4. 测试策略

### 4.1 测试类型

- [x] 功能（Functional）
- [x] UI/交互（UI）
- [x] 集成（Integration）
- [x] 回归（Regression）
- [ ] 安全（Security）
- [ ] 性能/稳定性（Performance/Stability）

### 4.2 方法与设计原则

- 正向 / 反向 / 边界值 / 等价类
- 先验证当前批次承诺的 P0 路径，再覆盖近期高改动区域（Element Plus、Cron、上传字段）
- 每一步必须有可观测预期（可判定 Pass/Fail/Blocked）
- 自动化结果优先采用仓库现有 Django 测试与前端构建结果；未覆盖到的 UI 项保留为手工回归

---

## 5. 回归策略（必须填写）

> 回归套件分层：smoke / targeted / full。执行顺序建议：smoke → P0 → targeted → full → 探索。

### 5.1 Smoke（15–30 分钟）

- **目的**：快速确认 API 写操作、报告查询、评分回写、前端构建主路径可用
- **阻断规则**：任一 smoke 用例失败或阻塞即阻断交付并停止后续“通过”判定
- **覆盖**：`TC-001`、`TC-003`、`TC-004`、`TC-005`、`TC-008`

### 5.2 Targeted（30–60 分钟）

- **触发条件**：近期发生 Element Plus 替换、任务表单上传字段扩展、Cron 组件切换、仪表盘文案调整
- **覆盖**：`TC-006`、`TC-007`、`TC-008`

### 5.3 Full（2–4 小时 / 视规模）

- **目的**：当前批次并未形成完整业务闭环，Full 回归仅覆盖“骨架交付范围”
- **覆盖**：任务配置、任务停用、报告筛选、详情查看、评分 CRUD、关键 UI 页面与当前构建链路

---

## 6. 环境与数据

### 6.1 环境矩阵

| 维度 | 值 |
|---|---|
| OS | macOS 26 / Darwin 25.5.0 |
| 浏览器 | Chrome（手工回归待执行） |
| 设备 | Desktop |
| 后端环境 | Dev |

### 6.2 账号与权限

- **测试账号**：`N/A（当前 API 为 AllowAny）`
- **角色/权限**：`匿名访问；同域 Session/CSRF 尚未成型`
- **开关/配置**：`本地 Django + 本地 Vite`

### 6.3 测试数据准备

- 数据集来源：`Django TestCase 创建数据 + 前端本地构建产物`
- 重置方式：`backend/manage.py test apps.intelligence.tests` 自动创建/销毁测试库
- 清理要求：`无持久污染；手工 UI 回归前可重置 SQLite 或重建示例数据`

---

## 7. 准入标准（Entry Criteria）

- [x] 需求口径已冻结（`requirements/solution.md` 与 `requirements/prd.md` 可追溯）
- [x] 测试环境可用且关键依赖可用
- [x] 测试数据与命令入口可获取
- [ ] 构建版本可追溯（当前为 `CONTEXT GAP: version/build unknown`）

---

## 8. 准出标准（Exit Criteria，必须含阻断口径）

### 8.1 通过（Pass / Go）

- [ ] 当前批次 P0 用例通过（`TC-001`、`TC-003`、`TC-004`、`TC-005`、`TC-008`）
- [ ] smoke 套件通过
- [ ] 无阻断缺陷（Critical/P0）
- [ ] AC-016 有证据证明同域 Session/CSRF 写操作成立

### 8.2 不通过（Fail / No-Go）

- [x] 任一 P0 用例失败或阻塞
- [x] smoke 套件失败或阻塞
- [x] 存在阻断缺陷（当前关注：`TC-008`）
- [ ] 发现数据丢失/安全事故/不可逆风险

### 8.3 有条件通过（Conditional Pass）

- [ ] 仅存在 P1/P2 未覆盖或失败，且不影响当前批次验收 AC
- [ ] 遗留风险已记录且获干系人接受

---

## 9. 风险与验证清单（必须可执行）

| 风险 | 概率 | 影响 | 验证动作（最小） | Owner | 截止 | 信号/证据 |
|---|---|---|---|---|---|---|
| `AC-016 仅在 plan 中声明，代码中未见 credentials/CSRF header 处理` | 高 | 高 | 检查 `frontend/src/api/client.ts` 与写操作链路；补手工/自动化写操作验证 | FS | 2026-07-08 | `fetch` 未带 `credentials`，无 CSRF token 初始化 |
| `README 默认测试命令误报 0 tests` | 高 | 中 | 以 `backend/manage.py test apps.intelligence.tests` 代替并记录差异 | FS | 2026-07-08 | `manage.py test` 返回 `Found 0 test(s)` |
| `Cron 组件切换后 6/7 段到 5 段转换错误` | 中 | 中 | 手工验证 `vue3-cron-plus-picker` 选择结果与保存值 | FS | 2026-07-09 | 选择器输出与表单保存值一致 |
| `Element Plus 大量替换后 UI 空状态/导航可能回归` | 中 | 中 | 执行 `TC-006` 手工浏览主要页面 | FS | 2026-07-09 | 仪表盘/列表/详情无错位或崩溃 |
| `前端缺少 lint/typecheck` | 中 | 中 | 至少保证 `npm --prefix frontend run build` 通过，并记录门禁缺口 | FS | 2026-07-08 | build 成功，但缺少独立 lint/typecheck script |

---

## 10. 追溯链接（必须）

- `requirements/solution.md`：`../requirements/solution.md`
- `requirements/prd.md`：`../requirements/prd.md`
- `requirements/solution.md#impact-analysis`：`../requirements/solution.md#7-impact-analysis`
- `verification/usecase.md`：`./usecase.md`
- `verification/suites.md`：`./suites.md`

---

## 11. CONTEXT GAP（如有）

- `.aisdlc/project/memory/product.md` 缺失，无法引用项目级产品上下文
- `.aisdlc/project/memory/tech.md` 缺失，无法引用项目级技术约束 SSOT
- `.aisdlc/project/memory/glossary.md` 缺失，无法引用统一术语表
- 当前验证对应的构建/版本未形成可追溯标识，报告中以 `unknown` 记录
