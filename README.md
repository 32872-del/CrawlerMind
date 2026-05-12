# Crawler-Mind (CLM)

Crawler-Mind turns a natural-language crawl goal into a structured workflow:

```text
Planner -> Recon -> Strategy -> Executor -> Extractor -> Validator
```

It is a local research and engineering framework for building a stronger crawl
agent. It is already runnable, but it is not yet a universal crawler. See
[Current Limits](#current-limits).

## Quick Start

Python 3.11+ is recommended.

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

If PowerShell blocks activation:

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

On Linux servers, Playwright may also need:

```bash
playwright install-deps
```

If you do not need browser mode yet, you can skip `playwright install`. Browser
fallback will not work until Playwright browsers are installed.

## Easy Mode

Use `clm.py` as the primary user entry point.

Create local config:

```bash
python clm.py init
```

Run a local setup check without any API key:

```bash
python clm.py check
```

Run a deterministic mock crawl without network access:

```bash
python clm.py crawl "collect product titles and prices" mock://catalog --output dev_logs/runtime/mock_result.json
```

Expected result: `Final Status: completed` with 2 extracted items.

Run a public-page crawl:

```bash
python clm.py crawl "collect top 30 hot searches" "https://top.baidu.com/board?tab=realtime" --output dev_logs/runtime/baidu_hot.json
```

Run the local smoke test:

```bash
python clm.py smoke --kind runner
```

Show developer training commands:

```bash
python clm.py train
```

## Output

For beginner runs, prefer `--output`:

```bash
python clm.py crawl "collect product titles and prices" mock://catalog --output dev_logs/runtime/mock_result.xlsx
```

Supported Easy Mode output formats:

```text
.json
.xlsx
```

Workflow states are also persisted to SQLite:

```text
autonomous_crawler/storage/runtime/crawl_results.sqlite3
```

Inspect persisted results:

```bash
python run_results.py list
python run_results.py show <task_id>
python run_results.py items <task_id>
python run_results.py export-json <task_id> output.json
python run_results.py export-csv <task_id> output.csv
```

## Optional LLM Setup

CLM works without an API key in deterministic mode. LLM usage is opt-in.

Create config with LLM enabled:

```bash
python clm.py init --force --enable-llm --base-url https://api.openai.com/v1 --model gpt-4o-mini --api-key your-real-api-key
```

Most OpenAI-compatible providers only require changing `base_url`, `model`, and
`api_key`. If your provider does not support `response_format`, add:

```bash
--disable-response-format
```

Local setup check only:

```bash
python clm.py check
```

Real provider check:

```bash
python clm.py check --llm
```

Run with LLM forced on:

```bash
python clm.py crawl "collect top 30 hot searches" "https://top.baidu.com/board?tab=realtime" --llm
```

`clm_config.json` is git-ignored. Do not commit real API keys.

## FastAPI Service

Start the local API server:

```bash
uvicorn autonomous_crawler.api.app:app --reload
```

Open <http://127.0.0.1:8000/docs> for the interactive API docs.

Endpoints:

```text
GET /health
POST /crawl
GET /crawl/{task_id}
GET /history
```

## Run Tests

```bash
python -m unittest discover -s autonomous_crawler/tests
```

Optional browser smoke test:

```bash
# Linux / macOS
AUTONOMOUS_CRAWLER_RUN_BROWSER_SMOKE=1 python -m unittest autonomous_crawler.tests.test_real_browser_smoke -v

# Windows PowerShell
$env:AUTONOMOUS_CRAWLER_RUN_BROWSER_SMOKE='1'
python -m unittest autonomous_crawler.tests.test_real_browser_smoke -v
```

## What Works Today

- Easy Mode CLI: `init`, `check`, `crawl`, `smoke`, and `train`.
- Static HTML crawling and selector inference.
- Playwright browser fallback for rendered pages.
- Public JSON API and GraphQL API collection.
- Browser network observation with safe observed public JSON POST API replay.
- Basic multi-page JSON API pagination: page/limit, offset/limit, cursor.
- Browser resource interception foundation: block heavy resource types, capture
  JS bundle metadata, capture API-like response metadata, and inject init
  scripts for future hook work.
- JS asset inventory foundation: rank script assets by API endpoints, GraphQL,
  WebSocket, sourcemap, signature/token/encryption/challenge, and bundler clues.
- Transport diagnostics foundation: compare `requests`, `curl_cffi`, and
  browser behavior across status, HTTP version, transport profile, challenge,
  server, and edge/cache header differences.
- Optional OpenAI-compatible LLM advisor for Planner and Strategy.
- Deterministic fallback when LLM is disabled or fails.
- FastAPI background-job service.
- SQLite result persistence, URL frontier, and domain memory.
- Ecommerce small-sample training: Shopify JSON, Magento detail pages, variants.
- Generic resumable batch runner and product checkpoint foundation.
- Local synthetic stress testing for 30,000 ecommerce records.

## Current Limits

- Not yet a universal crawler. Dynamic sites, infinite scroll, and complex
  anti-bot pages need more training and tests.
- Cloudflare/CAPTCHA/login-required targets are diagnosis-only unless you have
  explicit authorization and provide a compliant access path.
- API pagination is an MVP; it still needs broader real-site hardening.
- FastAPI job registry is in-memory; state is lost on restart.
- No frontend UI yet.
- Site-specific quirks should become profiles or fixtures, not hard-coded core
  behavior.

## Safety

Use this project only on targets you are allowed to access. Do not use it to
bypass login systems, CAPTCHA, Cloudflare challenges, or other access controls
without explicit authorization.

## Developer And Legacy Commands

Normal users should start with `clm.py`. The older scripts remain useful for
development, compatibility, and focused training.

```bash
# Legacy simple entry point
python run_simple.py "collect product titles and prices" mock://catalog
python run_simple.py --check-llm

# Training rounds
python run_training_round1.py
python run_training_round2.py
python run_training_round3.py
python run_training_round4.py

# Ecommerce training sample
python run_ecommerce_training_2026_05_09.py

# Local synthetic stress test
python run_stress_test_2026_05_09.py --items 30000 --batch-size 500 --keep-excel

# Baidu hot search smoke test
python run_baidu_hot_test.py
```

Training and smoke outputs go under:

```text
dev_logs/training/
dev_logs/smoke/
dev_logs/stress/
```

Historical docs may mention old flat `dev_logs/<file>` paths. Current evidence
is partitioned under `dev_logs/development/`, `dev_logs/audits/`,
`dev_logs/training/`, `dev_logs/smoke/`, and `dev_logs/stress/`.

## Helper Scripts

```bash
bash scripts/setup_unix.sh
bash scripts/check_llm_unix.sh
bash scripts/run_mock_unix.sh
bash scripts/run_api_unix.sh
```

## Important Docs

- Current status: [PROJECT_STATUS.md](PROJECT_STATUS.md)
- Quick start (Windows): [docs/runbooks/QUICK_START_WINDOWS.md](docs/runbooks/QUICK_START_WINDOWS.md)
- Quick start (Linux/macOS): [docs/runbooks/QUICK_START_LINUX_MAC.md](docs/runbooks/QUICK_START_LINUX_MAC.md)
- Quick start (Chinese): [docs/runbooks/QUICK_START_CN.md](docs/runbooks/QUICK_START_CN.md)
- Ecommerce workflow: [docs/process/ECOMMERCE_CRAWL_WORKFLOW.md](docs/process/ECOMMERCE_CRAWL_WORKFLOW.md)
- Blueprint: [docs/blueprints/AUTONOMOUS_CRAWL_AGENT_BLUEPRINT.md](docs/blueprints/AUTONOMOUS_CRAWL_AGENT_BLUEPRINT.md)
- Team board: [docs/team/TEAM_BOARD.md](docs/team/TEAM_BOARD.md)
- Contributing: [CONTRIBUTING.md](CONTRIBUTING.md)

## License

MIT License. See [LICENSE](LICENSE).
