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
- Job registry concurrency limits: `POST /crawl` rejects with HTTP 429 when
  active background jobs reach the configured limit. Defaults to 4, configurable
  via `CLM_MAX_ACTIVE_JOBS` env var. Active-job counting and registration happen
  under one lock. Completed and failed jobs free their slots.
- Job registry TTL cleanup: completed/failed jobs are automatically removed
  after a configurable retention period. Defaults to 3600 seconds, configurable
  via `CLM_JOB_RETENTION_SECONDS` env var. Cleanup runs opportunistically on
  request handling. Running jobs are never removed.
- Local Git repository initialized on 2026-05-07 for project history and
  rollback.
- Remote Git repository configured:
  `https://github.com/32872-del/CrawlerMind.git`
- Employee memory model added under `docs/memory/`: employee identity is
  persistent project state, while AI sessions temporarily operate that state.
- ADR foundation added under `docs/decisions/`.
- Runbooks added under `docs/runbooks/`.
- Optional LLM Planner/Strategy interface design drafted under
  `docs/plans/2026-05-07_LLM_PLANNER_STRATEGY_INTERFACE_DESIGN.md`.
- Optional LLM Planner/Strategy design audited, revised, and accepted through
  ADR-005. Phase A implementation is assigned.
- LLM Advisor Phase A interfaces implemented: provider-neutral advisor
  protocols (`PlanningAdvisor`, `StrategyAdvisor`), closure-based node
  factories (`make_planner_node`, `make_strategy_node`), graph injection
  through `compile_crawl_graph(planning_advisor, strategy_advisor)`,
  append-only LLM audit state (`llm_enabled`, `llm_decisions`,
  `llm_errors`), bounded/redacted `raw_response_preview`, value-level
  strategy validation (mode, engine, selectors, wait_until, max_items),
  and 34 fake-advisor tests. No API key required.
- LLM Advisor Phase B/C merge hardening implemented: Planner validates
  advisor task types, target fields, max_items, constraints, and crawl
  preferences before merge; Strategy now merges advisor suggestions
  conservatively, preserving strong deterministic recon selectors and only
  filling missing selectors or replacing known fallback selectors. Advisor
  mode changes cannot downgrade browser mode, and deterministic max_items are
  preserved on conflict.
- OpenAI-compatible provider adapter added for optional real LLM-assisted
  Planner/Strategy runs. It reads `CLM_LLM_BASE_URL`, `CLM_LLM_MODEL`,
  optional `CLM_LLM_API_KEY`, and related tuning env vars. The adapter is
  opt-in through `run_skeleton.py --llm` or `CLM_LLM_ENABLED=1`; normal tests
  use fake clients and require no API key or network.
- Simplified user entrypoint added: copy `clm_config.example.json` to
  `clm_config.json`, fill API settings, then run `python run_simple.py "<goal>"
  "<url>"`. Missing config falls back to deterministic mode.
- OpenAI-compatible adapter hardened for practical providers: root base URLs
  are normalized to `/v1/chat/completions`, response previews are bounded and
  redacted, content parts and `choices[0].text` are supported, and unsupported
  `response_format` errors trigger one retry without that parameter.
- Real LLM-assisted smoke accepted on 2026-05-08: `run_simple.py` completed
  Baidu realtime hot-search extraction with LLM enabled, 30 items, confidence
  1.0, validation passed, 0 LLM errors.
- Mock fixture guardrail added: non-HTTP URLs cannot be routed to `fnspider`,
  and mock fixtures load before engine routing even when an advisor suggests an
  engine.

- FastAPI opt-in LLM advisor support added: `CrawlRequest` accepts optional
  `llm` config object, `POST /crawl` validates config eagerly (400 on missing
  base_url/model), background workflow passes advisor to graph compiler, and
  `llm_enabled`/`llm_decisions`/`llm_errors` are stored in persisted state.
  11 new tests (38 API tests, 186 suite tests).
- LLM provider diagnostics added: `python run_simple.py --check-llm` validates
  `clm_config.json`, prints the resolved endpoint without exposing the API key,
  and sends a minimal JSON chat request through the same OpenAI-compatible
  adapter path used by Planner/Strategy.

## Current Test Status

```text
python -m unittest discover -s autonomous_crawler/tests
Ran 192 tests (skipped=3)
OK
```

## Current Limitations

- Planner and Strategy can use optional LLM advisors through CLI/config and now
  also through FastAPI request-level configuration. Deterministic fallback
  remains the default.
- Recon selector inference is heuristic and currently strongest for product
  cards and Baidu-style ranking lists.
- `site_spec_draft` detail selectors are drafts when only a list page is known.
- API interception is not fully integrated into the graph.
- Dynamic/JS-heavy and Cloudflare-protected site coverage is not yet proven
  beyond local SPA browser fallback smoke tests.
- FastAPI background jobs use in-memory registry; jobs are lost on process
  restart. TTL cleanup limits stale completed/failed entries, but does not add
  durability.
- Storage is local SQLite only; no dashboard yet.
- Redis is still unused.
- Multiple Codex agents can now coordinate by document convention, but there is
  no automated lock/ownership system.
- Remote Git exists, but branch policy and automated locking are not configured
  yet.

## Next Development Goal

Move from the local MVP toward a more robust crawl service:

```text
provider diagnostics + broader site samples + dynamic-page capability tests
```

The last verified real LLM-assisted workflow is:

```text
python run_simple.py "collect top 30 hot searches" https://top.baidu.com/board?tab=realtime
Final Status: completed, Extracted Data: 30 items, Validation: passed, LLM errors: 0
```

## Next Tasks

1. ~~Add error-path tests for HTTP failures, empty HTML, invalid selectors, and
   retry exhaustion.~~ Done 2026-05-06.
2. ~~Decide how `fnspider` should be selected: automatic engine choice vs.
   explicit strategy option.~~ Explicit strategy option done 2026-05-06;
   automatic rules deferred until more site samples exist.
3. ~~Add browser-mode fallback for pages where HTTP HTML is incomplete.~~ Done 2026-05-06.
4. ~~Add optional LLM Planner/Strategy with deterministic fallback.~~ Design
   drafted, audited, revised, and accepted 2026-05-07; Phase A interfaces
   implemented and accepted 2026-05-07. Phase B/C merge hardening implemented
   2026-05-07. OpenAI-compatible provider adapter added 2026-05-07. First
   real-site LLM-assisted CLI smoke accepted 2026-05-08.
5. ~~Add background job execution for FastAPI crawl requests.~~ Done 2026-05-06.
6. ~~Add real browser SPA smoke validation.~~ Done 2026-05-06.
7. ~~Initialize local Git repository and employee memory model.~~ Done 2026-05-07.
8. ~~Configure remote Git repository and add ADR/runbook foundation.~~ Done 2026-05-07.
9. ~~Add background job registry concurrency limit.~~ Done 2026-05-07.
10. ~~Add background job registry TTL cleanup.~~ Done 2026-05-07.
11. ~~Implement LLM Advisor Phase A interfaces with fake-advisor tests.~~
    Done 2026-05-07.
12. ~~Add FastAPI opt-in LLM advisor support.~~ Done 2026-05-08.
13. ~~Add simple LLM provider diagnostics.~~ Done 2026-05-08 with
    `python run_simple.py --check-llm`.
