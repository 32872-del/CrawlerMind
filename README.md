# Crawler-Mind (CLM)

Crawler-Mind，简称 **CLM**，是一个正在快速迭代的 **AI 驱动数据采集 Agent / 爬虫工程平台**。

它不是一个只会跑单个脚本的 scraper，也不是把网页丢给大模型后让模型“猜一猜”的玩具项目。CLM 的目标是把高级爬虫开发中常见的能力沉淀成一个可运行、可观察、可恢复、可持续训练的系统：

```text
用户目标 / 目标网站 / 目录 URL / 字段要求
  -> 站点侦察与证据采样
  -> AI / 规则混合决策
  -> HTTP / Browser / API Replay / Profile Longrun Runtime
  -> 字段抽取 / 质量检查 / 覆盖率诊断
  -> 失败分析 / 修复动作 / 重跑
  -> 导出 / 报告 / 训练沉淀
```

当前项目仍处于工程开发阶段，但已经从早期 LangGraph 爬虫原型，发展成一个具备 CLI、FastAPI、中文 Web 工作台、CLM-native 采集后端、长跑 checkpoint、AI managed loop、真实网站训练记录的本地平台。

## Community / Private Core 声明

当前公开仓库是 **CLM Community**：用于公开展示、基础采集、开发验证、工作台体验和可复现 demo。

CLM 的高级采集核心、真实站点训练资产、企业级策略、私有 profile、深度修复策略和长期积累的失败样本，由作者在独立私有核心包中维护。公开版会保持真实可运行，但不代表 CLM 的全部商业能力和全部训练资产已经公开。

```text
CLM Community:
  - 可运行 CLI / API / 工作台
  - 可复现 demo
  - 基础采集 runtime
  - 基础 managed workflow

CLM Private Core:
  - 高级 managed repair policy
  - 真实站点 profile / playbook
  - 深度 API/XHR/GraphQL replay 策略
  - 高级 browser/session/proxy 策略
  - 训练数据、失败样本和企业级扩展
```

## 项目背景

传统爬虫项目最大的问题不是“写一个请求”有多难，而是后续一连串工程问题很难稳定处理：

- 网站是静态 HTML、SPA、接口驱动、GraphQL，还是混合渲染？
- 商品目录、分页、详情页、变体、价格、尺码、颜色、图片字段在哪里？
- 页面是否需要浏览器渲染，是否存在 XHR/API 可以直接 replay？
- 一个站点有几千到几万商品时，如何 checkpoint、恢复、并发、去重、补采？
- 为什么明明网站有 5000 条商品，最后只采到 4000 条？
- 失败是访问失败、目录漏掉、分页没跑、字段 selector 错了、API token 失效，还是质量门拒绝？
- AI 到底能不能不仅“提建议”，而是参与分析、决策、执行、修复和复盘？

CLM 就是围绕这些问题做的。

它的产品目标是：**让爬虫开发者和数据团队用更低成本完成复杂采集任务，同时保留工程可控性和可解释性。**

## 当前定位

```text
项目名称: Crawler-Mind
简称: CLM
状态: active development
后端: Python + FastAPI + CLM-native crawler runtime
前端: Vite + React 中文工作台
AI 接入: OpenAI-compatible provider interface
推荐 Python: 3.11+
当前成熟度: 早期平台，可本地运行，仍在进行真实站点硬化
```

当前进度评估：

```text
Level 1 skeleton: complete
Level 2 usable MVP: complete
Level 3 advanced crawler backend: 75% - 82%
Level 4 visible AI decision loop: 58% - 68%
Level 5 product workbench / long-run operations: 45% - 55%
Overall: 68% - 75%
```

当前主线：

```text
AI managed workflow
  -> evidence/recon
  -> profile/runtime patch
  -> long-run execution
  -> quality/export
```

下一阶段核心目标是 **AI Managed Crawl Loop v2**：让 AI 不只是参与站点分析，而是贯穿“分析、试跑、诊断、修复、重跑、导出”的完整采集闭环。

