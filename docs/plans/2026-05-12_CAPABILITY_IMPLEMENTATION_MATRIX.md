# Crawler-Mind 顶尖爬虫能力落地矩阵

日期：2026-05-12

来源能力清单：

```text
C:/Users/Administrator/Downloads/顶尖爬虫开发者能力清单.md
```

## 主管纠偏

过去几轮开发已经打下了不少工程基础，但早期任务没有始终把每个模块绑定到明确的高级爬虫能力编号。这样会让项目看起来像在堆工程模块，而不是沿着“顶尖爬虫开发者能力清单”逐项产品化。

从 2026-05-12 开始，CLM 的主线任务需要标注能力编号：

```text
CAP-1.x 网络与协议
CAP-2.x JS 逆向与对抗分析
CAP-3.x 工程架构与规模化
CAP-4.x 浏览器自动化与指纹
CAP-5.x AI 与策略推理
CAP-6.x 治理与审计
CAP-7.x 工具链与生态
```

## 总体判断

当前项目已经从“简单爬虫 MVP”推进到“高级爬虫开发工具地基”阶段。能力重心目前落在：

- CAP-3 工程架构：frontier、runner、storage、artifact manifest、FastAPI/Easy Mode。
- CAP-4 浏览器自动化：browser fetch、network observer、interceptor、context、fingerprint profile/probe。
- CAP-5 AI 与策略推理：可选 LLM advisor、JS evidence advisory、策略保守合并。
- CAP-6 治理与审计：access policy、安全边界、challenge 诊断、证据留存。

仍然薄弱的部分：

- CAP-1 深层网络协议：已有 transport diagnostics，但还没有真实 JA3/ALPN/SNI 控制和连接池指标。
- CAP-2 深层 JS 逆向：已有 JS inventory/static evidence 和 crypto/signature evidence，但不是完整 AST、控制流、数据流、反混淆或 Wasm 分析。
- CAP-4 指纹一致性：已有配置侧报告和 opt-in runtime probe，但还没有指纹池、真实一致性评分闭环或 stealth/spoofing。
- CAP-7 外部工具生态：mitmproxy/Charles/Wireshark/Scrapy/Selenium 适配仍未开始。

## 2026-05-12 能力冲刺结果

本轮已把几个“未开始”的高级能力推进到可测试基础阶段：

- CAP-2.1：已从 JS asset inventory 扩展到 pre-AST static analysis，并通过 `js_evidence.py` 接入 Recon/Strategy 证据链。诚实状态：这是静态分析基础，不是完整 AST 逆向。
- CAP-4.2：已完成配置侧 `BrowserContextConfig` 指纹一致性报告，并新增 opt-in runtime probe。诚实状态：配置侧报告不是浏览器侧证明；runtime probe 是 evidence-only，不做 stealth/spoofing。
- CAP-4.4：已实现 opt-in browser interception/recon path。诚实状态：默认不会拦截浏览器资源，必须通过 `constraints.intercept_browser=true` 启用。
- CAP-5.1：Strategy 已能读取 `recon_report.js_evidence` 并生成 advisory hints。诚实状态：JS evidence 只提供建议和补缺，不覆盖强 DOM、observed API、challenge/browser 决策。

## 能力编号与当前落地状态

