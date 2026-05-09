# Crawler-Mind Linux / macOS Quick Start

This guide assumes Bash or Zsh from the repository root.

## 1. Clone

```bash
git clone https://github.com/32872-del/CrawlerMind.git
cd CrawlerMind
```

## 2. Create Virtual Environment

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
```

## 3. Install Dependencies

```bash
python -m pip install -r requirements.txt
playwright install
```

On Linux servers, Playwright may also need system dependencies:

```bash
playwright install-deps
```

If you do not need browser mode yet, you can skip browser smoke tests. Browser
fallback will not work until Playwright browsers are installed.

## 4. Configure LLM

```bash
cp clm_config.example.json clm_config.json
${EDITOR:-nano} clm_config.json
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

```bash
python run_simple.py --check-llm
```

## 6. Run Local Mock

```bash
python run_simple.py "collect product titles and prices" mock://catalog
```

Expected result:

```text
Final Status: completed
Extracted Data: 2 items
```

## 7. Run Real Smoke

```bash
python run_simple.py "collect top 30 hot searches" "https://top.baidu.com/board?tab=realtime"
```

## 8. Start API

```bash
uvicorn autonomous_crawler.api.app:app --reload
```

Open:

```text
http://127.0.0.1:8000/docs
```

## 9. Run Tests

```bash
python -m unittest discover -s autonomous_crawler/tests
```

Optional browser smoke:

```bash
AUTONOMOUS_CRAWLER_RUN_BROWSER_SMOKE=1 python -m unittest autonomous_crawler.tests.test_real_browser_smoke -v
```

## Helper Scripts

```bash
bash scripts/setup_unix.sh
bash scripts/check_llm_unix.sh
bash scripts/run_mock_unix.sh
bash scripts/run_api_unix.sh
```

## Notes

- `clm_config.json` is ignored by Git.
- Runtime SQLite and cache files are ignored by Git.
- Use `python run_results.py list` to inspect persisted crawl results.
