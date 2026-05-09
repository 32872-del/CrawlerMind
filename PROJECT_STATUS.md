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
- Real-site training ladder preserved under `docs/team/training/` and linked
  from the team board.
- Open-source preparation docs added for GitHub users, including a rewritten
  root README, Windows quick start, Linux/macOS quick start, release checklist,
  and Unix helper scripts.
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
- Structured error codes added: 11 machine-readable error code constants
  (`LLM_CONFIG_INVALID`, `LLM_PROVIDER_UNREACHABLE`, `LLM_RESPONSE_INVALID`,
  `FETCH_UNSUPPORTED_SCHEME`, `FETCH_HTTP_ERROR`, `BROWSER_RENDER_FAILED`,
  `EXTRACTION_EMPTY`, `SELECTOR_INVALID`, `VALIDATION_FAILED`,
  `ANTI_BOT_BLOCKED`, `RECON_FAILED`) defined in `autonomous_crawler/errors.py`.
  Executor, validator, recon, planner, and strategy agents set `error_code` on
  failure paths. `LLMResponseError` gains optional `error_code` attribute for
  transport vs. response error classification. API exposes `error_code` in job
  registry and GET /crawl/{id} responses. LLM config validation errors return
  structured `{"error_code": "...", "message": "..."}`. 23 focused tests.
  7 of 10 priority codes are actively used; 3 reserved for future paths.
- P1 access diagnostics started: new project-local
  `autonomous_crawler/tools/access_diagnostics.py` detects JS shell pages,
  challenge/CAPTCHA/access-block signals, embedded structured data
  (`JSON-LD`, `__NEXT_DATA__`, `__NUXT__`), API-like hints, target selector
  misses, and safe recommendations. Recon stores the diagnostics in
  `recon_report.access_diagnostics`. Strategy promotes JS-shell and
  challenge-like pages to browser mode before `api_intercept`. Validator maps
  empty challenge-page results to `ANTI_BOT_BLOCKED`. Added deterministic
  `mock://js-shell`, `mock://challenge`, and `mock://structured` fixtures plus
  focused tests.
- P1 fetch-best-page policy added: new
  `autonomous_crawler/tools/fetch_policy.py` scores fetch attempts across
  `requests`, `curl_cffi`, and browser modes, records an escalation trace, and
  selects the best HTML for Recon. Recon now stores
  `recon_report.fetch.selected_mode`, `selected_score`, and `fetch_trace`.
  Strategy keeps browser mode when Recon selected browser-rendered HTML. Pure
  transport failures skip browser launch to avoid slow redundant failures.
- P1 crawl foundation completed for real-site training:
  - `tools/site_zoo.py` provides static, SPA, structured-data, challenge,
    API-backed, product-detail, and variant-detail fixtures.
  - `tools/api_candidates.py` ranks API hints, fetches JSON APIs, extracts
    common record shapes, and normalizes records.
  - Executor `api_intercept` now performs real JSON extraction and passes
    structured data through the graph.
  - `storage/frontier.py` adds a project-local SQLite URL frontier with
    dedupe, queued/running/done/failed states, leases, and retry requeue.
  - `storage/domain_memory.py` adds per-domain preferred mode and challenge
    memory.
  - `tools/product_tasks.py` adds generic list/detail/variant helpers.
  - Real-site training ladder normalized and linked into the team workflow.
- Open source CI and contributor basics added on 2026-05-09: GitHub Actions
  workflow runs unit tests on Python 3.11/3.12 with compile check. Browser smoke
  skipped (no Playwright in CI). `CONTRIBUTING.md` with setup, test command,
  no-secrets rule, branch/PR guidance, and crawling safety note. Three GitHub
  issue templates: bug report, feature request, crawl target/training report.
- Rendered DOM selector training added on 2026-05-09: improved
  `infer_dom_structure` for modern SPA/SSR list pages. Added HN Algolia-style
  fixtures (`mock://hn-algolia`, `mock://hn-algolia-variant`) with CSS module
  class names, `data-testid` attributes, nested link/title structures, bare-text
  score nodes, and `<time>` elements. Field selectors now support
  `[data-testid*=title]` fallback, `<time[datetime]>` date detection, and
  `POINTS_RE` score matching ("123 points", "45 votes"). `_find_score_element`
  checks `data-testid`, class names, and text patterns. 15 new tests.
- Browser network observation skeleton added on 2026-05-09:
  `tools/browser_network_observer.py` observes Playwright response events,
  redacts sensitive headers, captures bounded JSON/post-data previews, scores
  JSON/API/GraphQL candidates, and can be enabled in Recon through
  `constraints.observe_network=true`. QA expanded coverage to 55 focused tests;
  duplicate API candidates now keep the higher-score observation.
