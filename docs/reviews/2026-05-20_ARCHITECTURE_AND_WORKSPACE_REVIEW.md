# CLM 架构与工作区复盘

日期：2026-05-20

## 结论

CLM 没有偏离最初目标，但架构已经从最初的 LangGraph 爬虫 pipeline，升级成了一个“AI 编排 + 原生采集后端 + 工作台”的 crawler platform 雏形。

最初目标是让用户用自然语言或少量配置完成网站分析、策略选择、采集执行、质量验证和结果导出。当前代码仍然沿着这个方向走，只是中间为了补硬实力，增加了大量 runtime、profile、checkpoint、evidence、replay、frontend API 模块。方向没有变，复杂度上来了，文档和工作区需要跟上。

当前阶段可以概括为：

```text
Level 1: 骨架跑通                     100%
Level 2: 可用 MVP                     100%
Level 3: 高级采集后端                 70% - 75%
Level 4: AI 全程决策与可见闭环          45% - 55%
Level 5: 产品级工作台和长任务运营       30% - 40%
整体距离“顶尖数据采集 Agent”目标       55% - 65%
```

## 工作区整理结果

本次暂停开发后，先做了工作区清理：

- 已保存 supervisor 记忆到 agentmemory。
- 已保留本地 fallback memory：
  - `docs/memory/supervisor/2026-05-20_backend_replay_memory.md`
  - `docs/memory/supervisor/2026-05-20_backend_hard_capability_memory.md`
- 已删除 Python 缓存目录：
  - 根目录 `__pycache__`
  - `autonomous_crawler/**/__pycache__`
- 已删除一个明显由错误路径生成的空目录：
  - `Fdataworkagentautonomous_crawlerllm`
- 已在日报中记录 2026-05-20 的后端 replay/runtime 收口。

没有删除历史日报、训练报告、验收记录和开发日志。它们虽然多，但属于项目证据链，后续更适合做索引和归档，不适合直接删。

## 当前真实架构

### 1. 用户入口层

当前入口已经不再只有开发脚本：

- `clm.py`：Easy Mode CLI，适合命令行快速检查、烟测和训练。
- FastAPI：负责工作台、任务、站点分析、模型配置、导出、事件流等接口。
- `frontend/`：中文工作台已经开始承载真实使用流程。
- 旧脚本：`run_*` 系列保留为训练、烟测和开发工具。

状态判断：入口变多是合理演进，但需要明确“用户主入口是工作台 + clm.py”，旧脚本只做工程训练。

### 2. AI 决策层

已有能力：

- OpenAI-compatible LLM provider。
- 模型列表拉取和第三方 API 接入。
- Planner/Strategy advisor。
- managed actions。
- `llm_traces` / managed step / evidence pack。
- AI profile patch allowlist。
- replay diagnostics 到 executable replay runtime 的初步桥接。

主要不足：

- AI 还不是每一步都在“掌勺”。它可以建议和 patch，但还没有形成稳定的全程控制循环。
- 前端可见性仍不足，用户还不能清楚看到模型为什么这样判断、下一步准备怎么做、失败后如何修。
- LLM 的输出仍需要更强的状态约束和可执行计划约束，否则容易变成建议文本。

判断：AI 层已经从“可选 advisor”升级到“managed workflow 雏形”，但还没到真正 autonomous operator。

### 3. 采集硬后端

已有能力：

- Native static fetch。
- Native async fetch pool。
- Native parser。
- adaptive selector relocation。
- selector memory。
- Native browser runtime。
- browser context/session/profile/pool。
- browser network observation。
- WebSocket observation。
- proxy config / health / trace。
- rate limit / backpressure。
- challenge/access evidence。
- JS asset inventory、crypto clues、hook/sandbox planning。
- API/XHR replay。
- POST/GraphQL replay。
- dynamic input replay diagnostics。
- executable API replay runtime bridge。

主要不足：

- 大量能力有模块和测试，但真实高难站点训练仍不够。
- 目录发现、分页发现、详情页覆盖率、变体字段提取还需要更强的自动闭环。
- API replay 已进入可执行层，但对复杂签名、会话绑定、token 刷新、混合浏览器/API 执行的稳定性仍需强化。
- 代理池具备模型和健康机制，但真实供应商 adapter 和长跑质量评分还不完整。

判断：后端硬实力已经不是早期 MVP 水平，处于高级采集后端的中后段，但还缺真实站点反复打磨。

### 4. Profile 和长任务层

已有能力：

- SiteProfile。
- profile ecommerce runner。
- profile longrun。
- BatchRunner。
- checkpoint store。
- URL frontier。
- product store。
- multi-site runner。
- coverage/quality/diagnostics 基础。
- pause/resume/cancel/delete 的 API 支撑正在形成。

主要不足：

- 长任务任务状态仍需要更强的持久化注册表。
- 覆盖率漏斗还要更前置地服务于“为什么少采了 1000 条”这类问题。
- profile 自动生成、自动修复、训练沉淀还没有完全闭环。

判断：长任务地基已经有，但离产品级稳定长跑还差一层调度和诊断闭环。

### 5. 前端工作台

