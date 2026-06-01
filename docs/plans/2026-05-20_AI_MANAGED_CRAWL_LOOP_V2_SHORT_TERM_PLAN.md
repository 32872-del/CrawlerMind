# AI Managed Crawl Loop v2 短期开发重点
日期：2026-05-20

## 一句话结论

CLM 当前最大问题不是“没有采集工具”，而是“AI 还没有一个能全程驾驶这些工具的闭环流程”。

目前后端已经有很多硬能力：静态抓取、浏览器渲染、API/XHR 观察、GraphQL/POST replay、replay diagnostics、profile longrun、managed actions、evidence pack、导出、工作台 API。真正缺的是把这些能力整理成一条 AI 可以持续观察、决策、执行、修复和重跑的主流程。

短期开发重点应定为：

```text
AI Managed Crawl Loop v2
```

目标不是再零散加工具，而是让 AI 从“顾问”变成“采集主管”。

## 当前问题拆解

### 1. 工具空间已经不少

CLM 已经有这些能力：

- HTTP/static fetch
- Playwright/native browser runtime
- parser/adaptive selector/selector memory
- browser network observer
- API/XHR/GraphQL replay
- replay diagnostics
- executable API replay runtime
- SiteProfile/profile ecommerce/profile longrun
- BatchRunner/checkpoint/frontier/product store
- managed actions
- evidence pack
- LLM provider/model list
- FastAPI workflow API
- Chinese frontend workbench

所以当前瓶颈不是“厨房里没有锅和刀”，而是“还没有一套让模型按步骤做菜的操作台”。

### 2. 最大断点在流程闭环

当前流程大致是：

```text
分析一部分证据 -> LLM 给建议或 patch -> 后端执行一部分
```

目标流程应该是：

```text
采样证据
-> AI 判断站点和任务
-> AI 输出结构化动作
-> 后端执行动作
-> 生成运行结果和质量报告
-> AI 判断失败原因
-> AI 生成修复 patch
-> 自动重跑
-> 输出最终数据、成功率、漏采原因
```

这里缺的不是单点工具，而是统一的状态、统一的动作、统一的事件流和统一的修复重跑机制。

### 3. 前端可见性不足会放大问题

用户现在看不到 AI 在每一步到底判断了什么，也看不到它为什么决定用 API、浏览器、profile patch 或 replay patch。于是即使后端执行了一些智能动作，产品体验上仍然像“程序自己瞎跑”。

所以 v2 必须同时解决：

- 后端 AI 闭环
- 前端过程可见
- 失败后可解释
- 修复动作可追踪

## 目标架构

目标主流程：

```text
User Goal / Site URL / Optional Catalog / Fields
  -> Evidence Pack Builder
  -> LLM Decision Step
  -> Structured Action Plan
  -> Action Executor
  -> Runtime / Profile / Replay / Browser Execution
  -> Quality & Coverage Diagnosis
  -> Repair Plan
  -> Rerun / Export
  -> Final Report
```

每一步都必须产生结构化事件：

```text
step_id
stage
input_snapshot
evidence
llm_trace
decision
actions
execution_result
quality_result
next_step
```

这样前端才能完整显示“AI 正在做什么”。

## 需要几步完成

建议拆成 6 步完成。

### Step 1：统一 Managed Crawl State

目标：给 AI 一个完整、稳定、可传递的任务状态。

要做：

- 定义 `ManagedCrawlState` 或等价结构。
- 聚合用户目标、站点 URL、目录、字段、profile、runtime evidence、历史动作、运行结果。
- 把已有 evidence pack、job status、profile report、quality report 整合进去。
- 每一步都读写同一个状态，不再散落在不同 API 返回值里。

验收：

- 任意任务能导出一个完整 state JSON。
- state 中能看到目录、字段、策略、运行、失败、修复上下文。

工作量：中等，约 0.5 - 1 天。

### Step 2：定义结构化 Action Plan 协议

目标：让 AI 输出可执行动作，不只是建议文本。

要做：

- 定义动作类型，例如：
  - `analyze_site`
  - `select_catalog`
  - `resolve_fields`
  - `switch_runtime`
  - `patch_profile`
  - `patch_selector`
  - `promote_xhr_to_api`
  - `apply_replay_runtime`
  - `run_test`
  - `rerun_failed`
  - `export_results`
- 每个 action 要有 schema、allowlist、验证规则。
- LLM 输出必须被解析成 action plan。
- 非法动作拒绝，不进入执行层。

验收：

- Fake LLM 能输出 3 - 5 个动作并被后端执行。
- 非法字段、危险 patch、无效 runtime 被拒绝。

工作量：中等偏大，约 1 天。

### Step 3：打通 Action Executor

目标：让结构化动作真正调用现有后端工具。

要做：

