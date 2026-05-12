# Crawler-Mind 顶尖爬虫能力落地矩阵

日期：2026-05-12

来源能力清单：

```text
C:/Users/Administrator/Downloads/顶尖爬虫开发者能力清单.md
```

## 主管纠偏

CLM 的目标已经从“能跑的爬虫 MVP”推进到“产品化高级爬虫开发能力”。从 2026-05-12 开始，主线任务需要显式标注能力编号，避免工程模块堆叠却看不清能力进度。

能力编号：

```text
CAP-1.x 网络与协议
CAP-2.x JS 逆向与对抗分析
CAP-3.x 工程架构与规模化
CAP-4.x 浏览器自动化与指纹
CAP-5.x AI 与策略推理
CAP-6.x 治理与审计
CAP-7.x 工具链与生态
```

## 状态标签

- `production-ready`：默认主链路可用，并经过真实或端到端验收。
- `opt-in`：能力存在，但必须通过 constraints/config 显式启用。
- `evidence-only`：只产出诊断/证据/建议，不自动执行绕过、破解、重放或策略覆盖。
- `mocked only`：主要由 mock/fake/fixture 测试证明，还没有真实站点或真实浏览器验收。
- `initial`：可测试基础已经存在，但不应对外宣传为完整能力。

## 2026-05-12 激进能力冲刺结果

今天的 sprint 推进了多个高级能力，但必须保持诚实措辞：

- CAP-1.4 WebSocket：WebSocket observer 已完成，Recon 也已支持 `constraints.observe_websocket=true` 的 opt-in 接入；当前属于 `opt-in + evidence-only`，不是 WebSocket 协议逆向、帧重放或生产级 WS 采集。
- CAP-2.1/CAP-2.2 JS/crypto evidence：已有 JS inventory、pre-AST static analysis、crypto/signature evidence，并接入 `js_evidence`；当前属于 `evidence-only`，不是完整 AST、反混淆、hook 执行、密钥恢复或绕过。
- CAP-3.3 Proxy pool：已有 pluggable proxy pool、static provider、health store、provider adapter template；当前属于 `opt-in + initial`，不是商业代理供应商完整接入，也不是自动代理绕过。
- CAP-5.1 Strategy evidence reasoning：已有 `StrategyEvidenceReport`，能统一 DOM/API/JS/crypto/transport/fingerprint/challenge/WebSocket evidence；当前属于 advisory evidence layer，不是完整自动策略评分器或 autonomous reverse-engineering planner。
- CAP-6.2 Evidence/audit：artifact、diagnostics、strategy evidence、AntiBotReport 都在增强证据链；当前仍缺跨运行趋势、企业审计策略和仪表盘。

安全边界保持不变：

- 不破解登录。
- 不绕验证码。
- 不自动 CAPTCHA solving。
- 不默认启用代理、session、browser interception、fingerprint probe、WebSocket observation。
- 不把 cookie、API key、proxy credentials 写入日志或公开文档。

## 能力编号与当前落地状态

