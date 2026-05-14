# Scrapling Capability Absorption Runbook

Date: 2026-05-14

Audience: CLM developers, runtime adapter workers, documentation reviewers, and
future maintainers.

## Purpose

CLM is absorbing Scrapling 0.4.8 as an engineering reference for a stronger
native crawler backend. This is not a long-term plan to wrap the `scrapling`
package and expose it as a CLM feature. It is a plan to study, test, and
rebuild the useful capabilities inside CLM-owned runtime modules.

The product goal is:

```text
CLM = agent decision layer + runtime protocol + evidence/training/long-run system
Scrapling = capability reference and temporary adapter benchmark
Final backend = CLM-native crawler runtime
```

CLM owns planning, recon, strategy, validation, evidence reports, training
records, long-running job control, result storage, and product governance. The
Scrapling adapters that exist today are transition bridges: they prove the
runtime protocol shape and provide a benchmark while the capabilities are
reimplemented or reorganized as CLM-native backend pieces.

## Why Scrapling Capability Absorption

The current CLM runtime already has useful pieces: `httpx` fetch, browser
fallback, fnspider integration, network observation, access diagnostics, result
storage, and batch-runner foundations. The gap is that advanced runtime
behavior is still spread across several tools.

Scrapling 0.4.8 provides a mature external reference for:

- static HTTP fetch and parser ergonomics
- adaptive selector and DOM querying patterns
- browser and protected-environment execution concepts
- session continuity and browser identity concepts
- proxy rotation concepts
- spider scheduling and checkpoint-oriented crawling concepts
- CLI/MCP-oriented developer workflow ideas

Using it as a capability source should reduce blind reinvention while still
letting CLM become its own product-grade backend.

## Absorption Principle

The desired end state is not:

```text
CLM -> import scrapling -> call Fetcher/DynamicFetcher/Spider
```

The desired end state is:

```text
CLM Agent -> CLM Runtime Protocol -> CLM Native Backend
```

Scrapling informs the backend design, tests, and behavior targets. The current
`ScraplingStaticRuntime`, `ScraplingParserRuntime`, and
`ScraplingBrowserRuntime` adapters are allowed only as transition paths and
comparison baselines.

## Runtime Protocol

All crawler execution should go through CLM runtime protocols.

Allowed direction:

- Strategy selects a runtime mode or engine.
- Executor calls a CLM runtime adapter.
- The adapter or native runtime maps CLM request models to executable backend
  behavior.
- The adapter returns CLM response models, artifacts, events, and traces.

Avoid:

- hard-coding site selectors in core runtime code
- importing Scrapling implementation classes directly inside Planner, Recon,
  Strategy, Extractor, Validator, or site-specific business logic
- treating "the scrapling package is installed" as acceptance for CLM backend
  capability
- letting a Scrapling-specific response shape leak into stored CLM state
- replacing evidence reports with opaque runtime success/failure strings
- mixing customer/site-specific rules into reusable runtime modules

## Runtime Protocol Shape

The near-term protocol should keep these interfaces stable even if adapters
change:

```text
FetchRuntime
BrowserRuntime
ParserRuntime
SpiderRuntime
ProxyRuntime
SessionRuntime
```

Core request fields:

```text
url
method
headers
cookies
params
body/json
mode: static | dynamic | protected | spider
selector_config
browser_config
session_profile
proxy_config
capture_xhr
wait_selector
wait_until
timeout_ms
max_items
```

Core response fields:

```text
ok
final_url
status_code
headers
cookies
body/html/text
items
captured_xhr
artifacts
proxy_trace
runtime_events
error
```

The transition adapter may use Scrapling internally, but stored and audited
outputs must remain CLM-native. New capability work should prefer native CLM
modules once the behavior has been understood.

## Absorption Matrix

