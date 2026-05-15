# Autonomous Crawl Agent - Project Status

## Current Stage

The project is a runnable MVP with a beginner-facing Easy Mode CLI. The
LangGraph workflow exists and can complete deterministic fixture crawls, real
Baidu realtime hot-search extraction, public JSON/GraphQL/API workflows, one
public SPA observed API replay workflow on HN Algolia, and selected ecommerce
training runs.

The product target has been sharpened: CLM should become an agent that
productizes advanced crawler development, not just a simple scraper. The
current major capability track is Scrapling capability absorption plus the
access/browser/proxy/JS evidence stack needed for difficult real-world
collection.

Access Layer MVP work started on 2026-05-12. The first shipped slice turns
advanced access concerns into explicit, testable policy objects: structured
challenge detection, access decisions, proxy configuration, session profiles,
browser-context configuration, and per-domain rate-limit/backoff rules.

Scrapling capability absorption work started on 2026-05-14. The intent is not
to leave CLM as a thin wrapper around the `scrapling` package. The intent is to
use Scrapling 0.4.8 as a strong engineering reference, then absorb its useful
capabilities into CLM-owned runtime/backend modules. The major Scrapling
backend patterns now have accepted CLM-native baseline equivalents: static
fetch, async fetch, parser/adaptive selectors, browser/session/profile/proxy,
spider/checkpoint/link/robots/site profile, and evidence/visual reporting.
Transition adapters remain as comparison oracles, not the final product
architecture.

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
- Easy Mode CLI added through `clm.py`:
  `init`, `check`, `crawl`, `smoke`, and `train`. New users should start here
  instead of using the older development scripts directly.
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
- Scrapling capability absorption path accepted on 2026-05-14:
  - `autonomous_crawler/runtime/` defines CLM-owned runtime models and
    protocols.
  - `ScraplingStaticRuntime` is a transition adapter for Scrapling static
    fetching.
  - `ScraplingParserRuntime` is a transition adapter for Scrapling selector
    parsing.
  - `ScraplingBrowserRuntime` maps dynamic/protected browser config, sessions,
    XHR capture fields, and proxy conversion as a transition adapter.
  - Planner/Strategy accept `engine="scrapling"`.
  - Executor routes static/http Scrapling work through
    `ScraplingStaticRuntime.fetch()` and browser Scrapling work through
    `ScraplingBrowserRuntime.render()`.
  - Focused Scrapling runtime suite: 162 tests passing.
  - Follow-up goal: replace adapter-backed behavior with CLM-native
    fetch/parser/browser/spider/checkpoint implementations that absorb
    Scrapling's capabilities.
- SCRAPLING-ABSORB-1 native runtime slice accepted on 2026-05-14:
  - `NativeFetchRuntime` provides CLM-owned static fetching through `httpx`
    with optional `curl_cffi`, normalized `RuntimeResponse`, runtime events,
    proxy trace, and structured failures.
  - `NativeParserRuntime` provides CLM-owned CSS/XPath/text/regex extraction
    and selector-result normalization without importing Scrapling.
  - Native-vs-transition parity suite compares native runtimes against
    Scrapling transition adapters on local fixtures.
  - Acceptance records:
    `docs/team/acceptance/2026-05-14_native_fetch_runtime_ACCEPTED.md`,
    `docs/team/acceptance/2026-05-14_native_parser_runtime_ACCEPTED.md`, and
    `docs/team/acceptance/2026-05-14_native_runtime_parity_ACCEPTED.md`.
- SCRAPLING-ABSORB-1B native executor routing accepted on 2026-05-14:
  - Planner and Strategy accept explicit `engine="native"`.
  - Executor static path routes through `NativeFetchRuntime` and
    `NativeParserRuntime`.
  - `engine_result.selector_results` now carries native parser evidence.
  - `run_native_transition_comparison_2026_05_14.py` compares native and
    transition static runtime outputs.
  - `clm.py train --round native-vs-transition` prints the comparison command.
  - Smoke evidence:
    `dev_logs/training/2026-05-14_native_transition_comparison_smoke.json`.
- SCRAPLING-ABSORB-1D native adaptive parser accepted on 2026-05-14:
  - `adaptive_parser.py` adds CLM-native element signatures, structural
    similarity scoring, selector-miss relocation, and same-depth similar-node
    discovery.
  - `NativeParserRuntime` can recover missed CSS/XPath selectors from
    `selector_config.adaptive_signatures` or per-selector signatures.
  - Executor now passes `RuntimeRequest.selector_config` into parser runtimes,
    so adaptive parsing is reachable from real runtime execution paths.
  - Focused and full verification passed:
    `test_native_adaptive_parser`, `test_native_parser_runtime`,
    `test_scrapling_executor_routing`, `test_native_runtime_parity`, and full
    `unittest discover`.
- SCRAPLING-ABSORB-1E native selector memory accepted on 2026-05-14:
  - `SelectorMemoryStore` persists successful element signatures in SQLite.
  - `NativeParserRuntime` can auto-save CSS/XPath signatures through
    `selector_config.adaptive_auto_save` or `adaptive_memory_path`.
  - On later selector miss, the runtime can load the stored signature and
    recover the element through structural relocation.
  - This moves adaptive parsing from one-off supplied signatures toward a
    learned backend capability for long-running crawls.
