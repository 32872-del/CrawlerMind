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

## Safety Boundary

CLM should support authorized advanced crawling. It should not become a default
black-box bypass or abuse tool.

Allowed product direction:

- diagnose Cloudflare/CAPTCHA/login/access-control pages
- support user-provided authorized sessions and cookies
- support proxy configuration and health checks
- support browser rendering, network observation, screenshots, OCR, and visual
  field detection
- generate reverse-engineering reports for public/authorized data flows
- keep rate limits, retry caps, and domain politeness controls

Not a default product direction:

- automatic CAPTCHA cracking as the standard path
- stealing or replaying private authenticated tokens
- bypassing login or paywalls without authorization
- hostile Cloudflare challenge circumvention
- credential/proxy black-box abuse

If a feature can cross the line, implement it as diagnosis, manual handoff, or
authorized-plugin integration with explicit user configuration and logs.

## Capability Gap Matrix

| Capability Area | Top crawler expectation | CLM current state | Gap |
|---|---|---|---|
| HTTP/HTML crawling | robust requests, headers, retries, connection reuse | `httpx` static fetch, basic headers | needs policy, retry/backoff, HTTP/2/TLS options |
| TLS/browser fingerprint | JA3/HTTP2/browser consistency awareness | `curl_cffi` exists through fnspider, not productized | needs access strategy layer |
| Playwright/browser | rendered DOM, screenshots, context control, network observation | browser fetch, screenshots, network observer MVP | needs context manager, storage state, routing, artifacts |
| Scrapy/Selenium | framework-level crawler compatibility | no Scrapy/Selenium integration | likely optional adapters, not core dependency |
| API replay | observe XHR/fetch/GraphQL, replay public data APIs | API candidate observation and replay MVP | needs stronger pagination, auth boundary, profiles |
| JS reverse engineering | AST, hooks, signatures, Wasm, CDP | not implemented | future expert-assist module |
| Mobile reverse engineering | Frida/Xposed/SSL pinning analysis | not implemented | out of MVP; possible future external integration |
| CAPTCHA/OCR | detect, classify, solve or handoff | detect only; no OCR/solver | implement visual diagnosis/manual handoff first |
| Proxy pool | config, rotation, health score, per-domain routing | fnspider traces only; no CLM manager | high-priority Access Layer gap |
| Session/cookies | authorized cookie/localStorage profiles | not productized | high-priority Access Layer gap |
| Rate limiting | per-domain politeness, backoff, retry caps | partial runner/frontier basis | high-priority reliability gap |
| Distributed scale | Redis/RabbitMQ/Kafka/K8s/Scrapyd | local SQLite/frontier only | later service phase |
| Data pipeline | schema, quality, storage/export, lineage | SQLite, product store, quality checks, Excel/JSON | needs event log, profiles, richer exports |
| Visual understanding | screenshots -> OCR/layout/selector inference | screenshots only | future VisualRecon module |
| Compliance/governance | risk classification, logs, data handling | safety docs exist | needs explicit access policy engine |

## Target Architecture Layers

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

- `access_policy.py`: safe boundaries and risk classification
- `proxy_manager.py`: config model, disabled default, health check hooks
- `session_profile.py`: authorized cookies/headers/storage-state model
- `rate_limit_policy.py`: per-domain delay, retry cap, backoff
- `challenge_detector.py`: structured Cloudflare/CAPTCHA/login/429 detection
- docs/runbook for authorized sessions and proxies

Acceptance:

- no real proxy credentials in repo
- no CAPTCHA solving by default
- deterministic tests for proxy/session/rate-limit decisions
- crawl final state records access decisions

### P2: Browser Context And Network Intelligence

Goal: make Playwright a first-class advanced crawler tool.

Deliverables:

- browser context config: UA, viewport, locale, timezone, storage_state
- optional screenshot artifact per failure/challenge
- network observation artifacts with redacted headers
- stronger API replay guardrails
- POST pagination loop support where safe

Acceptance:

- local SPA tests
- one public API-backed SPA training target
- no private token replay

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

- no CAPTCHA solving by default
- visual extraction helps fields or diagnostics on controlled fixtures

### P5: Expert Reverse-Engineering Assist

Goal: assist developers with JS/API analysis while preserving legal/ethical
boundaries.

Deliverables:

- JS asset inventory
- API signature parameter detector
- request-diff tool
- optional AST parser integration
- reverse-engineering report template

Acceptance:

- reports evidence and hypotheses
- does not automatically bypass access controls

## Strategic Decision

CLM should compete by making expert crawler work systematic:

```text
diagnose -> plan -> execute -> observe -> profile -> validate -> resume
```

The product should not promise magic access to every blocked website. It should
promise that a crawler developer can understand and solve difficult collection
problems faster, with safer defaults, better evidence, and reusable profiles.

That is a credible path to a commercial crawler agent.