已有能力：

- 中文工作台。
- LLM provider 配置与模型列表。
- 站点分析入口。
- 任务创建、详情、事件流、AI managed panel。
- 导出参数和格式传递正在打通。

主要不足：

- 工作流页面之间仍需要更顺滑地共享状态。
- 站点分析结果需要直接进入“选择目录/选择字段/试跑/全量跑”。
- AI 决策过程需要可见、可流式、可回放。
- 任务停止、清除、重新运行、导出路径、导出格式需要继续做端到端验证。

判断：前端已经从展示页进入真实工作台，但用户体验还没到“低门槛产品”。

## 是否偏离原始目标

没有偏离，但经历了一次必要的架构升级。

原始目标：

```text
自然语言需求 -> 自动理解网站 -> 选择采集策略 -> 执行 -> 校验 -> 导出
```

当前实际架构：

```text
用户/前端/CLI
  -> LLM 配置与任务描述
  -> 站点证据采样
  -> Recon / Evidence / API / Browser / JS / Access 诊断
  -> AI managed decision / profile patch / replay plan
  -> Native runtime / profile runner / longrun
  -> quality / coverage / export / event stream
```

这是对原始目标的展开，不是偏航。问题在于：能力层补得很快，产品主线和文档节奏落后，导致表面看起来“到处都是模块”。下一步应该把这些模块收束进一个清晰主流程。

## 已有核心能力清单

- 静态 HTML 和 JSON/API 采集。
- 百度热搜等榜单采集。
- 商品列表/详情/变体字段基础抽取。
- Playwright 浏览器渲染。
- XHR/API/GraphQL 观察和 replay。
- POST/GraphQL profile replay。
- dynamic inputs/replay diagnostics。
- JS asset/crypto/signature clue 分析。
- proxy/session/rate-limit/backpressure 基础。
- selector memory 和 adaptive selector。
- checkpoint/frontier/batch runner。
- profile-driven ecommerce longrun。
- 多站点并发基础。
- SQLite 存储和 CSV/XLSX/JSON 导出。
- FastAPI 工作流接口。
- 中文前端工作台雏形。
- LLM provider 配置、模型列表和 advisor/managed action。

## 仍需开发的关键能力

### P0：AI 全程控制闭环

目标：让 AI 不只是分析站点，而是能持续观察、决策、修复和重跑。

需要补：

- 每个阶段生成可见 `llm_trace`。
- managed action 必须能产出可执行 plan，不只是建议。
- 失败后生成修复方案并触发重跑。
- 前端展示模型推理强度、步骤、证据、决策、修复动作。
- 约束 LLM 输出到 profile patch、runtime patch、field mapping、pagination plan 等结构。

### P1：采集成功率和速度

目标：真实电商站点大体量采集时，能解释并减少漏采。

需要补：

- 目录发现覆盖率。
- 分页发现和分页循环稳定性。
- 列表页到详情页覆盖率。
- 变体字段提取，尤其颜色、尺码、图片、原价。
- async/browser/API 混合执行调度。
- 每站点并发、每域名限速、失败重试和 backpressure 自动调节。
- 覆盖率漏斗报告。

### P2：高难站点能力

目标：面对 SPA、复杂 API、签名参数、会话状态时，能尽量进入可执行路径。

需要补：

- signed API replay 更强的 hook/sandbox 执行。
- session-bound token 刷新。
- browser session 到 API replay 的状态转移。
- CDP trace 和 console/source map 证据。
- real proxy provider adapter。
- protected browser profile 的真实训练集。

### P3：工作台产品化

目标：让用户通过前端完成完整任务，而不是在多个页面和脚本之间跳。

需要补：

- 配置 LLM -> 分析站点 -> 目录确认 -> 字段确认 -> 试跑 -> 全量 -> 监控 -> 导出的一条主线。
- 用户导入目录和模板。
- 导出路径和导出格式严格生效。
- 任务中止、清除、重跑、历史恢复。
- 工作流状态持久化，刷新页面不丢。

### P4：文档和工作区治理

目标：让任何新员工或新 AI 接入时能快速知道“现在到哪了”。

需要补：

- `PROJECT_STATUS.md` 保持当前总状态。
- `PLAN.md` 保持下一阶段主线。
- 每日只写日报和开发日志，不把临时讨论散落到根目录。
- 训练结果统一放 `dev_logs/training/`。
- 架构复盘放 `docs/reviews/`。
- 能力路线图放 `docs/plans/`。
- 员工记忆放 `docs/memory/`。

## 下一步建议

下一轮不建议继续零散加模块，应该做一个大块：

```text
AI Managed Crawl Loop v2
```

范围：

1. 把站点分析、目录发现、字段定位、试跑、失败诊断、profile patch、重跑串成一个统一后端流程。
2. 把 API replay runtime、browser evidence、coverage report 纳入这个流程。
3. 前端只调用这一条工作流，并展示每一步事件和 AI 决策。
4. 用两个真实电商站点做训练，重点看成功率、速度和漏采原因。

这一步完成后，CLM 才会真正从“有很多能力的后端”变成“会使用这些能力的 Agent”。
