# CLM Scrapling 能力吸收近期计划

日期：2026-05-14

## 战略判断

CLM 不应该继续把强采集后端当成远期自研目标慢慢重造。Scrapling 0.4.8 已经具备成熟的静态请求、动态浏览器、protected environment、adaptive parser、spider 调度、checkpoint、proxy rotation 和 CLI/MCP 思路。

近期目标不是把 Scrapling 当成一个外部库长期封装，也不是简单把源码 vendor 进项目后继续调用它的品牌 API。正确目标是把 Scrapling 的能力拆解、验证、吸收、重组为 CLM 自己的采集后端能力。

当前 `Scrapling*Runtime` adapter 是过渡层：它帮助 CLM 快速理解 Scrapling 的能力边界、验证接口形状、跑通主链路和训练样本。最终交付物必须是 CLM 原生 runtime/backend 模块，而不是“CLM 调用 Scrapling”。

## 产品定位

```text
CLM = Agent 决策层 + 采集运行时协议 + 训练/证据/长跑系统
Scrapling = 能力样板和工程参考
最终目标 = CLM Native Crawler Backend
```

CLM 继续负责：

- Planner / Recon / Strategy / Executor / Extractor / Validator
- 运行策略选择
- 证据链和诊断报告
- 训练集、任务看板、员工协作
- 长任务、存储、导出、项目化开发体验
- 治理文档、发布条款、客户责任和商业部署说明

Scrapling 能力吸收方向：

- Static HTTP fetch runtime
- Browser dynamic rendering runtime
- Protected environment runtime
- Parser and adaptive selector runtime
- Spider scheduler/runtime
- Session continuity
- Browser identity abstraction
- Proxy rotation
- Checkpoint / pause / resume
- Captured XHR and browser artifacts

## 架构原则

1. 不在 workflow 中硬编码站点 selector。
2. 不让业务层直接调用 Playwright/Scrapling 具体类。
3. 所有采集能力经由 CLM Runtime Protocol 暴露。
4. Scrapling adapter 只能作为过渡桥和对照组，不能作为最终产品形态。
5. 先快速验证能力，再逐步把关键模块原生化到 `autonomous_crawler/runtime/`、`tools/`、`storage/` 和 `BatchRunner`。
6. 保持 fnspider、httpx、现有 Playwright 工具作为 fallback 或专项工具。
7. 底层依赖可以吸收 Scrapling 使用过的成熟组件，例如 `curl_cffi`、`lxml`、`cssselect`、`orjson`、`tld`、`w3lib`、Playwright/Patchright 思路等；但 CLM 对外提供的是自己的 runtime。

## Runtime Protocol 草案

```text
autonomous_crawler/runtime/
  protocols.py
    FetchRuntime
    BrowserRuntime
    ParserRuntime
    SpiderRuntime
    ProxyRuntime
    SessionRuntime

  models.py
    RuntimeRequest
    RuntimeResponse
    RuntimeArtifact
    RuntimeProxyTrace
    RuntimeSelectorResult
    RuntimeEvent

  scrapling_static.py      # transition adapter
  scrapling_parser.py      # transition adapter
  scrapling_browser.py     # transition adapter

  native_static.py         # target CLM-owned backend
  native_parser.py         # target CLM-owned backend
  native_browser.py        # target CLM-owned backend
  native_spider.py         # target CLM-owned backend
```

统一输入：

```text
RuntimeRequest:
- url
- method
- headers
- cookies
- body/json/params
- mode: static | dynamic | protected | spider
- selector_config
- browser_config
- session_profile
- proxy_config
- capture_xhr
- wait_selector
- wait_until
- timeout_ms
- max_items
```

统一输出：

```text
RuntimeResponse:
- ok
- final_url
- status_code
- headers
- cookies
- body/html/text
- captured_xhr
- items
- artifacts
- proxy_trace
- runtime_events
- error
```

## 当前交付状态

### 当前状态总评

状态：Scrapling 能力吸收处于 **Phase 1 过渡适配完成，原生化尚未完成**。

已经完成的是：

- CLM runtime protocol 已经成型。
- `engine="scrapling"` 可以进入主链路。
- 静态请求、解析、浏览器/session/proxy 已有 adapter 或 contract。
- 测试证明这些 adapter 可以被 CLM executor 调度，并把结果转换成 CLM state。

还没有完成的是：

- Scrapling 的能力还没有全部转化为 CLM 原生实现。
- `AsyncFetcher` 对应的并发 runtime 尚未落地。
- `spiders/` 的 scheduler、checkpoint、request/result、robots、session 体系还没有吸收到 BatchRunner。
- adaptive parser 的深层选择器生成/相似节点匹配能力还没有 CLM 原生化。
- protected/browser runtime 还缺真实站点训练和稳定性回归。
- CLI/MCP 思路还没有转化为 CLM 自己的开发者工作流。

因此不能把当前状态描述为“Scrapling 已完全接入后端”。准确描述是：

```text
CLM 已经具备 Scrapling 能力吸收的过渡桥，下一阶段要把能力从 adapter-backed 迁移为 CLM-native backend。
```

## 能力吸收分解

