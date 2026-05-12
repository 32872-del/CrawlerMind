# Crawler-Mind Windows Quick Start

This guide uses the Easy Mode CLI. Run all commands from the repository root in
PowerShell.

## 1. Clone

```powershell
git clone https://github.com/32872-del/CrawlerMind.git
cd CrawlerMind
```

## 2. Create Environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
```

If PowerShell blocks activation:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

## 3. Install Dependencies

```powershell
python -m pip install -r requirements.txt
playwright install
```

`playwright install` is needed for browser fallback. You can skip it for static
HTML/API-only experiments.

## 4. Initialize CLM

```powershell
python clm.py init
```

This creates `clm_config.json` with LLM disabled by default.

## 5. Check Setup

```powershell
python clm.py check
```

No API key is required.

## 6. First Crawl

```powershell
python clm.py crawl "collect product titles and prices" mock://catalog --output dev_logs/runtime/mock_result.json
```

Expected:

```text
Final Status: completed
Extracted Data: 2 items
```

## 7. Public Crawl

```powershell
python clm.py crawl "collect top 30 hot searches" "https://top.baidu.com/board?tab=realtime" --output dev_logs/runtime/baidu_hot.json
```

## 8. Optional LLM

```powershell
python clm.py init --force --enable-llm --base-url https://api.openai.com/v1 --model gpt-4o-mini --api-key your-real-api-key
python clm.py check --llm
python clm.py crawl "collect top 30 hot searches" "https://top.baidu.com/board?tab=realtime" --llm
```

If your provider does not support OpenAI `response_format`, add:

```powershell
--disable-response-format
```

`clm_config.json` is git-ignored. Do not commit real API keys.

## 9. Results

Easy Mode can write JSON or Excel:

```powershell
python clm.py crawl "collect product titles and prices" mock://catalog --output dev_logs/runtime/mock_result.xlsx
```

Persisted workflow history is stored in:

```text
autonomous_crawler/storage/runtime/crawl_results.sqlite3
```

Inspect persisted runs:

```powershell
python run_results.py list
python run_results.py show <task_id>
python run_results.py items <task_id>
python run_results.py export-json <task_id> output.json
python run_results.py export-csv <task_id> output.csv
```

## 10. Optional Service And Tests

```powershell
uvicorn autonomous_crawler.api.app:app --reload
python -m unittest discover -s autonomous_crawler/tests
```

Browser smoke:

```powershell
$env:AUTONOMOUS_CRAWLER_RUN_BROWSER_SMOKE='1'
python -m unittest autonomous_crawler.tests.test_real_browser_smoke -v
```

## Notes

- Use `python clm.py smoke --kind runner` for a local smoke test.
- Use `python clm.py train` to list developer training scripts.
- `run_simple.py` is kept as a legacy/developer entry point; new users should
  start with `clm.py`.