- action -> product workflow API
- action -> profile patch
- action -> browser/API replay runtime
- action -> test/full run
- action -> export
- action -> coverage/quality diagnosis
- action execution 结果回写 state。

验收：

- 一个动作计划能完成：

```text
分析站点 -> 选择目录 -> 字段定位 -> 试跑 -> 导出
```

- 执行结果可以在事件流里看到。

工作量：大，约 1.5 - 2 天。

### Step 4：失败诊断与自动修复闭环

目标：失败后不是只报错，而是自动分类、修复、重跑。

要做：

- 失败分类：
  - 没有目录
  - 没有商品链接
  - selector 失效
  - API replay 失败
  - token/signature 失效
  - 浏览器渲染失败
  - 访问被拦截
  - 字段质量差
  - 覆盖率不足
- 每类失败映射到可执行修复动作。
- 修复后自动启动 child run 或 rerun。
- 生成前后对比。

验收：

- 零数据任务能触发诊断。
- 至少 3 类失败可以自动生成 patch 并重跑。
- 前端能看到失败原因和修复动作。

工作量：大，约 2 天。

### Step 5：前端全程可见

目标：让用户看到 AI 的每一步决策，而不是只看到最后失败。

要做：

- 任务详情页显示：
  - 当前阶段
  - evidence 摘要
  - AI 决策
  - action plan
  - action 执行结果
  - 质量报告
  - 修复/重跑记录
- 支持流式或近实时事件刷新。
- 站点分析结果能直接进入试跑。
- 页面切换不丢状态。

验收：

- 用户从前端可以完整走完：

```text
配置模型 -> 输入站点 -> 分析 -> 试跑 -> 修复 -> 重跑 -> 导出
```

- 过程可见，不需要打开后端日志猜。

工作量：中等偏大，约 1.5 - 2 天。

### Step 6：真实站点训练和收口

目标：用真实网站检验闭环，不停留在 mock。

要做：

- 选 2 - 3 个电商站点。
- 每个站点先跑 50 - 100 条试跑。
- 记录：
  - 目录发现是否成功
  - 商品链接覆盖率
  - 字段完整率
  - API/browser/DOM 哪条路径有效
  - 修复动作是否真的提升结果
  - 导出是否正确
- 把训练结论写入报告和 profile 样例。

验收：

- 至少一个真实站点完成闭环自动修复。
- 至少一个真实站点能说明失败卡在哪里。
- 生成训练报告。

工作量：中等，约 1 天。

## 总工作量评估

如果由一个主 Codex 连续做：

```text
约 7 - 9 个高强度开发日
```

如果主管 + 2 到 3 个员工并行：

```text
约 3 - 5 个开发日可以完成第一版可用闭环
```

其中最难的部分不是写接口，而是统一状态、动作协议和失败修复闭环。

## 建议分工

### 主管主线

负责：

- Managed Crawl State
- Action Plan 协议
- Action Executor 主流程
- 后端验收
- 架构收口

原因：这部分决定整个 agent 是否偏航，必须统一设计。

### 001 后端员工

负责：

- 失败诊断分类
- coverage/quality diagnosis
- 修复动作映射
- 单测

### 002 后端员工

负责：

- profile patch / replay patch / runtime patch 执行细节
- API replay、browser evidence 和 profile longrun 的桥接测试

### 004 前端员工

负责：

- AI 决策链展示
- action timeline
- 站点分析结果到试跑任务的页面打通
- 页面切换状态保持

## 风险

### 风险 1：继续堆工具但没有主流程

这是当前最需要避免的事情。后续所有新能力都必须问一句：

```text
它能不能进入 AI Managed Crawl Loop？
```

不能进入主流程的能力，优先级降低。

### 风险 2：LLM 输出不可控

必须坚持结构化 action plan，不能让模型自由写一段自然语言建议后交给人猜。

### 风险 3：前端只展示结果，不展示过程

这个 agent 的价值在于“AI 帮你开发爬虫”，所以过程必须可见。用户要看到模型怎么判断、怎么修、为什么重跑。

### 风险 4：闭环只在 mock 中成立

必须尽快用真实电商站点训练，否则闭环会变成漂亮但虚的架构。

## 是否要现在做

建议现在做。

理由：

- 后端工具已经足够多，继续零散补工具的边际收益变低。
- 用户当前最大痛点正是“AI 没有全程掌控采集流程”。
- 前端工作台已经存在，正适合接入可见闭环。
- 做完这一步后，后续补代理、JS 逆向、视觉 OCR、长跑调度都会更容易，因为它们都有地方接入。

## 完成后的项目变化

完成 `AI Managed Crawl Loop v2` 后，CLM 的定位会从：

```text
有很多采集能力的后端框架
```

升级为：

```text
AI 能调度采集能力、诊断失败、自动修复并重跑的数据采集 Agent
```

这是从“工具集合”到“真正 Agent”的关键一步。