| Scrapling capability | CLM-native target | Current status | Acceptance target |
|---|---|---|---|
| `Fetcher` static HTTP | `NativeFetchRuntime` | transition adapter | CLM-owned fetch runtime with headers, cookies, proxy, timeout, body, status, events |
| `AsyncFetcher` | async fetch pool / BatchRunner processor | not absorbed | concurrent fetch runtime with per-domain caps, retries, backpressure, metrics |
| `Selector` / `Selectors` | `NativeParserRuntime` | transition adapter | lxml/cssselect parser, candidate selectors, repeated node scoring, field extraction evidence |
| `DynamicFetcher` | `NativeBrowserRuntime` | transition adapter contract | browser render, wait policy, artifact manifest, XHR capture, runtime events |
| `StealthyFetcher` / protected concepts | `ProtectedBrowserRuntime` | transition adapter contract | browser profile, fingerprint consistency, access evidence, real training cases |
| `ProxyRotator` | `ProxyManager` / `ProxyPoolProvider` | partial CLM model exists | rotation, health score, cooldown, domain sticky, BatchRunner metrics |
| sessions | `SessionProfile` / `BrowserContextConfig` | partial CLM model exists | cookie/header/storage-state lifecycle and cross-request continuity |
| spider scheduler | `BatchRunner` / `URLFrontier` | CLM runner exists, not aligned to Scrapling concepts | request/result/event model, failure buckets, streaming items |
| checkpoint | `CheckpointStore` / product checkpoint sinks | partial CLM runner checkpoint exists | URL/item/batch checkpoint recovery and stress tests |
| robots/link extraction | Recon/profile helpers | not absorbed | robots/sitemap/link filters feeding profile and frontier generation |
| CLI/MCP workflow | `clm.py` / future CLM MCP | partial CLI exists | diagnostics, training, profile generation, runtime reports |

## Capability Tracks

### Static Fetch And Parser

Maturity target: Phase 1 MVP.

Expected behavior:

- `engine="scrapling"` can execute public static pages through a CLM transition
  adapter.
- Parser output maps into CLM extraction fields and `engine_result`.
- Mock fixtures remain deterministic and do not depend on Scrapling.
- Next target is a CLM-native fetch/parser backend that matches or exceeds the
  adapter behavior on training fixtures.

Keep separate:

- no site-specific rules in runtime core
- existing `httpx` and fnspider paths remain available as fallback or
  specialized engines

### Browser Runtime

Maturity target: Phase 2.

Expected behavior:

- dynamic pages can be routed through a browser runtime adapter
- browser identity, wait policy, screenshots, artifacts, and XHR capture map
  into CLM runtime events and evidence
- browser/session/proxy artifacts map into CLM runtime responses and reports
- sensitive runtime values are redacted in persisted evidence

### Protected Runtime

Maturity target: Phase 2.

Expected behavior:

- protected-environment runtime is represented as an explicit mode with
  inspectable inputs, runtime events, and result evidence
- Strategy can route difficult pages to Scrapling dynamic/protected runtime
  when evidence says a stronger browser backend is needed
- CAPTCHA/OCR, visual recognition, and provider integrations are modeled as
  future plug-in tracks instead of being hidden inside static fetch

### Spider And Long-Running Runtime

Maturity target: Phase 3.

Expected behavior:

- Scrapling spider scheduling concepts are mapped into CLM BatchRunner,
  frontier, checkpoint, item events, retry buckets, and export paths
- pause/resume and failure recovery remain CLM-owned
- 1,000 / 10,000 / 30,000 item training runs can compare runtime behavior

Keep separate:

- no replacement of CLM result store and audit trail with a vendor-specific
  state format
- concurrency, retry, and checkpoint policy stay owned by CLM BatchRunner

## Phase Plan

### Phase 1: Static And Parser Runtime

Deliverables:

- CLM runtime protocol models
- Scrapling static fetch transition adapter
- Scrapling parser transition adapter
- executor engine routing for `engine="scrapling"`
- local fixture tests and mock preservation
- native fetch/parser design targets

Acceptance:

- compile and unit tests remain green
- `mock://` paths stay deterministic
- static HTML extraction returns CLM-native `engine_result`
- adapter output includes observable events and error reasons
- a follow-up task exists to replace adapter-backed behavior with CLM-native
  implementations

### Phase 2: Browser, Session, Proxy, XHR

Deliverables:

- dynamic browser adapter
- protected runtime adapter contract
- browser identity config mapping
- session continuity mapping
- XHR capture and artifact manifest mapping
- proxy rotator mapping with redaction

Acceptance:

- local SPA and at least one authorized real-site smoke
- runtime events are persisted or carried in workflow state
- proxy credentials do not appear in logs, events, or stored results
- Strategy can route dynamic pages to the Scrapling browser runtime through
  `engine="scrapling"` plus browser/protected runtime mode evidence

### Phase 3: Spider And Long Runs

Deliverables:

- CLM-native spider runtime inspired by Scrapling scheduler/checkpoint concepts
- checkpoint / pause / resume mapping
- streaming item event model
- blocked retry event model
- per-domain concurrency model
- BatchRunner integration

Acceptance:

- recoverable long task
- failure buckets are inspectable
- Excel/JSON/SQLite export remains stable
- ecommerce training run can be replayed without core site-specific code

## Source Tracking And License Notice

Scrapling 0.4.8 is licensed under BSD 3-Clause according to:

```text
F:\datawork\Scrapling-0.4.8\LICENSE
F:\datawork\Scrapling-0.4.8\pyproject.toml
```

Observed source metadata:

```text
package: scrapling
version: 0.4.8
license: BSD 3-Clause
author/maintainer: Karim Shoair
repository: https://github.com/D4Vinci/Scrapling
documentation: https://scrapling.readthedocs.io/en/latest/
```

CLM should keep a project-local source tracking record before copying,
adapting, or reimplementing Scrapling-informed behavior. The record should
include:

- upstream package name and version
- upstream repository URL
- upstream license text or license file path
- exact source acquisition date
- copied files, adapted files, or APIs referenced
- local adapter files that depend on the source
- rationale for native absorption instead of direct dependency use
- update policy and owner
- license notice location for source and binary redistribution

Recommended archive location:

```text
docs/plans/2026-05-14_SCRAPLING_SOURCE_TRACKING_PLAN.md
docs/vendor/scrapling/NOTICE.md        # future, if vendor docs are allowed
docs/vendor/scrapling/SOURCE_RECORD.md # future, if vendor docs are allowed
```

If CLM redistributes copied Scrapling source or binary artifacts, preserve the
BSD 3-Clause copyright notice, conditions, and disclaimer in the distributed
documentation or materials. If CLM only reimplements behavior using the same
low-level dependencies and public ideas, keep the source record as engineering
provenance for maintainers.

## Documentation Rules

- Describe Scrapling work as capability absorption toward a CLM-native backend,
  not as a magic crawler mode or permanent third-party wrapper.
- Put legal/compliance/deployment rules in `docs/governance/`, not in runtime
  capability modules.
- Keep runtime docs focused on capability, protocol shape, evidence, and
  training acceptance.
- Keep site profiles, selectors, API hints, and quality overrides outside core
  runtime code.
- Update README only after the adapter path is usable for new users.
- Update TEAM_BOARD only through a supervisor/board task, not from this audit.

## Related Documents

- Runtime plan: `docs/plans/2026-05-14_SCRAPLING_FIRST_RUNTIME_PLAN.md`
- Source tracking plan:
  `docs/plans/2026-05-14_SCRAPLING_SOURCE_TRACKING_PLAN.md`
- Capability roadmap:
  `docs/plans/2026-05-12_TOP_CRAWLER_CAPABILITY_ROADMAP.md`
- Capability matrix:
  `docs/plans/2026-05-12_CAPABILITY_IMPLEMENTATION_MATRIX.md`
- Access Layer runbook: `docs/runbooks/ACCESS_LAYER.md`
- Advanced diagnostics runbook: `docs/runbooks/ADVANCED_DIAGNOSTICS.md`