- SCRAPLING-ABSORB-2A native browser runtime shell accepted on 2026-05-14:
  - `NativeBrowserRuntime` provides a CLM-owned Playwright browser backend
    without importing Scrapling.
  - Native browser execution supports BrowserContextConfig mapping, headers,
    cookies, storage state, proxy config, wait selector/state, wait_until,
    render delay, optional screenshots, blocked resource types, blocked
    domains, init scripts, and XHR/JSON response preview capture.
  - Executor now routes `engine="native"` + `mode="browser"` through
    `NativeBrowserRuntime.render()` and preserves runtime events, artifacts,
    selector evidence, captured XHR, and proxy trace in workflow state.
  - Remaining ABSORB-2 work: real SPA/dynamic comparison training, session
    reuse lifecycle, protected-profile/fingerprint tuning, and runtime failure
    classification on harder sites.
- SCRAPLING-ABSORB-2B dynamic comparison harness accepted on 2026-05-14:
  - `run_native_transition_comparison_2026_05_14.py` supports
    `--suite dynamic` and starts a deterministic local SPA/API training server.
  - Dynamic smoke compares `NativeBrowserRuntime` against
    `ScraplingBrowserRuntime` on rendered DOM selectors and captured XHR
    evidence.
  - Smoke evidence:
    `dev_logs/training/2026-05-14_native_transition_dynamic_smoke.json`.
  - Latest dynamic smoke: both engines executed with HTTP 200, HTML ratio 1.0,
    selector deltas 0 for title/price/link, captured XHR count 1 each, review
    false.
- SCRAPLING-ABSORB-2B follow-up profile comparison accepted on 2026-05-14:
  - `run_native_transition_comparison_2026_05_14.py` now supports
    `--suite profile` and `--profile <json>` for reusable comparison targets.
  - The default bundled profile includes three local targets: product-card
    catalog, JSON-LD/script coexistence, and local SPA product list.
  - Comparison summaries now record captured XHR preview, runtime event types,
    artifact kinds, fingerprint risk, and expectation checks.
  - `clm.py train --round native-vs-transition-profile` prints the profile
    comparison command.
  - Evidence:
    `dev_logs/training/2026-05-14_native_transition_profile_comparison.json`.
- SCRAPLING-ABSORB-2C session lifecycle slice accepted on 2026-05-14:
  - `NativeBrowserRuntime` supports persistent browser context via
    `browser_config.user_data_dir`.
  - Runtime can export storage state through
    `browser_config.storage_state_output_path` and returns a `storage_state`
    runtime artifact.
  - Runtime evidence now records `session_mode` as `ephemeral`,
    `storage_state`, `persistent`, or `cdp`.
  - This is the first native session lifecycle layer; cross-request pool reuse
    and batch-managed context leasing remain future work.
- SCRAPLING-ABSORB-2D protected profile evidence and browser failure
  classification accepted on 2026-05-14:
  - `NativeBrowserRuntime` now attaches `fingerprint_report` evidence to both
    successful and failed browser responses.
  - Protected mode applies a first native profile-tuning layer through
    Playwright launch flags and a bounded init script.
  - Browser failures are classified into `playwright_missing`,
    `browser_install_or_launch`, `navigation_timeout`, `proxy_error`,
    `http_blocked`, `challenge_like`, `unknown`, or `none`.
  - HTTP block/challenge-like rendered pages are preserved as structured
    runtime evidence instead of becoming opaque browser errors.
- SCRAPLING-ABSORB-2F native browser session/profile pool accepted on
  2026-05-14:
  - `BrowserPoolManager` provides opt-in Playwright context leasing by
    `browser_config.pool_id`.
  - Pool fingerprints include session/profile-relevant browser context fields,
    allowing controlled reuse while keeping site rules out of runtime code.
  - `NativeBrowserRuntime(pool=...)` can reuse contexts across requests and
    reports credential-safe pool evidence in `engine_result`.
  - Supervisor cleanup fixed request-count double counting during lease reuse.
- CAP-3.3 / SCRAPLING-ABSORB-1C proxy health and fetch diagnostics accepted on
  2026-05-14:
  - Proxy health lifecycle, cooldown/backoff, health-aware pool selection, and
    redacted proxy trace behavior are covered by focused tests.
  - `NativeFetchRuntime` exposes transport/proxy evidence through
    `engine_result`, runtime events, and `RuntimeProxyTrace`.
  - Remaining work is active orchestration: retry failed proxy requests with
    alternative healthy proxies and carry metrics into long-running spider runs.
- SCRAPLING-ABSORB-3A native spider request/result/event models accepted on
  2026-05-14:
  - `CrawlRequestEnvelope` provides deterministic request identity,
    canonical URL handling, safe serialization, and conversion to
    `RuntimeRequest`.
  - `CrawlItemResult` bridges spider item processing back into the existing
    `BatchRunner` `ItemProcessResult` contract.
  - `SpiderRunSummary` records long-run counters, response status buckets,
    failure buckets, and runtime events.
  - This is the data-contract layer for future `CheckpointStore`,
    LinkDiscovery, RobotsPolicy, and SpiderBatchRunner work.
- SCRAPLING-ABSORB-3B native checkpoint store accepted on 2026-05-14:
  - `CheckpointStore` persists spider runs, batch checkpoints, item records,
    request events, and failure buckets in inspectable SQLite tables.
  - Checkpoints are JSON-based rather than pickle-based, so paused and failed
    runs can be inspected by CLM and future UI tools.
  - Run lifecycle now supports `running`, `paused`, and `completed` markers.
  - Failure buckets can be queried by run and bucket, with error/proxy
    credential redaction preserved.