## Quick Demo

第一次看项目，建议先跑这个离线 demo：

```bash
python clm.py demo ecommerce
```

它不依赖外部网站，适合新环境、GitHub 访客和录屏展示。这个 demo 会展示：

- profile-driven ecommerce collection。
- pause / resume。
- checkpoint store。
- product store。
- quality gate。
- report generation。

预期结果：

```text
Demo accepted
records: 55
status: completed
```

输出文件：

```text
dev_logs/runtime/clm_demo_ecommerce.json
```

更多稳定示例见：[examples/README.md](examples/README.md)

录制展示流程见：[docs/runbooks/DEMO_RECORDING_GUIDE.md](docs/runbooks/DEMO_RECORDING_GUIDE.md)

## 架构演进

CLM 最初是一个 LangGraph 风格的确定性 pipeline：

```text
Planner -> Recon -> Strategy -> Executor -> Extractor -> Validator
```

这条链路现在仍然保留，用于简单任务、兼容测试和基础工作流。但项目已经扩展为更完整的平台结构：

```text
                       +----------------------+
User Goal / Site URL ->| Evidence / Recon     |
Catalog / Fields       +----------+-----------+
                                  |
                                  v
                       +----------------------+
                       | Managed Action Plan  |
                       | LLM + deterministic  |
                       +----------+-----------+
                                  |
                                  v
        +-------------------------+-------------------------+
        |                         |                         |
        v                         v                         v
  Static HTTP Runtime       Browser Runtime            API Replay Runtime
  Parser Runtime            XHR Observation            GraphQL / JSON Replay
        |                         |                         |
        +-------------------------+-------------------------+
                                  |
                                  v
                       +----------------------+
                       | Profile Longrun      |
                       | Checkpoint / Store   |
                       +----------+-----------+
                                  |
                                  v
                       +----------------------+
                       | Quality / Coverage   |
                       | Diagnose / Repair    |
                       +----------+-----------+
                                  |
                                  v
                       Export / Report / Training Evidence
```

## 已有核心能力

### 1. 易用入口

CLM 提供了一个统一的新手入口 `clm.py`：

```bash
python clm.py init
python clm.py check
python clm.py crawl "collect product titles and prices" mock://catalog
python clm.py smoke --kind runner
python clm.py train
```

这个入口用于替代早期散落的开发脚本，让用户可以先完成安装检查、配置初始化、mock 采集、简单真实站点采集和训练命令查看。

### 2. FastAPI 后端

CLM 已经有本地 API 服务，用于前端工作台、任务管理和 managed workflow：

```text
GET  /health
POST /crawl
GET  /crawl/{task_id}
GET  /history

POST /site/analyze
POST /runs/managed/execute-and-run
POST /runs/managed/diagnose-and-repair
POST /runs/{task_id}/managed-control-loop
```

这些接口把站点分析、任务执行、AI managed action、诊断修复、导出等能力暴露给 Web 工作台。

### 3. 中文 Web 工作台

`frontend/` 下已经包含 Vite + React 中文工作台。当前工作台目标流程是：

```text
配置模型 -> 输入站点 -> 分析目录 -> 选择字段
  -> 试跑 -> 诊断/修复 -> 全量运行 -> 监控 -> 导出
```

目前前端已经具备模型配置、模型列表获取、任务详情、AI managed 面板、导出路径、站点分析和任务运行入口。后续还在继续加强一键闭环、过程可见性、页面状态保持和实时事件流。

### 4. OpenAI-compatible LLM 接入

CLM 的 LLM 配置面向 OpenAI-compatible 协议设计，方便接入 OpenAI、兼容中转站以及其他兼容服务：

```text
base_url
api_key
model
response_format support
reasoning / managed trace options
```

当前 LLM 能力包括：

- Planner / Strategy advisor。
- model list discovery。
- LLM trace / decision record。
- managed action plan。
- deterministic fallback。
- provider 失败时不中断基础流程。

