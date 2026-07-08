# Firecrawl 爬虫接入 实现计划（SSOT）

> **必需技能：** `spec-execute`（按批次执行本计划）
> **上下文获取：** 必须先执行 `spec-context` 获取上下文，定位 `{FEATURE_DIR}`，失败即停止

**目标：** 将采集层从 httpx+playwright+BeautifulSoup+html2text 迁移到 Firecrawl v2 crawl API，支持 AI 爬虫建议（crawl_hint）+ 多页爬取 + 合并单快照。

**范围：**
- In：crawler_service.py 重写（Firecrawl v2 REST API）、scheduler_service.py 调用点传 crawl_hint、serializers.py 放宽校验、settings.py + .env.example + base.txt 配置/依赖、前端 ProjectForm.vue + projects.ts + ProjectFormPage.vue 新增 crawl_hint、clear_snapshots 管理命令、测试重写
- Out：数据模型 schema 变更（JSONField 兼容）、diff 熔断逻辑、LLM 链路（004）、飞书推送（005）、调度器（scheduler.py 不变）

**架构：** crawler_service 整文件重写为 Firecrawl v2 REST API 调用（POST /v2/crawl 传 prompt + GET /v2/crawl/{id} 轮询），多页结果按 metadata.sourceURL 字典序拼接为单快照。crawl_hint 非空时作为 prompt 传入；0 页结果时自动回退无 prompt 重 crawl。保留 `fetch_and_clean(url, crawl_hint="") -> tuple[str, str]` 签名兼容。

**验收口径：** solution.md AC-001~AC-010（10 条验收标准）

**影响范围：**
| 模块 | 影响类型 | 关键不变量 |
|------|----------|-----------|
| intelligence-crawler（crawler_service.py） | **重写** | 修订-6：httpx+playwright → Firecrawl v2 crawl API |
| intelligence-scheduler（scheduler_service.py） | 修改调用 | L85 调用点传 crawl_hint |
| intelligence-api（serializers.py） | 修改校验 | 修订-7：competitor_urls 新增可选 crawl_hint |
| intelligence-models（models.py） | 无 schema 改动 | JSONField 兼容 crawl_hint |
| frontend-console（ProjectForm.vue） | 新增输入 | competitor_urls 编辑表单加 crawl_hint |
| config（settings.py） | 新增配置 | FIRECRAWL_API_KEY |
| dependencies（base.txt） | 依赖替换 | 移除 httpx/playwright/BS/html2text，新增 firecrawl-py |

**需遵守的不变量：**
- 修订-6（不变量7）：采集统一使用 Firecrawl 云端 crawl API，不再使用 httpx/Playwright/BeautifulSoup/html2text
- 修订-7（不变量10）：competitor_urls 每项 {url, title, crawl_hint?}，crawl_hint 可选
- 不变量4：采集失败写空快照/ERROR_CRAWL
- 不变量5：006 范围止步 DataSnapshot，不写 IntelligenceFeed
- 不变量6：空 URL 跳过

**子仓范围：** 无

---

## TL;DR

将 crawler_service 从 httpx+playwright+BS+html2text 整文件重写为 Firecrawl v2 crawl API 调用，支持 crawl_hint prompt + 多页拼接 + 0 页回退。同时修改 scheduler 调用点传 crawl_hint、serializer 放宽校验、前端表单加输入框、配置/依赖替换、清理历史快照命令、测试重写。

## 范围与边界

- **In**：crawler_service 重写 / scheduler 调用点 / serializer 放宽 / settings+.env+base.txt / 前端 3 文件 / clear_snapshots 命令 / 测试重写
- **Out**：数据模型 schema / diff 熔断 / LLM 链路 / 飞书推送 / 调度器

## 影响范围与约束

### 受影响模块清单

| 模块 | 影响类型 | 来源 |
|------|----------|------|
| intelligence-crawler | **重写** | solution.md#impact-analysis 7.1 |
| intelligence-scheduler | 修改调用 | solution.md#impact-analysis 7.1 |
| intelligence-api | 修改校验 | solution.md#impact-analysis 7.1 |
| intelligence-models | 无 schema 改动 | solution.md#impact-analysis 7.1 |
| frontend-console | 新增输入 | solution.md#impact-analysis 7.1 |
| config | 新增配置 | solution.md#impact-analysis 7.1 |
| dependencies | 依赖替换 | solution.md#impact-analysis 7.1 |