- SCRAPLING-ABSORB-3C native spider runtime processor accepted on 2026-05-14:
  - `SpiderRuntimeProcessor` connects `CrawlRequestEnvelope`,
    `CrawlItemResult`, runtime backends, parser callbacks, discovered request
    callbacks, and `CheckpointStore`.
  - The processor is compositional around the existing `BatchRunner`; it does
    not replace queue mechanics or introduce site-specific rules into core.
  - Static and browser runtime modes are both supported through runtime
    protocols.
  - Runtime failures map to retryable `ItemProcessResult` values and
    checkpointed failure buckets.
- SCRAPLING-ABSORB-3D native link discovery and robots policy helpers accepted
  on 2026-05-14:
  - `LinkDiscoveryHelper` supports allow/deny regex rules, allow/deny domain
    rules, CSS/XPath extraction scopes, ignored extensions, duplicate/offsite
    drop counters, URL canonicalization, and profile-driven URL
    classification.
  - JSON API links are retained by default and can be classified as `api`.
  - `RobotsPolicyHelper` supports `respect`, `record_only`, and `disabled`
    modes, robots cache, `can_fetch`, crawl-delay, request-rate, prefetch, and
    runtime events.
- SCRAPLING-ABSORB-3E native spider pause/resume smoke accepted on 2026-05-14:
  - `run_spider_runtime_smoke_2026_05_14.py` proves the local long-running
    spider path without public network access.
  - The smoke connects `URLFrontier`, `BatchRunner`, `SpiderRuntimeProcessor`,
    `CheckpointStore`, `NativeParserRuntime`, and `LinkDiscoveryHelper`.
  - First pass processes only the seeded list page, discovers two detail URLs,
    records paused checkpoint state, and leaves the frontier resumable.
  - Resume pass processes two detail records and one deterministic missing
    fixture failure, then marks the run completed.
  - Evidence is saved at
    `dev_logs/smoke/2026-05-14_spider_runtime_smoke.json`.
  - `clm.py smoke --kind native-spider` now runs this local smoke from Easy
    Mode.
- SCRAPLING-ABSORB-2H native browser profile rotation and real dynamic
  training accepted on 2026-05-14:
  - `BrowserProfile` and `BrowserProfileRotator` provide reusable browser
    identity/profile selection.
  - `NativeBrowserRuntime(rotator=...)` can apply rotating profiles while
    keeping site rules outside runtime modules.
  - Real dynamic training artifacts are preserved under `dev_logs/training/`.
- SCRAPLING-ABSORB-1F native async fetch pool accepted on 2026-05-14:
  - `NativeAsyncFetchRuntime` supports per-domain and global concurrency.
  - Runtime events expose pool acquisition, release, backpressure, proxy retry,
    and completion evidence.
  - `AsyncFetchMetrics` summarizes status, proxy, domain, and backpressure
    behavior for long-running fetch batches.
- SCRAPLING-ABSORB-3G site profile and profile-driven ecommerce runner accepted
  on 2026-05-14:
  - `SiteProfile` centralizes selectors, access config, pagination/link hints,
    and quality expectations.
  - `profile_ecommerce.py` maps profiles into generic selector, record, and
    link callbacks for `SpiderRuntimeProcessor`.
  - Local smoke evidence:
    `dev_logs/smoke/2026-05-14_profile_ecommerce_runner_smoke.json`.
- CAP-5.2 VisualRecon Strategy/AntiBot integration accepted on 2026-05-14:
  - Visual screenshot/OCR evidence now feeds Strategy evidence.
  - Challenge-like visual findings become AntiBotReport challenge findings.
  - OCR-only text remains low-risk diagnostic evidence.
- Scrapling absorption baseline closeout accepted on 2026-05-14:
  - major backend patterns have CLM-owned baseline modules or integration
    points.
  - next work is large-run proof, real-site hardening, and simpler operation,
    not more wrapper work.
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
- Legacy simple entrypoint retained: `run_simple.py` still supports config-file
  based crawls and LLM diagnostics. Current user-facing docs now prefer
  `python clm.py ...`.
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
- LLM provider diagnostics added. Current Easy Mode path is
  `python clm.py check --llm`; the legacy path
  `python run_simple.py --check-llm` remains available.
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
- P1 Access Layer MVP started on 2026-05-12:
  - `tools/challenge_detector.py` provides structured Cloudflare/CAPTCHA/login/
    429/access-block classification.
  - `tools/access_policy.py` converts diagnostics into auditable decisions such
    as `standard_http`, `browser_render`, `backoff`, `manual_handoff`, and
    `authorized_browser_review`.
  - `tools/proxy_manager.py` adds opt-in proxy selection with credential
    redaction and per-domain routing.
  - `tools/session_profile.py` adds authorized header/cookie/storage-state
    profile modeling with domain scoping and safe summaries.
  - `tools/rate_limit_policy.py` adds per-domain delay, retry cap, and backoff
    decisions.
  - `fetch_policy.fetch_best_page()` can now receive access config and records
    redacted access context in fetch attempts.
  - Recon can pass access config through to fetch policy and stores a safe
    access context in `recon_report.access_config`.
- CAP-3.3 Pluggable proxy pool foundation added on 2026-05-12:
  - `tools/proxy_pool.py` defines `ProxyPoolProvider`, `ProxyEndpoint`,
    `ProxyPoolConfig`, `ProxySelection`, and `StaticProxyPoolProvider`.
  - Static pools support `round_robin`, `domain_sticky`, and `first_healthy`
    selection, failure-count exclusion, cooldown checks, and safe summaries.
  - `ProxyManager` now keeps manual per-domain rules first, proxy pool second,
    and default proxy last. Proxy support remains opt-in and credentials are
    redacted.
  - `storage/proxy_health.py` adds persistent SQLite success/failure/cooldown
    tracking with credential-safe proxy IDs and redacted labels.
  - `StaticProxyPoolProvider` can optionally write through to a health store
    and skip proxies in persisted cooldown.
  - `ProviderAdapter` provides a template for future paid/API-backed proxy
    providers. No concrete vendor adapter is implemented yet.