项目当前重点不是“让模型自由写自然语言建议”，而是让模型输出可验证、可执行、可追踪的 action。

### 5. CLM-native 采集后端

CLM 正在吸收成熟爬虫框架能力，最终目标不是长期依赖外部库 wrapper，而是形成自己的 native runtime。

目前已经具备：

- 静态 HTTP fetch runtime。
- `httpx` / `curl_cffi` 风格传输诊断基础。
- Parser runtime，支持 CSS、XPath、文本、正则。
- adaptive selector relocation。
- selector memory。
- Playwright browser runtime。
- browser context、headers、cookies、storage state、proxy config。
- browser profile / profile pool foundation。
- XHR / JSON response evidence capture。
- API replay runtime。
- GraphQL / JSON replay 基础。
- replay diagnostics。
- link discovery。
- robots policy helper。
- URL frontier。
- checkpoint store。
- spider runtime processor。
- profile-driven ecommerce longrun。
- product store。
- product quality gate。
- coverage report。

### 6. 电商采集基础

CLM 的一个重点方向是电商数据采集，因为电商站点集中包含了目录、分页、详情页、SKU、价格、颜色、尺码、图片、描述、库存、变体、API、动态渲染等复杂问题。

当前已有能力：

- 目录 URL / 商品 URL 发现。
- product record schema。
- 商品标题、价格、图片、描述、分类、链接等基础字段处理。
- 变体字段训练，包括尺码、颜色等。
- category-aware dedupe。
- product quality validation。
- 质量拒绝原因统计。
- valid / invalid product 区分。
- 长跑 checkpoint。
- Excel / JSON / CSV 导出基础。

### 7. 长任务和大体量基础

CLM 已经开始从“能跑通一次”升级为“能长时间运行”：

- `BatchRunner` 支持批量处理。
- URL frontier 支持任务队列。
- checkpoint store 支持暂停、恢复、完成状态记录。
- product store 支持增量写入。
- coverage report 支持定位漏采环节。
- profile longrun 支持以站点 profile 形式组织长跑。
- synthetic stress test 验证过 30,000 条记录级别的本地处理。

这些能力是后续支持单站几千到几万商品采集的基础。

## 训练成果与阶段进展

CLM 的开发不是只在 mock 里自嗨。项目一直保留真实网站训练、smoke test、stress test 和验收记录，方便把失败转成能力。

### 百度热搜 smoke test

早期端到端测试已经跑通：

```text
目标: 百度实时热搜前 30 条
链路: Planner -> Recon -> Strategy -> Executor -> Extractor -> Validator
结果: 成功采集 30 条
意义: 证明完整 LangGraph 工作流可以在真实页面上闭环
```

### Public API / JSON / GraphQL 训练

2026-05-09 real-site training round 4 覆盖了多个公开 API 和一个浏览器网络观察场景：

| 场景 | 结果 | 数量 | 关键收获 |
|---|---:|---:|---|
| DummyJSON products API | completed | 10 | 产品 API 字段标准化 |
| Hacker News Algolia API | completed | 10 | `hits` JSON shape 支持 |
| GitHub CPython issues API | completed | 10 | `html_url` / comments 映射 |
| Quotes to Scrape API | completed | 10 | `quotes` JSON shape 支持 |
| HN Algolia browser-network observation | completed | 10 | 观察 XHR 后 replay JSON POST |

这轮训练修复了两个通用问题：

- JSON payload 中出现 `captcha` 等词时，不应该误判成 HTML 反爬页面。
- `hits`、`quotes` 等常见 API response shape 需要被 generic extractor 支持。

训练后 HN Algolia SPA 场景可以通过观察公共 XHR 并 replay JSON POST 完成采集。

### 电商真实站训练

2026-05-11 进行了两轮真实站训练：

```text
Round 1: 5 个公开目标，每个 50 条
Round 2: Tatuum / The Sting / BalticBHP，每站 200 条
总计: 850 行导出数据
```