### 需遵守的 API/Data 契约不变量

1. **修订-6**（来源：intelligence-scheduler 不变量3）：采集统一使用 Firecrawl v2 crawl API，不再使用 httpx/Playwright/BeautifulSoup/html2text
2. **修订-7**（来源：intelligence-models 不变量1）：competitor_urls 每项 {url, title, crawl_hint?}
3. **不变量4**（来源：intelligence-scheduler）：采集失败返回 ("","") → ERROR_CRAWL
4. **不变量5**（来源：intelligence-scheduler）：006 不写 IntelligenceFeed
5. **不变量6**（来源：intelligence-scheduler）：空 URL 跳过

### 跨模块影响

- **crawler_service → scheduler_service**：`fetch_and_clean(url)` 签名扩展为 `fetch_and_clean(url, crawl_hint="")`，scheduler L85 调用点需传 crawl_hint
- **serializer 放宽 → 前端配合**：serializer 允许 crawl_hint 可选；前端新增 crawl_hint 输入并提交
- **依赖移除 → 测试重写**：test_crawler_service.py（6 用例 mock httpx/playwright）重写为 mock requests；test_scheduler_service.py（23 用例 mock fetch_and_clean）需更新 mock 签名
- **与 004（LLM）合并已完成**：dev 已合并到 006 分支，settings.py / .env.example / base.txt 已含 004 的 LLM 配置，006 追加 Firecrawl 配置

## 代码工作区清单

无子仓。仅根项目。

## 里程碑与节奏

| 批次 | 任务 | 交付物 | 预估 |
|------|------|--------|------|
| Batch 1 | T1-T3 后端配置+依赖+crawler重写 | crawler_service.py + settings + .env + base.txt | 核心 |
| Batch 2 | T4-T5 scheduler+serializer | scheduler_service.py + serializers.py | 中等 |
| Batch 3 | T6-T7 前端表单 | ProjectForm.vue + projects.ts + ProjectFormPage.vue | 中等 |
| Batch 4 | T8 清理命令 | clear_snapshots management command | 轻量 |
| Batch 5 | T9-T11 测试重写 | test_crawler_service + test_scheduler_service + test_api | 中等 |
| Batch 6 | T12 全量验证 | 全量测试通过 + 前端构建 | 轻量 |

## 依赖与资源

- Firecrawl API key（用户提供：fc-d195b6ed794d4519a3f3f341bc08b1b4）
- Firecrawl v2 REST API（https://api.firecrawl.dev/v2/crawl）
- 已有：python-dotenv + load_dotenv（004 已加入 settings.py）

## 风险与验证

| ID | 风险 | 验证方式 | Owner | 截止 |
|----|------|----------|-------|------|
| V-011 | AI 生成 includePaths 导致 0 页 | 0 页时回退无 prompt 重 crawl | DEV | I2 中 |
| V-001-T | 120s 超时是否够 | 实测 crawl 耗时 | DEV | I2 中 |
| V-004 | 前端 crawl_hint 回填 | 手动测试新建/编辑/回填 | DEV | I2 中 |
| V-009 | 额度消耗 1 credit/页 | 5竞品×limit=10=50/日 | DEV | I2 前 |

## 验收口径

- AC-001：crawler_service 调 Firecrawl v2 crawl API，返回拼接 (raw_html, clean_md)；crawl_hint 非空时作 prompt 传入
- AC-002：crawl_hint 为空时不传 prompt，正常爬取
- AC-003：轮询 120s 超时返回 ("","") → ERROR_CRAWL
- AC-004：多页按 metadata.sourceURL 字典序拼接
- AC-005：一 URL 一快照，双字段落盘
- AC-006：competitor_urls 支持可选 crawl_hint，serializer 通过
- AC-007：前端 crawl_hint 输入框，新建/编辑/回填正确
- AC-008：clear_snapshots 管理命令可清理
- AC-009：httpx/playwright/BS/html2text 移除，firecrawl-py 新增
- AC-010：FIRECRAWL_API_KEY 从环境变量读取

