# Crawler-Mind 顶尖爬虫能力落地矩阵

日期：2026-05-12

来源能力清单：

```text
C:/Users/Administrator/Downloads/顶尖爬虫开发者能力清单.md
```

## 主管纠偏

过去几轮开发确实做了不少基础能力，但没有把每个任务明确绑定到
“顶尖爬虫开发者能力清单”。这会造成一个问题：项目看起来像在堆工程模块，
而不是沿着高级爬虫能力逐项攻坚。

从现在开始，CLM 的每个主线任务都必须标注能力编号：

```text
CAP-1.x 网络与协议
CAP-2.x 逆向与对抗
CAP-3.x 工程架构与规模化
CAP-4.x 浏览器自动化与指纹
CAP-5.x AI 与算法
CAP-6.x 治理与审计
CAP-7.x 工具链与生态
```

## 总体判断

当前项目不是没有往能力清单走，而是主要落在：

- CAP-3 工程架构
- CAP-4 浏览器自动化基础
- CAP-5 LLM 辅助
- CAP-6 审计与证据

真正还没有开始或非常薄弱的是：

- CAP-1 网络协议深水区：HTTP/2、TLS/JA3、连接池、WebSocket
- CAP-2 JS 逆向、Hook、Wasm、验证码视觉识别
- CAP-4 指纹一致性、CDP hook、资源拦截
- CAP-7 Scrapy/Selenium/mitmproxy/抓包生态适配

也就是说：我们打了工程地基，但还没有足够进入“高级爬虫技术攻坚层”。

## 能力编号与当前落地状态

| 能力编号 | 能力项 | 当前状态 | 已落地内容 | 缺口 |
|---|---|---|---|---|
| CAP-1.1 | HTTP/1.1 / HTTP/2 | 部分 | `httpx` fetch、headers、错误处理、rate-limit | HTTP/2 指纹、连接复用、协议诊断未产品化 |
| CAP-1.2 | TLS/SSL / JA3 | 初步 | `transport_diagnostics.py` 可对比 requests/curl_cffi/browser 的状态码、HTTP 版本、挑战信号、质量分和响应头线索 | 还没有真实 JA3/ALPN/SNI 指纹采集与调参 |
| CAP-1.3 | TCP/IP / 连接池 | 很弱 | 基础 `httpx.Client` | 没有连接池指标、DNS 缓存、并发背压 |
| CAP-1.4 | WebSocket | 未开始 | 无 | 需要 WS 观察、帧记录、重放/解析 |
| CAP-2.1 | JS AST 逆向 | 未开始 | 无 | 需要 JS asset inventory、AST 解析、混淆特征 |
| CAP-2.2 | Hook 技术 | 未开始 | 无 | 需要 Playwright init script / CDP hook 能力 |
| CAP-2.3 | Wasm 逆向 | 未开始 | 无 | 需要 Wasm 发现、下载、反编译入口 |
| CAP-2.4 | V8/CDP 调试 | 很弱 | Playwright 基础执行 | 没有 CDP session、断点、Runtime 追踪 |
| CAP-2.5 | 验证码/OCR | 诊断级 | ChallengeDetector 识别 CAPTCHA/Cloudflare | 无 OCR、无滑块/点选视觉分析、无人工插件接口 |
| CAP-3.1 | 任务调度 | 部分 | URLFrontier、BatchRunner、FastAPI background jobs | 未接 LangGraph processor，缺 progress events |
| CAP-3.2 | 去重系统 | 部分 | SQLite frontier 去重 | 无 Bloom/Redis/大规模内存优化 |
| CAP-3.3 | 代理池 | 初步 | ProxyConfig、ProxyManager、域名路由、脱敏 | 无健康评分、熔断、供应商适配 |
| CAP-3.4 | 指纹池 | 初步 | BrowserContextConfig: UA/viewport/locale/timezone | 无 Canvas/WebGL/font 指纹一致性 |
| CAP-3.5 | 高并发性能 | 初步 | BatchRunner、rate-limit | 无 asyncio pipeline、背压、并发池 |
| CAP-3.6 | 数据管道 | 部分 | SQLite result/product store、Excel/JSON、artifact manifest | 无 Kafka/ClickHouse/Parquet/流式导出 |
| CAP-4.1 | CDP / Playwright | 部分 | browser fetch、network observer、context config | 未暴露 CDP 原始能力、request interception |
| CAP-4.2 | 指纹一致性 | 初步 | 统一 browser context | 无指纹 profile、无一致性校验 |
| CAP-4.3 | JS 执行隔离 | 未开始 | 无 | 需要 QuickJS/Node VM adapter |
| CAP-4.4 | 资源拦截与修改 | 未开始 | 无 | 需要 route/fulfill/inject script 能力 |
| CAP-5.1 | NLP 辅助选择器 | 部分 | LLM Advisor、selector merge、DOM recon | 未做真实复杂站 selector agent 训练闭环 |
| CAP-5.2 | 图像识别 | 未开始 | screenshot artifact | 无 OCR/layout/视觉区域检测 |
| CAP-5.3 | 自动探索 | 初步 | Recon -> Strategy -> Executor 图 | 无强化探索策略、站点地图决策 |
| CAP-5.4 | 异常检测 | 初步 | validator、quality checks、artifact evidence | 无成功率时序监控、自动策略切换 |
| CAP-6.1 | 边界识别 | 部分 | AccessPolicy、ChallengeDetector、安全摘要 | 后续要形成企业条款/配置开关 |
| CAP-6.2 | 反爬策略分析 | 部分 | access diagnostics、fetch trace、artifact manifest | 缺完整 AntiBotReport |
| CAP-6.3 | 自适应限速 | 部分 | DomainRateLimiter 执行 per-domain delay | 尚未根据响应动态调速 |
| CAP-6.4 | 数据治理 | 初步 | secret redaction、runtime artifacts ignored | 无数据分级、加密、访问审计 |
| CAP-7.1 | 抓包工具生态 | 未开始 | browser network observer | 无 mitmproxy/Charles/Wireshark 导入 |
| CAP-7.2 | Scrapy/Selenium | 未开始 | fnspider 集成 | 无 Scrapy/Selenium adapter |
| CAP-7.3 | 部署/监控 | 很弱 | GitHub CI、FastAPI MVP | 无 Docker/K8s/Prometheus |

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

