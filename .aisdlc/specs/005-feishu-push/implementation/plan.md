---
title: I1 Implementation Plan（SSOT）
status: draft
---

# 飞书推送接入 实现计划（SSOT）

> **必需技能：** `spec-execute`（按批次执行本计划）
> **上下文获取：** 必须先执行 `spec-context` 获取上下文，定位 `{FEATURE_DIR}`，失败即停止

**目标：** 实现独立 feishu_service 推送服务——在 LLM 情报生成完成后构建飞书交互式卡片并推送，成功后更新 push_status 为 PUSHED。
**范围：** In = feishu_service 推送服务 + push_status 字段迁移 + 手动推送 API + MD 下载 API + SITE_BASE_URL 配置；Out = LLM 情报生成链路（Spec 004）、调度链路修改、飞书回调处理
**架构：** 独立 `feishu_service.py` 提供 `push_intelligence(feed_id)` 函数接口，httpx POST 推送飞书卡片 JSON，2 次重试间隔 30s，push_status 状态追踪。不修改 scheduler_service，自动触发由 Spec 004 集成。
**验收口径：** `requirements/solution.md` Mini-PRD AC-001~AC-009
**影响范围：** intelligence-models（新增字段）、intelligence-api（新增端点）、新增 feishu_service 服务模块
**需遵守的不变量：** job_status 保持三态不扩展；push_status 与 job_status 正交；仅 CHANGED 推送；不引入消息队列；httpx 优先
**子仓范围：** 无

---

## TL;DR（3–7 行）

- 一句话目标：实现飞书推送服务，在情报生成后构建卡片推送飞书，成功更新 push_status=PUSHED
- In/Out：In = feishu_service + push_status 字段 + 2 个 API 端点 + SITE_BASE_URL；Out = LLM 链路 / 调度修改 / 飞书回调
- 关键路径：T1（字段迁移）→ T2（配置）→ T3（推送服务+测试）→ T4（API 端点+测试）
- 最大风险与优先验证点：V-001（飞书卡片 JSON 格式）、V-002（推送重试逻辑）、V-005（卡片链接可访问性）

---

## 范围与边界（In / Out）

- **In**：
  1. IntelligenceFeed 新增 `push_status` 字段（NOT_PUSHED/PUSHED/PUSH_FAILED）+ migration 0005
  2. `feishu_service.py` 推送服务：`push_intelligence(feed_id)` 函数接口
  3. 飞书交互式卡片模板构建（标题 + change_summary + strategic_intent + 在线预览按钮 + 下载 MD 按钮）
  4. httpx POST 推送 + 2 次重试间隔 30s
  5. push_status 状态更新
  6. REST API：POST /api/feeds/{id}/push + GET /api/feeds/{id}/download_md
  7. settings.py 新增 SITE_BASE_URL
  8. serializers 新增 push_status 字段
- **Out**：
  - LLM 情报生成链路（Spec 004）
  - scheduler_service 调度链路修改
  - 飞书消息回调/交互回调处理
  - 前端 push_status 展示
- **不变量/关键约束**：
  1. job_status 保持 CHANGED/NO_CHANGE/ERROR_CRAWL 三态不扩展（来源：intelligence-models.md#不变量6）
  2. push_status 与 job_status 正交（来源：raw.md R1-Q1）
  3. 仅 job_status=CHANGED 触发推送（来源：001 prd.md#规则-5）
  4. 不引入消息队列，重试用 time.sleep（来源：001 prd.md#规则-9，raw.md R1-Q4）
  5. 推送失败情报和报告仍保留（来源：001 prd.md#AC-015）
- **影响面**：数据模型（新增字段）、服务层（新增 feishu_service）、API（新增 2 端点）、配置（SITE_BASE_URL）、序列化器

## 代码工作区清单

无子仓。本需求仅涉及根项目代码。

---

## 里程碑与节奏

- M0（MVP）：4 个任务全部完成，推送服务可独立运行和测试
  - 产物：feishu_service.py + migration 0005 + 2 个 API 端点 + 单元测试
  - 验证标准：AC-001~AC-009 全部通过

---

## 依赖与资源

