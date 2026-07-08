---
title: 测试计划（Test Plan）
status: draft
---

# 飞书推送接入 测试计划

> 本计划冻结范围、策略、环境、准入/准出标准、风险与验证清单，并与 `requirements/solution.md` 的 AC-001~AC-009 保持可追溯一致。

---

## 1. 基本信息

- **Spec / Feature**：`/Users/melody/code/ai-workshop-005/.aisdlc/specs/005-feishu-push`
- **版本/构建**：`005-feishu-push` 分支，commit `40596cf`（I2 完成点）
- **环境**：Dev（本地 Django + SQLite）+ 飞书测试群（真实 webhook）
- **测试负责人**：DEV
- **计划日期**：2026-07-08

---

## 2. 执行摘要

- **待测能力**：飞书推送服务——在 LLM 情报生成完成后构建飞书交互式卡片并推送到群机器人 webhook，成功后更新 push_status 为 PUSHED。
- **目标**：验证 AC-001~AC-009 全部通过；推送服务可独立运行；手动推送 API 和 MD 下载接口功能正确；飞书测试群能收到格式正确的卡片消息。
- **关键风险**：
  1. 飞书卡片 JSON 格式被飞书 API 拒绝（V-001）
  2. 重试 30s×2 阻塞调用线程（V-002，Spec 004 集成后）
  3. SITE_BASE_URL 未配置导致卡片链接无效（V-005）
  4. Spec 004 集成点未正确调用推送接口（V-008，跨 Spec 依赖）
- **结论门槛（预告）**：见"准出标准"——所有 P0 用例通过 + 飞书测试群收到正确卡片 + 全量回归 44 tests 无回归

---

## 3. 测试范围

### 3.1 范围内（In Scope）

- push_status 字段存在性 + 默认值 + 枚举三态（AC-001, AC-009）
- feishu_service.push_intelligence 推送服务核心逻辑（AC-002~AC-005, AC-008）
- 飞书交互式卡片 JSON 构建：标题 + change_summary + strategic_intent + 2 个按钮（AC-003, AC-008）
- httpx POST 推送 + 2 次重试间隔 30s + 状态更新（AC-002, AC-004）
- webhook 为空跳过推送（AC-005）
- 非 CHANGED 状态跳过推送（AC-005 补充）
- POST /api/feeds/{id}/push 手动推送 API（AC-006）
- GET /api/feeds/{id}/download_md MD 下载 API（AC-007）
- serializers 包含 push_status 字段（AC-009）
- **飞书测试群集成测试**：使用真实 webhook 发送测试卡片，验证卡片格式和按钮链接（V-001, V-005）

### 3.2 范围外（Out of Scope）

- LLM 情报生成链路（Spec 004 负责）
- 调度链路自动触发推送（Spec 004 集成后端到端验证，V-008）
- 飞书消息回调/交互回调处理
- 飞书推送频率限制/限流
- 前端 push_status 展示（P1 候选）
- 推送性能/并发压测（单用户场景，无需）

---

## 4. 测试策略

### 4.1 测试类型

- [x] 功能（Functional）——单元测试覆盖推送服务核心逻辑和 API 端点
- [ ] UI/交互（UI）——无前端交互变化
- [x] 集成（Integration）——真实飞书 webhook 发送测试卡片
- [x] 回归（Regression）——全量测试套件确认无回归
- [ ] 安全（Security）——单用户场景，API 权限暂为 AllowAny
- [ ] 性能/稳定性（Performance/Stability）——单用户场景，重试 30s×2 可接受

### 4.2 方法与设计原则

- **正向测试**：推送成功 → push_status=PUSHED；下载成功 → 文件流返回
- **反向测试**：非 CHANGED 推送 → 400；webhook 为空 → 跳过；文件不存在 → 404
- **边界值**：change_summary/strategic_intent 截断 500 字符；卡片正文为空字符串
- **Mock 策略**：单元测试中 `@patch httpx.post` + `@patch time.sleep` 避免真实网络调用和等待；集成测试中使用真实 webhook
- **覆盖关键路径优先**：先验证推送成功链路（P0），再验证重试/跳过/下载（P1）

---

## 5. 回归策略

### 5.1 Smoke（5 分钟）