- CAP-3.3 Proxy health trace accepted on 2026-05-12:
  - `tools/proxy_trace.py` adds credential-safe proxy selection traces and
    aggregate health summaries.
  - Traces can be built from `ProxySelection` or `ProxyManager` and can enrich
    output with `ProxyHealthStore` cooldown/failure evidence.
  - Error messages, proxy credentials, and token/password/API-key patterns are
    redacted.
- CAP-5.1 Strategy Evidence Report added on 2026-05-12:
  - `tools/strategy_evidence.py` normalizes DOM, observed API, JS evidence,
    crypto/signature evidence, transport diagnostics, runtime fingerprint
    probe, challenge/access diagnostics, and WebSocket summary into ranked
    `EvidenceSignal` records.
  - Strategy now attaches `crawl_strategy.strategy_evidence`.
  - When crypto/signature/encryption evidence is present, Strategy attaches
    `crawl_strategy.reverse_engineering_hints`; API replay mode also gets
    `crawl_strategy.api_replay_warning`.
  - This remains evidence-only and advisory. It does not execute JS, recover
    keys, solve challenges, or override strong DOM/API/browser decisions.
- CAP-5.1 Strategy Scoring Policy added on 2026-05-12:
  - `tools/strategy_scoring.py` scores `http`, `api_intercept`, `browser`,
    `deeper_recon`, and `manual_handoff` from normalized evidence.
  - Strategy now attaches `crawl_strategy.strategy_scorecard`,
    `crawl_strategy.strategy_guardrails`, and an advisory
    `crawl_strategy.strategy_scorecard_warning` when scorecard guidance differs
    from deterministic routing.
  - This is still advisory-first; it does not replace final deterministic mode
    selection yet.
- CAP-6.2 Unified AntiBotReport added on 2026-05-12:
  - `tools/anti_bot_report.py` consolidates access diagnostics, HTTP 429/API
    block evidence, transport diagnostics, browser fingerprint probe results,
    JS anti-bot/crypto clues, WebSocket runtime evidence, proxy health traces,
    and Strategy warnings into one safe report.
  - Strategy now attaches `crawl_strategy.anti_bot_report` with risk level,
    risk score, categories, findings, recommended action, next steps,
    guardrails, and evidence sources.
  - This remains diagnostic/advisory today. Future OCR/CAPTCHA provider,
    protected browser, signed-request profile, and proxy-provider tracks are
    tracked in the capability roadmap and governance docs.
- CAP-1.4 WebSocket Recon opt-in integration accepted on 2026-05-12:
  - Recon can run `observe_websocket()` through
    `constraints.observe_websocket=true`.
  - Results are stored as `recon_report.websocket_observation` and compact
    `recon_report.websocket_summary`.
  - Default behavior is unchanged; non-HTTP URLs and unset constraints do not
    run WebSocket observation.
  - This is opt-in and evidence-only; no frame replay, protocol reverse
    engineering, or binary decoding is implemented yet.
- CAP-1.4 Real WebSocket smoke accepted on 2026-05-12:
  - `tests/test_real_websocket_smoke.py` runs a local HTTP page plus local
    WebSocket echo server and validates real Playwright WebSocket events.
  - The smoke covers sent/received frames, summaries, JSON serialization,
    truncation, sensitive preview redaction, and pages with no WebSockets.
  - It skips cleanly if browser or `websockets` dependencies are unavailable.
- Aggressive capability sprint documentation audit accepted on 2026-05-12:
  - `docs/plans/2026-05-12_CAPABILITY_IMPLEMENTATION_MATRIX.md` was refreshed
    as readable UTF-8 Chinese text.
  - Capability maturity labels now distinguish production-ready, opt-in,
    evidence-only, mocked-only, and initial work to avoid overclaiming.
- Advanced diagnostics runbook accepted on 2026-05-12:
  - `docs/runbooks/ADVANCED_DIAGNOSTICS.md` explains advanced diagnostics,
    enabling constraints, outputs, maturity labels, and explicit limitations.
  - README links to the runbook without turning the front page into an internal
    engineering document.
- Browser Context foundation added on 2026-05-12:
  - `tools/browser_context.py` centralizes Playwright launch/context settings:
    headless, user agent, viewport, locale, timezone, extra headers,
    storage-state path, proxy URL, JavaScript toggle, HTTPS-error handling, and
    color scheme.
  - `browser_fetch.fetch_rendered_html()` and
    `browser_network_observer.observe_browser_network()` now use the same
    context model, so rendering and API observation can run under a consistent
    browser environment.
  - Browser context summaries redact sensitive headers and proxy credentials.
  - Executor browser mode can receive `access_config.browser_context` from
    workflow state or recon constraints and records the safe context used.
- Access Layer QA/docs/audit accepted on 2026-05-12:
  - Worker QA expanded Access Layer coverage to include proxy default-off,
    session redaction, 429 backoff decisions, challenge no-auto-solve behavior,
    and fetch-trace leak prevention.
  - Access Layer runbook added at `docs/runbooks/ACCESS_LAYER.md`.
  - Safety audit accepted; supervisor fixed two product-hardening findings:
    empty `allowed_domains` now emits a global-session warning, and
    `storage_state_path` is redacted in safe summaries.