- 环境/权限：主仓库 venv `/Users/melody/code/ai-workshop/.venv/bin/python`（worktree 共享），httpx 0.27.2 已安装
- 外部系统/团队：飞书群机器人 webhook（测试用），飞书开放平台卡片消息文档
- 数据/样本：需创建 CHANGED 状态的 IntelligenceFeed 测试数据（可用 fixtures 或测试中创建）
- Spec 004 依赖：feishu_service.push_intelligence(feed_id) 接口需在 Spec 004 merge 后由情报生成链路调用（V-008）

---

## 风险与验证（可执行）

| # | 风险/假设 | 验证方式 | 成功信号 | 失败信号 | Owner | 截止 | 下一步动作 |
|---|---|---|---|---|---|---|---|
| R1 | 飞书卡片 JSON 格式可能被飞书 API 拒绝 | 发送测试卡片到测试群 | API 返回 200 + StatusCode:0 | API 返回 4xx/非 0 | DEV | T3 完成后 | 对照飞书文档修正 JSON |
| R2 | 重试 30s×2 可能阻塞调度线程（Spec 004 集成后） | 端到端测试计时 | 推送总耗时 ≤ 90s | 超时或阻塞 | DEV | T3 完成后 | 改为异步或缩短间隔 |
| R3 | SITE_BASE_URL 未配置导致卡片链接无效 | 检查 settings.py 配置 | 链接可打开 | 链接 404 | DEV | T4 完成后 | 确认 .env 或 settings 配置 |

---

## 验收口径（可追溯）

- 追溯：`requirements/solution.md` Mini-PRD AC-001~AC-009
- 关键验收点：
  - AC-001：push_status 字段 + migration 0005 成功
  - AC-002：push_intelligence 推送成功后 push_status=PUSHED
  - AC-003：飞书卡片含标题 + change_summary + strategic_intent + 2 个按钮
  - AC-004：推送失败重试 2 次间隔 30s，最终 PUSH_FAILED
  - AC-005：webhook 为空跳过推送，push_status 保持 NOT_PUSHED
  - AC-006：POST /api/feeds/{id}/push 返回推送结果
  - AC-007：GET /api/feeds/{id}/download_md 返回 MD 文件
  - AC-008：卡片链接使用 SITE_BASE_URL 绝对 URL
  - AC-009：serializers 包含 push_status 字段

---

## NEEDS CLARIFICATION（未消除前不得进入 I2）

无未消除的不确定项。所有需求裁决已在 R1 澄清完成（raw.md R1-Q1~Q4 + 附加确认）。飞书卡片 JSON 格式细节在实现阶段通过飞书文档确认（V-001 验证）。

---

## 任务清单（SSOT）

> Python 命令统一使用主仓库 venv：`/Users/melody/code/ai-workshop/.venv/bin/python`
> Django manage.py 位于 `backend/` 目录，需 `cd backend` 后执行

### Task T1: IntelligenceFeed 新增 push_status 字段 + migration + serializers

- [x] **状态**：完成

**代码仓范围：**
- 根项目：`backend/apps/intelligence/`
- 子仓：无

**文件：**
- 修改：`backend/apps/intelligence/models.py`（IntelligenceFeed 类内新增 push_status 字段 + PushStatus 枚举）
- 创建：`backend/apps/intelligence/migrations/0005_intelligencefeed_push_status.py`（由 makemigrations 生成）
- 修改：`backend/apps/intelligence/serializers.py`（IntelligenceFeedListSerializer + IntelligenceFeedDetailSerializer 的 fields 加 push_status）
- 测试：`backend/apps/intelligence/tests/test_feishu_service.py`（新建，先写字段存在性测试）

**验收点：**
- [AC-001] IntelligenceFeed 有 push_status 字段，默认 NOT_PUSHED
- [AC-009] List 和 Detail Serializer 包含 push_status 字段
- migration 0005 执行成功

**步骤 1：写失败测试**
- 修改点：`backend/apps/intelligence/tests/test_feishu_service.py`（新建文件）
- 测试内容：创建 IntelligenceFeed，验证 push_status 默认为 NOT_PUSHED；验证 PushStatus 枚举有 NOT_PUSHED/PUSHED/PUSH_FAILED
- Run: `cd /Users/melody/code/ai-workshop-005/backend && /Users/melody/code/ai-workshop/.venv/bin/python manage.py test apps.intelligence.tests.test_feishu_service.PushStatusFieldTest --verbosity=2`
- Expected: FAIL（字段不存在，报 `AttributeError` 或 `FieldError`）

