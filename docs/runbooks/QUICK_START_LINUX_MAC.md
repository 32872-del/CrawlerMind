# Crawler-Mind Linux / macOS Quick Start

This guide uses the Easy Mode CLI. Run all commands from the repository root in
Bash or Zsh.

## 1. Clone

```bash
git clone https://github.com/32872-del/CrawlerMind.git
cd CrawlerMind
```

## 2. Create Environment

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

On Linux servers, Playwright may also need:

```bash
playwright install-deps
```

You can skip Playwright for static HTML/API-only experiments. Browser fallback
will not work until Playwright browsers are installed.

## 4. Initialize CLM

```bash
python clm.py init
```

This creates `clm_config.json` with LLM disabled by default.

## 5. Check Setup

```bash
python clm.py check
```

No API key is required.

## 6. First Crawl

```bash
python clm.py crawl "collect product titles and prices" mock://catalog --output dev_logs/runtime/mock_result.json
```

Expected:

```text
Final Status: completed
Extracted Data: 2 items
```

## 7. Public Crawl

```bash
python clm.py crawl "collect top 30 hot searches" "https://top.baidu.com/board?tab=realtime" --output dev_logs/runtime/baidu_hot.json
```

## 8. Optional LLM

```bash
python clm.py init --force --enable-llm --base-url https://api.openai.com/v1 --model gpt-4o-mini --api-key your-real-api-key
python clm.py check --llm
python clm.py crawl "collect top 30 hot searches" "https://top.baidu.com/board?tab=realtime" --llm
```

If your provider does not support OpenAI `response_format`, add:

```bash
--disable-response-format
```

`clm_config.json` is git-ignored. Do not commit real API keys.

## 9. Results

Easy Mode can write JSON or Excel:

```bash
python clm.py crawl "collect product titles and prices" mock://catalog --output dev_logs/runtime/mock_result.xlsx
```

Persisted workflow history is stored in:

```text
autonomous_crawler/storage/runtime/crawl_results.sqlite3
```

Inspect persisted runs:

```bash
python run_results.py list
python run_results.py show <task_id>
python run_results.py items <task_id>
python run_results.py export-json <task_id> output.json
python run_results.py export-csv <task_id> output.csv
```

## 10. Optional Service And Tests

```bash
uvicorn autonomous_crawler.api.app:app --reload
python -m unittest discover -s autonomous_crawler/tests
```

Browser smoke:

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

- Use `python clm.py smoke --kind runner` for a local smoke test.
- Use `python clm.py train` to list developer training scripts.
- `run_simple.py` is kept as a legacy/developer entry point; new users should
  start with `clm.py`.
