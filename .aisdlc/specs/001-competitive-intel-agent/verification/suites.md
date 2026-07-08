# 测试套件模板（verification/suites.md）

> 本模板用于把 `verification/usecase.md` 中的用例编号组织成可执行集合（smoke / targeted / regression），并明确执行顺序、依赖与阻断口径。

---

## 1. 基本信息

- **Spec / Feature**：`/Users/melody/code/ai-workshop/.aisdlc/specs/001-competitive-intel-agent`
- **版本/构建**：`unknown`
- **环境**：`Dev`
- **维护人**：`Codex / FS`
- **更新日期**：`2026-07-08`

---

## 2. 执行顺序（推荐）

1. **Smoke**
2. **P0 Critical**
3. **Targeted**
4. **Regression**
5. **探索性测试（可选）**

> 规则：smoke 失败即停止后续执行，并在 `report-*.md` 中判定为“不可交付/阻断交付”。

---

## 3. Smoke（15–30 分钟）

### 3.1 目的

- 快速确认构建可用、关键 API 主路径可跑通、评分写回可用、关键验收口径无阻断项。

### 3.2 阻断规则（必须与 test-plan 的 Exit Criteria 一致）

- 任一 smoke 用例失败 → **阻断交付**（Fail / No-Go）
- 任一 smoke 用例阻塞（Blocked）且无法在本轮解决 → 记录阻塞原因并阻断后续执行

### 3.3 用例清单（必须可定位到 TC 编号）

- `TC-001`
- `TC-003`
- `TC-004`
- `TC-005`
- `TC-008`

---

## 4. Targeted（30–60 分钟）

### 4.1 触发条件（必须填写）

- 变更点：`Element Plus 全量替换、仪表盘命名调整、任务表单上传增强、Cron 组件切换为 vue3-cron-plus-picker`
- 影响面来源：`../requirements/solution.md#7-impact-analysis`、`verification/test-plan.md` 风险清单、当前工作区前端改动

### 4.2 用例清单

- `TC-006`
- `TC-007`
- `TC-008`

---

## 5. Regression / Full（2–4 小时，视规模）

### 5.1 目的

- 验证当前骨架交付范围在近期前后端修改后仍保持稳定，不因为 UI 重构或字段扩展破坏既有 API 契约。

### 5.2 分组（可选）

按模块分组：

- Task Management
  - `TC-001`
  - `TC-002`
  - `TC-007`
- Reports & Feedback
  - `TC-003`
  - `TC-004`
  - `TC-005`
- Frontend Shell & Acceptance Gate
  - `TC-006`
  - `TC-008`

### 5.3 用例清单

- `TC-001`
- `TC-002`
- `TC-003`
- `TC-004`
- `TC-005`
- `TC-006`
- `TC-007`
- `TC-008`

---

## 6. Pass/Fail/Conditional 判定口径（简版）

- **PASS / Go**：smoke 全通过；P0 全通过；无阻断缺陷
- **FAIL / No-Go**：任一 P0 失败；或存在阻断缺陷；或 smoke 失败/阻塞
- **CONDITIONAL PASS**：仅存在 P1 未执行或失败，且有明确变通方案与修复/回归计划（需在 `report-*.md` 说明）

---

## 7. 维护规则（建议）

- 每次发布后：
  - 将本轮发现的 UI 回归或 API 契约问题补入 targeted 或 regression
  - 若 `AC-016` 仍未闭环，保留 `TC-008` 于 smoke
  - 当 Cron 组件或任务表单字段再发生变更时，必须回归 `TC-001`、`TC-007`
