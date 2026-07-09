# ai-workshop

## Competitive Intel Agent

当前仓库正在实现 `001-competitive-intel-agent` 的骨架版：

- 后端：`backend/`，Django + DRF + SQLite
- 前端：`frontend/`，Vue 3 + Vite
- 当前批次范围：任务 CRUD、报告列表/详情、评分 CRUD
- 当前批次不含：爬虫、LLM、调度、飞书联调

## Workspace Layout

```text
backend/   Django application, API, models, fixtures, tests
frontend/  Vue application, routes, pages, API client
```

## Planned Local Commands

后端：

```bash
.venv/bin/python backend/manage.py migrate
.venv/bin/python backend/manage.py runserver
.venv/bin/python backend/manage.py test
```

前端：

```bash
npm --prefix frontend install
npm --prefix frontend run dev
npm --prefix frontend run build
```
