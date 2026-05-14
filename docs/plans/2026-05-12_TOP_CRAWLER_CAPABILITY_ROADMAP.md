# Top Crawler Capability Roadmap

Date: 2026-05-12

Source reference:

```text
C:/Users/Administrator/Downloads/
Original file: "Top crawler developer capability checklist" Chinese markdown,
provided by project owner on 2026-05-12.
```

## Product Positioning

Crawler-Mind should not be only a collection of simple scrapers. The product
goal is to make advanced crawler development simpler, faster, safer, and more
repeatable.

The commercial value is:

```text
turn expert crawler engineering workflows into an agent-assisted product
```

That means CLM must grow beyond static HTML extraction into a system that can
diagnose access problems, choose an execution strategy, inspect browser/API
traffic, manage long-running jobs, preserve evidence, and help developers build
site-specific profiles without hard-coding every site into the core.

## Capability Direction

CLM should support advanced crawler development as a productized workflow. The
capability layer should be strong enough for developers and enterprise teams to
handle difficult public or customer-approved targets without hand-writing a new
framework every time.

Core product direction:

- diagnose Cloudflare/CAPTCHA/login/access-control pages
- support user-provided sessions, cookies, headers, browser profiles, and site
  profiles
- support proxy configuration, rotation, health checks, and provider adapters
- support browser rendering, network observation, screenshots, OCR, and visual
  field detection
- generate reverse-engineering reports for API/JS/signature data flows
- build optional runtime tracks for CAPTCHA/OCR, protected browser profiles,
  JS hook/sandbox analysis, and long-running spider execution
- keep rate limits, retry caps, domain politeness controls, and audit evidence
  as runtime/governance configuration

Usage rules, customer responsibility, release terms, and commercial deployment
policy live in `docs/governance/CRAWLING_GOVERNANCE.md`.

## Capability Gap Matrix

| Capability Area | Top crawler expectation | CLM current state | Gap |
|---|---|---|---|
| HTTP/HTML crawling | robust requests, headers, retries, connection reuse | `httpx` static fetch, basic headers | needs policy, retry/backoff, HTTP/2/TLS options |
| TLS/browser fingerprint | JA3/HTTP2/browser consistency awareness | `curl_cffi` exists through fnspider, not productized | needs access strategy layer |
| Playwright/browser | rendered DOM, screenshots, context control, network observation | browser fetch, screenshots, network observer MVP | needs context manager, storage state, routing, artifacts |
| Scrapy/Selenium | framework-level crawler compatibility | no Scrapy/Selenium integration | likely optional adapters, not core dependency |
| API replay | observe XHR/fetch/GraphQL, replay data APIs | API candidate observation and replay MVP | needs stronger pagination, auth profiles, validation |
| JS reverse engineering | AST, hooks, signatures, Wasm, CDP | not implemented | future expert-assist module |
| Mobile reverse engineering | Frida/Xposed/SSL pinning analysis | not implemented | out of MVP; possible future external integration |
| CAPTCHA/OCR | detect, classify, solve or handoff | detection only; OCR/solver planned | implement VisualRecon and provider interface |
| Proxy pool | config, rotation, health score, per-domain routing | fnspider traces only; no CLM manager | high-priority Access Layer gap |
| Session/cookies | authorized cookie/localStorage profiles | not productized | high-priority Access Layer gap |
| Rate limiting | per-domain politeness, backoff, retry caps | partial runner/frontier basis | high-priority reliability gap |
| Distributed scale | Redis/RabbitMQ/Kafka/K8s/Scrapyd | local SQLite/frontier only | later service phase |
| Data pipeline | schema, quality, storage/export, lineage | SQLite, product store, quality checks, Excel/JSON | needs event log, profiles, richer exports |
| Visual understanding | screenshots -> OCR/layout/selector inference | screenshots only | future VisualRecon module |
| Compliance/governance | risk classification, logs, data handling | safety docs exist | needs explicit access policy engine |

## Target Architecture Layers

### Layer 0: Native Crawler Backend Absorption

Purpose: turn proven crawler-engine capabilities into CLM-owned runtime
modules instead of leaving them as scattered tool calls or third-party wrappers.

Current main source:

```text
F:\datawork\Scrapling-0.4.8
```

Near-term target:

- absorb static fetch behavior into `NativeFetchRuntime`
- absorb parser/adaptive selector behavior into `NativeParserRuntime`
- absorb browser/protected/session/proxy behavior into CLM browser runtime
- absorb spider scheduler/checkpoint/request-result concepts into BatchRunner
- keep transition adapters only as comparison baselines until native modules are
  stronger

Tracking docs:

- `docs/plans/2026-05-14_SCRAPLING_FIRST_RUNTIME_PLAN.md`
- `docs/plans/2026-05-14_SCRAPLING_ABSORPTION_RECORD.md`
- `docs/runbooks/SCRAPLING_FIRST_RUNTIME.md`