- **目的**：快速确认构建可用、关键路径可跑通
- **阻断规则**：任一 smoke 用例失败即阻断后续回归并判定"不具备交付条件"
- **覆盖**：
  - `PushStatusFieldTest`（2 tests）——字段存在性和枚举
  - `PushSuccessTest`（1 test）——推送成功核心链路
  - `FeedPushViewTest.test_push_changed_feed_returns_pushed`——API 推送成功
- **执行命令**：
  ```bash
  cd /Users/melody/code/ai-workshop-005/backend && /Users/melody/code/ai-workshop/.venv/bin/python manage.py test \
    apps.intelligence.tests.test_feishu_service.PushStatusFieldTest \
    apps.intelligence.tests.test_feishu_service.PushSuccessTest \
    apps.intelligence.tests.test_api.FeedPushViewTest.test_push_changed_feed_returns_pushed \
    --verbosity=2
  ```

### 5.2 Targeted（10 分钟）

- **触发条件**：基于 `solution.md#impact-analysis` 受影响模块和变更点
- **覆盖**：
  - `BuildCardTest`（5 tests）——卡片 JSON 结构验证
  - `PushRetryTest`——重试逻辑验证
  - `WebhookEmptyTest`——webhook 为空跳过
  - `NonChangedSkipTest`——非 CHANGED 跳过
  - `FeedPushViewTest.test_push_non_changed_feed_returns_400`——非 CHANGED API 返回 400
  - `FeedDownloadMdViewTest`（2 tests）——MD 下载成功和 404
  - **飞书测试群集成测试**——使用真实 webhook 发送测试卡片（手动执行）
- **执行命令**：
  ```bash
  cd /Users/melody/code/ai-workshop-005/backend && /Users/melody/code/ai-workshop/.venv/bin/python manage.py test \
    apps.intelligence.tests.test_feishu_service \
    apps.intelligence.tests.test_api.FeedPushViewTest \
    apps.intelligence.tests.test_api.FeedDownloadMdViewTest \
    --verbosity=2
  ```

### 5.3 Full（15 分钟）

- **目的**：发布前全面验证，确认无回归
- **覆盖**：全量 intelligence 模块测试套件（44 tests）
- **执行命令**：
  ```bash
  cd /Users/melody/code/ai-workshop-005/backend && /Users/melody/code/ai-workshop/.venv/bin/python manage.py test apps.intelligence --verbosity=2
  ```
- **预期**：44 tests passed, 0 failures

---

## 6. 环境与数据

### 6.1 环境矩阵

| 维度 | 值 |
|---|---|
| OS | macOS (Darwin 25.5.0) |
| 浏览器 | N/A（后端 API 测试） |
| 设备 | Desktop |
| 后端环境 | Dev（本地 Django runserver + SQLite） |
| Python | 3.12（venv `/Users/melody/code/ai-workshop/.venv/bin/python`） |
| 飞书测试群 | webhook: `https://open.feishu.cn/open-apis/bot/v2/hook/2a5ba4db-8216-4fc0-952f-310fe3108ded` |

### 6.2 账号与权限

- **测试账号**：N/A（单用户场景，API permission_classes = AllowAny）
- **角色/权限**：无权限限制
- **开关/配置**：
  - `SITE_BASE_URL` 默认 `http://localhost:5173`
  - 飞书测试群 webhook 地址已配置

### 6.3 测试数据准备

- **数据集来源**：测试代码中动态创建（`MonitorProject.objects.create()` + `IntelligenceFeed.objects.create()`）
- **重置方式**：Django TestCase 自动回滚（每个测试方法独立事务）
- **清理要求**：
  - `FeedDownloadMdViewTest.tearDown`：删除临时 MD 文件
  - 集成测试后无需清理（飞书消息不可撤回，但不影响后续测试）

---

## 7. 准入标准（Entry Criteria）

- [x] 需求口径已冻结（`requirements/solution.md` Mini-PRD AC-001~AC-009 可追溯）
- [x] 测试环境可用且关键依赖可用（Django + SQLite + httpx + venv）
- [x] 测试账号/权限/数据准备完成（AllowAny，测试数据动态创建）
- [x] 构建已部署且版本可追溯（commit `40596cf`，分支 `005-feishu-push`）
- [x] 飞书测试群 webhook 可用（`https://open.feishu.cn/open-apis/bot/v2/hook/2a5ba4db-8216-4fc0-952f-310fe3108ded`）

