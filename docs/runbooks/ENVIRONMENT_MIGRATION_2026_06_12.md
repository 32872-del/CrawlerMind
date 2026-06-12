# CLM Environment Migration Runbook - 2026-06-12

## Purpose

Use this when moving Crawler-Mind (CLM) to a new development machine.

The Git repository should contain source code, tests, frontend source,
documentation, team records, and lightweight training evidence. It intentionally
does not contain machine-local caches, runtime databases, browser artifacts,
virtual environments, node modules, or API keys.

## What Is Synced Through Git

Expected to be available after `git clone`:

- Python source under `autonomous_crawler/`
- FastAPI service and product workflow endpoints
- Chinese React workbench under `frontend/`
- Tests under `autonomous_crawler/tests/`
- Scripts such as `clm.py`, `run_simple.py`, and training/smoke scripts
- Project documents under `docs/`
- Developer logs and lightweight training reports under `dev_logs/`
- 2026-06-02 E2E managed-loop training evidence under:

```text
dev_logs/training/e2e_site_list_20260602/
```

## What Is Not Synced

These are intentionally ignored and should be regenerated locally:

```text
.venv/
frontend/node_modules/
frontend/dist/
clm_config.json
autonomous_crawler/storage/runtime/
autonomous_crawler/tools/runtime/
autonomous_crawler/engines/runtime/
dev_logs/runtime/
dev_logs/exports/
output/
*.zip
```

Reason:

- Runtime DBs and browser artifacts are machine-specific and can grow quickly.
- `clm_config.json` may contain API keys.
- Node/Python dependency directories are reproducible from lockfiles and
  requirements.

## Clone And Install

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

Linux servers may also need:

```bash
playwright install-deps
```

## Frontend Setup

```bash
cd frontend
npm install
npm run build
```

For local development:

```bash
npm run dev -- --port 5174
```

Open:

```text
http://127.0.0.1:5174
```

The backend should run separately:

```bash
uvicorn autonomous_crawler.api.app:app --reload --host 127.0.0.1 --port 8000
```

## Optional LLM Config

Create a local config after cloning:

```bash
python clm.py init
```

Enable an OpenAI-compatible provider:

```bash
python clm.py init --force --enable-llm --base-url https://api.example.com/v1 --model your-model --api-key your-key
```

If the provider rejects `response_format`, initialize with:

```bash
--disable-response-format
```

Never commit `clm_config.json`.

## Smoke Verification

Run these first:

```bash
python clm.py check
python clm.py crawl "collect product titles and prices" mock://catalog --output dev_logs/runtime/mock_result.json
```

Expected result:

```text
Final Status: completed
Extracted Data: 2 items
```

Fast API smoke:

```bash
python -m unittest autonomous_crawler.tests.test_product_workflow_api.ProductWorkflowAPITests -v
```

Managed loop focused smoke:

```bash
python -m unittest autonomous_crawler.tests.test_managed_actions autonomous_crawler.tests.test_auto_repair autonomous_crawler.tests.test_extended_coverage -v
```

Frontend build:

```bash
cd frontend
npm run build
```

## Current Project State To Remember

As of 2026-06-12:

- Overall project maturity is roughly 68% - 75% toward the target crawler
  agent.
- The core direction remains:

```text
AI managed workflow -> evidence/recon -> profile/runtime patch -> long-run execution -> quality/export
```

- Major backend capabilities exist: native fetch/parser/browser runtime,
  profile longrun, checkpoint/frontier/product store, browser/XHR evidence,
  API/GraphQL replay, replay diagnostics, managed actions, QualityGate,
  `execute_and_run()`, `diagnose_and_repair()`, and extraction contract
  discovery.
- The Chinese frontend workbench exists and can call workflow APIs.
- The next priority is real-site hardening of the managed loop so it improves
  success rate rather than degrading direct crawl paths.

## Known Migration Notes

- If dynamic/SPAs fail immediately, confirm Playwright browsers are installed.
- If LLM model list works but managed calls fail, check whether the provider
  supports `response_format`, `reasoning_effort`, and streaming. CLM has fallback
  handling, but some relays still need conservative config.
- If old runtime results are needed, copy the ignored runtime directories
  manually from the old machine. They are not required for development.
- Some historical Chinese logs were written with encoding issues. Treat them as
  historical evidence, not user-facing documentation.