### Layer 1: Easy Mode

Purpose: make first use simple.

Status: current MVP.

Key interface:

```text
python clm.py init
python clm.py check
python clm.py crawl ...
python clm.py smoke --kind runner
```

Next improvements:

- better error messages
- richer setup report
- config validation command
- concise output summary

### Layer 2: Access Layer

Purpose: make real-world access strategy explicit and reusable.

Modules to add:

- `ProxyManager`
- `SessionProfile`
- `RateLimitPolicy`
- `BrowserContextManager`
- `ChallengeDetector`
- `AccessStrategyReport`
- `ManualHandoff`

This is the most important next layer if CLM is expected to handle difficult
public websites.

### Layer 3: Recon And API Intelligence

Purpose: discover where data flows.

Modules to improve:

- browser network observer
- API candidate scoring
- GraphQL detection
- pagination inference
- JSON shape inference
- public/authorized replay policy
- request/response artifact storage

### Layer 4: Profile-Driven Extraction

Purpose: keep site-specific knowledge outside the core engine.

Profiles should contain:

- selectors
- API hints
- pagination strategy
- browser wait rules
- session requirements
- quality overrides
- known pitfalls

Core agent behavior should stay generic.

### Layer 5: Long-Running Execution

Purpose: support thousands to millions of records safely.

Modules to add/improve:

- runner retry limits
- progress event table
- checkpoint sinks
- per-domain concurrency limits
- pause/resume controls
- failure buckets
- export streaming

### Layer 6: Visual And Reverse-Engineering Assist

Purpose: help expert crawler developers with hard sites.

Initial safe version:

- screenshot capture
- OCR text extraction
- visual repeated-card detection
- visual field-to-DOM alignment
- JS asset inventory
- signature parameter detection
- generated reverse-engineering notes

Later optional/expert integrations:

- AST analysis
- CDP hooks
- Wasm inventory
- mitmproxy import
- authorized CAPTCHA provider plugin

## Priority Plan

### P0: Close Current Easy Mode

Goal: make CLM credible to first-time users.

- resolve conditional CLI test acceptance
- commit Easy Mode and docs
- make `clm.py check` more informative
- keep `run_simple.py` as legacy/developer path

### P1: Access Layer MVP

Goal: stop treating real-world access problems as random failures.

Deliverables:

- `access_policy.py`: strategy classification and governance hooks
- `proxy_manager.py`: config model, disabled default, health check hooks
- `session_profile.py`: cookies/headers/storage-state model
- `rate_limit_policy.py`: per-domain delay, retry cap, backoff
- `challenge_detector.py`: structured Cloudflare/CAPTCHA/login/429 detection
- docs/runbook for sessions, proxies, and runtime profiles

Acceptance:

- redacted proxy/session values in repo outputs
- CAPTCHA/OCR provider track designed as a plug-in capability
- deterministic tests for proxy/session/rate-limit decisions
- crawl final state records access decisions

### P2: Browser Context And Network Intelligence

Goal: make Playwright a first-class advanced crawler tool.

Deliverables:

- browser context config: UA, viewport, locale, timezone, storage_state
- optional screenshot artifact per failure/challenge
- network observation artifacts with redacted headers
- stronger API replay validation
- POST pagination loop support

Acceptance:

- local SPA tests
- one public API-backed SPA training target
- auth/profile handling documented in governance and runtime config

### P3: Profile System

Goal: let CLM learn site-specific strategies without polluting core logic.

Deliverables:

- `profiles/` directory
- profile schema
- profile loader
- profile application in Recon/Strategy/Executor
- Tatuum color extraction profile as first concrete training case

Acceptance:

- Tatuum color issue fixed through profile/fixture, not hard-coded core logic
- profile can override selectors and quality expectations

### P4: VisualRecon

Goal: introduce OCR and visual reasoning for hard pages.

Deliverables:

- screenshot artifact catalog
- OCR adapter interface
- visual repeated region detection MVP
- DOM mapping report

Acceptance:

- OCR/layout extraction helps fields or diagnostics on controlled fixtures
- CAPTCHA/OCR provider interface has a clear plug-in contract

### P5: Expert Reverse-Engineering Assist

Goal: assist developers with JS/API analysis and turn repeatable reverse
engineering work into CLM-supported workflows.

Deliverables:

- JS asset inventory
- API signature parameter detector
- request-diff tool
- optional AST parser integration
- reverse-engineering report template

Acceptance:

- reports evidence and hypotheses
- supports profile generation, hook planning, and request-building hypotheses

## Strategic Decision

CLM should compete by making expert crawler work systematic:

```text
diagnose -> plan -> execute -> observe -> profile -> validate -> resume
```

The product should not promise magic access to every blocked website. It should
promise that a crawler developer can understand and solve difficult collection
problems faster, with safer defaults, better evidence, and reusable profiles.

That is a credible path to a commercial crawler agent.

