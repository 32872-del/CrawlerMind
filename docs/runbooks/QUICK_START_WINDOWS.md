# Crawler-Mind Windows Quick Start

This guide assumes Windows PowerShell from the repository root.

## 1. Clone

```powershell
git clone https://github.com/32872-del/CrawlerMind.git
cd CrawlerMind
```

## 2. Create Virtual Environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
```

If PowerShell blocks activation, run:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

Then activate again.

## 3. Install Dependencies

```powershell
python -m pip install -r requirements.txt
playwright install
```

`playwright install` is required for browser fallback and browser smoke tests.

## 4. Configure LLM

```powershell
Copy-Item clm_config.example.json clm_config.json
notepad clm_config.json
```

Fill the provider fields:

```json
{
  "llm": {
    "enabled": true,
    "base_url": "https://api.openai.com/v1",
    "model": "gpt-4o-mini",
    "api_key": "your-api-key",
    "use_response_format": true
  }
}
```

If your provider does not support `response_format`, set:

```json
"use_response_format": false
```

## 5. Check LLM

```powershell
python run_simple.py --check-llm
```

## 6. Run Local Mock

```powershell
python run_simple.py "collect product titles and prices" mock://catalog
```

Expected result:

```text
Final Status: completed
Extracted Data: 2 items
```

## 7. Run Real Smoke

```powershell
python run_simple.py "collect top 30 hot searches" "https://top.baidu.com/board?tab=realtime"
```

## 8. Start API

```powershell
uvicorn autonomous_crawler.api.app:app --reload
```

Open:

```text
http://127.0.0.1:8000/docs
```

## 9. Run Tests

```powershell
python -m unittest discover -s autonomous_crawler/tests
```

Optional browser smoke:

```powershell
$env:AUTONOMOUS_CRAWLER_RUN_BROWSER_SMOKE='1'
python -m unittest autonomous_crawler.tests.test_real_browser_smoke -v
```

## Notes

- `clm_config.json` is ignored by Git.
- Runtime SQLite and cache files are ignored by Git.
- Use `python run_results.py list` to inspect persisted crawl results.
