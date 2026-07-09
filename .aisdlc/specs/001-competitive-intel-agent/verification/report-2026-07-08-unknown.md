# 测试报告模板（verification/report-{date}-{version}.md）

> 本模板用于产出“结论性测试报告”：是否满足 AC、是否可交付、阻断点与下一步动作是什么。
>
> 约束：缺陷不在 Spec Pack 内单独落盘，报告只做外部缺陷系统的编号/链接引用，并关联到 `TC-*`。

---

## 1. 基本信息

- **日期**：`2026-07-08`
- **版本/构建**：`unknown`
- **环境**：`Dev`
- **测试人员**：`Codex / FS`
- **Spec / Feature**：`/Users/melody/code/ai-workshop/.aisdlc/specs/001-competitive-intel-agent`

---

## 2. 测试摘要（必须给出结论）

- **结论**：`不通过`
- **阻断交付**：`是`
- **一句话说明**：`当前批次的 API 逻辑与前端构建通过，但 AC-016 对应的同域 Session/CSRF 写操作未形成可验证闭环，且 smoke 套件中的 TC-008 处于阻塞状态。`

---

## 3. 覆盖统计（必须）

### 3.1 按套件统计

| Suite | Total | Executed | Pass | Fail | Blocked | NotRun | PassRate |
|---|---:|---:|---:|---:|---:|---:|---:|
| Smoke | 5 | 5 | 4 | 0 | 1 | 0 | 80.0% |
| Targeted | 3 | 1 | 0 | 0 | 1 | 2 | 0.0% |
| Regression | 8 | 6 | 5 | 0 | 1 | 2 | 62.5% |
| **TOTAL（唯一用例）** | 8 | 6 | 5 | 0 | 1 | 2 | 62.5% |

### 3.2 按优先级统计（从用例提取或手工汇总）

| Priority | Total | Executed | Pass | Fail | Blocked | NotRun |
|---|---:|---:|---:|---:|---:|---:|
| P0 | 5 | 5 | 4 | 0 | 1 | 0 |
| P1 | 3 | 1 | 1 | 0 | 0 | 2 |
| P2 | 0 | 0 | 0 | 0 | 0 | 0 |
| P3 | 0 | 0 | 0 | 0 | 0 | 0 |

---

## 4. AC↔TC 覆盖映射（必须）

> 至少要回答：哪些 AC 被哪些 TC 覆盖；哪些 AC 仍缺口（Gap）。

| AC | 来源链接 | 覆盖用例（TC-...） | 覆盖状态（完整/部分/缺口） | 备注 |
|---|---|---|---|---|
| AC-001 | `../requirements/prd.md#61-场景-s-001-的-acvue-配置--首采` | `TC-001` | 完整 | 已由 API 自动化测试验证 |
| AC-004 | `../requirements/prd.md#61-场景-s-001-的-acvue-配置--首采` | `TC-004` | 部分 | 已验证详情响应含报告路径；未验证真实文件可访问/可下载 |
| AC-009 | `../requirements/prd.md#62-场景-s-002-的-ac执行列表` | `TC-003` | 部分 | 仅状态过滤被自动化验证；项目/时间范围过滤待补测 |
| AC-011 | `../requirements/prd.md#63-场景-s-003-的-ac收件箱--反馈` | `TC-004` | 部分 | 详情 API 验证通过；前端详情页手工浏览未执行 |
| AC-012 | `../requirements/prd.md#63-场景-s-003-的-ac收件箱--反馈` | `TC-005` | 完整 | 评分创建/更新/清空均通过 |
| AC-016 | `../requirements/prd.md#64-异常路径-ac` | `TC-008` | 缺口 | 未见 Session/CSRF 集成证据，smoke 阻塞 |

---

## 5. 关键失败与阻断项（必须可追溯到 TC）

### 5.1 阻断项清单

| TC | 现象摘要 | 外部缺陷（ID/链接） | 严重程度 | 状态 | 是否阻断交付 | 下一步动作 |
|---|---|---|---|---|---|---|
| `TC-008` | 前端 API client 未设置 `credentials`，仓库中未发现同域 Session/CSRF bootstrap 路径，AC-016 无法成立 | `未创建 / -` | Critical / P0 | Open | 是 | 补齐同域 Session/CSRF 集成，新增验证用例/脚本后重跑 smoke |

### 5.2 失败明细（可选：按套件/模块分组）

- `TC-008`：代码检查显示 [frontend/src/api/client.ts](/Users/melody/code/ai-workshop/frontend/src/api/client.ts) 仅发送 JSON body，不携带 `credentials`，也未注入 CSRF token；后端路由层未提供可见的同域写操作 bootstrap 证据。

---

## 6. 缺陷清单（仅引用，必须关联 TC）

> 不在 Spec Pack 内新增缺陷文件；此处记录外部缺陷系统引用信息，并关联到用例编号。

| BUG | 链接 | 标题 | Severity | Priority | 状态 | 关联用例（TC-...） | 备注 |
|---|---|---|---|---|---|---|---|
| `未创建` | `-` | Vue API 写操作未形成 Session/CSRF 校验闭环 | Critical | P0 | Open | `TC-008` | 建议补外部缺陷并回写编号 |

---

## 7. 遗留风险与建议（必须可执行）

- **遗留风险**：
  - `README` 标准后端测试命令当前返回 `0 tests`，容易误判全绿
  - 前端缺少独立 `lint` / `typecheck` script
  - `TC-006` / `TC-007` 的浏览器级 UI 回归尚未执行
- **建议**：
  - 返工：补齐同域 Session/CSRF 路径，至少包括前端 `credentials`/token 处理与后端对应入口
  - 补测：修复后优先重跑 `TC-008`，并联动回归 `TC-001`、`TC-005`
  - 补门禁：修正 README 的后端测试命令，并补前端 `typecheck` / `lint` 脚本
  - UI 回归：启动本地前后端后执行 `TC-006`、`TC-007`，补浏览器级证据

---

## 8. 追溯链接

- `verification/test-plan.md`：`./test-plan.md`
- `verification/usecase.md`：`./usecase.md`
- `verification/suites.md`（如有）：`./suites.md`
- `requirements/solution.md` / `requirements/prd.md`：`../requirements/solution.md`、`../requirements/prd.md`

---

## 9. CONTEXT GAP（如有）

- `.aisdlc/project/memory/product.md` 缺失
- `.aisdlc/project/memory/tech.md` 缺失
- `.aisdlc/project/memory/glossary.md` 缺失
- 当前验证版本为未提交工作区，未形成可追溯 build id，因此记录为 `unknown`
- `TC-006`、`TC-007` 未执行浏览器级手工回归，当前报告主要基于后端自动化测试、代码检查与前端构建结果
