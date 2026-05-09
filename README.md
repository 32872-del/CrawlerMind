# Crawler-Mind (CLM)

Crawler-Mind is an early autonomous crawl-agent MVP. It turns a natural-language
crawl goal into a structured crawl workflow:

```text
Planner -> Recon -> Strategy -> Executor -> Extractor -> Validator
```

The current project is runnable and useful for supported targets, but it is
still under active development. It is best treated as a local research and
engineering framework for building a stronger crawling agent.

## Project Vision

CLM is being built as a practical crawl agent rather than a single-purpose
scraper. The long-term target is:

1. Understand a user's crawl request.
2. Inspect the target site.
3. Choose a safe strategy: static HTML, browser rendering, public API replay, or
   diagnosis-only.
4. Extract structured data.
5. Validate quality and retry when useful.
6. Persist results, logs, and decisions so long runs can be resumed and audited.

The project also includes a file-based team workflow for multi-agent
development: daily reports, handoffs, employee IDs, assignments, acceptance
records, and project memory live under `docs/`.

## What Works Today

- Static HTML crawling and selector inference.
- Playwright browser fallback for rendered pages.
- Public JSON API and GraphQL API collection.
- Browser network observation that can replay a safe observed public JSON POST
  API. Verified on the HN Algolia SPA.
- Basic multi-page JSON API pagination for page/limit, offset/limit, and
  cursor-style responses.
- Optional OpenAI-compatible LLM advisor for Planner and Strategy.
- Deterministic fallback when LLM is disabled or fails.
- FastAPI background-job service.
- SQLite result persistence.
- SQLite URL frontier and domain memory.
- Result inspection/export CLI.
- Bundled `fnspider` engine for project-local portability.
- Ecommerce small-sample training: Shopify JSON, Magento list/detail pages,
  Magento `jsonConfig` variants, Cloudflare diagnosis-only handling, and
  corporate product pages without fake prices.
- Local synthetic stress testing for 30,000 ecommerce records.
- Team workflow docs, daily reports, handoff memory, and training ladder.

Verified examples include:

- Baidu realtime hot search: 30 validated items.
- JSONPlaceholder direct JSON.
- Reddit `.json`.
- Countries GraphQL.
- AniList GraphQL.
- Bilibili public ranking API.
- Douban Top250.
- HN Algolia public SPA observed API replay: 10 validated items.
- Deterministic paged/offset/cursor JSON API fixtures.
- Donsje public Shopify products JSON.
- Clausporto and uvex Magento-style product pages.
- 30,000-row local synthetic ecommerce stress export.

## Capability Matrix

| Area | Current status | Evidence |
|---|---|---|
| Static HTML list/detail | Usable MVP | Baidu hot search, Douban, Magento product pages |
| Browser fallback | Usable MVP | Local SPA smoke and optional browser tests |
| Public JSON API | Usable MVP | JSONPlaceholder, Reddit JSON, GitHub, DummyJSON |
| GraphQL API | Usable MVP | Countries and AniList public GraphQL tests |
| Browser network observation | Early MVP | HN Algolia SPA API replay |
| API pagination | MVP | page/limit, offset/limit, cursor fixtures |
| Ecommerce extraction | Training-stage MVP | Donsje, Clausporto, uvex, Bosch, Shoesme diagnosis |
| Large-volume local handling | Initial pass | 30,000 synthetic records through frontier/store/export |
| Long-running real-site crawl | Not production-ready | Needs checkpointed product storage and resumability |
| Frontend UI | Not started | Planned for later P1/P2 |

## Current Limits

- This is not yet a universal crawler.
- Dynamic sites, infinite scroll, virtualized lists, and hostile anti-bot pages
  still need more training and tests.
- API pagination is an MVP; it still needs cross-page dedupe, analytics
  endpoint denylist, and stronger loop guards before broad real-site use.
- Large ecommerce runs need checkpointed product storage. The current result
  store can save large local batches, but it is not yet the right architecture
  for multi-hour crawls with retries and resumability.
- Cloudflare/CAPTCHA/login-required targets are diagnosis-only until explicit
  authorized workflows exist.
- FastAPI job registry is in-memory; running job state is lost on process
  restart.
- No frontend UI yet.

## Repository Map

```text
autonomous_crawler/
  agents/        LangGraph workflow nodes
  api/           FastAPI service
  engines/       Bundled crawler engines
  llm/           Optional OpenAI-compatible advisor adapter
  models/        State schemas
  storage/       SQLite result store, frontier, domain memory
  tests/         Unit and integration tests
  tools/         Recon, browser, API, fetch policy, product helpers
  training/      Real-site training runner
  workflows/     LangGraph graph

docs/
  blueprints/    Long-term architecture
  decisions/     ADRs
  memory/        Handoffs and persistent employee memory model
  plans/         Short-term and feature plans
  process/       Collaboration guide
  reports/       Daily/project reports
  runbooks/      Setup and operation guides
  team/          Team board, employees, assignments, acceptance records

dev_logs/        Developer logs and selected training summaries
scripts/         Cross-platform helper scripts
```