---

## 8. 准出标准（Exit Criteria，必须含阻断口径）

### 8.1 通过（Pass / Go）

- [ ] 所有 P0 用例通过（AC-001, AC-002, AC-003, AC-006, AC-007）
- [ ] smoke 套件通过（PushStatusFieldTest + PushSuccessTest + FeedPushViewTest 1 test）
- [ ] 全量回归 44 tests 通过，无回归
- [ ] 飞书测试群收到格式正确的卡片消息（V-001 集成验证）
- [ ] 卡片按钮链接可访问或 URL 格式正确（V-005）
- [ ] 无阻断缺陷（Critical/P0）

### 8.2 不通过（Fail / No-Go）

- [ ] 任一 P0 用例失败（推送成功链路 / API 端点 / 字段迁移）
- [ ] smoke 套件失败
- [ ] 飞书测试群未收到卡片或卡片格式错误（V-001 失败）
- [ ] 全量回归出现失败用例
- [ ] 发现数据丢失/安全事故/不可逆风险

### 8.3 有条件通过（Conditional Pass）

- [ ] P0 全部通过，P1 存在失败但有明确变通方案与修复计划
- [ ] V-008（Spec 004 集成兼容性）尚未验证，但已标注为 Spec 004 merge 后验证，不阻断本 Spec 交付
- [ ] 遗留风险已记录且已获干系人接受（需在 `report-*.md` 中明确）

---

## 9. 风险与验证清单（必须可执行）

| # | 风险 | 概率 | 影响 | 验证动作（最小） | Owner | 截止 | 信号/证据 |
|---|---|---|---|---|---|---|---|
| V-001 | 飞书卡片 JSON 格式被飞书 API 拒绝 | 中 | 高 | 使用真实 webhook `https://open.feishu.cn/open-apis/bot/v2/hook/2a5ba4db-8216-4fc0-952f-310fe3108ded` 发送测试卡片 | DEV | 2026-07-09 | 飞书 API 返回 200 + `{"StatusCode":0}`，测试群收到卡片 |
| V-002 | 重试 30s×2 阻塞调用线程 | 低 | 中 | 单元测试 `PushRetryTest` 验证重试 3 次 + sleep 2 次 | DEV | 2026-07-09 | mock_post.call_count=3, mock_sleep.call_count=2 |
| V-003 | push_status 状态流转不正确 | 低 | 高 | 单元测试覆盖推送成功/失败/跳过 3 种场景 | DEV | 2026-07-09 | PUSHED / PUSH_FAILED / NOT_PUSHED 分别正确 |
| V-004 | webhook 为空时仍尝试推送 | 低 | 高 | 单元测试 `WebhookEmptyTest` 验证无 HTTP 请求 | DEV | 2026-07-09 | mock_post.assert_not_called() |
| V-005 | 卡片链接不可访问 | 中 | 中 | 发送测试卡片到飞书群，点击按钮验证 URL 格式 | DEV | 2026-07-10 | URL 含 SITE_BASE_URL + feed_id，格式正确 |
| V-006 | MD 下载接口文件不存在时 500 | 低 | 中 | 单元测试 `FeedDownloadMdViewTest.test_download_md_not_found` | DEV | 2026-07-09 | 返回 404 而非 500 |
| V-007 | 手动推送 API 非 CHANGED 返回错误码 | 低 | 中 | 单元测试 `FeedPushViewTest.test_push_non_changed_feed_returns_400` | DEV | 2026-07-09 | 返回 400 + {"detail": "Only CHANGED feeds can be pushed"} |
| V-008 | Spec 004 集成点未正确调用推送接口 | 中 | 高 | Spec 004 merge 后端到端测试 | DEV | Spec 004 merge 后 2 天 | feishu_service 被调用且 push_status=PUSHED |

---

## 10. AC 追溯矩阵（AC → 测试用例 → 验证项）

