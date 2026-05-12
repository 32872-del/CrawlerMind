# Crawler-Mind 中文快速上手

这份文档使用 Easy Mode 入口 `clm.py`。所有命令都在项目根目录执行。

## 1. 克隆项目

```bash
git clone https://github.com/32872-del/CrawlerMind.git
cd CrawlerMind
```

## 2. 创建虚拟环境

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
```

Linux / macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
```

## 3. 安装依赖

```bash
python -m pip install -r requirements.txt
playwright install
```

Linux 服务器可能还需要：

```bash
playwright install-deps
```

如果暂时只做静态 HTML 或公开 API 采集，可以先跳过 Playwright。浏览器渲染兜底需要安装 Playwright 浏览器。

## 4. 初始化配置

```bash
python clm.py init
```

这会生成 `clm_config.json`，默认不启用 LLM，所以不需要 API key。

## 5. 检查环境

```bash
python clm.py check
```

这个命令只检查本地环境，不会请求 LLM provider。

## 6. 第一次采集

```bash
python clm.py crawl "collect product titles and prices" mock://catalog --output dev_logs/runtime/mock_result.json
```

看到类似结果就说明流程跑通：

```text
Final Status: completed
Extracted Data: 2 items
```

## 7. 采集公开网页

```bash
python clm.py crawl "collect top 30 hot searches" "https://top.baidu.com/board?tab=realtime" --output dev_logs/runtime/baidu_hot.json
```

这个例子不需要 LLM。

## 8. 可选：配置 LLM

CLM 默认可以不用 LLM。需要 LLM 辅助 Planner 和 Strategy 时再启用：

```bash
python clm.py init --force --enable-llm --base-url https://api.openai.com/v1 --model gpt-4o-mini --api-key your-real-api-key
python clm.py check --llm
```

如果你的 provider 不支持 OpenAI 的 `response_format` 参数，初始化时加上：

```bash
--disable-response-format
```

启用 LLM 后运行：

```bash
python clm.py crawl "collect top 30 hot searches" "https://top.baidu.com/board?tab=realtime" --llm
```

`clm_config.json` 已经被 git 忽略，不要提交真实 API key。

## 9. 查看结果

Easy Mode 可以直接输出 JSON 或 Excel：

```bash
python clm.py crawl "collect product titles and prices" mock://catalog --output dev_logs/runtime/mock_result.xlsx
```

运行历史也会保存到：

```text
autonomous_crawler/storage/runtime/crawl_results.sqlite3
```

查看历史结果：

```bash
python run_results.py list
python run_results.py show <task_id>
python run_results.py items <task_id>
python run_results.py export-json <task_id> output.json
python run_results.py export-csv <task_id> output.csv
```

## 10. 可选：启动 API 服务和测试

```bash
uvicorn autonomous_crawler.api.app:app --reload
python -m unittest discover -s autonomous_crawler/tests
```

浏览器 smoke 测试：

```bash
# Linux / macOS
AUTONOMOUS_CRAWLER_RUN_BROWSER_SMOKE=1 python -m unittest autonomous_crawler.tests.test_real_browser_smoke -v

# Windows PowerShell
$env:AUTONOMOUS_CRAWLER_RUN_BROWSER_SMOKE='1'
python -m unittest autonomous_crawler.tests.test_real_browser_smoke -v
```

## 常见问题

### 我需要先配置 API key 吗？

不需要。先用 `python clm.py check` 和 `mock://catalog` 跑通本地流程。只有使用 `--llm` 或 `python clm.py check --llm` 时才需要真实 API key。

### 输出文件在哪里？

建议新手直接使用 `--output`，例如：

```bash
python clm.py crawl "collect product titles and prices" mock://catalog --output dev_logs/runtime/mock_result.json
```

开发训练产物在 `dev_logs/training/`，smoke 结果在 `dev_logs/smoke/`，压力测试结果在 `dev_logs/stress/`。

### `run_simple.py` 还要用吗？

普通用户优先使用 `clm.py`。`run_simple.py` 保留为旧入口和开发调试命令。

### 当前不能做什么？

不要用 CLM 未授权绕过登录、验证码、Cloudflare challenge 或其他访问控制。遇到这些目标时，当前策略是诊断和记录，不是破解。