## Quick Start

Python 3.11+ is recommended.

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

You can also use the helper scripts:

```bash
bash scripts/setup_unix.sh
bash scripts/check_llm_unix.sh
bash scripts/run_mock_unix.sh
bash scripts/run_api_unix.sh
```

## LLM Configuration

Copy the example config:

```bash
cp clm_config.example.json clm_config.json
```

On Windows:

```powershell
Copy-Item clm_config.example.json clm_config.json
```

Then edit:

```json
{
  "llm": {
    "enabled": true,
    "base_url": "https://api.openai.com/v1",
    "model": "gpt-4o-mini",
    "api_key": "replace-with-your-api-key",
    "provider": "openai-compatible",
    "timeout_seconds": 30,
    "temperature": 0,
    "max_tokens": 800,
    "use_response_format": true
  }
}
```

Most OpenAI-compatible providers only require changing:

- `base_url`
- `model`
- `api_key`

If your provider does not support `response_format`, set:

```json
"use_response_format": false
```

`clm_config.json` is ignored by Git. Do not commit real API keys.

## Run A Crawl

Deterministic mock:

```bash
python run_simple.py "collect product titles and prices" mock://catalog
```

Real smoke:

```bash
python run_simple.py "collect top 30 hot searches" "https://top.baidu.com/board?tab=realtime"
```

Baidu smoke script:

```bash
python run_baidu_hot_test.py
```

Training rounds:

```bash
python run_training_round1.py
python run_training_round2.py
python run_training_round3.py
python run_training_round4.py
```

Ecommerce training sample:

```bash
python run_ecommerce_training_2026_05_09.py
```

This writes:

```text
dev_logs/2026-05-09_ecommerce_training_sample.xlsx
dev_logs/2026-05-09_ecommerce_training_sample.json
dev_logs/2026-05-09_ecommerce_training_summary.md
```

Local stress test:

```bash
python run_stress_test_2026_05_09.py --items 30000 --batch-size 500 --keep-excel
```

This test is synthetic and does not send requests to public websites.

## FastAPI Service

Start the local API:

```bash
uvicorn autonomous_crawler.api.app:app --reload
```

Open:

```text
http://127.0.0.1:8000/docs
```

Endpoints:

```text
GET  /health
POST /crawl
GET  /crawl/{task_id}
GET  /history
```

Example request:

```json
{
  "user_goal": "collect top 30 hot searches",
  "target_url": "https://top.baidu.com/board?tab=realtime",
  "max_retries": 3,
  "llm": {
    "enabled": false
  }
}
```

## Result CLI

```bash
python run_results.py list
python run_results.py show <task_id>
python run_results.py items <task_id>
python run_results.py export-json <task_id> output.json
python run_results.py export-csv <task_id> output.csv
```

## Tests

Run the standard suite:

```bash
python -m unittest discover -s autonomous_crawler/tests
```

Run optional browser smoke:

```bash
# Linux / macOS
AUTONOMOUS_CRAWLER_RUN_BROWSER_SMOKE=1 python -m unittest autonomous_crawler.tests.test_real_browser_smoke -v
```

```powershell
# Windows PowerShell
$env:AUTONOMOUS_CRAWLER_RUN_BROWSER_SMOKE='1'
python -m unittest autonomous_crawler.tests.test_real_browser_smoke -v
```

## Important Docs

- Current status: `PROJECT_STATUS.md`
- Project showcase: `docs/reports/2026-05-09_PROJECT_SHOWCASE.md`
- Blueprint: `docs/blueprints/AUTONOMOUS_CRAWL_AGENT_BLUEPRINT.md`
- Ecommerce workflow: `docs/process/ECOMMERCE_CRAWL_WORKFLOW.md`
- Quick start for Linux/macOS: `docs/runbooks/QUICK_START_LINUX_MAC.md`
- Quick start for Windows: `docs/runbooks/QUICK_START_WINDOWS.md`
- Team board: `docs/team/TEAM_BOARD.md`
- Training ladder: `docs/team/training/2026-05-08_REAL_SITE_TRAINING_LADDER.md`
- Stage analysis: `docs/reports/2026-05-08_STAGE_AND_BLUEPRINT_ANALYSIS.txt`

## Near-Term Roadmap

The next engineering step is to turn the ecommerce training scripts into
reusable product infrastructure:

1. `ProductRecord` schema and validation.
2. Product-specific SQLite storage with checkpointed upserts.
3. Resumable long-run progress and batch-level metrics.
4. Real-site pagination and infinite-scroll training.
5. A lightweight frontend for API configuration, task submission, example
   upload, and result review.

## License

This project is released under the MIT License. See `LICENSE`.

## Safety Note

Use this project only on targets you are allowed to access. Do not use it to
bypass login systems, CAPTCHA, Cloudflare challenges, or other access controls
without explicit authorization.