- Unified Access Config and Artifact Manifest foundation added on 2026-05-12:
  - `tools/access_config.py` resolves session/profile/proxy/rate/browser
    configuration from workflow state and recon constraints into typed objects.
  - Recon and Executor now share the same access-config resolver.
  - Browser executor passes resolved session headers, Playwright storage state,
    proxy URL, and browser context to browser fetch.
  - `tools/artifact_manifest.py` adds serializable recon/browser evidence
    manifests for future artifact persistence and enterprise debugging.
  - Recon and browser executor results now include `artifact_manifest`.
- Rate-limit enforcement and artifact persistence started on 2026-05-12:
  - `tools/rate_limiter.py` adds executable per-domain throttling with
    injectable clock/sleeper for deterministic tests.
  - `fetch_policy.fetch_best_page()` now enforces the configured rate-limit
    delay before each fetch-mode attempt and records `rate_limit_event` in each
    fetch attempt trace.
  - `artifact_manifest.persist_artifact_bundle()` writes `manifest.json`,
    optional `snapshot.html`, and optional `network_trace.json` under
    `autonomous_crawler/tools/runtime/artifacts/`.
  - Recon and browser executor now persist artifact bundles so complex-site
    failures have a replay/debug evidence index.
- CAP-1.2 HTTP/TLS transport diagnostics started on 2026-05-12:
  - `tools/transport_diagnostics.py` compares transport modes for a target URL:
    `requests`, `curl_cffi`, and browser.
  - Reports status-code differences, HTTP-version differences, challenge
    differences, mode-specific transport errors, response header clues, and
    selected transport recommendation.
  - Diagnostics now include transport profile labels such as `httpx-default`,
    `curl_cffi:chrome124`, and `playwright-browser-context`, plus server-header
    and edge/cache-header difference findings.
  - `fetch_policy.FetchAttempt` now records response headers and HTTP version
    where available.
  - Recon can run transport diagnostics through
    `constraints.transport_diagnostics=true`.
  - This is a diagnostic foundation, not full JA3/ALPN/SNI fingerprint control
    yet.
- CAP-4.4 Browser Interception and CAP-2.1 JS Asset Inventory accepted on
  2026-05-12:
  - `tools/browser_interceptor.py` adds Playwright route interception,
    resource blocking, JS/API response metadata capture, and init-script
    injection.
  - `tools/js_asset_inventory.py` extracts script assets and ranks JS clues:
    signature/token/encryption/challenge/fingerprint keywords, API endpoints,
    GraphQL strings, WebSocket URLs, and sourcemap references.
  - `tools/js_static_analysis.py` adds the pre-AST static-analysis layer:
    string table, endpoint strings, suspicious function names, and suspicious
    call clues.
  - `tools/js_crypto_analysis.py` adds built-in crypto/signature evidence:
    hash/HMAC/signature/WebCrypto/AES/RSA/base64/timestamp/nonce/param-sort/
    custom-token clues. This is evidence-only; it does not execute JS or
    recover keys.
  - `tools/js_evidence.py` now connects JS inventory and static analysis into
    ranked evidence, including `crypto_analysis` and `top_crypto_signals`.
    Recon stores this under `recon_report.js_evidence` for fetched HTML.
- CAP-4.2 Browser Fingerprint Profile accepted on 2026-05-12:
  - `tools/browser_fingerprint.py` turns `BrowserContextConfig` into a
    serializable config-side fingerprint profile.
  - Reports UA/viewport mismatch, locale/timezone mismatch, default UA with
    custom profile, proxy/default mismatch, risk level, and recommendations.
  - Config-side profile reporting remains useful before launching a browser.
- CAP-4.2 Runtime Fingerprint Probe accepted on 2026-05-12:
  - `tools/browser_fingerprint_probe.py` launches Playwright and samples
    browser-side evidence: navigator identity, webdriver, timezone, screen,
    viewport, WebGL vendor/renderer, canvas hash metadata, and a bounded font
    probe.
  - Recon can run it through `constraints.probe_fingerprint=true` and stores
    evidence under `recon_report.browser_fingerprint_probe`.
  - This is evidence-only; no stealth/spoofing or fingerprint pool is
    implemented yet.
- Opt-in Browser Interception Recon Path accepted on 2026-05-12:
  - Recon supports `constraints.intercept_browser=true`.
  - When enabled, Recon runs `intercept_page_resources()`, stores
    `recon_report.browser_interception`, and feeds captured JS assets into
    `recon_report.js_evidence`.
  - Default Recon remains unchanged unless this constraint is explicitly set.
- Strategy JS Evidence Advisory accepted on 2026-05-12:
  - Strategy reads `recon_report.js_evidence`.
  - Adds `crawl_strategy.js_evidence_hints` and optional
    `crawl_strategy.js_evidence_warning`.
  - JS evidence is advisory: it can explain API/hook/challenge clues and fill a
    missing endpoint only after `api_intercept` has already been selected; it
    does not override good DOM, observed API, or challenge-browser decisions.
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
- Observed API pagination/cursor MVP added on 2026-05-09:
  `api_intercept` now supports multi-page JSON API crawling with three
  pagination strategies: page/limit (`next_page` hint), offset/limit
  (`next_offset` hint), and cursor-based (`next_cursor`/`after`/`page_token`
  hints). `fetch_paginated_api()` loops across pages, respects `max_items` as
  a universal termination guard, and caps at `max_pages`. Three deterministic
  mock fixtures (`mock://api/paged-products`, `mock://api/offset-products`,
  `mock://api/cursor-products`) provide fixture-only testing. Executor routes
  to the pagination loop when `strategy.pagination.type` is `page`, `offset`,
  or `cursor`. 26 new pagination tests. 385 total tests pass after the
  ecommerce and stress-test documentation updates.