## NEEDS CLARIFICATION

无。所有不确定性已在 R1/D1/D2 阶段消除。V-005-REST 已实测关闭。

---

## 任务清单（SSOT）

### Task T1: 配置 Firecrawl API key + 依赖替换

- [ ] **状态**：未开始

**代码仓范围：**
- 根项目

**文件：**
- 修改：`backend/config/settings.py`（L145 后追加 Firecrawl 配置）
- 修改：`backend/.env.example`（L7 后追加 Firecrawl env vars）
- 修改：`backend/requirements/base.txt`（移除 L4-7 httpx/html2text/beautifulsoup4/playwright，追加 firecrawl-py）

**验收点：**
- [ ] settings.py 含 `FIRECRAWL_API_KEY = os.environ.get("FIRECRAWL_API_KEY", "")`
- [ ] .env.example 含 `FIRECRAWL_API_KEY=`
- [ ] base.txt 不含 httpx/html2text/beautifulsoup4/playwright，含 firecrawl-py
- [ ] `pip install -r backend/requirements/base.txt` 成功

**步骤 1：修改 settings.py**
- 在 L145（`LLM_MAX_TOKENS` 行）后追加：
```python

# Firecrawl 配置
FIRECRAWL_API_KEY = os.environ.get("FIRECRAWL_API_KEY", "")
FIRECRAWL_API_URL = "https://api.firecrawl.dev"
```

**步骤 2：修改 .env.example**
- 在 L7 后追加：
```

# Firecrawl 配置
FIRECRAWL_API_KEY=
```

**步骤 3：修改 base.txt**
- 移除 L4-L7（httpx, html2text, beautifulsoup4, playwright）
- 在 L14（python-dotenv）后追加：
```
# Firecrawl 爬虫
firecrawl-py>=1.0.0
requests>=2.31.0
```

**步骤 4：安装依赖**
- Run: `cd /Users/melody/code/ai-workshop-006 && .venv/bin/pip install --no-user -r backend/requirements/base.txt`
- Expected: 安装成功，无报错

**步骤 5：提交**
- Commit message: `feat: 配置 Firecrawl API key + 依赖替换（移除 httpx/playwright/BS/html2text）`

---

### Task T2: 重写 crawler_service.py — Firecrawl v2 crawl API

- [ ] **状态**：未开始

**代码仓范围：**
- 根项目

**文件：**
- 重写：`backend/apps/intelligence/services/crawler_service.py`（整文件 85 行 → 新文件）

**验收点：**
- [ ] `fetch_with_firecrawl(url, crawl_hint="")` 返回 `(raw_html, clean_md)`，失败返回 `("", "")`
- [ ] crawl_hint 非空时作为 prompt 传入 POST /v2/crawl
- [ ] crawl_hint 为空时不传 prompt
- [ ] 0 页结果时自动回退无 prompt 重 crawl
- [ ] 多页按 `metadata.sourceURL` 字典序拼接
- [ ] 轮询间隔 5s + 总超时 120s + 429 Retry-After 处理

