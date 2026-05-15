# Scrapling Capability Absorption Record

Date: 2026-05-14

Purpose: track how Scrapling 0.4.8 capabilities are being absorbed into
Crawler-Mind as CLM-native backend capabilities.

This record is intentionally different from a vendor record. The goal is not to
ship a product that merely wraps `scrapling`. The goal is to use Scrapling as a
strong implementation reference, then rebuild or reorganize the useful behavior
inside CLM's own runtime, runner, parser, proxy, browser, session, evidence, and
training systems.

## Current Truth

Current status:

```text
Transition adapters exist.
SCRAPLING-ABSORB-1 initial native fetch/parser slice is accepted.
SCRAPLING-ABSORB-1B native executor routing is accepted.
SCRAPLING-ABSORB-2A native browser runtime shell is accepted.
SCRAPLING-ABSORB-2B dynamic comparison harness is accepted.
SCRAPLING-ABSORB-2B profile comparison follow-up is accepted.
SCRAPLING-ABSORB-2C native browser session lifecycle slice is accepted.
SCRAPLING-ABSORB-2D protected profile evidence and failure classification is accepted.
SCRAPLING-ABSORB-2F native browser session/profile pool is accepted.
SCRAPLING-ABSORB-2H native browser profile rotation and real dynamic training is accepted.
SCRAPLING-ABSORB-1D native adaptive parser is accepted.
SCRAPLING-ABSORB-1E native selector memory is accepted.
SCRAPLING-ABSORB-1F native async fetch pool and long-run stress metrics are accepted.
CAP-3.3 / SCRAPLING-ABSORB-1C proxy health and fetch diagnostics are accepted.
SCRAPLING-ABSORB-3A native spider request/result/event models are accepted.
SCRAPLING-ABSORB-3B native CheckpointStore is accepted.
SCRAPLING-ABSORB-3C native SpiderRuntimeProcessor is accepted.
SCRAPLING-ABSORB-3D native LinkDiscoveryHelper and RobotsPolicyHelper are accepted.
SCRAPLING-ABSORB-3E native spider pause/resume smoke is accepted.
SCRAPLING-ABSORB-3F sitemap/robots long-run integration is accepted.
SCRAPLING-ABSORB-3G site profile and profile-driven ecommerce runner is accepted.
CAP-5.2 VisualRecon Strategy/AntiBot integration is accepted.
Scrapling major backend capability absorption baseline is accepted.
Remaining work is hardening, scale proof, real-site training, and UX simplification.
```

Already accepted:

- `autonomous_crawler/runtime/protocols.py`
- `autonomous_crawler/runtime/models.py`
- `autonomous_crawler/runtime/scrapling_static.py`
- `autonomous_crawler/runtime/scrapling_parser.py`
- `autonomous_crawler/runtime/scrapling_browser.py`
- `autonomous_crawler/runtime/native_static.py`
- `autonomous_crawler/runtime/native_parser.py`
- `autonomous_crawler/runtime/native_browser.py`
- `autonomous_crawler/runtime/native_async.py`
- `autonomous_crawler/runtime/adaptive_parser.py`
- `autonomous_crawler/runtime/browser_pool.py`
- `autonomous_crawler/storage/selector_memory.py`
- `engine="scrapling"` routing in Planner, Strategy, and Executor
- `engine="native"` static runtime routing in Planner, Strategy, and Executor
- `engine="native"` browser runtime routing in Executor
- protected-mode native browser evidence and failure classification
- `autonomous_crawler/runners/spider_models.py`
- `autonomous_crawler/runners/spider_runner.py`
- `autonomous_crawler/runners/site_profile.py`
- `autonomous_crawler/runners/langgraph_processor.py`
- `autonomous_crawler/runners/profile_ecommerce.py`
- `autonomous_crawler/storage/checkpoint_store.py`
- `autonomous_crawler/tools/link_discovery.py`
- `autonomous_crawler/tools/robots_policy.py`
- `autonomous_crawler/tools/visual_recon.py`
- `run_spider_runtime_smoke_2026_05_14.py`
- `run_profile_ecommerce_runner_smoke_2026_05_14.py`
- `run_profile_rotation_smoke_2026_05_14.py`
- `run_real_dynamic_training_2026_05_14.py`
- focused Scrapling runtime tests
- native runtime focused and parity tests
- native-vs-transition comparison helper and example.com smoke evidence
- local SPA native-vs-transition dynamic smoke evidence
- reusable local profile comparison evidence
- local native spider pause/resume smoke evidence
- browser profile rotation and real dynamic training evidence
- profile-driven ecommerce runner smoke evidence
- visual strategy / AntiBotReport evidence integration