| AC | 描述 | 现有测试用例 | 验证项 | P0/P1 |
|---|---|---|---|---|
| AC-001 | push_status 字段 + migration 0005 | `PushStatusFieldTest.test_push_status_default_is_not_pushed` + `test_push_status_choices` | V-003 | P0 |
| AC-002 | 推送成功后 push_status=PUSHED | `PushSuccessTest.test_push_success_updates_pushed` | V-003 | P0 |
| AC-003 | 卡片含标题 + change_summary + strategic_intent + 2 按钮 | `BuildCardTest`（5 tests） | V-001 | P0 |
| AC-004 | 推送失败重试 2 次间隔 30s，最终 PUSH_FAILED | `PushRetryTest.test_push_retry_3_attempts_then_failed` | V-002 | P1 |
| AC-005 | webhook 为空跳过推送，NOT_PUSHED | `WebhookEmptyTest.test_skip_push_when_webhook_empty` + `NonChangedSkipTest.test_skip_push_when_not_changed` | V-004 | P1 |
| AC-006 | POST /api/feeds/{id}/push 返回结果，非 CHANGED 返回 400 | `FeedPushViewTest`（2 tests） | V-007 | P0 |
| AC-007 | GET /api/feeds/{id}/download_md 返回 MD 文件 | `FeedDownloadMdViewTest`（2 tests） | V-006 | P0 |
| AC-008 | 卡片链接使用 SITE_BASE_URL 绝对 URL | `BuildCardTest.test_card_button_urls_contain_site_base_url` | V-005 | P0 |
| AC-009 | serializers 包含 push_status | `PushStatusFieldTest`（间接验证，序列化器 fields 含 push_status） | V-003 | P1 |

---

## 11. 飞书测试群集成测试方案

### 11.1 目的

验证飞书卡片 JSON 格式正确性（V-001）和按钮链接可访问性（V-005），使用真实飞书 webhook 发送测试卡片。

### 11.2 测试 webhook

```
https://open.feishu.cn/open-apis/bot/v2/hook/2a5ba4db-8216-4fc0-952f-310fe3108ded
```

### 11.3 执行步骤

1. 启动 Django 开发服务器
2. 创建测试项目（配置真实 webhook）
3. 创建 CHANGED 状态的 IntelligenceFeed 记录
4. 调用 POST /api/feeds/{id}/push 触发推送
5. 检查飞书测试群是否收到卡片
6. 验证卡片内容：标题含项目名、变化摘要、战略意图、2 个按钮
7. 点击"在线预览"按钮验证 URL 格式
8. 点击"下载 MD"按钮验证 URL 格式

### 11.4 预期结果

- 飞书 API 返回 200 + `{"StatusCode":0}`
- push_status 更新为 PUSHED
- 测试群收到交互式卡片消息
- 卡片标题："竞品情报速报 · {project_name}"
- 卡片正文含"变化摘要"和"战略意图"段落
- 卡片底部含"在线预览"（primary 按钮）和"下载 MD"（default 按钮）
- 按钮链接格式为 `{SITE_BASE_URL}/view/html/{feed_id}` 和 `{SITE_BASE_URL}/api/feeds/{feed_id}/download_md`

---

## 12. 追溯链接（必须）

- `requirements/solution.md`：[../requirements/solution.md](../requirements/solution.md)
- `requirements/solution.md#impact-analysis`：[../requirements/solution.md#7-impact-analysis需求影响分析](../requirements/solution.md)
- `implementation/plan.md`：[../implementation/plan.md](../implementation/plan.md)
- `verification/usecase.md`：`<TODO>`（生成后补）
- `verification/suites.md`：`<TODO>`（如有）

---

## 13. CONTEXT GAP

- `CONTEXT GAP`：Spec 004 的 `requirements/raw.md` 不在 dev 分支（worktree 基于 dev，004 分支未 merge）。V-008（Spec 004 集成兼容性）无法在本阶段验证，需 Spec 004 merge 后补充端到端测试。
  - 建议动作：Spec 004 merge 后执行 V-008 验证
- `CONTEXT GAP`：项目级 NFR 文档缺失（来源：`.aisdlc/project/memory/tech.md`），推送服务性能/稳定性无长期约束基线。
  - 建议动作：merge-back 时补充 NFR 入口
