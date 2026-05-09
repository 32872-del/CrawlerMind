# Crawler-Mind 中文快速上手

## 最短路径

### Windows PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
playwright install

Copy-Item clm_config.example.json clm_config.json
notepad clm_config.json
python run_simple.py --check-llm
python run_simple.py "collect product titles and prices" mock://catalog
```

### Linux / macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
playwright install

cp clm_config.example.json clm_config.json
${EDITOR:-nano} clm_config.json
python run_simple.py --check-llm
python run_simple.py "collect product titles and prices" mock://catalog
```

## 配置 LLM API

`clm_config.json` 示例:

```json
{
  "llm": {
    "enabled": true,
    "base_url": "https://api.openai.com/v1",
    "model": "gpt-4o-mini",
    "api_key": "你的 API key",
    "provider": "openai-compatible",
    "timeout_seconds": 30,
    "temperature": 0,
    "max_tokens": 800,
    "use_response_format": true
  }
}
```

兼容 OpenAI-compatible API。通常只需要改:

- `base_url`
- `model`
- `api_key`

如果供应商不支持 `response_format`，把:

```json
"use_response_format": true
```

改成:

```json
"use_response_format": false
```

## 没有 API 时先试跑

```bash
python run_simple.py "collect product titles and prices" mock://catalog
```

看到 `Final Status: completed` 就说明基础流程能跑。

## 真实页面 smoke

```bash
python run_simple.py "collect top 30 hot searches" "https://top.baidu.com/board?tab=realtime"
```

## 常用命令

跑测试:

```bash
python -m unittest discover -s autonomous_crawler/tests
```

跑百度热搜:

```bash
python run_baidu_hot_test.py
```

查看历史结果:

```bash
python run_results.py list
python run_results.py show <task_id>
python run_results.py items <task_id>
```

启动 API:

```bash
uvicorn autonomous_crawler.api.app:app --reload
```

打开:

```text
http://127.0.0.1:8000/docs
```

## 常见问题

### 提示 API key 还是示例值

打开 `clm_config.json`，把:

```text
replace-with-your-api-key
```

换成真实 key。

### 浏览器相关测试失败

安装浏览器:

```bash
playwright install
```

Linux 服务器可能还需要:

```bash
playwright install-deps
```

### LLM 结果不稳定

先用 `mock://catalog` 确认基础流程没问题，再换真实网站。

当前阶段 LLM 只辅助 Planner/Strategy，系统仍保留 deterministic fallback。

如果怀疑 API 地址、模型名或 key 配错，先运行:

```bash
python run_simple.py --check-llm
```