Transition adapters are still useful as bridges and benchmarks. They should not
be treated as the final backend architecture.

## Absorption Map

| Upstream Scrapling area | CLM native target | Current state | Next action |
|---|---|---|---|
| `scrapling.fetchers.requests.Fetcher` | `NativeFetchRuntime` | native implementation and executor routing accepted | scale/proxy/transport tuning |
| `scrapling.fetchers.requests.AsyncFetcher` | `NativeAsyncFetchRuntime` | native async runtime, per-domain pool, proxy retry, and metrics accepted | persistent client pooling, DNS reuse, adaptive concurrency |
| `scrapling.parser.Selector` / `Selectors` | `NativeParserRuntime` / `adaptive_parser` / `SelectorMemoryStore` | native parser, adaptive relocation, similar-element discovery, and persistent selector memory accepted | feed memory into product/profile diagnostics |
| `scrapling.fetchers.chrome.DynamicFetcher` | `NativeBrowserRuntime` | native runtime, dynamic comparison, XHR capture, and real dynamic training accepted | more real dynamic training and wait/resource tuning |
| `scrapling.fetchers.stealth_chrome.StealthyFetcher` | protected mode within `NativeBrowserRuntime` | protected profile evidence, profile rotation, and failure classification accepted | profile health scoring and real protected training |
| `scrapling.fetchers.DynamicSession` / `StealthySession` | `SessionProfile`, browser context lifecycle, and `BrowserPoolManager` | persistent context, storage-state export, pool leasing, rotation, and smoke evidence accepted | carry metrics into spider summaries |
| `scrapling.engines.toolbelt.proxy_rotation.ProxyRotator` | `ProxyManager` / `ProxyPoolProvider` | health store, cooldown, redacted trace, retry orchestration, and native fetch diagnostics accepted | provider adapters and long-run domain quality metrics |
| `scrapling.engines.toolbelt.fingerprints` | browser fingerprint/profile pool | initial profile model, runtime/config report, rotation, and protected evidence accepted | health scoring and real-site calibration |
| `scrapling.spiders.scheduler.Scheduler` | `URLFrontier`, `BatchRunner`, and `SpiderRuntimeProcessor` | native models, processor, checkpoint integration, and pause/resume smoke accepted | 10k/30k native long-run stress |
| `scrapling.spiders.checkpoint.CheckpointManager` | `CheckpointStore` / product checkpoint sinks | native SQLite `CheckpointStore` accepted and wired into spider processor smokes | large-run resume and report exports |
| `scrapling.spiders.request.Request` | CLM crawl request/event model | `CrawlRequestEnvelope` accepted and used by spider processor | profile-driven request generation hardening |
| `scrapling.spiders.result.CrawlResult` / `CrawlStats` | CLM runtime result and metrics | `CrawlItemResult`, `SpiderRunSummary`, and checkpoint events accepted | richer async/proxy/browser metrics |
| `scrapling.spiders.robotstxt.RobotsTxtManager` | Recon/profile helper | `RobotsPolicyHelper`, sitemap helper, and rate-limit metadata accepted | real sitemap training |
| `scrapling.spiders.links.LinkExtractor` | link discovery/profile generator | `LinkDiscoveryHelper` accepted and wired into native spider/profile smokes | broaden profile generation |
| `scrapling.core.storage` | CLM storage / artifact stores | CLM has SQLite result, checkpoint, selector memory, proxy health, and product stores | export/report polish |
| `scrapling.cli` / `agent-skill` / MCP ideas | `clm.py` and future CLM MCP | Easy Mode CLI and smoke/train entrypoints partially modeled | future UI/MCP simplification |