这轮训练推动了几个重要基础能力：

- `ProductRecord`。
- SQLite `ProductStore`。
- product quality validation。
- category-aware dedupe。
- generic resumable `BatchRunner`。
- 长跑 ecommerce runbook。
- `dev_logs/` 分区整理。
- `clm.py` Easy Mode CLI。

也暴露了真实差距：

- 颜色字段在部分站点仍然需要更强的变体识别。
- 空 HTTP 200、详情页字段缺失、站点差异化 profile 还需要持续沉淀。
- 长跑需要比“单次脚本导出”更可靠的 checkpoint 和恢复。

### 本地大体量 stress test

项目做过 30,000 条 synthetic ecommerce record 级别的本地压力验证：

```text
记录数: 30,000
能力验证:
  - frontier insert / claim / done
  - result storage save / load
  - Excel export
  - memory observation
结论:
  - 本地基础存储和批处理可以支撑大体量训练
  - 真实长跑仍需要更强 product checkpoint 和 runtime resume
```

### 双电商 10 分钟训练

2026-05-18 对 `https://www.sephora.pl/` 和 `https://uvex.com.pl/` 做了 10 分钟训练，重点不是追求最终 2000 条，而是诊断速度、成功率和漏损位置。

| 站点 | 有效记录 | 尝试数 | 接受率 | 记录/分钟 | 主要损失 |
|---|---:|---:|---:|---:|---|
| Sephora PL | 121 | 232 | 52.16% | 10.26 | 候选 PID 无效、质量拒绝 |
| uvex PL | 340 | 340 | 100.00% | 50.98 | 目录发现耗时、顺序抓取慢 |

关键发现：

- Sephora 并不是发现不到商品，发现到了 `24,642` 个 sitemap product URL 和 `669` 个 category URL，主要问题是候选 PID 过滤和质量拒绝。
- uvex 当前质量很好，`340/340` 通过，但目录发现和详情页抓取太顺序，需要并行和缓存。
- 训练推动了 `coverage-report/v1`，把漏采拆成 inventory、discovery、schedule、access、render、parse、quality、export 等阶段。

### AI Managed Loop 训练

2026-06-02 的 E2E managed-loop 训练保存在：

```text
dev_logs/training/e2e_site_list_20260602/
```

这批训练证明 managed loop 可以运行，也暴露了重要问题：

- 某些场景下 managed loop 会低于 direct crawl 的成功路径。
- JSON API、pagination pages、Superdry-style ecommerce 等场景需要继续硬化。
- 后续修复重点是保留 direct crawl 已经成功的路径，避免 AI repair 用较弱路径覆盖已知好路径。

### 迁移前同步状态

2026-06-12 的迁移同步报告确认，当前仓库已经具备：

- Easy Mode CLI。
- FastAPI product workflow APIs。
- 中文 React workbench。
- CLM-native runtime backend。
- profile longrun / checkpoint foundation。
- managed actions。
- quality gate。
- diagnosis / repair loop。
- extraction contract discovery。
- real-site training evidence。

## 后续开发计划

当前最重要的路线不是继续零散增加工具，而是让工具进入一条 AI 能驾驶的主流程。

### P0：AI Managed Crawl Loop v2

目标：AI 从“顾问”升级为“采集主管”。

要完成：

- 统一 managed crawl state。
- 让每一步都有 evidence、decision、action、result、quality。
- 让 LLM 输出结构化 action plan，而不是自然语言建议。
- action executor 真正调用已有后端能力。
- 失败后自动 diagnosis -> repair -> rerun。
- 前端完整显示 AI 决策过程。
- 保留 direct crawl 成功路径，不让 AI 介入后退步。

### P1：真实站点硬化

重点：

- 目录发现准确率。
- 商品 URL 覆盖率。
- 分页执行。
- 详情页字段质量。
- API/XHR replay 稳定性。
- GraphQL / pure JSON array / Firebase-like API。
- 浏览器渲染与 XHR evidence。
- profile patch 与 selector memory。