| 能力编号 | 能力项 | 当前状态 | 已落地内容 | 缺口 / 边界 |
|---|---|---|---|---|
| CAP-1.1 | HTTP/1.1 / HTTP/2 | 部分 | `httpx` fetch、headers、错误处理、rate-limit | HTTP/2 指纹、连接复用、连接池指标未产品化 |
| CAP-1.2 | TLS/SSL / JA3 | initial / evidence-only | `transport_diagnostics.py` 对比 requests/curl_cffi/browser 状态码、HTTP 版本、挑战信号、响应头线索、transport profile 标签 | 没有真实 JA3/ALPN/SNI 指纹采集、控制和调参 |
| CAP-1.3 | TCP/IP / 连接池 | 很弱 | 基础 `httpx.Client` | DNS 缓存、连接池指标、并发背压、连接复用诊断 |
| CAP-1.4 | WebSocket | initial / opt-in / evidence-only | `websocket_observer.py` 连接/帧模型、sent/received、text/binary、预览截断、敏感信息脱敏、mock Playwright `page.on("websocket")` 观测路径；Recon 通过 `constraints.observe_websocket=true` 输出 `websocket_observation` 和 `websocket_summary`；StrategyEvidenceReport 可生成 `websocket_activity` signal | 不是帧重放或协议逆向；真实 WS 站点 smoke、协议解析、二进制格式解析、策略动作仍待做 |
| CAP-2.1 | JS 逆向基础 / pre-AST 静态分析 | initial / evidence-only | `js_asset_inventory.py`、`js_static_analysis.py`、`js_evidence.py`；提取 JS 资源、字符串表、endpoint、GraphQL/WebSocket/sourcemap、可疑函数和调用；Recon 输出 `recon_report.js_evidence` | 不是完整 AST；缺 parser-backed AST、反混淆、控制流/数据流、source map 下载、外部 JS 全量抓取 |
| CAP-2.2 | Hook / 签名加密入口定位 | initial / evidence-only | `js_crypto_analysis.py` 识别 hash/HMAC/signature/WebCrypto/AES/RSA/base64/timestamp/nonce/param-sort/custom-token 线索；StrategyEvidenceReport 输出 reverse-engineering hints 和 API replay warning | 不执行 JS、不恢复密钥、不做 CDP hook/monkey patch/runtime tracing |
| CAP-2.3 | Wasm 逆向 | 未开始 | 无 | Wasm 发现、下载、反编译入口、导入导出表分析 |
| CAP-2.4 | V8/CDP 调试 | 很弱 | Playwright 基础执行 | CDP session、断点、Runtime 追踪、console/source map 调试 |
| CAP-2.5 | 验证码 / OCR | 诊断级 | ChallengeDetector 识别 CAPTCHA/Cloudflare/login/access-block | 不破解验证码；任何 CAPTCHA provider 都需要单独 ADR 和安全审查 |
| CAP-3.1 | 任务调度 | 部分 | URLFrontier、BatchRunner、FastAPI background jobs | LangGraph processor 未接入 runner，缺 progress events、持久 job registry |
| CAP-3.2 | 去重系统 | 部分 | SQLite frontier 去重、category-aware product dedupe | Bloom/Redis/大规模内存优化 |
| CAP-3.3 | 可插拔代理池 | initial / opt-in | ProxyConfig、ProxyManager、域名路由、凭证脱敏；`proxy_pool.py` 提供 ProxyPoolProvider、StaticProxyPoolProvider、round_robin/domain_sticky/first_healthy；`proxy_health.py` 持久化 success/failure/cooldown；ProviderAdapter template | 默认不启用代理；付费供应商 adapter、真实健康探测、跨进程池状态、质量评分仍待做 |
| CAP-3.4 | 指纹池 | 初步 | BrowserContextConfig、browser fingerprint profile/probe foundation | 缺可轮换指纹池、profile 分组、跨请求一致性治理 |
| CAP-3.5 | 高并发性能 | 初步 | BatchRunner、rate-limit、frontier claim loop | asyncio pipeline、背压、并发池、长任务监控 |
| CAP-3.6 | 数据管道 | 部分 | SQLite result/product store、Excel/JSON export、artifact manifest | Kafka/ClickHouse/Parquet/流式导出、artifact retention policy |
| CAP-4.1 | CDP / Playwright | 部分 | browser fetch、network observer、browser context、browser interceptor、runtime fingerprint probe、WebSocket observer | 原始 CDP 能力尚未封装；interception/probe/WS observation 均为 opt-in |
| CAP-4.2 | 浏览器指纹一致性 | initial / opt-in / evidence-only | `browser_fingerprint.py` 配置侧 profile/risk/recommendations；`browser_fingerprint_probe.py` opt-in runtime evidence：navigator/screen/Intl/WebGL/canvas/font | 配置侧报告不是 runtime 证明；runtime probe 不做 stealth/spoofing；无指纹池一致性闭环 |
| CAP-4.3 | JS 执行隔离 | 未开始 | 无 | QuickJS/Node VM adapter、沙箱执行、超时和副作用隔离 |
| CAP-4.4 | 资源拦截与修改 | initial / opt-in | `browser_interceptor.py` 支持 route interception、资源 blocking、JS/API metadata capture、init script；Recon 通过 `constraints.intercept_browser=true` 启用并把 captured JS 输入 `js_evidence` | 默认不启用；缺 CDP 原始事件、request fulfill/rewrite、稳定 JS bundle 持久化策略 |
| CAP-5.1 | NLP / 策略证据推理 | 部分 / advisory | LLM Advisor、selector merge、DOM recon、`js_evidence` hints；`strategy_evidence.py` 统一 DOM、observed API、JS/crypto、transport、fingerprint、challenge、WebSocket evidence；`strategy_scoring.py` 输出 http/api/browser/deeper_recon/manual_handoff scorecard；Strategy 输出 `strategy_evidence`、`strategy_scorecard`、`reverse_engineering_hints`、`api_replay_warning` | scorecard 仍是 advisory，不替代最终 mode；缺真实复杂站点校准、自动 hook/sandbox 执行 |
| CAP-5.2 | 图像识别 | 未开始 | screenshot artifact 基础 | OCR/layout/视觉区域检测、DOM 与截图对齐 |
| CAP-5.3 | 自动探索 | 初步 | Recon -> Strategy -> Executor 图、domain memory、site zoo fixtures | 缺强化探索策略、站点地图决策、自动 profile 生成 |
| CAP-5.4 | 异常检测 | 初步 | validator、quality checks、artifact evidence、challenge/error codes | 缺成功率时序监控、自动策略切换 |
| CAP-6.1 | 边界识别 | 部分 | AccessPolicy、ChallengeDetector、安全摘要、manual handoff | 还需企业条款配置、项目级安全策略开关 |
| CAP-6.2 | 反爬策略分析与证据审计 | 部分 / evidence-only | access diagnostics、fetch trace、artifact manifest、transport diagnostics、strategy evidence、proxy health evidence、AntiBotReport | 缺跨运行趋势、审计仪表盘、企业审计策略 |
| CAP-6.3 | 自适应限速 | 部分 | DomainRateLimiter 执行 per-domain delay，fetch trace 记录 rate_limit_event | 未根据响应动态调速 |
| CAP-6.4 | 数据治理 | 初步 | secret redaction、runtime artifacts ignored、storage-state path redaction、proxy credential redaction | 数据分级、加密、访问审计 |
| CAP-7.1 | 抓包工具生态 | 未开始 | browser network observer/interceptor 作为内部观测基础 | mitmproxy/Charles/Wireshark 导入与报告适配 |
| CAP-7.2 | Scrapy/Selenium | 未开始 | fnspider 集成 | Scrapy/Selenium adapter |
| CAP-7.3 | 部署/监控 | 很弱 | GitHub CI、FastAPI MVP | Docker/K8s/Prometheus、服务化监控 |