| 能力编号 | 能力项 | 当前状态 | 已落地内容 | 缺口 |
|---|---|---|---|---|
| CAP-1.1 | HTTP/1.1 / HTTP/2 | 部分 | `httpx` fetch、headers、错误处理、rate-limit | HTTP/2 指纹、连接复用、连接池指标还未产品化 |
| CAP-1.2 | TLS/SSL / JA3 | 初步 | `transport_diagnostics.py` 对比 requests/curl_cffi/browser 状态码、HTTP 版本、挑战信号、响应头线索、transport profile 标签 | 还没有真实 JA3/ALPN/SNI 指纹采集、控制和调参 |
| CAP-1.3 | TCP/IP / 连接池 | 很弱 | 基础 `httpx.Client` | DNS 缓存、连接池指标、并发背压、连接复用诊断 |
| CAP-1.4 | WebSocket | 初步 | `websocket_observer.py` 已验收：连接/帧模型、sent/received 方向、text/binary 标记、预览截断、敏感信息脱敏、mock Playwright `page.on("websocket")` 观察路径、`build_ws_summary()` | 还需要 Recon opt-in 集成、真实 WS 站点 smoke、帧重放、协议解析和二进制格式解析 |
| CAP-2.1 | JS 逆向基础 / pre-AST 静态分析 | 初步 | `js_asset_inventory.py`、`js_static_analysis.py`、`js_evidence.py`；提取 JS 资源、字符串表、endpoint、GraphQL/WebSocket/sourcemap、可疑函数和调用；Recon 输出 `recon_report.js_evidence` | 不是完整 AST；缺 parser-backed AST、反混淆、控制流/数据流、source map 下载、外部 JS 全量抓取 |
| CAP-2.2 | Hook / 签名加密入口定位 | 初步 | CAP-4.4 支持 init script；`js_crypto_analysis.py` 可识别 hash/HMAC/signature/WebCrypto/AES/RSA/base64/timestamp/nonce/param sort/custom token 线索，并接入 `js_evidence` | 未做 CDP hook、函数 monkey patch、运行时调用追踪；不执行 JS、不还原密钥 |
| CAP-2.3 | Wasm 逆向 | 未开始 | 无 | Wasm 发现、下载、反编译入口、导入导出表分析 |
| CAP-2.4 | V8/CDP 调试 | 很弱 | Playwright 基础执行 | CDP session、断点、Runtime 追踪、console/source map 调试 |
| CAP-2.5 | 验证码 / OCR | 诊断级 | ChallengeDetector 识别 CAPTCHA/Cloudflare/login/access-block | 不破解验证码；缺 OCR/layout/视觉区域检测；任何 CAPTCHA provider 都需要单独 ADR 和安全审查 |
| CAP-3.1 | 任务调度 | 部分 | URLFrontier、BatchRunner、FastAPI background jobs | LangGraph processor 未接入 runner，缺 progress events、持久 job registry |
| CAP-3.2 | 去重系统 | 部分 | SQLite frontier 去重、category-aware product dedupe | Bloom/Redis/大规模内存优化 |
| CAP-3.3 | 可插拔代理池 | 初步 | ProxyConfig、ProxyManager、域名路由、凭证脱敏；`proxy_pool.py` 提供 ProxyPoolProvider 协议、静态池、round_robin/domain_sticky/first_healthy、失败熔断和安全摘要；默认不启用代理 | 付费供应商 adapter、真实健康探测、跨进程池状态、质量评分仍待做 |
| CAP-3.4 | 指纹池 | 初步 | BrowserContextConfig、Browser fingerprint profile/probe foundation | 缺可轮换指纹池、profile 分组、跨请求一致性治理 |
| CAP-3.5 | 高并发性能 | 初步 | BatchRunner、rate-limit、frontier claim loop | asyncio pipeline、背压、并发池、长任务监控 |
| CAP-3.6 | 数据管道 | 部分 | SQLite result/product store、Excel/JSON export、artifact manifest | Kafka/ClickHouse/Parquet/流式导出、artifact retention policy |
| CAP-4.1 | CDP / Playwright | 部分 | browser fetch、network observer、browser context、browser interceptor、runtime fingerprint probe | 原始 CDP 能力尚未封装；request interception 仍是 opt-in |
| CAP-4.2 | 浏览器指纹一致性 | 初步 | `browser_fingerprint.py` 配置侧 profile/risk/recommendations；`browser_fingerprint_probe.py` opt-in runtime evidence：navigator/screen/Intl/WebGL/canvas/font | 配置侧报告不是 runtime 证明；runtime probe evidence-only；无 stealth/spoofing、无指纹池一致性闭环 |
| CAP-4.3 | JS 执行隔离 | 未开始 | 无 | QuickJS/Node VM adapter、沙箱执行、超时和副作用隔离 |
| CAP-4.4 | 资源拦截与修改 | 初步 | `browser_interceptor.py` 支持 route interception、资源 blocking、JS/API metadata capture、init script；Recon 可通过 `constraints.intercept_browser=true` 启用 | 默认不启用；还缺 CDP 原始事件、request fulfill/rewrite、稳定的 JS bundle 持久化策略 |
| CAP-5.1 | NLP / 策略证据推理 | 部分 | LLM Advisor、selector merge、DOM recon、`js_evidence` advisory hints；Strategy 可解释 API/hook/challenge clues 并在 api_intercept 已选中时补缺 endpoint | JS evidence 不覆盖强证据；缺多证据评分器、真实复杂站点策略训练闭环 |
| CAP-5.2 | 图像识别 | 未开始 | screenshot artifact 基础 | OCR/layout/视觉区域检测、DOM 与截图对齐 |
| CAP-5.3 | 自动探索 | 初步 | Recon -> Strategy -> Executor 图、domain memory、site zoo fixtures | 缺强化探索策略、站点地图决策、自动 profile 生成 |
| CAP-5.4 | 异常检测 | 初步 | validator、quality checks、artifact evidence、challenge/error codes | 缺成功率时序监控、自动策略切换 |
| CAP-6.1 | 边界识别 | 部分 | AccessPolicy、ChallengeDetector、安全摘要、manual handoff | 还需企业条款配置、项目级安全策略开关 |
| CAP-6.2 | 反爬策略分析 | 部分 | access diagnostics、fetch trace、artifact manifest、transport diagnostics | 缺完整 AntiBotReport 和跨运行趋势 |
| CAP-6.3 | 自适应限速 | 部分 | DomainRateLimiter 执行 per-domain delay，fetch trace 记录 rate_limit_event | 未根据响应动态调速 |
| CAP-6.4 | 数据治理 | 初步 | secret redaction、runtime artifacts ignored、storage-state path redaction | 数据分级、加密、访问审计 |
| CAP-7.1 | 抓包工具生态 | 未开始 | browser network observer/interceptor 作为内部观测基础 | mitmproxy/Charles/Wireshark 导入与报告适配 |
| CAP-7.2 | Scrapy/Selenium | 未开始 | fnspider 集成 | Scrapy/Selenium adapter |
| CAP-7.3 | 部署/监控 | 很弱 | GitHub CI、FastAPI MVP | Docker/K8s/Prometheus、服务化监控 |