**步骤 1：重写 crawler_service.py**
- 整文件重写，核心结构：
```python
import logging
import time

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

FIRECRAWL_BASE = settings.FIRECRAWL_API_URL  # https://api.firecrawl.dev
POLL_INTERVAL = 5       # 秒
POLL_TIMEOUT = 120      # 秒
CRAWL_LIMIT = 10        # 最大页数


def fetch_with_firecrawl(url: str, crawl_hint: str = "") -> tuple[str, str]:
    """
    使用 Firecrawl v2 crawl API 采集 URL。
    返回 (raw_html, clean_md)。
    crawl_hint 非空时作为 prompt 传入。
    失败返回 ("", "")。
    """
    # 1. 带 prompt crawl（如果 crawl_hint 非空）
    if crawl_hint.strip():
        raw_html, clean_md = _crawl_and_merge(url, crawl_hint.strip())
        if raw_html or clean_md:
            return (raw_html, clean_md)
        # 0 页 → 回退无 prompt
        logger.warning(f"crawl 带 prompt 返回 0 页，回退无 prompt: {url}")

    # 2. 无 prompt crawl
    return _crawl_and_merge(url, "")


def _crawl_and_merge(url: str, prompt: str) -> tuple[str, str]:
    """启动 crawl → 轮询 → 合并多页。"""
    try:
        job_id = _start_crawl(url, prompt)
        if not job_id:
            return ("", "")

        documents = _poll_crawl(job_id)
        if not documents:
            return ("", "")

        return _merge_documents(documents)
    except Exception as e:
        logger.error(f"Firecrawl crawl 异常: {url} - {e}", exc_info=True)
        return ("", "")


def _start_crawl(url: str, prompt: str) -> str:
    """POST /v2/crawl，返回 job_id。"""
    headers = {
        "Authorization": f"Bearer {settings.FIRECRAWL_API_KEY}",
        "Content-Type": "application/json",
    }
    body = {
        "url": url,
        "limit": CRAWL_LIMIT,
        "scrapeOptions": {"formats": ["markdown", "html"]},
    }
    if prompt:
        body["prompt"] = prompt

    resp = requests.post(f"{FIRECRAWL_BASE}/v2/crawl", json=body, headers=headers, timeout=30)
    if resp.status_code == 429:
        retry_after = int(resp.headers.get("Retry-After", "15"))
        logger.warning(f"Firecrawl 限流，等待 {retry_after}s")
        time.sleep(retry_after)
        resp = requests.post(f"{FIRECRAWL_BASE}/v2/crawl", json=body, headers=headers, timeout=30)

    if not resp.ok:
        logger.error(f"Firecrawl start crawl 失败: {resp.status_code} {resp.text}")
        return ""

    data = resp.json()
    if not data.get("success"):
        logger.error(f"Firecrawl start crawl 不成功: {data}")
        return ""

    return data.get("id", "")


def _poll_crawl(job_id: str) -> list:
    """GET /v2/crawl/{id} 轮询直到完成/失败/超时。"""
    headers = {"Authorization": f"Bearer {settings.FIRECRAWL_API_KEY}"}
    deadline = time.time() + POLL_TIMEOUT

    while time.time() < deadline:
        resp = requests.get(f"{FIRECRAWL_BASE}/v2/crawl/{job_id}", headers=headers, timeout=30)

        if resp.status_code == 429:
            retry_after = int(resp.headers.get("Retry-After", "15"))
            time.sleep(min(retry_after, POLL_TIMEOUT))
            continue

        if not resp.ok:
            logger.error(f"Firecrawl poll 失败: {resp.status_code}")
            return []

        data = resp.json()
        status = data.get("status", "")

        if status == "completed":
            return data.get("data", [])
        elif status in ("failed", "cancelled"):
            logger.error(f"Firecrawl job {status}: {job_id}")
            return []

        time.sleep(POLL_INTERVAL)

    logger.error(f"Firecrawl 轮询超时 {POLL_TIMEOUT}s: {job_id}")
    return []


def _merge_documents(documents: list) -> tuple[str, str]:
    """按 metadata.sourceURL 字典序排序，拼接 markdown + html。"""
    def get_url(doc):
        return doc.get("metadata", {}).get("sourceURL", "")

    sorted_docs = sorted(documents, key=get_url)

    md_parts = []
    html_parts = []
    for doc in sorted_docs:
        url = get_url(doc)
        md = doc.get("markdown", "")
        html = doc.get("html", "")
        if md:
            md_parts.append(f"\n\n---\nsource: {url}\n\n{md}")
        if html:
            html_parts.append(f"\n<!-- {url} -->\n{html}")

    return ("\n".join(html_parts), "\n".join(md_parts))


# 兼容旧调用签名（scheduler_service 逐步迁移）
def fetch_and_clean(url: str, crawl_hint: str = "") -> tuple[str, str]:
    """兼容旧签名的代理函数。"""
    return fetch_with_firecrawl(url, crawl_hint)
```