### P2：长跑和并发能力

重点：

- 单站几千到几万商品长跑。
- 最多多站并行采集。
- async fetch pool。
- backpressure。
- checkpoint resume。
- replacement queue。
- catalog discovery cache。
- export streaming。
- 运行过程 ETA 和成功率估算。

### P3：前端产品化

重点：

- 全中文向导式工作流。
- LLM 配置和模型选择。
- 目录导入与目录分析结果合并。
- 字段选择和自然语言字段定位。
- 测试运行 / 全量运行。
- 暂停 / 取消 / 删除 / 清除。
- 实时事件流。
- AI 推理强度和过程显示。
- 导出路径、格式、模板映射。

### P4：高级爬虫能力

重点：

- 更强 browser profile。
- session-bound API replay。
- proxy provider adapter。
- JS evidence / token / signature 分析。
- 视觉/OCR 辅助字段识别。
- CAPTCHA / challenge 诊断和处理策略。
- 更完整的站点 profile 学习机制。

## 安装与使用

### Windows PowerShell

```powershell
git clone https://github.com/32872-del/CrawlerMind.git
cd CrawlerMind

python -m venv .venv
.\.venv\Scripts\Activate.ps1

python -m pip install --upgrade pip
python -m pip install -r requirements.txt
playwright install
```

如果 PowerShell 阻止虚拟环境激活：

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

### Linux / macOS

```bash
git clone https://github.com/32872-del/CrawlerMind.git
cd CrawlerMind

python3 -m venv .venv
source .venv/bin/activate

python -m pip install --upgrade pip
python -m pip install -r requirements.txt
playwright install
```

Linux 服务器可能还需要：

```bash
playwright install-deps
```

### 初始化配置

```bash
python clm.py init
python clm.py check
```

### 配置 LLM

CLM 支持 OpenAI-compatible API：

```bash
python clm.py init --force --enable-llm \
  --base-url https://api.openai.com/v1 \
  --model gpt-4o-mini \
  --api-key your-real-api-key
```

Windows PowerShell 写法：

```powershell
python clm.py init --force --enable-llm `
  --base-url https://api.openai.com/v1 `
  --model gpt-4o-mini `
  --api-key your-real-api-key
```

如果中转站不支持 `response_format`：

```bash
python clm.py init --force --enable-llm --disable-response-format ...
```

检查 LLM：

```bash
python clm.py check --llm
```

`clm_config.json` 已经被 git ignore，不要提交真实 API key。

### 运行 mock 采集

```bash
python clm.py crawl "collect product titles and prices" mock://catalog --output dev_logs/runtime/mock_result.json
```

预期结果：

```text
Final Status: completed
Extracted Data: 2 items
```

### 运行推荐 Demo

```bash
python clm.py demo ecommerce
```

其他 demo：

```bash
python clm.py demo mock
python clm.py demo spider
```

### 运行真实页面 smoke

```bash
python clm.py crawl "collect top 30 hot searches" "https://top.baidu.com/board?tab=realtime" --output dev_logs/runtime/baidu_hot.json
```

### 启动 API 服务

```bash
uvicorn autonomous_crawler.api.app:app --reload --host 127.0.0.1 --port 8000
```

API 文档：

```text
http://127.0.0.1:8000/docs
```

### 启动前端工作台

先启动后端：

```bash
uvicorn autonomous_crawler.api.app:app --reload --host 127.0.0.1 --port 8000
```

再启动前端：

```bash
cd frontend
npm install
npm run dev -- --port 5174
```

打开：

```text
http://127.0.0.1:5174
```

### 测试

后端完整测试：

```bash
python -m unittest discover -s autonomous_crawler/tests
```

工作流 API 测试：

```bash
python -m unittest autonomous_crawler.tests.test_product_workflow_api.ProductWorkflowAPITests -v
```

编译检查：