### Browser Context Foundation

对应能力：

- CAP-3.4 指纹池雏形
- CAP-4.1 Playwright 自动化
- CAP-4.2 指纹一致性雏形

实际产物：

```text
browser_context.py
browser_fetch.py
browser_network_observer.py
```

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

## 立刻调整的开发顺序

能力优先后，下一阶段不再继续泛泛扩工程层，而是直接攻清单里的高级能力。

### T1：CAP-4.4 资源拦截与 JS 注入

目标：

让 Playwright 不只是打开页面，而是能：

- route 请求
- block 图片/字体/媒体
- 捕获和保存 JS bundle
- 注入 init script
- 记录被调用的 fetch/XHR/WebSocket

为什么优先：

这是动态站、反调试、API 发现、Hook 技术的入口。

### T2：CAP-2.1 JS Asset Inventory + AST 基础分析

目标：

对页面 JS 资源做清单：

- JS 文件 URL
- 文件大小/hash
- 可疑关键词：sign、token、encrypt、crypto、wbi、captcha、webpack
- API endpoint 字符串
- sourcemap 线索

再进入 AST：

- 提取函数名
- 提取字符串字面量
- 找疑似签名函数

### T3：CAP-1.2 TLS/HTTP 指纹诊断

目标：

至少先输出诊断报告：

- requests/httpx 与 curl_cffi 的响应差异
- HTTP/2 是否启用
- TLS impersonate profile
- 403/429 是否与 transport mode 相关

当前落地：

```text
autonomous_crawler/tools/transport_diagnostics.py
autonomous_crawler/tests/test_transport_diagnostics.py
Recon constraints.transport_diagnostics=true
```

### T4：CAP-4.2 Browser Fingerprint Profile

目标：

把 browser_context 升级成 profile：

- UA
- viewport
- locale
- timezone
- color scheme
- device scale factor
- touch/mobile
- WebGL/Canvas/font 检查报告

### T5：CAP-5.2 VisualRecon / OCR MVP

目标：

先不做验证码破解，先做视觉理解：

- screenshot catalog
- OCR adapter interface
- 页面文字提取
- repeated card 视觉区域检测
- DOM selector 对齐

## 新的任务模板要求

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
```

## 下一步建议

立刻开始：

```text
CAP-4.4 Browser Request Interception + JS Capture MVP
CAP-2.1 JS Asset Inventory MVP
```

这两个最符合“高级爬虫开发者”的差异化能力，也最能解释为什么企业不用普通
LLM 写脚本，而要用 CLM。