## Near-Term Milestones

### SCRAPLING-ABSORB-1: Native Static And Parser

Deliverables:

- `NativeFetchRuntime` - initial implementation complete
- `NativeParserRuntime` - initial implementation complete
- adapter-vs-native parity tests - initial suite complete
- static fixture and real static training comparison

Acceptance:

- no regression in existing `mock://` paths - accepted in full suite
- native path returns CLM-native `RuntimeResponse` and selector results - accepted
- native path matches or exceeds transition adapter on focused tests - accepted
- transition adapter remains available as an oracle until training confidence is high

Acceptance records:

- `docs/team/acceptance/2026-05-14_native_fetch_runtime_ACCEPTED.md`
- `docs/team/acceptance/2026-05-14_native_parser_runtime_ACCEPTED.md`
- `docs/team/acceptance/2026-05-14_native_runtime_parity_ACCEPTED.md`
- `docs/team/acceptance/2026-05-14_native_executor_routing_ACCEPTED.md`

Accepted ABSORB-1B work:

- route explicit native runtime choices through executor/workflow
- compare native and transition outputs with a developer helper
- smoke result on `https://example.com/`: native and transition both HTTP 200,
  same HTML length, same selector hits

Remaining ABSORB-1C work:

- run full built-in static comparison list
- add ecommerce/list-page comparison targets
- decide default runtime preference only after broader training evidence

### SCRAPLING-ABSORB-2: Native Browser, Session, Proxy, XHR

Deliverables:

- native browser runtime behavior aligned with current browser tools - initial
  shell accepted
- session headers/cookies/storage-state policy - request mapping, persistent
  user-data context, storage-state export, pool leasing, and profile rotation
  accepted
- proxy trace and health metrics in runtime events - proxy trace, retry, and
  async metrics accepted
- XHR capture mapped into evidence/artifacts - initial response preview capture
  accepted
- local dynamic comparison harness - accepted
- profile-driven comparison harness - accepted
- protected-mode profile evidence and browser failure classification - accepted
- browser profile rotator and real dynamic training - accepted

Acceptance:

- local mocked runtime contract and executor routing tests - accepted
- runtime events preserved in workflow state - accepted
- proxy/session secrets redacted through runtime model safe dicts - accepted
- local real SPA smoke through native and transition runtime paths - accepted
- profile-driven local static and dynamic evidence comparisons - accepted
- real external SPA/dynamic training run - initial accepted
- persistent user-data context and storage-state artifact test - accepted
- fingerprint report appears in native browser runtime evidence - accepted
- browser failures classify install, timeout, proxy, HTTP block, and
  challenge-like cases - accepted in focused tests
- pool/profile evidence is available for long-running browser work - accepted

Acceptance records:

- `docs/team/acceptance/2026-05-14_native_browser_runtime_ACCEPTED.md`
- `docs/team/acceptance/2026-05-14_native_dynamic_comparison_ACCEPTED.md`
- `docs/team/acceptance/2026-05-14_native_browser_session_lifecycle_ACCEPTED.md`
- `docs/team/acceptance/2026-05-14_native_browser_protected_failure_evidence_ACCEPTED.md`
- `docs/team/acceptance/2026-05-14_native_browser_session_pool_ACCEPTED.md`
- `docs/team/acceptance/2026-05-14_browser_pool_real_smoke_batch_wiring_ACCEPTED.md`
- `docs/team/acceptance/2026-05-14_native_browser_profile_rotation_real_dynamic_ACCEPTED.md`

### SCRAPLING-ABSORB-3: Native Spider And Long Runs

