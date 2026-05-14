# Crawler-Mind 高级爬虫能力落地矩阵

日期：2026-05-14

来源能力清单：

```text
C:/Users/Administrator/Downloads/顶尖爬虫开发者能力清单.md
```

## 主线判断

CLM 的产品目标已经从“能跑通的爬虫 Agent MVP”升级为“把高级爬虫开发能力产品化”。项目面向企业、爬虫开发者和技术团队，核心卖点不是替用户写几个固定站点规则，而是把顶尖爬虫工程师常用的判断、诊断、采集、逆向、调度、代理、浏览器、证据和长任务能力沉淀成可复用的 Agent runtime。

2026-05-14 起，Scrapling 能力吸收成为采集后端主线：

```text
CLM = Agent 决策层 + 运行时协议 + 训练/证据/长跑系统
Scrapling = 能力样板和过渡 adapter 对照组
最终目标 = CLM Native Crawler Backend
```

这条主线不等于长期封装 `scrapling` 包，也不等于简单把源码搬进仓库。它的含义是：把 Scrapling 0.4.8 中已经证明有价值的采集能力拆解出来，转化为 CLM 自己的 runtime、runner、parser、browser、proxy、session、checkpoint 和证据系统。

## 状态标签

| 标签 | 含义 |
|---|---|
| `done` | 已进入主链或稳定工具层，并有测试覆盖 |
| `initial` | 已有可测试基础，但还需要更多真实站点训练 |
| `adapter-ready` | 协议或适配器已具备，等待更深主链集成 |
| `transition-adapter` | 当前靠 Scrapling adapter 验证行为，最终仍需 CLM 原生化 |
| `planned` | 已明确产品方向，尚未实现 |
| `training-needed` | 能力存在，但需要更多实战样本校准 |

## 总览矩阵