**步骤 2：写最少实现**
- 修改 `backend/apps/intelligence/models.py`：
  - IntelligenceFeed 类内新增 `class PushStatus(models.TextChoices)`：`NOT_PUSHED = "NOT_PUSHED"` / `PUSHED = "PUSHED"` / `PUSH_FAILED = "PUSH_FAILED"`
  - 新增字段 `push_status = models.CharField(max_length=20, choices=PushStatus.choices, default=PushStatus.NOT_PUSHED)`
- 修改 `backend/apps/intelligence/serializers.py`：
  - IntelligenceFeedListSerializer.fields 加 `"push_status"`
  - IntelligenceFeedDetailSerializer.fields 加 `"push_status"`
- 生成 migration：
  - Run: `cd /Users/melody/code/ai-workshop-005/backend && /Users/melody/code/ai-workshop/.venv/bin/python manage.py makemigrations intelligence --name intelligencefeed_push_status`
  - 预期生成 `0005_intelligencefeed_push_status.py`

**步骤 3：运行验证**
- Run: `cd /Users/melody/code/ai-workshop-005/backend && /Users/melody/code/ai-workshop/.venv/bin/python manage.py migrate intelligence`
- Run: `cd /Users/melody/code/ai-workshop-005/backend && /Users/melody/code/ai-workshop/.venv/bin/python manage.py test apps.intelligence.tests.test_feishu_service.PushStatusFieldTest --verbosity=2`
- Expected: PASS（push_status 默认 NOT_PUSHED，枚举三态正确）

**步骤 4：提交（AUTO_COMMIT=true）**
- Commit message: `feat: IntelligenceFeed 新增 push_status 字段与 migration 0005`
- 审计信息：
  - repo: `root`
    branch: `005-feishu-push`
    commit: `d7f827a`
    pr: `<TBD>`
    changed_files:
      - `backend/apps/intelligence/models.py`
      - `backend/apps/intelligence/migrations/0005_intelligencefeed_push_status.py`
      - `backend/apps/intelligence/serializers.py`
      - `backend/apps/intelligence/tests/test_feishu_service.py`

---

### Task T2: settings.py 新增 SITE_BASE_URL 配置

- [x] **状态**：完成

**代码仓范围：**
- 根项目：`backend/config/`
- 子仓：无

**文件：**
- 修改：`backend/config/settings.py`（新增 SITE_BASE_URL 配置项）

**验收点：**
- [AC-008] SITE_BASE_URL 配置项存在，默认 `http://localhost:5173`
- 可通过环境变量覆盖

**步骤 1：写最少实现**
- 修改 `backend/config/settings.py`：
  - 在文件顶部 import 区域加 `import os`（如已有则跳过）
  - 在配置区域新增：`SITE_BASE_URL = os.environ.get("SITE_BASE_URL", "http://localhost:5173")`

**步骤 2：运行验证**
- Run: `cd /Users/melody/code/ai-workshop-005/backend && /Users/melody/code/ai-workshop/.venv/bin/python -c "import django; import os; os.environ['DJANGO_SETTINGS_MODULE']='config.settings'; django.setup(); from django.conf import settings; print(settings.SITE_BASE_URL)"`
- Expected: 输出 `http://localhost:5173`

**步骤 3：提交（AUTO_COMMIT=true）**
- Commit message: `feat: settings 新增 SITE_BASE_URL 配置项`
- 审计信息：
  - repo: `root`
    branch: `005-feishu-push`
    commit: `f02e781`
    pr: `<TBD>`
    changed_files:
      - `backend/config/settings.py`

---

### Task T3: feishu_service 推送服务实现 + 单元测试

- [x] **状态**：完成

**代码仓范围：**
- 根项目：`backend/apps/intelligence/services/`
- 子仓：无

**文件：**
- 创建：`backend/apps/intelligence/services/feishu_service.py`
- 修改：`backend/apps/intelligence/tests/test_feishu_service.py`（追加推送服务测试）

**验收点：**
- [AC-002] push_intelligence 推送成功后 push_status=PUSHED
- [AC-003] 卡片含标题"竞品情报速报 · {project_name}" + change_summary + strategic_intent + 在线预览按钮 + 下载 MD 按钮
- [AC-004] 推送失败重试 2 次间隔 30s，最终 push_status=PUSH_FAILED
- [AC-005] webhook 为空时跳过推送，push_status 保持 NOT_PUSHED
- [AC-008] 卡片链接使用 SITE_BASE_URL 绝对 URL