- Browser network observation timing and API replay improved on 2026-05-09:
  observation now defaults to `networkidle`, supports optional
  `render_time_ms`, distinguishes Algolia-style JSON POST search bodies from
  GraphQL, carries POST JSON bodies into Strategy, and lets Executor replay
  safe observed JSON POST APIs through `api_intercept`.
- Real-site training round 4 completed on 2026-05-09:
  DummyJSON products API, HN Algolia API, GitHub CPython issues API, and
  Quotes to Scrape API completed with 10 items each. Training fixed JSON
  anti-bot false positives and added support for `hits`/`quotes` response
  shapes plus common score/summary/link normalization. After the timing/API
  replay fix, the HN Algolia public SPA observation scenario also completes:
  Recon observes Algolia XHR, Strategy chooses `api_intercept`, Executor POSTs
  the observed JSON body, and 10 story items validate successfully.
- Controlled XHR-backed SPA browser-network smoke added on 2026-05-09:
  optional real-browser smoke now serves a local SPA that calls
  `/api/products?page=1`; `observe_browser_network()` captures the real XHR
  response and promotes it to a JSON API candidate. This proves the browser
  network observation path end-to-end without relying on external sites.

## Current Test Status

```text
python -m unittest discover -s autonomous_crawler/tests
Ran 345 tests (skipped=4)
OK
```

Additional verification on 2026-05-09:

```text
python -m unittest autonomous_crawler.tests.test_browser_network_observer -v
Ran 60 tests
OK

python -m unittest autonomous_crawler.tests.test_api_intercept -v
Ran 23 tests
OK

python -m unittest autonomous_crawler.tests.test_access_diagnostics -v
Ran 9 tests
OK

python -m compileall autonomous_crawler run_skeleton.py run_baidu_hot_test.py run_results.py run_simple.py run_training_round1.py run_training_round2.py run_training_round3.py run_training_round4.py
OK

python run_training_round4.py
5 completed, 0 failed
HN Algolia browser-network observation: completed, mode=api_intercept, items=10

AUTONOMOUS_CRAWLER_RUN_BROWSER_SMOKE=1 python -m unittest autonomous_crawler.tests.test_real_browser_smoke -v
Ran 4 tests
OK
```

## Current Limitations

- Planner and Strategy can use optional LLM advisors through CLI/config and now
  also through FastAPI request-level configuration. Deterministic fallback
  remains the default.
- Recon selector inference is heuristic and currently strongest for product
  cards and Baidu-style ranking lists.
- `site_spec_draft` detail selectors are drafts when only a list page is known.
- API interception is integrated for direct JSON URLs, API hints, explicit
  GraphQL queries, and observed JSON POST APIs. It still needs
  pagination/cursor handling and richer provider-specific field mapping.
- Dynamic/JS-heavy site coverage is proven for local SPA rendering, local
  XHR-backed network observation smoke tests, and one public HN Algolia SPA
  API-replay scenario. Cloudflare/CAPTCHA/login-required targets remain
  diagnosis-only.
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
14. ~~Add structured error codes.~~ Done 2026-05-08. 11 codes defined, 7
    actively used, 23 focused tests, 215 total tests pass.
15. Start P1 crawl capability iteration.
16. ~~Add open source CI and contributor basics.~~ Done 2026-05-09. GitHub
    Actions workflow, CONTRIBUTING.md, and three issue templates.
    - Access diagnostics done 2026-05-08.
    - Fetch mode escalation done 2026-05-08.
    - Site-zoo fixtures, API intercept, SQLite frontier, domain memory, and
      product list/detail/variant helpers done 2026-05-08.
    - Real-site training round 1 done 2026-05-08:
      JSONPlaceholder direct JSON, Reddit `.json`, and Countries GraphQL all
      completed with 10 validated items each.
      `run_training_round1.py` writes
      `dev_logs/2026-05-08_real_site_training_round1.json`.
    - Browser network observation skeleton done 2026-05-09 with mocked
      Playwright tests and explicit Recon opt-in.
    - Real-site training round 4 done 2026-05-09:
      5/5 scenarios completed after absorbing JSON/API failures into generic
      tests and normalizers, then fixing browser-network timing and observed
      JSON POST replay for the HN Algolia public SPA.
17. ~~Run a real browser-network observation smoke against a controlled
    SPA/API-backed target and convert useful findings into fixtures/tests.~~
    Done 2026-05-09 with local XHR-backed SPA smoke.
18. ~~Improve rendered DOM selector inference for public SPA list layouts and
    retry the HN Algolia browser-network observation probe.~~ Done 2026-05-09;
    HN Algolia now completes via observed API replay.
