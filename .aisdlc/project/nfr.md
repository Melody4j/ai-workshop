# NFR

## 当前基线

- 质量门禁：
  - Django check
  - 后端应用级测试
  - 前端 build
- 部署形态：
  - 本地开发优先
  - 前后端分离但同仓
- 数据基线：
  - 当前数据库为 SQLite

## 长期护栏

1. 项目级“完成确认”至少要覆盖后端 check、测试与前端构建
2. 写操作安全口径需要有明确的同域 Session/CSRF 或等效方案
3. 前端质量门禁最终需要独立 lint / typecheck 入口

## Evidence

- [backend/config/settings.py](../../backend/config/settings.py)
- [frontend/package.json](../../frontend/package.json)
- [frontend/src/api/client.ts](../../frontend/src/api/client.ts)
- [verification/report-2026-07-08-unknown.md](../specs/001-competitive-intel-agent/verification/report-2026-07-08-unknown.md)

## Evidence Gaps

- 缺口：前端尚无 `lint` / `typecheck` scripts
  - 影响：当前只能通过 build 兜底基础静态检查
- 缺口：同域 Session/CSRF 方案未闭环
  - 影响：`AC-016` 仍是阻断项，安全门禁未达成稳定基线
- 缺口：LLM 延迟/成本 NFR 基线尚未实测（来源：Spec 004 MB-005）
  - 影响：3 次 LLM 调用总计延迟与 token 成本无数据，无法声明 NFR 达标
  - 计划：V 阶段实测后补充基线（3 次调用总计延迟目标 + 单 URL token 成本）
