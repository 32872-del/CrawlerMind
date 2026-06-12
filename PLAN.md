# CLM 当前主线计划

更新时间：2026-06-12

## 开发前死命令

每次开发前必须先读：

```text
PLAN.md
docs/plans/2026-05-20_AI_MANAGED_CRAWL_LOOP_V2_SHORT_TERM_PLAN.md
```

详细规则见：

```text
docs/process/DEVELOPMENT_STARTUP_RULE.md
```

读完后才能认领任务。所有开发必须围绕当前主线实事求是地形成闭环，不允许发散到孤立模块。

## 当前判断

CLM 没有偏离原始目标。它已经从早期 LangGraph 爬虫 pipeline 升级为：

```text
AI 编排 + CLM-native crawler backend + profile longrun + Web 工作台
```

当前整体进度约为 68% - 75%（更新于 2026-06-12）。

- Step 1 统一 Managed Crawl State：✅ 已完成
- Step 2 结构化 Action Plan 协议：✅ 已完成
- Step 3 Action Executor：✅ 90%（managed actions、execute_and_run、API 端点、contract extraction 已打通）
- Step 4 失败诊断与自动修复闭环：🟡 72%（diagnose_and_repair、QualityGate、修复重跑链路已成型，真实站点稳定性继续打磨）
- Step 5 前端全程可见：🟡 58%（中文工作台、任务详情、managed action/trace 可见性已接入，仍需更顺滑的一键闭环）
- Step 6 真实站点训练和收口：🟡 58%（E2E v1/v2、managed loop 覆盖训练已保留，成功率和动态站能力仍是重点）

## 下一阶段主线

### AI Managed Crawl Loop v2

目标：让 AI 不只是分析站点，而是贯穿完整采集过程。

现在最重要的下一步是：

```text
Step 4 + Step 6: 失败诊断/自动修复闭环真实站点硬化
```

重点不是再做孤立工具，而是让 managed loop 在真实站点上稳定提升成功率：

- 保留 direct crawl 已经能成功的路径，避免 managed loop 介入后退步。
- 强化 API/JSON/GraphQL 自动识别，尤其是纯 JSON array、Firebase、GraphQL endpoint。
- 把浏览器/XHR evidence、extraction contract discovery、API replay promotion 纳入同一修复闭环。
- 前端继续围绕“分析 -> 试跑 -> 诊断 -> 修复 -> 重跑 -> 导出”做一条可见主线。
