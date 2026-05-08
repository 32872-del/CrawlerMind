# Crawler-Mind 上手指南

## 最短路径

只做三步：

```powershell
python -m pip install -r requirements.txt
Copy-Item clm_config.example.json clm_config.json
notepad clm_config.json
python run_simple.py "collect product titles and prices" https://example.com
```

`clm_config.json` 里填你的 LLM API：

```json
{
  "llm": {
    "enabled": true,
    "base_url": "https://api.openai.com/v1",
    "model": "gpt-4o-mini",
    "api_key": "你的key",
    "use_response_format": true
  }
}
```

`base_url` 可以填根地址或 `/v1` 地址，CLM 会自动拼到 `/v1/chat/completions`。如果供应商报 `response_format` 不支持，把 `use_response_format` 改成 `false`。

先检查 LLM API 配置：

```powershell
python run_simple.py --check-llm
```

## 没有 API 先试跑

```powershell
python run_simple.py "collect product titles and prices" mock://catalog
```

看到 `Final Status: completed` 就说明基础流程能跑。

## 真实页面 smoke

```powershell
python run_simple.py "collect top 30 hot searches" "https://top.baidu.com/board?tab=realtime"
```

## 常用命令

跑测试：

```powershell
python -m unittest discover -s autonomous_crawler/tests
```

跑百度热搜：

```powershell
python run_baidu_hot_test.py
```

查看历史结果：

```powershell
python run_results.py list
python run_results.py show <task_id>
```

启动 API：

```powershell
uvicorn autonomous_crawler.api.app:app --reload
```

## 常见问题

### 提示 API key 还是示例值

打开 `clm_config.json`，把：

```text
replace-with-your-api-key
```

换成真实 key。

### 浏览器相关测试失败

安装浏览器：

```powershell
playwright install
```

### LLM 结果不稳定

先用 `mock://catalog` 确认基础流程没问题，再换真实网站。

当前阶段 LLM 只是辅助 Planner/Strategy，系统仍保留 deterministic fallback。

如果怀疑 API 地址、模型名或 key 配错，先运行：

```powershell
python run_simple.py --check-llm
```