- Ecommerce product storage and quality foundation added on 2026-05-11:
  `ProductRecord`, category-aware dedupe, SQLite `ProductStore`, batch upsert,
  product quality validation, and 30,000-row store tests. Site-specific
  collection rules remain outside the core and should live in profiles,
  fixtures, or training artifacts.
- Long-running ecommerce runbook added on 2026-05-11. Large ecommerce crawls
  must checkpoint frontier progress and product records batch-by-batch instead
  of relying on a final in-memory workflow state.
- Generic resumable `BatchRunner` added on 2026-05-11:
  frontier-backed claim/process/checkpoint loop, bounded `max_batches` resume
  support, failure/retry handling, discovered URL insertion, checkpoint error
  handling, and a `ProductRecordCheckpoint` adapter. Local smoke proves a
  two-pass run can process 25 records across an intentional pause/resume.
- Two-round real-site training completed on 2026-05-11:
  round 1 collected 50 records each from five public targets
  (JSONPlaceholder, DummyJSON, GitHub CPython issues, HN Algolia, and Quotes
  to Scrape). Round 2 collected 200 product detail records each from Tatuum,
  The Sting, and BalticBHP through public sitemap/detail pages. Total: 850
  rows exported to JSON and Excel under `dev_logs/training/`.

## Current Test Status

```text
python -m unittest discover -s autonomous_crawler/tests
Ran 1773 tests in 75.809s
OK (skipped=5)
```

Latest Scrapling absorption baseline closeout on 2026-05-15:

```text
python -m unittest discover -s autonomous_crawler/tests
Ran 1773 tests in 75.809s
OK (skipped=5)

python -m compileall autonomous_crawler clm.py run_profile_ecommerce_runner_smoke_2026_05_14.py run_profile_rotation_smoke_2026_05_14.py run_real_dynamic_training_2026_05_14.py run_spider_runtime_smoke_2026_05_14.py
OK
```

Latest SCRAPLING-ABSORB-1 native runtime verification on 2026-05-14:

```text
python -m unittest autonomous_crawler.tests.test_native_static_runtime -v
Ran 9 tests
OK

python -m unittest autonomous_crawler.tests.test_native_parser_runtime -v
Ran 48 tests
OK

python -m unittest autonomous_crawler.tests.test_native_runtime_parity -v
Ran 66 tests
OK (skipped=1)

python -m compileall autonomous_crawler run_skeleton.py run_baidu_hot_test.py run_results.py run_simple.py clm.py
OK
```

Latest SCRAPLING-ABSORB-1B native executor routing verification on 2026-05-14:

```text
python -m unittest autonomous_crawler.tests.test_native_transition_comparison autonomous_crawler.tests.test_scrapling_executor_routing -v
Ran 16 tests
OK

python run_native_transition_comparison_2026_05_14.py --scenario example_home_static --output dev_logs\training\2026-05-14_native_transition_comparison_smoke.json
native=executed(200), transition=executed(200), html_ratio=1.0, review=False
```

Latest SCRAPLING-ABSORB-2A native browser runtime verification on 2026-05-14:

```text
python -m unittest autonomous_crawler.tests.test_native_browser_runtime autonomous_crawler.tests.test_scrapling_executor_routing -v
Ran 20 tests
OK
```

Latest SCRAPLING-ABSORB-2B dynamic comparison harness verification on 2026-05-14:

```text
python -m unittest autonomous_crawler.tests.test_native_transition_comparison -v
Ran 8 tests
OK

python run_native_transition_comparison_2026_05_14.py --suite dynamic --output dev_logs\training\2026-05-14_native_transition_dynamic_smoke.json
native=executed(200), transition=executed(200), html_ratio=1.0, review=False
```

Latest SCRAPLING-ABSORB-2C session lifecycle verification on 2026-05-14:

```text
python -m unittest autonomous_crawler.tests.test_native_browser_runtime -v
Ran 8 tests
OK
```

Latest SCRAPLING-ABSORB-2D protected/failure evidence verification on 2026-05-14:

```text
python -m unittest autonomous_crawler.tests.test_native_browser_runtime -v
Ran 11 tests
OK

python -m unittest autonomous_crawler.tests.test_native_browser_runtime autonomous_crawler.tests.test_scrapling_executor_routing autonomous_crawler.tests.test_native_transition_comparison -v
Ran 32 tests
OK

python -m compileall autonomous_crawler run_native_transition_comparison_2026_05_14.py clm.py
OK
```

Latest SCRAPLING-ABSORB-3A spider model verification on 2026-05-14:

```text
python -m unittest autonomous_crawler.tests.test_spider_models -v
Ran 9 tests
OK

python -m unittest autonomous_crawler.tests.test_spider_models autonomous_crawler.tests.test_batch_runner -v
Ran 19 tests
OK

python -m unittest discover -s autonomous_crawler/tests
Ran 1431 tests in 68.943s
OK (skipped=5)
```

Latest SCRAPLING-ABSORB-3B checkpoint store verification on 2026-05-14:

```text
python -m unittest autonomous_crawler.tests.test_checkpoint_store autonomous_crawler.tests.test_spider_models autonomous_crawler.tests.test_batch_runner -v
Ran 25 tests
OK

python -m unittest discover -s autonomous_crawler/tests
Ran 1437 tests in 70.602s
OK (skipped=5)

python -m compileall autonomous_crawler run_native_transition_comparison_2026_05_14.py clm.py
OK
```

Latest SCRAPLING-ABSORB-3C spider processor verification on 2026-05-14:

```text
python -m unittest autonomous_crawler.tests.test_spider_runner autonomous_crawler.tests.test_checkpoint_store autonomous_crawler.tests.test_spider_models autonomous_crawler.tests.test_batch_runner -v
Ran 30 tests
OK

python -m unittest discover -s autonomous_crawler/tests
Ran 1442 tests in 69.480s
OK (skipped=5)

python -m compileall autonomous_crawler run_native_transition_comparison_2026_05_14.py clm.py
OK
```

Latest SCRAPLING-ABSORB-3D link/robots verification on 2026-05-14:

```text
python -m unittest autonomous_crawler.tests.test_link_discovery autonomous_crawler.tests.test_robots_policy autonomous_crawler.tests.test_spider_runner autonomous_crawler.tests.test_checkpoint_store -v
Ran 22 tests
OK

python -m unittest discover -s autonomous_crawler/tests
Ran 1453 tests in 70.401s
OK (skipped=5)

python -m compileall autonomous_crawler run_native_transition_comparison_2026_05_14.py clm.py
OK
```

Latest CAP-3.3/CAP-2.x capability verification on 2026-05-12:

```text
python -m unittest autonomous_crawler.tests.test_proxy_pool autonomous_crawler.tests.test_access_layer -v
Ran 83 tests
OK

python -m unittest autonomous_crawler.tests.test_js_crypto_analysis autonomous_crawler.tests.test_js_evidence autonomous_crawler.tests.test_js_static_analysis -v
Ran 66 tests
OK
```

Latest CAP-5.1 Strategy Evidence Report verification on 2026-05-12:

```text
python -m unittest autonomous_crawler.tests.test_strategy_evidence autonomous_crawler.tests.test_strategy_js_evidence autonomous_crawler.tests.test_js_crypto_analysis -v
Ran 73 tests
OK

python -m unittest discover -s autonomous_crawler/tests
Ran 968 tests in 46.115s
OK (skipped=4)
```

Latest unified capability sprint acceptance verification on 2026-05-12:

```text
python -m unittest autonomous_crawler.tests.test_recon_websocket_observation autonomous_crawler.tests.test_websocket_observer -v
Ran 62 tests
OK

python -m unittest autonomous_crawler.tests.test_proxy_health autonomous_crawler.tests.test_proxy_pool -v
Ran 50 tests
OK

python -m unittest discover -s autonomous_crawler/tests
Ran 968 tests in 45.110s
OK (skipped=4)

python -m compileall autonomous_crawler run_skeleton.py run_baidu_hot_test.py run_results.py run_simple.py clm.py
OK
```

Latest CAP-5.1 Strategy Scoring Policy verification on 2026-05-12:

```text
python -m unittest autonomous_crawler.tests.test_strategy_scoring autonomous_crawler.tests.test_strategy_evidence autonomous_crawler.tests.test_strategy_js_evidence -v
Ran 73 tests
OK

python -m unittest discover -s autonomous_crawler/tests
Ran 1020 tests in 69.209s
OK (skipped=4)
```

Latest CAP-6.2 AntiBotReport verification on 2026-05-12:

```text
python -m unittest autonomous_crawler.tests.test_anti_bot_report autonomous_crawler.tests.test_strategy_evidence autonomous_crawler.tests.test_strategy_scoring -v
Ran 21 tests
OK

python -m unittest autonomous_crawler.tests.test_access_diagnostics autonomous_crawler.tests.test_access_layer autonomous_crawler.tests.test_error_codes -v
Ran 97 tests
OK
```

Latest worker-output acceptance verification on 2026-05-12:

```text
python -m unittest autonomous_crawler.tests.test_real_websocket_smoke autonomous_crawler.tests.test_websocket_observer autonomous_crawler.tests.test_recon_websocket_observation -v
Ran 68 tests
OK

python -m unittest autonomous_crawler.tests.test_proxy_trace autonomous_crawler.tests.test_proxy_health autonomous_crawler.tests.test_proxy_pool -v
Ran 89 tests
OK
```

Latest full-suite verification after worker acceptance on 2026-05-12:

```text
python -m unittest discover -s autonomous_crawler/tests
Ran 1026 tests in 68.851s
OK (skipped=4)

python -m compileall autonomous_crawler run_skeleton.py run_baidu_hot_test.py run_results.py run_simple.py clm.py
OK
```

Latest CAP-4.2 runtime fingerprint probe verification on 2026-05-12:

```text
python -m unittest autonomous_crawler.tests.test_browser_fingerprint_probe -v
Ran 22 tests
OK
```

Latest capability verification on 2026-05-12:

```text
python -m unittest autonomous_crawler.tests.test_transport_diagnostics autonomous_crawler.tests.test_browser_interceptor autonomous_crawler.tests.test_js_asset_inventory -v
Ran 108 tests
OK
```

Latest Easy Mode verification on 2026-05-11:

```text
python -m unittest autonomous_crawler.tests.test_clm_cli -v
Ran 7 tests
OK

python clm.py check --config dev_logs/runtime/clm_test_config.json
OK

python clm.py smoke --kind runner
accepted: true

python clm.py crawl "collect product titles" mock://catalog --config dev_logs/runtime/clm_test_config.json --no-llm --output dev_logs/runtime/clm_mock_output.json
Final Status: completed
```

Additional verification on 2026-05-09:

```text
python -m unittest autonomous_crawler.tests.test_browser_network_observer -v
Ran 60 tests
OK

python -m unittest autonomous_crawler.tests.test_api_intercept -v
Ran 63 tests
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
- Scrapling absorption is no longer only a transition-adapter track. The major
  backend capability baseline is now CLM-native. Remaining work is production
  hardening: 10k/30k native long-run proof, persistent async client pooling,
  browser profile health scoring, richer run metrics, and more real-site
  calibration.
- Recon selector inference is heuristic and currently strongest for product
  cards and Baidu-style ranking lists.
- `site_spec_draft` detail selectors are drafts when only a list page is known.
- API interception is integrated for direct JSON URLs, API hints, explicit
  GraphQL queries, observed JSON POST APIs, and multi-page pagination
  (page/limit, offset/limit, cursor). It still needs POST-based pagination
  loop support, cross-page deduplication, and richer provider-specific field
  mapping.
- Dynamic/JS-heavy site coverage is proven for local SPA rendering, local
  XHR-backed network observation smoke tests, profile-driven browser smokes,
  real dynamic training, and one public HN Algolia SPA API-replay scenario.
  Hard protected targets still need more real training and profile-health
  calibration.
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

Move from a runnable engineering MVP toward a simpler user-facing crawl tool
and a stronger CLM-native crawler backend:

```text
Easy Mode CLI + Access Layer + Scrapling capability absorption + resumable runner + profile-driven crawl execution + broader dynamic-page training
```

Reference roadmap:

```text
docs/plans/2026-05-12_TOP_CRAWLER_CAPABILITY_ROADMAP.md
```

The last verified real LLM-assisted workflow is:

```text
python clm.py crawl "collect top 30 hot searches" https://top.baidu.com/board?tab=realtime --llm
Final Status: completed, Extracted Data: 30 items, Validation: passed, LLM errors: 0
```

## Next Tasks

Current supervisor priority:

```text
SCRAPLING-HARDEN: prove the native backend baseline at scale and simplify operation.
```

Immediate steps:

1. Run 10k/30k native long-run stress through `SpiderRuntimeProcessor`,
   `CheckpointStore`, async fetch, and profile-driven callbacks.
2. Run real dynamic/ecommerce profile training with browser profile rotation,
   visual evidence, and checkpointed product output.
3. Carry async/proxy/browser-pool metrics into `SpiderRunSummary` and run
   reports.
4. Add persistent async client pooling, DNS reuse tuning, adaptive concurrency,
   browser profile health scoring, and observed API pagination inside
   profile-driven ecommerce runs.

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
      `dev_logs/training/2026-05-08_real_site_training_round1.json`.
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
19. ~~Add observed API pagination/cursor MVP.~~ Done 2026-05-09.
    `api_intercept` supports page/limit, offset/limit, and cursor-based
    pagination with `max_items` guard and `max_pages` cap. Three deterministic
    mock fixtures, 26 new pagination tests, 385 total tests pass after today's
    full verification.
20. ~~Accept ecommerce workflow and QA planning from `spider_text` lessons.~~
    Done 2026-05-09. Workflow and QA docs accepted; scope stays public or
    authorized pages only, with challenge/login handling as diagnosis-only.
21. ~~Run first ecommerce real-site training batch.~~ Done 2026-05-09.
    Five sites exported to `dev_logs/training/2026-05-09_ecommerce_training_sample.xlsx`
    with separate sheets: Shoesme diagnosis-only, Donsje Shopify JSON,
    Clausporto Magento DOM/detail, uvex Magento DOM/detail plus `jsonConfig`
    sizes, and Bosch corporate product category partial records.
22. ~~Run first local large-volume stress test.~~ Done 2026-05-09.
    `run_stress_test_2026_05_09.py` generated 30,000 synthetic ecommerce
    records without public network access. SQLite frontier inserted, claimed,
    and marked all 30,000 URLs done; result storage saved/loaded 30,000 items;
    Excel export completed. Peak memory was about 196 MB. Finding: CLM needs
    checkpointed product storage before real long-running multi-hour crawls.
23. ~~Sync 2026-05-09 worker deliveries and supervisor outputs to GitHub.~~
    Done 2026-05-09. `main` and `origin/main` are at commit `4af3f81`
    (`Advance API pagination and ecommerce training docs`), which includes
    001/002/004 deliveries, acceptance records, ecommerce training outputs,
    stress-test outputs, and updated project documentation.
24. ~~Add generic ecommerce product storage and quality foundation.~~ Done
    2026-05-11. `ProductRecord`, `ProductStore`, product quality validation,
    30,000-row storage tests, long-running ecommerce runbook, and supervisor
    acceptance records added.
25. ~~Add generic resumable batch runner MVP.~~ Done 2026-05-11.
    `BatchRunner` supports bounded frontier claims, pause/resume via
    `max_batches`, success/failure/retry marking, discovered URL insertion,
    checkpoint sinks, and product checkpoint integration. Local smoke:
    25 synthetic records processed as 10 + 15 across two passes.
26. ~~Run two-round real-site training batch.~~ Done 2026-05-11.
    Round 1: 5 sources x 50 records. Round 2: 3 ecommerce sites x 200
    products. Exported `dev_logs/training/2026-05-11_two_round_real_training.json` and
    `.xlsx`. Findings: public sitemap/detail flow can scale to 200 records per
  site, but real runs need incremental checkpointing, fetch fallback for empty
  HTTP 200 responses, and profile-based field extraction. Known gap: Tatuum
  color extraction remains incomplete even though the site exposes color data.
27. ~~Add CLM Easy Mode user entrypoint.~~ Done 2026-05-11.
    `clm.py` now provides `init`, `check`, `crawl`, `smoke`, and `train`.
    README and platform quick starts now use `clm.py` as the primary user path.
    `run_simple.py` remains as a legacy/developer compatibility command.