**步骤 1：写失败测试**
- 修改点：`backend/apps/intelligence/tests/test_feishu_service.py`（追加测试类）
- 测试内容：
  1. `BuildCardTest`：调用 `feishu_service._build_card(feed)`，验证卡片 JSON 结构（header.title.content 含 project_name、elements 含 change_summary 和 strategic_intent 的 div、action 含 2 个 button、button url 含 SITE_BASE_URL 和 feed_id）
  2. `PushSuccessTest`：mock httpx POST 返回 200，调用 `push_intelligence(feed_id)`，验证 push_status=PUSHED
  3. `PushRetryTest`：mock httpx POST 始终抛异常，调用 `push_intelligence(feed_id)`，验证调用 3 次（含重试 2 次），push_status=PUSH_FAILED（注意：测试中 mock time.sleep 避免真实等待）
  4. `WebhookEmptyTest`：feishu_webhook="" 的项目，调用 `push_intelligence(feed_id)`，验证 push_status 保持 NOT_PUSHED，无 HTTP 请求
  5. `NonChangedSkipTest`：job_status=NO_CHANGE 的 feed，调用 `push_intelligence(feed_id)`，验证 push_status 保持 NOT_PUSHED
- Run: `cd /Users/melody/code/ai-workshop-005/backend && /Users/melody/code/ai-workshop/.venv/bin/python manage.py test apps.intelligence.tests.test_feishu_service --verbosity=2`
- Expected: FAIL（feishu_service 模块不存在，ImportError）

**步骤 2：写最少实现**
- 创建 `backend/apps/intelligence/services/feishu_service.py`：
  - `import httpx, time, logging`
  - `from django.conf import settings`
  - `from apps.intelligence.models import IntelligenceFeed`
  - `_build_card(feed) -> dict`：构建飞书交互式卡片 JSON
    - header: title="竞品情报速报 · {feed.project.project_name}"，template="blue"
    - elements[0]: div, lark_md, "**变化摘要**\n{feed.change_summary}"（截断 500 字符）
    - elements[1]: hr
    - elements[2]: div, lark_md, "**战略意图**\n{feed.strategic_intent}"（截断 500 字符）
    - elements[3]: action, 2 个 button
      - button 1: text="在线预览", url="{SITE_BASE_URL}/view/html/{feed.id}", type="primary"
      - button 2: text="下载 MD", url="{SITE_BASE_URL}/api/feeds/{feed.id}/download_md", type="default"
  - `push_intelligence(feed_id) -> str`：核心推送函数
    - 查库获取 feed + project
    - 前置校验：feed.job_status != CHANGED → 返回 "skipped"，记日志
    - 前置校验：project.feishu_webhook 为空 → 返回 "skipped_no_webhook"，记日志
    - 构建卡片 JSON
    - httpx POST 推送，重试 2 次间隔 30s（`time.sleep(30)`）
    - 成功 → feed.push_status = PUSHED, feed.save(update_fields=["push_status"])
    - 失败 → feed.push_status = PUSH_FAILED, feed.save(update_fields=["push_status"])
    - 返回 "pushed" / "push_failed"

**步骤 3：运行验证**
- Run: `cd /Users/melody/code/ai-workshop-005/backend && /Users/melody/code/ai-workshop/.venv/bin/python manage.py test apps.intelligence.tests.test_feishu_service --verbosity=2`
- Expected: PASS（5 个测试类全部通过）
- 注意：测试中需 `@patch("apps.intelligence.services.feishu_service.time.sleep")` 避免 30s 真实等待
- 注意：测试中需 `@patch("apps.intelligence.services.feishu_service.httpx.post")` mock HTTP 调用

**步骤 4：提交（AUTO_COMMIT=true）**
- Commit message: `feat: 实现 feishu_service 飞书推送服务（卡片构建+httpx推送+重试+状态更新）`
- 审计信息：
  - repo: `root`
    branch: `005-feishu-push`
    commit: `e573cc8`
    pr: `<TBD>`
    changed_files:
      - `backend/apps/intelligence/services/feishu_service.py`
      - `backend/apps/intelligence/tests/test_feishu_service.py`

---

### Task T4: API 端点（手动推送 + MD 下载）+ API 测试

- [x] **状态**：完成

**代码仓范围：**
- 根项目：`backend/apps/intelligence/`
- 子仓：无

