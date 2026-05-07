# Autonomous Crawl Agent - Project Status

## Current Stage

The project is an early but runnable MVP. The LangGraph workflow exists and can
complete deterministic fixture crawls and a real automatic Baidu realtime hot
search workflow.

## Completed

- LangGraph skeleton:
  `Planner -> Recon -> Strategy -> Executor -> Extractor -> Validator`
- Real HTTP execution with browser-like headers.
- Deterministic mock catalog fixture for stable tests.
- Local HTML recon helper for basic framework, anti-bot, API hint, and repeated
  card selector inference.
- Strategy consumes inferred selectors instead of only hardcoded product
  selectors.
- Generic field extraction, including ranking/list fields such as `rank`,
  `hot_score`, and `summary`.
- Validation based on requested target fields.
- Bundled `fnspider` engine inside this project.
- Project-local `fnspider` runtime paths for cache and SQLite output.
- `site_spec_draft` adapter for spider_Uvex/fnspider-compatible specs.
- Baidu realtime hot-search smoke test collected 30 items successfully.
- Automatic `ranking_list` workflow:
  `Planner -> Recon -> Strategy -> Executor -> Extractor -> Validator`
  can collect the first 30 items from Baidu realtime hot search through inferred
  DOM selectors.
- Ranking-list planning detects task type and `max_items` from goals such as
  `采集百度热搜榜前30条`.
- Recon can infer Baidu-style ranking containers and fields including `rank`,
  `title`, `link`, `hot_score`, `summary`, and `image`.
- Strategy now keeps reliable ranking-list pages on DOM parsing instead of
  switching to incomplete API extraction.
- Project-local SQLite result storage for workflow final states, extracted
  items, validation status, and history listing.
- `run_skeleton.py` and `run_baidu_hot_test.py` now persist completed or failed
  runs to `autonomous_crawler/storage/runtime/crawl_results.sqlite3`.
- `recon_tools.py` now wraps the real deterministic HTML recon helpers instead
  of returning placeholder tool outputs.
- FastAPI MVP service with:
  `GET /health`, `POST /crawl`, `GET /crawl/{task_id}`, and `GET /history`.
- Project documentation structure standardized under `docs/`:
  blueprints, reviews, plans, reports, and process docs are separated.
- Developer logs are now reserved for timestamped implementation events only.
- Multi-Codex collaboration guide added.
- `run_results.py` CLI added for listing, inspecting, and exporting persisted
  crawl results.
- Full-record ZIP package was generated and verified.
- Error-path hardening: 30 new tests covering unsupported URL schemes, HTTP
  failures, empty HTML, invalid CSS selectors, retry exhaustion, and failure
  persistence. Extractor now handles None HTML and malformed selectors gracefully.
  Graph exits early with `recon_failed` status when recon fails instead of
  continuing through the full pipeline.
- Explicit `fnspider` engine routing: product-list tasks can request the bundled
  engine with `preferred_engine="fnspider"` or
  `crawl_preferences={"engine": "fnspider"}`. Ranking-list tasks remain on the
  lightweight DOM path.
- Browser fallback MVP: Playwright-based browser executor for SPA and anti-bot
  pages. Supports wait_selector, wait_until, timeout, and optional screenshots.
  Executor now has four paths: HTTP, browser, mock, and fnspider.
- Supervisor/worker LLM team workspace added under `docs/team/`, including
  badges, assignments, acceptance protocol, accepted-work records, and new LLM
  onboarding.
- FastAPI background job execution: POST /crawl now returns immediately with
  status "running" and executes the workflow in a background thread. In-memory
  job registry tracks pending/running/completed/failed states. GET /crawl/{id}
  checks registry first, then falls back to persisted SQLite results.
- Real browser SPA smoke test: local deterministic SPA fixture served via
  `http.server`, validated end-to-end with Playwright browser fallback. Tests
  skip cleanly when Playwright/browser binaries are unavailable. No external
  network access required.
- Local Git repository initialized on 2026-05-07 for project history and
  rollback.
- Remote Git repository configured:
  `https://github.com/32872-del/CrawlerMind.git`
- Employee memory model added under `docs/memory/`: employee identity is
  persistent project state, while AI sessions temporarily operate that state.
- ADR foundation added under `docs/decisions/`.
- Runbooks added under `docs/runbooks/`.

## Current Test Status

```text
python -m unittest discover autonomous_crawler\tests
Ran 84 tests (skipped=3)
OK
```

## Current Limitations

- Planner still uses deterministic keyword matching, not an LLM.
- Recon selector inference is heuristic and currently strongest for product
  cards and Baidu-style ranking lists.
- `site_spec_draft` detail selectors are drafts when only a list page is known.
- API interception is not fully integrated into the graph.
- FastAPI background jobs use in-memory registry; jobs are lost on process restart.
- Storage is local SQLite only; no dashboard yet.
- Redis is still unused.
- Multiple Codex agents can now coordinate by document convention, but there is
  no automated lock/ownership system.
- Remote Git exists, but branch policy and automated locking are not configured
  yet.

## Next Development Goal

Move from the local MVP toward a more robust crawl service:

```text
durable jobs + LLM-assisted planning + broader site samples
```

The last verified real workflow is:

```text
python run_skeleton.py "采集百度热搜榜前30条" https://top.baidu.com/board?tab=realtime
Final Status: completed, Extracted Data: 30 items, Validation: passed
```

## Next Tasks

1. ~~Add error-path tests for HTTP failures, empty HTML, invalid selectors, and
   retry exhaustion.~~ Done 2026-05-06.
2. ~~Decide how `fnspider` should be selected: automatic engine choice vs.
   explicit strategy option.~~ Explicit strategy option done 2026-05-06;
   automatic rules deferred until more site samples exist.
3. ~~Add browser-mode fallback for pages where HTTP HTML is incomplete.~~ Done 2026-05-06.
4. Add optional LLM Planner/Strategy with deterministic fallback.
5. ~~Add background job execution for FastAPI crawl requests.~~ Done 2026-05-06.
6. ~~Add real browser SPA smoke validation.~~ Done 2026-05-06.
7. ~~Initialize local Git repository and employee memory model.~~ Done 2026-05-07.
8. ~~Configure remote Git repository and add ADR/runbook foundation.~~ Done 2026-05-07.