| 能力编号 | 能力项 | 当前状态 | 已落地内容 | 下一步 |
|---|---|---|---|---|
| CAP-1.1 | HTTP/HTML 基础采集 | `done` | `httpx` 请求、headers、错误码、BeautifulSoup 提取、mock fixtures，Scrapling static transition adapter | 建 CLM 原生 `NativeFetchRuntime`，用 Scrapling adapter 做对照测试 |
| CAP-1.2 | TLS/HTTP 指纹与传输诊断 | `initial` | requests/curl_cffi/browser 对比、状态码/HTTP 版本/header 差异、transport profile 标签 | 增加 JA3/ALPN/SNI 证据和 impersonation profile 选择 |
| CAP-1.3 | 连接池、DNS、重试、背压 | `initial` | `httpx.Client`、rate-limit policy、runner 基础 | 增加连接池指标、DNS 缓存、并发背压、动态 retry/backoff |
| CAP-1.4 | WebSocket 观察 | `initial` | Playwright WS 连接/帧模型、预览截断、Recon opt-in 集成、本地 smoke | 增加协议解析、二进制帧解析、WS 采集 profile |
| CAP-2.1 | JS 静态分析 | `initial` | JS asset inventory、字符串表、endpoint、GraphQL/WebSocket/sourcemap、可疑函数/调用线索 | 接 parser-backed AST、source map 下载、控制流/数据流分析 |
| CAP-2.2 | 签名/加密入口定位 | `initial` | hash/HMAC/signature/WebCrypto/AES/RSA/base64/timestamp/nonce/param-sort/custom-token 线索 | 接 runtime hook、sandbox 执行、签名函数定位报告 |
| CAP-2.3 | Wasm 分析 | `planned` | 暂无 | 发现、下载、导入导出表分析、Wasm 反编译入口 |
| CAP-2.4 | CDP/V8 调试 | `planned` | Playwright 基础执行、browser interception 基础 | CDP session、Runtime tracing、console/source map 调试 |
| CAP-2.5 | CAPTCHA/OCR/视觉识别 | `planned` | ChallengeDetector 可识别验证码页，已有 screenshot artifact 基础 | VisualRecon/OCR、验证码分类、可插拔求解器接口、人工/服务商回传协议 |
| CAP-3.1 | 任务调度 | `done` | URLFrontier、BatchRunner、FastAPI background jobs | 把 LangGraph workflow 包成 BatchRunner processor |
| CAP-3.2 | 去重系统 | `done` | SQLite frontier 去重、category-aware product dedupe | Bloom/Redis/大规模去重、跨任务去重策略 |
| CAP-3.3 | 可插拔代理池 | `initial` | ProxyConfig、ProxyManager、StaticProxyPoolProvider、round_robin/domain_sticky/first_healthy、ProxyHealthStore、ProviderAdapter template | 接真实供应商 adapter、健康探测、质量评分、BatchRunner 指标 |
| CAP-3.4 | 指纹池 | `initial` | BrowserContextConfig、browser fingerprint profile/probe | profile pool、跨请求一致性、指纹轮换策略 |
| CAP-3.5 | 高并发性能 | `initial` | BatchRunner、frontier claim loop、rate-limit | async pipeline、并发池、背压、长任务监控 |
| CAP-3.6 | 数据管道 | `done` | SQLite result/product store、Excel/JSON/CSV export、artifact manifest | Parquet/ClickHouse/Kafka/流式导出、artifact retention |
| CAP-4.1 | Playwright/CDP 浏览器采集 | `done` | browser fetch、screenshots、network observer、browser context、runtime fingerprint probe、WebSocket observer，Scrapling browser transition adapter | 吸收 dynamic/protected browser 机制到 CLM 原生 browser runtime |
| CAP-4.2 | 浏览器指纹一致性 | `initial` | 配置侧 profile/risk/recommendations，runtime probe 采样 navigator/screen/Intl/WebGL/canvas/font | 指纹池和真实浏览器训练集 |
| CAP-4.3 | JS 执行隔离 | `planned` | 暂无 | QuickJS/Node VM adapter、超时、副作用隔离、签名函数 sandbox |
| CAP-4.4 | 资源拦截与修改 | `initial` | route interception、资源 blocking、JS/API metadata capture、init script 注入 | request fulfill/rewrite、CDP 原始事件、JS bundle 持久化 |
| CAP-5.1 | Agent 策略推理 | `done` | LLM Advisor、StrategyEvidenceReport、StrategyScoringPolicy、AntiBotReport、DOM/API/JS/crypto/transport/fingerprint/WebSocket evidence | 让 scorecard 在明确场景下影响 mode，增加真实站点校准 |
| CAP-5.2 | 图像理解 | `planned` | screenshot artifact 基础 | OCR/layout/视觉区域检测、DOM 与截图对齐 |
| CAP-5.3 | 自主探索 | `initial` | Recon -> Strategy -> Executor 图、domain memory、site zoo fixtures | 自动 profile 生成、站点地图探索、策略树搜索 |
| CAP-5.4 | 异常检测 | `initial` | validator、quality checks、error codes、artifact evidence | 成功率时序监控、自动策略切换 |
| CAP-6.1 | 治理与策略配置 | `initial` | 文档层已有治理入口，运行层有 redaction 和 access config | 项目级策略配置、企业条款模板、审计仪表盘 |
| CAP-6.2 | 证据链与报告 | `done` | fetch trace、strategy evidence、AntiBotReport、proxy trace、runtime artifacts | CLI/API 报告摘要和趋势视图 |
| CAP-6.3 | 自适应限速 | `initial` | DomainRateLimiter、per-domain delay、fetch trace rate_limit_event | 根据响应动态调速、429/5xx 自适应 backoff |
| CAP-6.4 | 数据治理 | `initial` | secret redaction、storage-state path redaction、proxy credential redaction | 数据分级、加密、访问审计 |
| CAP-7.1 | 抓包工具生态 | `planned` | browser observer/interceptor 作为内部抓包基础 | mitmproxy/Charles/Wireshark HAR 导入与报告 |
| CAP-7.2 | Scrapy/Selenium/框架兼容 | `initial` | fnspider 集成，Scrapling 能力吸收主线 | Scrapy/Selenium adapter，统一 runtime protocol |
| CAP-7.3 | 部署与监控 | `initial` | GitHub CI、FastAPI MVP | Docker/K8s/Prometheus、服务化 worker |
| SCRAPLING-ABSORB-1 | Static/parser 原生化 | `transition-adapter` | Runtime protocol、Scrapling static/parser adapter、executor routing、162 focused tests | 建 `NativeFetchRuntime` / `NativeParserRuntime`，adapter 做基准 |
| SCRAPLING-ABSORB-2 | Browser/session/proxy 原生化 | `adapter-ready` | browser adapter、session config、proxy rotator mapping、executor dynamic routing | 真实 SPA/protected-mode smoke，并迁移为 CLM 原生 browser backend |
| SCRAPLING-ABSORB-3 | Spider/checkpoint/long-run 原生化 | `planned` | 计划已入看板，CLM 已有 BatchRunner 和 Frontier 基础 | 吸收 scheduler、request/result、checkpoint、robots/link extractor、streaming item events |