| Scrapling 能力 | CLM 目标模块 | 当前状态 | 下一步交付 |
|---|---|---|---|
| `Fetcher` 静态请求 | `NativeFetchRuntime` | adapter-backed proof | 基于 `curl_cffi/httpx` 做 CLM 原生 fetch runtime，保留 headers/cookies/proxy/timeout/response 规范化 |
| `AsyncFetcher` | `AsyncFetchRuntime` / BatchRunner 并发执行器 | 未吸收 | async fetch 池、连接复用、并发限流、失败桶、指标 |
| `Selector` / `Selectors` | `NativeParserRuntime` | adapter-backed proof | 基于 `lxml/cssselect` 做 CLM 原生 parser，补相似节点、字段候选、selector 质量评分 |
| dynamic browser | `NativeBrowserRuntime` | adapter contract | 统一 Playwright/Patchright 思路、等待策略、XHR capture、artifact manifest |
| protected browser | `ProtectedBrowserRuntime` | adapter contract | runtime profile、指纹一致性、失败证据、真实站点训练 |
| proxy rotation | `ProxyManager` / `ProxyPoolProvider` | initial | 轮换策略、健康评分、cooldown、BatchRunner 指标 |
| session continuity | `SessionProfile` / `BrowserContextConfig` | initial | cookie/header/storage state 生命周期、跨请求一致性 |
| spider scheduler | `BatchRunner` / `URLFrontier` | 部分已有，不是 Scrapling 吸收版 | request/result/event 模型对齐，流式 item，任务暂停恢复 |
| checkpoint | `CheckpointStore` | 部分已有 | 批次级、URL级、item级 checkpoint 和恢复测试 |
| robots/link extractor | Recon/profile helper | 未吸收 | sitemap/robots/link filter/profile 生成 |
| CLI/MCP 工作流 | `clm.py` / future MCP tool | 部分已有 | 把训练、诊断、profile 生成变成 CLM 命令 |

### Phase 1: Static And Parser Runtime

状态：过渡适配层已完成并验收；原生化待做。

交付：

- Runtime Protocol 初版
- Scrapling static fetch transition adapter
- Scrapling parser transition adapter
- executor engine routing
- mock + local fixture tests
- README、看板、状态文档更新

验收：

- `engine="scrapling"` 可进入 executor 主链路
- static/html 路径走 `ScraplingStaticRuntime.fetch()`
- parser 证据走 `ScraplingParserRuntime.parse()`
- `mock://` 路径仍 deterministic
- 162 个 Scrapling focused tests 通过
- 1273 个全量 tests 通过，4 skipped

### Phase 2: Browser, Session, Proxy, XHR

状态：adapter contract 已完成，真实训练和 CLM 原生化待做。

交付：

- dynamic browser adapter
- protected runtime adapter contract
- browser identity config mapping
- session continuity mapping
- XHR capture 字段映射
- proxy rotator 映射
- executor routing 到 `ScraplingBrowserRuntime.render()`

下一步验收：

- 本地 SPA smoke
- 真实 SPA / protected runtime smoke
- runtime events 进入 workflow state
- proxy/session 证据进入 BatchRunner 指标

### Phase 3: Spider And Long Runs

状态：计划中。

目标：把 Scrapling Spider 的 scheduler/checkpoint/request/result/session/robots/link extractor 思路吸收到 CLM 长任务后端，而不是直接让 CLM 依赖 Scrapling spider。

交付：

- spider runtime adapter
- checkpoint / pause / resume
- streaming item event
- blocked retry event
- per-domain concurrency
- BatchRunner 对接
- 1,000 / 10,000 / 30,000 级压力回归

验收：

- 可恢复长任务
- failure bucket 可追踪
- Excel/JSON/SQLite 导出稳定
- 真实电商训练站点至少一轮 600+ 数据回归

## 当前 Sprint 拆分与验收

### Supervisor mainline: CLM Runtime Protocol + Executor Routing

Owner: LLM-2026-000

状态：已完成。

验收文档：

```text
docs/team/acceptance/2026-05-14_scrapling_executor_routing_ACCEPTED.md
```

### Worker 001: Static + Parser Adapter

Owner: LLM-2026-001

状态：已完成并验收。

验收文档：

```text
docs/team/acceptance/2026-05-14_scrapling_static_parser_adapter_ACCEPTED.md
```

### Worker 002: Browser + Session + Proxy Runtime Design

Owner: LLM-2026-002

状态：已完成并验收。

验收文档：

```text
docs/team/acceptance/2026-05-14_scrapling_browser_session_proxy_runtime_ACCEPTED.md
```

### Worker 004: Docs + Source Tracking + Board Audit

Owner: LLM-2026-004

状态：已完成并验收。

验收文档：

```text
docs/team/acceptance/2026-05-14_scrapling_runtime_docs_source_tracking_ACCEPTED.md
```

## 下一步任务

1. `SCRAPLING-ABSORB-1`：把当前 static/parser adapter 的行为转写为 CLM 原生 `NativeFetchRuntime` 和 `NativeParserRuntime`，adapter 只保留为对照测试。
2. `SCRAPLING-ABSORB-2`：真实静态站点 + SPA 站点通过 adapter 与 CLM native runtime 双跑训练，记录差异。
3. `SCRAPLING-ABSORB-3`：把 spider scheduler/checkpoint/request/result/session/robots/link extractor 思路接入 BatchRunner。
4. `SCRAPLING-ABSORB-4`：吸收 dynamic/protected browser runtime 的等待、XHR、指纹、session、proxy 机制，形成 CLM 原生 browser backend。
5. `CAP-2.1 / CAP-2.2`：JS AST + hook + sandbox MVP，用于签名函数定位。
6. `CAP-3.3`：真实代理池 provider adapter + health scoring + runner metrics。
7. `CAP-5.2`：VisualRecon/OCR MVP。

## 成功标准

近期成功不是“安装 Scrapling 包并调通”，也不是“完全复制 Scrapling 文件树”，而是：

```text
CLM 默认拥有一个强力、协议化、可训练、可长跑的原生 crawler backend；
Scrapling 0.4.8 的关键采集能力已经被拆解并吸收到 CLM 的 runtime、runner、proxy、session、parser、browser 和证据系统中。
```

这会把 CLM 从“Agent 调工具”推进到“Agent 驱动生产级采集运行时”。