## 最近工作真实对应的能力项

### Access Layer MVP

对应能力：

- CAP-3.3 代理池基础
- CAP-6.1 边界识别
- CAP-6.2 反爬策略分析
- CAP-6.3 自适应限速雏形

实际产物：

```text
access_policy.py
challenge_detector.py
proxy_manager.py
session_profile.py
rate_limit_policy.py
rate_limiter.py
access_config.py
```

### Browser Context / Fingerprint Foundation

对应能力：

- CAP-3.4 指纹池雏形
- CAP-4.1 Playwright 自动化
- CAP-4.2 浏览器指纹一致性

实际产物：

```text
browser_context.py
browser_fetch.py
browser_network_observer.py
browser_fingerprint.py
browser_fingerprint_probe.py
```

边界：

- `browser_fingerprint.py` 是配置侧报告。
- `browser_fingerprint_probe.py` 是 opt-in runtime evidence，不做 stealth/spoofing。

### Browser Interception / JS Evidence

对应能力：

- CAP-2.1 JS 逆向基础
- CAP-2.2 Hook 技术准备
- CAP-4.4 资源拦截与 JS 捕获
- CAP-5.1 策略证据推理

实际产物：

```text
browser_interceptor.py
js_asset_inventory.py
js_static_analysis.py
js_crypto_analysis.py
js_evidence.py
agents/strategy.py
```

边界：

- browser interception 是 opt-in，需要 `constraints.intercept_browser=true`。
- JS analysis 是静态启发式基础，不是完整 AST/反混淆。
- Crypto/signature analysis 是证据定位，不执行 JS、不恢复密钥。
- Strategy 只把 JS evidence 作为 advisory hints，不覆盖强证据。

### Artifact Manifest

对应能力：

- CAP-3.6 数据管道
- CAP-5.4 异常检测基础
- CAP-6.2 反爬策略分析证据

实际产物：

```text
artifact_manifest.py
runtime/artifacts/
```

### LLM Advisor / Easy Mode

对应能力：

- CAP-5.1 NLP 辅助

实际产物：

```text
llm/
planner advisor
strategy advisor
clm.py
```

## 下一步建议

优先级建议：

1. CAP-1.4 WebSocket Recon 集成：把已验收的 WebSocket observer 作为 opt-in evidence channel 接入 Recon。
2. CAP-5.1 多证据策略评分器：把 DOM、observed API、JS evidence、WS evidence、transport diagnostics、challenge diagnostics 合成统一 strategy evidence score。
3. CAP-4.2 Fingerprint profile pool：在 runtime probe 基础上做 profile 分组、一致性评分和真实浏览器训练记录。
4. CAP-1.2 Transport diagnostics 下一阶段：补 ALPN/SNI/JA3 可观测性边界说明，避免误称“已支持 TLS 指纹控制”。
5. CAP-5.2 VisualRecon/OCR MVP：只做页面文字和布局理解，不做验证码破解。

## 新任务模板要求

以后每个员工任务和主管主线必须包含：

```text
Capability IDs:
- CAP-x.x

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