**文件：**
- 修改：`backend/apps/intelligence/views.py`（新增 FeedPushView + FeedDownloadMdView）
- 修改：`backend/apps/intelligence/urls.py`（注册 2 个新路由）
- 修改：`backend/apps/intelligence/tests/test_feishu_service.py`（追加 API 测试）或 `backend/apps/intelligence/tests/test_api.py`（追加 API 测试）

**验收点：**
- [AC-006] POST /api/feeds/{id}/push 返回推送结果（push_status），非 CHANGED feed 返回 400
- [AC-007] GET /api/feeds/{id}/download_md 返回 MD 文件下载流（Content-Type: text/markdown）
- [AC-008] 下载链接 URL 格式为 /api/feeds/{id}/download_md

**步骤 1：写失败测试**
- 修改点：`backend/apps/intelligence/tests/test_api.py`（追加测试类）
- 测试内容：
  1. `FeedPushViewTest`：
     - 创建 CHANGED feed + webhook 非空项目，mock httpx.post 返回 200，POST /api/feeds/{id}/push，验证返回 200 + push_status=PUSHED
     - 创建 NO_CHANGE feed，POST /api/feeds/{id}/push，验证返回 400
  2. `FeedDownloadMdViewTest`：
     - 创建 feed，md_table_path 指向一个临时 MD 文件，GET /api/feeds/{id}/download_md，验证返回 200 + Content-Type 含 text/markdown + Content-Disposition 含 attachment
- Run: `cd /Users/melody/code/ai-workshop-005/backend && /Users/melody/code/ai-workshop/.venv/bin/python manage.py test apps.intelligence.tests.test_api.FeedPushViewTest apps.intelligence.tests.test_api.FeedDownloadMdViewTest --verbosity=2`
- Expected: FAIL（路由不存在，返回 404）

**步骤 2：写最少实现**
- 修改 `backend/apps/intelligence/views.py`：
  - 新增 `class FeedPushView(APIView)`：
    - permission_classes = [AllowAny]
    - post(self, request, pk)：获取 feed，调用 feishu_service.push_intelligence(pk)，返回 Response({"push_status": feed.push_status})
    - 非 CHANGED feed 返回 400 + {"detail": "Only CHANGED feeds can be pushed"}
  - 新增 `class FeedDownloadMdView(APIView)`：
    - permission_classes = [AllowAny]
    - get(self, request, pk)：获取 feed，检查 md_table_path 非空且文件存在，返回 FileResponse（content_type="text/markdown", as_attachment=True, filename=...）
    - 文件不存在返回 404
- 修改 `backend/apps/intelligence/urls.py`：
  - 新增 `path("feeds/<int:pk>/push", FeedPushView.as_view(), name="feed-push")`
  - 新增 `path("feeds/<int:pk>/download_md", FeedDownloadMdView.as_view(), name="feed-download-md")`
  - import 新增的 View 类

**步骤 3：运行验证**
- Run: `cd /Users/melody/code/ai-workshop-005/backend && /Users/melody/code/ai-workshop/.venv/bin/python manage.py test apps.intelligence.tests.test_api.FeedPushViewTest apps.intelligence.tests.test_api.FeedDownloadMdViewTest --verbosity=2`
- Expected: PASS（推送 API 返回 push_status，下载 API 返回文件流）
- Run 全量测试：`cd /Users/melody/code/ai-workshop-005/backend && /Users/melody/code/ai-workshop/.venv/bin/python manage.py test apps.intelligence --verbosity=2`
- Expected: PASS（所有测试通过，无回归）

**步骤 4：提交（AUTO_COMMIT=true）**
- Commit message: `feat: 新增飞书推送触发 API 和 MD 下载接口`
- 审计信息：
  - repo: `root`
    branch: `005-feishu-push`
    commit: `52a5743`
    pr: `<TBD>`
    changed_files:
      - `backend/apps/intelligence/views.py`
      - `backend/apps/intelligence/urls.py`
      - `backend/apps/intelligence/tests/test_api.py`

---

## Merge-back 待办清单（仅记录，不在本阶段执行）

- MB-001：feishu_service 推送服务实现完成后，将 `intelligence-models.md` 更新 push_status 字段不变量；将 `intelligence-api.md` 新增推送和下载端点契约。来源：本 Spec 005 的 Impact Analysis 7.1 受影响模块表。