**步骤 2：验证导入**
- Run: `cd /Users/melody/code/ai-workshop-006 && .venv/bin/python -c "from apps.intelligence.services.crawler_service import fetch_with_firecrawl; print('OK')"`
- Expected: `OK`

**步骤 3：提交**
- Commit message: `feat: 重写 crawler_service 为 Firecrawl v2 crawl API（prompt + 轮询 + 多页拼接 + 0页回退）`

---

### Task T3: 验证 crawler_service 单元逻辑（快速冒烟）

- [ ] **状态**：未开始

**文件：**
- 创建：`backend/apps/intelligence/tests/test_crawler_service.py`（重写，替换旧 6 用例）

**验收点：**
- [ ] mock requests.post + requests.get 测试 _start_crawl / _poll_crawl / _merge_documents
- [ ] 测 crawl_hint 非空时 prompt 传入 body
- [ ] 测 crawl_hint 为空时 prompt 不传入 body
- [ ] 测 0 页结果回退无 prompt
- [ ] 测多页按 sourceURL 字典序拼接
- [ ] 测超时返回空
- [ ] 测 429 限流重试

**步骤 1：写测试文件**
- 重写 `test_crawler_service.py`，mock `requests.post` 和 `requests.get`
- 测试用例：
  1. `test_start_crawl_with_prompt` — crawl_hint 非空时 body 含 prompt
  2. `test_start_crawl_without_prompt` — crawl_hint 为空时 body 不含 prompt
  3. `test_poll_crawl_completed` — 轮询到 completed 返回 documents
  4. `test_poll_crawl_timeout` — 超时返回 []
  5. `test_poll_crawl_failed` — status=failed 返回 []
  6. `test_merge_documents_sorted_by_source_url` — 按 sourceURL 字典序拼接
  7. `test_fetch_with_firecrawl_zero_results_fallback` — 0 页回退无 prompt
  8. `test_fetch_with_firecrawl_network_error_returns_empty` — 网络异常返回 ("","")
  9. `test_429_retry` — 429 限流后重试成功

**步骤 2：运行测试**
- Run: `cd /Users/melody/code/ai-workshop-006/backend && ../.venv/bin/python manage.py test apps.intelligence.tests.test_crawler_service --verbosity=2`
- Expected: 9 tests pass

**步骤 3：提交**
- Commit message: `test: 重写 crawler_service 测试为 mock requests（9 用例）`

---

### Task T4: 修改 scheduler_service.py 调用点传 crawl_hint

- [ ] **状态**：未开始

**文件：**
- 修改：`backend/apps/intelligence/services/scheduler_service.py`（L49-57 区域）

**验收点：**
- [ ] L49 循环中从 `item` 取 `crawl_hint`
- [ ] `_process_url()` 签名增加 `crawl_hint` 参数
- [ ] L85 调用 `crawler_service.fetch_and_clean(url, crawl_hint)` 传入 crawl_hint

**步骤 1：修改 scheduler_service.py**
- L49-55 区域，在 `title = (item or {}).get("title", "")` 后追加：
```python
            crawl_hint = (item or {}).get("crawl_hint", "")
```
- L57 `_process_url` 调用改为：
```python
                _process_url(project, url, title, now, crawl_hint)
```
- L78 `_process_url` 定义改为：
```python
def _process_url(project, url, title, now, crawl_hint=""):
```
- L85 调用改为：
```python
        raw_md, clean_md = crawler_service.fetch_and_clean(url, crawl_hint)
```

**步骤 2：运行现有 scheduler 测试**
- Run: `cd /Users/melody/code/ai-workshop-006/backend && ../.venv/bin/python manage.py test apps.intelligence.tests.test_scheduler_service --verbosity=2`
- Expected: 现有 23 个测试可能因 mock 签名变更而部分失败，需在 T10 中修复

**步骤 3：提交**
- Commit message: `feat: scheduler_service 传 crawl_hint 到 crawler_service`

---

### Task T5: 修改 serializers.py 放宽 competitor_urls 校验

- [ ] **状态**：未开始

**文件：**
- 修改：`backend/apps/intelligence/serializers.py`（L37-47 validate_competitor_urls）