## 当前最强能力

1. **端到端 Agent 工作流**：Planner、Recon、Strategy、Executor、Extractor、Validator 已经能跑通，并有 LLM advisor 可选接入。
2. **证据驱动策略层**：StrategyEvidenceReport、StrategyScoringPolicy、AntiBotReport 已经把 DOM/API/JS/crypto/transport/fingerprint/WebSocket/proxy 线索统一成决策证据。
3. **Scrapling 能力吸收主线**：static/parser/browser/session/proxy transition adapter 已进入 CLM 协议层，executor 已支持 `engine="scrapling"`；下一步是把 adapter 行为转成 CLM 原生后端。
4. **大体量基础**：BatchRunner、Frontier、ProductStore、30,000 synthetic stress test 证明了本地长跑基础。
5. **训练闭环**：真实电商、Baidu hot、HN Algolia、mock fixtures、site zoo 和员工验收文档已经形成训练材料。

## 当前主要不足

1. **Scrapling 还未完成原生吸收**：当前只是过渡 adapter 和能力对照；async fetch、adaptive parser、spider scheduler、checkpoint、robots/link extractor 等还没转成 CLM 原生模块。
2. **真实高难度站点训练还不够**：dynamic/protected runtime 需要更多 SPA、无限滚动、复杂电商、Cloudflare/反爬站点训练。
3. **JS 逆向还停在 evidence 层**：已经能发现签名和加密线索，但还没有 AST/Hook/Sandbox 自动执行闭环。
4. **代理池还不是商业级**：有可插拔模型和健康存储，但缺真实供应商 adapter、质量评分和长跑指标。
5. **视觉能力还没启动**：OCR/layout/图片识别还在计划层。
6. **长任务持久化还需增强**：FastAPI job registry 仍是内存态；BatchRunner 还没完全接 LangGraph processor。

## 下一步优先级

1. `SCRAPLING-ABSORB-1`：把 static/parser transition adapter 转化为 CLM 原生 fetch/parser runtime。
2. `SCRAPLING-ABSORB-2`：真实 SPA / protected browser smoke，验证并吸收 DynamicFetcher / StealthyFetcher / XHR capture / proxy mapping 思路。
3. `SCRAPLING-ABSORB-3`：把 spider/checkpoint/request/result/session/robots/link extractor 思路接到 BatchRunner，完成可恢复长任务。
4. `CAP-2.1 + CAP-2.2`：JS AST + hook + sandbox 签名函数定位 MVP。
5. `CAP-3.3`：真实代理池 provider adapter + health scoring + runner metrics。
6. `CAP-5.2`：VisualRecon/OCR MVP，先做页面文字和布局理解。
7. `CAP-7.2`：补 Scrapy/Selenium adapter，使 CLM 对开发者生态更友好。
