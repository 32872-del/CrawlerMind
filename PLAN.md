# CLM 当前主线计划

更新时间：2026-05-20

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

当前整体进度约为 60% - 68%。

- Step 1 统一 Managed Crawl State：已完成
- Step 2 结构化 Action Plan 协议：已完成
- Step 3 Action Executor：下一步
- Step 4 失败诊断与自动修复闭环：后续
- Step 5 前端全程可见：后续
- Step 6 真实站点训练和收口：后续

## 下一阶段主线

### AI Managed Crawl Loop v2

目标：让 AI 不只是分析站点，而是贯穿完整采集过程。

现在最重要的下一步是：

```text
Step 3: Action Executor
```

把结构化动作真正接到现有后端能力上，形成可见、可修复、可重跑的闭环。