**验收点：**
- [ ] validate_competitor_urls 允许 crawl_hint 可选字段
- [ ] crawl_hint 为字符串时通过，非字符串时报错
- [ ] 不含 crawl_hint 的旧数据仍通过

**步骤 1：修改 validate_competitor_urls**
- L44 后追加 crawl_hint 可选校验：
```python
            if "crawl_hint" in item and not isinstance(item.get("crawl_hint", ""), str):
                raise serializers.ValidationError("crawl_hint must be a string when provided.")
```

**步骤 2：运行 API 测试**
- Run: `cd /Users/melody/code/ai-workshop-006/backend && ../.venv/bin/python manage.py test apps.intelligence.tests.test_api --verbosity=2`
- Expected: 现有测试通过（crawl_hint 可选，不影响旧数据）

**步骤 3：提交**
- Commit message: `feat: serializer 放宽 competitor_urls 允许可选 crawl_hint`

---

### Task T6: 前端 — projects.ts 新增 crawl_hint 类型

- [ ] **状态**：未开始

**文件：**
- 修改：`frontend/src/api/projects.ts`（L3-6 CompetitorInput）

**验收点：**
- [ ] CompetitorInput 含 `crawl_hint?: string`

**步骤 1：修改 CompetitorInput**
- L3-6 改为：
```typescript
export interface CompetitorInput {
  title: string
  url: string
  crawl_hint?: string
}
```

**步骤 2：提交**
- Commit message: `feat: 前端 CompetitorInput 新增 crawl_hint 可选字段`

---

### Task T7: 前端 — ProjectForm.vue + ProjectFormPage.vue 新增 crawl_hint 输入

- [ ] **状态**：未开始

**文件：**
- 修改：`frontend/src/components/projects/ProjectForm.vue`（5 处改动）
- 修改：`frontend/src/views/projects/ProjectFormPage.vue`（2 处改动）

**验收点：**
- [ ] CompetitorFormRow 接口含 crawl_hint
- [ ] createEmptyCompetitor() 含 crawl_hint: ""
- [ ] mergeCompetitors() 回填 crawl_hint
- [ ] onSubmit() 提交 crawl_hint
- [ ] 模板含 crawl_hint 输入框（el-input textarea）
- [ ] ProjectFormPage.vue emptyProject + 非编辑分支含 crawl_hint

**步骤 1：修改 ProjectForm.vue**

1a. CompetitorFormRow 接口（L13-18）追加：
```typescript
  crawl_hint: string
```

1b. createEmptyCompetitor（L44-51）追加：
```typescript
    crawl_hint: "",
```

1c. mergeCompetitors（L62-67）return 追加：
```typescript
      crawl_hint: (item as any).crawl_hint ?? "",
```

1d. onSubmit（L173-176）competitorUrls 映射追加：
```typescript
    crawl_hint: item.crawl_hint.trim(),
```

1e. 模板（L269 后）追加 crawl_hint 输入框：
```html
              <div class="field-block">
                <div class="field-header">
                  <span>爬虫建议（可选）</span>
                </div>
                <el-input
                  v-model="competitor.crawl_hint"
                  type="textarea"
                  :rows="2"
                  placeholder="帮我爬取网页的主页数据和定价数据"
                />
              </div>
```

**步骤 2：修改 ProjectFormPage.vue**

2a. emptyProject（L20）追加 crawl_hint：
```typescript
  competitor_urls: [{ title: "", url: "", crawl_hint: "" }],
```

2b. 非编辑分支（L39）追加 crawl_hint：
```typescript
      competitor_urls: [{ title: "", url: "", crawl_hint: "" }],
```

**步骤 3：前端构建验证**
- Run: `cd /Users/melody/code/ai-workshop-006/frontend && npm run build`
- Expected: 构建成功无报错

**步骤 4：提交**
- Commit message: `feat: 前端 ProjectForm 新增 crawl_hint 输入框（新建/编辑/回填）`

---

### Task T8: 新增 clear_snapshots 管理命令

- [ ] **状态**：未开始

**文件：**
- 创建：`backend/apps/intelligence/management/__init__.py`
- 创建：`backend/apps/intelligence/management/commands/__init__.py`
- 创建：`backend/apps/intelligence/management/commands/clear_snapshots.py`

