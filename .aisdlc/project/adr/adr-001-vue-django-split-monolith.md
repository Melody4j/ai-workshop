# ADR-001：Vue SPA + Django Split-Monolith

## Status

Accepted

## Context

`001-competitive-intel-agent` 将产品前端统一收敛为 Vue 页面，同时保持 Django 作为业务 API 与后端编排单体。当前仓库处于绿地与 MVP 骨架阶段，需要在实现复杂度、产品一致性与后续扩展之间找到长期可复用的平衡点。

## Decision

- 产品页面统一由 Vue SPA 承担
- Django 作为 JSON API / 业务编排后端保留在单体中
- 当前数据库保持 SQLite
- 当前不引入消息队列或多服务拆分

## Invariants

1. 产品主入口不回退到 Django Admin / Jinja2 页面
2. 前后端在同一仓库协作，但职责分离
3. 单体后端承担 API、模型、未来调度与执行编排入口
4. 当前工程默认以本地开发和骨架交付为先，不额外增加基础设施复杂度

## Evidence

- [design/design.md](../../specs/001-competitive-intel-agent/design/design.md)
- [requirements/solution.md](../../specs/001-competitive-intel-agent/requirements/solution.md)
- [README.md](../../../README.md)

## Consequences

- 后续产品交互演进优先在前端完成
- 后续 merge-back 的 API/Data/Ops 护栏围绕 Vue + Django 分工展开
- 若未来拆服务，需要新增 ADR，而不是直接覆盖本决策
