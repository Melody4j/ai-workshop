# 业务边界（稳定语义）

## In / Out

- In：
  - 任务 CRUD
  - 报告列表 / 详情查看
  - 评分 CRUD
  - 前后端分离的产品管理台骨架
- Out：
  - 爬虫采集
  - LLM 降噪与情报生成
  - 调度执行
  - 飞书推送
  - 真实报告落盘闭环

## 业务地图入口

- [../products/index.md](../products/index.md)

## 术语入口

- [./glossary.md](./glossary.md)

## Evidence Gaps（缺口清单）

- 缺口：项目级业务模块页尚未建立
  - 期望补齐到的粒度：按业务域沉淀 <= 6 个长期产品模块入口
  - 候选证据位置：`.aisdlc/project/products/*.md`
  - 影响：当前只能给出单一产品骨架入口，难以承载后续产品级 merge-back
- 缺口：当前业务边界仍是“骨架交付范围”，未覆盖真实监控闭环
  - 期望补齐到的粒度：调度、采集、LLM、飞书等闭环进入产品级 SSOT
  - 候选证据位置：[.aisdlc/specs/001-competitive-intel-agent/requirements/prd.md](../../specs/001-competitive-intel-agent/requirements/prd.md)
  - 影响：project 级 product 目前只能代表当前实现子集