**验收点：**
- [ ] `python manage.py clear_snapshots` 删除所有 DataSnapshot + 关联文件
- [ ] `python manage.py clear_snapshots --project-id N` 只删指定项目
- [ ] 删除文件时跳过路径为空的记录
- [ ] 删除后输出删除数量

**步骤 1：创建目录 + __init__.py**
- 创建 `backend/apps/intelligence/management/__init__.py`（空文件）
- 创建 `backend/apps/intelligence/management/commands/__init__.py`（空文件）

**步骤 2：写 clear_snapshots.py**
```python
"""清理历史快照（DataSnapshot + 关联文件）。

用法：
  python manage.py clear_snapshots            # 清理所有项目
  python manage.py clear_snapshots --project-id 1  # 只清理指定项目
"""
import os

from django.core.management.base import BaseCommand
from django.db import models

from apps.intelligence.models import DataSnapshot


class Command(BaseCommand):
    help = "清理历史快照（DataSnapshot 记录 + 关联文件）"

    def add_arguments(self, parser):
        parser.add_argument(
            "--project-id",
            type=int,
            default=None,
            help="只清理指定项目的快照（不指定则清理全部）",
        )

    def handle(self, *args, **options):
        project_id = options.get("project_id")
        qs = DataSnapshot.objects.all()
        if project_id:
            qs = qs.filter(project_id=project_id)

        total = qs.count()
        if total == 0:
            self.stdout.write(self.style.WARNING("无快照可清理。"))
            return

        files_deleted = 0
        for snapshot in qs:
            for path_field in ["raw_html_path", "clean_md_path"]:
                path = getattr(snapshot, path_field, "")
                if path and os.path.exists(path):
                    try:
                        os.remove(path)
                        files_deleted += 1
                    except OSError as e:
                        self.stderr.write(f"删除文件失败: {path} - {e}")

        qs.delete()
        self.stdout.write(
            self.style.SUCCESS(f"已清理 {total} 条快照，删除 {files_deleted} 个文件。")
        )
```

**步骤 3：运行验证**
- Run: `cd /Users/melody/code/ai-workshop-006/backend && ../.venv/bin/python manage.py clear_snapshots --help`
- Expected: 显示帮助信息

**步骤 4：提交**
- Commit message: `feat: 新增 clear_snapshots 管理命令（清理历史快照+关联文件）`

---

### Task T9: 重写 test_crawler_service.py

- [ ] **状态**：未开始

**文件：**
- 重写：`backend/apps/intelligence/tests/test_crawler_service.py`

**验收点：**
- [ ] 9 个测试用例全部通过
- [ ] mock requests.post + requests.get，不发真实网络请求

> 注：T3 中已创建测试文件，T9 确认并补充遗漏用例。如 T3 已完整，T9 可合并。

**步骤 1：运行测试确认**
- Run: `cd /Users/melody/code/ai-workshop-006/backend && ../.venv/bin/python manage.py test apps.intelligence.tests.test_crawler_service --verbosity=2`
- Expected: 9 tests OK

**步骤 2：提交（如有补充）**
- Commit message: `test: 补充 crawler_service 测试用例`

---

### Task T10: 更新 test_scheduler_service.py mock 签名

- [ ] **状态**：未开始

**文件：**
- 修改：`backend/apps/intelligence/tests/test_scheduler_service.py`（23 个测试）

**验收点：**
- [ ] 所有 mock `fetch_and_clean` 的调用更新为新签名 `fetch_and_clean(url, crawl_hint="")`
- [ ] 23 个测试全部通过
- [ ] mock patch 路径不变：`apps.intelligence.services.scheduler_service.crawler_service.fetch_and_clean`

**步骤 1：检查 mock 调用签名**
- 搜索所有 `fetch_and_clean` 的 mock 调用
- 将 `mock.return_value = ("raw", "clean")` 保持不变
- 将 `mock.assert_called_once_with(url)` 改为 `mock.assert_called_once_with(url, "")` 或 `mock.assert_called_once()` （放宽断言）