Deliverables:

- native request/result/summary models - accepted
- SQLite checkpoint store for runs, batches, items, request events, and failure
  buckets - accepted
- BatchRunner processor for CLM workflow/runtime requests - accepted
- request/result/event model inspired by Scrapling spiders
- checkpoint store with URL/item/batch resume
- link extractor and robots helper integration - accepted
- deterministic pause/resume smoke with local fixtures - accepted
- sitemap helper integration - accepted
- site profile schema and profile-driven ecommerce runner - accepted

Acceptance:

- deterministic request fingerprint and redaction tests - accepted
- conversion to `RuntimeRequest` and `ItemProcessResult` - accepted
- save/load latest checkpoint, item checkpoint, failure bucket query, and
  run pause/completion tests - accepted
- runtime processor success/failure/browser-mode/checkpoint tests - accepted
- link allow/deny/domain/restrict/classification tests - accepted
- robots respect/record_only/disabled/crawl-delay/request-rate tests - accepted
- recoverable local spider smoke with first-pass pause and resume - accepted
- failure buckets visible in checkpoint store - accepted in local smoke
- profile-driven ecommerce smoke - accepted
- 1,000 / 10,000 / 30,000 synthetic native scale checks - pending
- at least one 600+ real ecommerce training regression through native profile
  runner - pending

Acceptance records:

- `docs/team/acceptance/2026-05-14_native_spider_models_ACCEPTED.md`
- `docs/team/acceptance/2026-05-14_native_checkpoint_store_ACCEPTED.md`
- `docs/team/acceptance/2026-05-14_native_spider_runtime_processor_ACCEPTED.md`
- `docs/team/acceptance/2026-05-14_native_link_robots_helpers_ACCEPTED.md`
- `docs/team/acceptance/2026-05-14_native_spider_pause_resume_smoke_ACCEPTED.md`
- `docs/team/acceptance/2026-05-14_sitemap_robots_longrun_ACCEPTED.md`
- `docs/team/acceptance/2026-05-14_profile_driven_ecommerce_runner_ACCEPTED.md`

### SCRAPLING-ABSORB-4: Evidence, Visual Recon, And Reports

Deliverables:

- unified Strategy evidence report - accepted
- unified AntiBotReport - accepted
- VisualRecon screenshot/OCR evidence model - accepted
- visual evidence integration into Strategy/AntiBotReport - accepted

Acceptance:

- visual degraded/OCR/challenge signals are normalized - accepted
- challenge-like visual findings affect AntiBotReport severity - accepted
- OCR-only text remains low-risk diagnostic evidence - accepted

Acceptance records:

- `docs/team/acceptance/2026-05-14_visual_recon_strategy_antibot_ACCEPTED.md`
- `docs/team/acceptance/2026-05-14_scrapling_absorption_baseline_ACCEPTED.md`

## Closeout Verification

Latest supervisor verification after worker acceptance and VisualRecon
integration:

```text
python -m unittest discover -s autonomous_crawler/tests
Ran 1773 tests in 75.809s
OK (skipped=5)

python -m compileall autonomous_crawler clm.py run_profile_ecommerce_runner_smoke_2026_05_14.py run_profile_rotation_smoke_2026_05_14.py run_real_dynamic_training_2026_05_14.py run_spider_runtime_smoke_2026_05_14.py
OK
```

Current conclusion: the Scrapling-inspired backend absorption baseline is
complete enough to stop treating Scrapling as a separate backend dependency in
planning. CLM now owns the baseline capability modules. The next stage is
evidence-driven hardening: larger runs, real dynamic/ecommerce training,
profile health scoring, async pooling, and simpler operator experience.

## Non-Goals

- Do not stop at `import scrapling`.
- Do not expose Scrapling-specific response objects in CLM state.
- Do not hard-code site rules into runtime modules.
- Do not make users understand Scrapling to use CLM.
- Do not rewrite historical logs; record current truth in active docs and new
  handoffs.
