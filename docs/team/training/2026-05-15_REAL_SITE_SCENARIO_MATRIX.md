# Real-Site Scenario Matrix

Date: 2026-05-15

Purpose: convert the owner-provided real-site training list into a clean,
long-lived CLM training matrix. The original source file has encoding damage in
this workspace, so this document keeps the usable scenario structure in the
team workflow.

## Training Principle

Use real websites to harden generic CLM capabilities. Do not bake site-specific
rules into runtime modules. If a site needs special selectors, API hints,
pagination, sessions, or waits, put those details into profiles, fixtures, or
training artifacts.

Each round should produce:

- code or profile changes when a reusable capability is missing
- deterministic fixture tests for the pattern
- a smoke/training script when useful
- JSON evidence under `dev_logs/training/` or `dev_logs/smoke/`
- handoff notes for later supervisor acceptance

## Scenario Families

| Scenario | Representative targets from source list | CLM capability under training | Current maturity | Next use |
|---|---|---|---|---|
| Public JSON / simple API | JSONPlaceholder, Reddit `.json`, DummyJSON, GitHub issues | API replay, schema normalization, result storage | proven | regression targets |
| GraphQL | Countries GraphQL, AniList, GitHub GraphQL docs, Shopify Storefront docs | GraphQL request shape, cursor pagination, nested field extraction | initial/proven on simple cases | public GraphQL fixture and profile training |
| Static / SSR | Douban Top250, React docs, Vue examples, Next/Nuxt docs, Shopify Hydrogen docs | HTML recon, SSR detection, selector inference | proven on simple cases | profile generation and selector-memory training |
| SPA / browser rendered | Vue examples, React demos, PayPal, Trello, HN Algolia-like flows | browser render, network observation, XHR capture, wait policy | initial/proven locally | real dynamic smoke and profile health training |
| Infinite scroll | Pinterest, Etsy search, public scroll demos, brand sites with lazy loading | scroll loop, XHR pagination, cursor/bookmark discovery | planned/initial | browser trainer for scroll evidence |
| Virtualized list | React Virtuoso, TanStack Virtual, React Window, Virtua demos | viewport-driven extraction, scroll position recovery, DOM recycling | planned | fixture + browser extraction harness |
| Mobile-first / PWA | SHEIN, Flipkart, AliExpress, Target, PWA demos | mobile UA/viewport/touch profile, service worker/cache evidence | planned | browser profile and access config training |
| Protected/challenge diagnosis | Scrapfly fingerprint page, ScrapingCourse Cloudflare page, DataDome/PerimeterX sites | fingerprint report, challenge classification, visual evidence, profile health | initial diagnosis | diagnostic training, not extraction success metric |
| Login/session-required | Taobao, JD, Costco, Sam's Club, Netflix | user-provided session profile, storage-state lifecycle, authorized profile reuse | initial | session-profile fixtures and manual profile loading |
| Ecommerce profile | Tatuum, The Sting, BalticBHP, Shoesme, Shopify/Magento examples | site profile, list/detail/API pagination, product quality | initial/proven samples | 600+ native profile regression |

## Second Hardening Round Assignments

### LLM-2026-001: Browser Scenario Trainer

Focus:

- Infinite scroll
- Virtualized list
- SPA/browser-rendered targets
- Mobile browser profile signals

Expected output:

- reusable browser training harness
- at least three deterministic local fixtures representing scroll,
  virtualization, and mobile viewport behavior
- optional real-site smoke evidence from safe public demos
- profile-health evidence connected to browser training results

### LLM-2026-002: API / GraphQL / Reverse Evidence Trainer

Focus:

- GraphQL request shape and cursor pagination
- observed XHR/API pagination evidence
- JS signature/encryption clues as replay blockers
- async/backpressure metrics during API training

Expected output:

- GraphQL fixture profile and tests
- API pagination stress/training script
- reverse-engineering evidence report improvements where needed
- async/proxy/backpressure metrics in training output

### LLM-2026-004: Profile Library And Ecommerce Training

Focus:

- reusable `SiteProfile` examples
- DOM list/detail profile
- API pagination profile
- ecommerce fields and quality reports

Expected output:

- profile examples under tests/fixtures or docs examples
- profile-driven 50+ item fixture training
- runbook update for writing profiles
- profile runner smoke/training output

## Supervisor Mainline

LLM-2026-000 owns:

- keep this scenario matrix updated
- build one supervisor-level training round manifest
- delay formal acceptance until round 1 and round 2 worker outputs are both
  available
- run focused and full verification after integration
- update `TEAM_BOARD`, `PROJECT_STATUS`, and capability matrix after acceptance

## Acceptance Metrics For The Combined Round

Minimum combined acceptance:

- browser fixtures prove scroll/virtual/mobile behavior without external
  dependency
- API/GraphQL fixtures prove pagination and replay evidence
- profile ecommerce runner can produce 50+ product-like records from fixtures
- native long-run path can still pass focused stress tests
- evidence reports explain failures instead of losing context
- full test suite passes after integration

Stretch acceptance:

- one real public dynamic target produces useful evidence
- one real public GraphQL/API target produces 50+ records
- one real ecommerce-like profile run produces 50+ records
- all generated artifacts are stored under the existing `dev_logs/` structure