## 最近工作真实对应的能力项

### Strategy Evidence Report

对应能力：

- CAP-5.1 策略证据推理
- CAP-6.2 Evidence/audit
- CAP-2.1 / CAP-2.2 JS/crypto evidence
- CAP-1.4 WebSocket evidence

实际产物：

```text
strategy_evidence.py
strategy_scoring.py
agents/strategy.py
```

边界：

- evidence-only / advisory。
- 不自动破解签名。
- 不执行 JS。
- 不覆盖强 DOM/API/browser/challenge 决策。
- scorecard 当前只解释和预警，不直接接管最终 mode。

### WebSocket Observation

对应能力：

- CAP-1.4 WebSocket
- CAP-4.1 Playwright automation
- CAP-6.2 Evidence/audit

实际产物：

```text
websocket_observer.py
agents/recon.py
tests/test_websocket_observer.py
tests/test_recon_websocket_observation.py
```

边界：

- opt-in：`constraints.observe_websocket=true`。
- 当前主要由 mocked Playwright 测试和 Recon mock 集成证明。
- 不做帧重放、协议逆向、二进制解析或登录/验证码绕过。

### Proxy Pool And Health

对应能力：

- CAP-3.3 代理池
- CAP-6.2 Evidence/audit

实际产物：

```text
proxy_pool.py
proxy_health.py
proxy_manager.py
```

边界：

- opt-in；默认不启用代理。
- 存储 redacted proxy ID/label，不保存明文密码。
- ProviderAdapter 是模板，不是具体付费供应商集成。

### JS / Crypto Evidence

对应能力：

- CAP-2.1 JS 逆向基础
- CAP-2.2 hook/签名加密入口定位
- CAP-5.1 strategy evidence reasoning

实际产物：

```text
js_asset_inventory.py
js_static_analysis.py
js_crypto_analysis.py
js_evidence.py
strategy_evidence.py
```

边界：

- evidence-only。
- 不执行 JS。
- 不恢复密钥。
- 不绕过签名、验证码、登录或 Cloudflare。

## 下一步建议

1. CAP-5.1：把 `StrategyEvidenceReport` 从“证据解释层”推进到显式 strategy scoring policy，但仍保留强证据优先和安全边界。
2. CAP-1.4：补真实本地 WS smoke 或受控 fixture，验证 Recon opt-in 路径在真实浏览器事件下工作。
3. CAP-3.3：接入 proxy health 到更多 fetch/runner 证据链，补 provider adapter 示例，但继续保持默认关闭。
4. CAP-2.1/CAP-2.2：设计 parser-backed AST / sandbox/hook 任务，明确它们是后续能力，不把当前 regex/static evidence 夸成完整逆向。
5. CAP-6.2：校准 AntiBotReport，把报告摘要接入 CLI/API，并用真实训练案例验证风险等级和推荐动作。
6. CAP-5.2：VisualRecon/OCR MVP 只做页面文字和布局理解，不做验证码破解。

## 新任务模板要求

以后每个员工任务和主管主线必须包含：

```text
Capability IDs:
- CAP-x.x

Capability maturity:
- production-ready / opt-in / evidence-only / mocked only / initial

Why this matters:
- 对企业/爬虫开发者的价值

Acceptance:
- 代码产物
- 测试
- 实战目标
- 证据产物

Safety boundary:
- 不破解登录
- 不绕验证码
- 不默认使用代理或会话
- 不提交密钥、cookie、proxy 凭证
```