```bash
python -m compileall autonomous_crawler clm.py run_simple.py -q
```

前端构建：

```bash
cd frontend
npm run build
```

## 仓库结构

```text
autonomous_crawler/
  agents/              Planner / Recon / Strategy / Executor / Extractor / Validator
  api/                 FastAPI 服务与工作台接口
  llm/                 LLM provider、advisor、trace、audit
  runtime/             CLM-native fetch/parser/browser/runtime contracts
  spider/              frontier、checkpoint、link discovery、spider processor
  product/             ProductRecord、ProductStore、quality gate
  workflows/           crawl graph 与 managed workflow
  tests/               单测、API 测试、runtime 测试、训练回归

frontend/
  Vite + React 中文工作台

docs/
  blueprints/          蓝图
  plans/               当前计划
  runbooks/            安装、迁移、诊断、前端 API
  reports/             日报、阶段报告、训练报告
  team/                多 Agent 协作、任务板、验收记录

dev_logs/
  development/         开发日志
  training/            真实站点与合成训练证据
  smoke/               smoke test 输出
  stress/              压力测试输出
  runtime/             本地运行输出
```

## 重要文档

- 当前状态：[PROJECT_STATUS.md](PROJECT_STATUS.md)
- 当前主计划：[PLAN.md](PLAN.md)
- AI managed loop 计划：[docs/plans/2026-05-20_AI_MANAGED_CRAWL_LOOP_V2_SHORT_TERM_PLAN.md](docs/plans/2026-05-20_AI_MANAGED_CRAWL_LOOP_V2_SHORT_TERM_PLAN.md)
- 稳定示例：[examples/README.md](examples/README.md)
- Demo 录制指南：[docs/runbooks/DEMO_RECORDING_GUIDE.md](docs/runbooks/DEMO_RECORDING_GUIDE.md)
- 新环境迁移：[docs/runbooks/ENVIRONMENT_MIGRATION_2026_06_12.md](docs/runbooks/ENVIRONMENT_MIGRATION_2026_06_12.md)
- 新手使用指南：[docs/runbooks/CLM_BEGINNER_USER_GUIDE_CN.md](docs/runbooks/CLM_BEGINNER_USER_GUIDE_CN.md)
- Windows 快速开始：[docs/runbooks/QUICK_START_WINDOWS.md](docs/runbooks/QUICK_START_WINDOWS.md)
- Linux/macOS 快速开始：[docs/runbooks/QUICK_START_LINUX_MAC.md](docs/runbooks/QUICK_START_LINUX_MAC.md)
- 高级诊断：[docs/runbooks/ADVANCED_DIAGNOSTICS.md](docs/runbooks/ADVANCED_DIAGNOSTICS.md)
- 电商采集流程：[docs/process/ECOMMERCE_CRAWL_WORKFLOW.md](docs/process/ECOMMERCE_CRAWL_WORKFLOW.md)
- 原始蓝图：[docs/blueprints/AUTONOMOUS_CRAWL_AGENT_BLUEPRINT.md](docs/blueprints/AUTONOMOUS_CRAWL_AGENT_BLUEPRINT.md)
- 团队看板：[docs/team/TEAM_BOARD.md](docs/team/TEAM_BOARD.md)
- 贡献指南：[CONTRIBUTING.md](CONTRIBUTING.md)

## 当前限制

CLM 已经具备较多后端能力，但还不是最终产品：

- AI managed loop 还需要继续强化真实站点稳定性。
- 前端工作台还需要更顺滑的一键流程和更完整的实时可见性。
- 高难动态站、无限滚动、签名 API、session-bound replay 仍需更多训练。
- 长任务虽然有 checkpoint 基础，但生产级任务调度、持久 job registry、跨进程恢复还需要继续完善。
- CAPTCHA/OCR、视觉字段识别、深层 JS 逆向属于后续高级能力，不应被描述成已完成默认路径。

## 许可证

MIT License. See [LICENSE](LICENSE).