**步骤 2：运行测试**
- Run: `cd /Users/melody/code/ai-workshop-006/backend && ../.venv/bin/python manage.py test apps.intelligence.tests.test_scheduler_service --verbosity=2`
- Expected: 23 tests OK

**步骤 3：提交**
- Commit message: `test: 更新 scheduler_service 测试 mock 签名（fetch_and_clean 新增 crawl_hint 参数）`

---

### Task T11: 更新 test_api.py — crawl_hint 字段测试

- [ ] **状态**：未开始

**文件：**
- 修改：`backend/apps/intelligence/tests/test_api.py`

**验收点：**
- [ ] 新增测试：创建项目时 competitor_urls 含 crawl_hint 字段
- [ ] 新增测试：创建项目时 competitor_urls 不含 crawl_hint 字段（兼容旧数据）
- [ ] 现有 13 个测试全部通过

**步骤 1：新增 crawl_hint 相关测试**
- 在 `ProjectApiTests` 中新增：
```python
    def test_create_project_with_crawl_hint(self):
        """competitor_urls 含 crawl_hint 字段时创建成功"""
        payload = {
            "project_name": "测试 crawl_hint",
            "competitor_urls": [
                {"title": "Lovable", "url": "https://lovable.dev", "crawl_hint": "爬取主页和定价页"}
            ],
            ...
        }
        # assert 201

    def test_create_project_without_crawl_hint(self):
        """competitor_urls 不含 crawl_hint 字段时创建成功（兼容旧数据）"""
        # payload 只含 title + url
        # assert 201
```

**步骤 2：运行测试**
- Run: `cd /Users/melody/code/ai-workshop-006/backend && ../.venv/bin/python manage.py test apps.intelligence.tests.test_api --verbosity=2`
- Expected: 全部通过

**步骤 3：提交**
- Commit message: `test: 新增 crawl_hint 字段 API 测试（含/不含 crawl_hint 兼容验证）`

---

### Task T12: 全量测试 + 前端构建验证

- [ ] **状态**：未开始

**验收点：**
- [ ] 后端全量测试通过（排除 e2e 网络测试）
- [ ] 前端构建成功
- [ ] `python manage.py check` 无错误

**步骤 1：后端全量测试**
- Run: `cd /Users/melody/code/ai-workshop-006/backend && ../.venv/bin/python manage.py test apps.intelligence.tests --exclude-tag=e2e --exclude-tag=network --verbosity=2`
- Expected: 全部通过

**步骤 2：Django check**
- Run: `cd /Users/melody/code/ai-workshop-006/backend && ../.venv/bin/python manage.py check`
- Expected: no issues

**步骤 3：前端构建**
- Run: `cd /Users/melody/code/ai-workshop-006/frontend && npm run build`
- Expected: 构建成功

**步骤 4：提交**
- Commit message: `chore: 全量验证通过（后端测试 + Django check + 前端构建）`

---

### 审计信息汇总

| Task | repo | branch | commit | changed_files |
|------|------|--------|--------|---------------|
| T1 | root | 006-firecrawl-crawler | `<TBD>` | settings.py, .env.example, base.txt |
| T2 | root | 006-firecrawl-crawler | `<TBD>` | crawler_service.py |
| T3 | root | 006-firecrawl-crawler | `<TBD>` | test_crawler_service.py |
| T4 | root | 006-firecrawl-crawler | `<TBD>` | scheduler_service.py |
| T5 | root | 006-firecrawl-crawler | `<TBD>` | serializers.py |
| T6 | root | 006-firecrawl-crawler | `<TBD>` | projects.ts |
| T7 | root | 006-firecrawl-crawler | `<TBD>` | ProjectForm.vue, ProjectFormPage.vue |
| T8 | root | 006-firecrawl-crawler | `<TBD>` | management/commands/clear_snapshots.py |
| T9 | root | 006-firecrawl-crawler | `<TBD>` | test_crawler_service.py |
| T10 | root | 006-firecrawl-crawler | `<TBD>` | test_scheduler_service.py |
| T11 | root | 006-firecrawl-crawler | `<TBD>` | test_api.py |
| T12 | root | 006-firecrawl-crawler | `<TBD>` | — |
