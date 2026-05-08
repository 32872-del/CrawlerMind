# 2026-05-08 External Crawler Strategy Import Plan

## Purpose

Review mature local crawler projects under `F:\datawork` and decide which
collection strategies should be absorbed into Crawler-Mind without making the
project depend on external folders.

The rule stays the same: CLM should remain portable under `F:\datawork\agent`.
External projects are references and test sources unless a small, generic piece
is intentionally copied or reimplemented inside CLM.

## Sources Reviewed

- `F:\datawork\dtae`
- `F:\datawork\crawler-mcp-server-v4.0`
- `F:\datawork\crawler-mcp-server-v5.0-open`
- `F:\datawork\spider_Uvex`
- `F:\datawork\spider_Zalando`
- `F:\datawork\spider_donsje`

## High-Value Strategies To Absorb

### 1. Access Diagnosis Before Crawl

Source reference:

- `crawler-mcp-server-v4.0/crawler_core/access_diagnostics.py`
- `crawler-mcp-server-v4.0/unified_crawler_server.py`

CLM should add a pre-crawl capability that scores the target before execution:

- compare HTTP, curl_cffi, and browser-rendered HTML quality
- detect JS shell pages
- detect challenge/captcha signals
- identify JSON-LD, `__NEXT_DATA__`, `__NUXT__`, and API-like hints
- produce a recommended execution mode and reason

This should become a first P1 module, because it directly addresses the current
uncertainty around dynamic pages and challenge pages.

### 2. Fetch Best Page / Mode Escalation

Source reference:

- MCP crawler release notes v4.0/v5.2
- `fetch_best_page`
- auto mode escalation: `requests -> curl_cffi -> browser`

CLM currently has separate HTTP and browser paths, but not a mature dispatcher.
The next version should add an executor policy:

- start from deterministic strategy mode
- if HTML is too short, selector misses, JS shell is detected, or challenge is
  suspected, escalate mode
- keep escalation trace in final state
- record per-domain successful mode for later reuse

Do not add Cloudflare bypass. Detect and report challenge pages, then recommend
authorized cookies, public APIs, lower rate limits, or manual review.

### 3. Browser Network Observation

Source reference:

- MCP crawler `observe_browser_network`
- network candidate scoring in `unified_crawler_server.py`

CLM needs an optional browser recon path that can capture XHR/fetch candidates.
This does not mean automatically reverse-engineering every API. It should:

- collect candidate URLs, methods, content types, and small redacted samples
- rank likely data APIs by URL keywords and JSON shape
- let Strategy choose `api_intercept` only when a public, stable candidate is
  visible and safe
- persist the evidence in `recon_report`

This should unlock the missing `api_intercept` path in a controlled way.

### 4. Product Task Model: List -> Detail -> Variant

Source reference:

- `F:\datawork\dtae\01_8a.py`
- `F:\datawork\spider_Zalando\3_xenos.py`
- `F:\datawork\spider_donsje\3_xenos.py`

Mature product crawlers all converge on the same shape:

```text
category/list page -> product detail page -> color/size variant detail
```

CLM should introduce this as an internal task model instead of treating all
extraction as one flat page:

- `list_page`: finds product links and pagination
- `detail_page`: extracts core fields
- `variant_page`: follows color/variant links or embedded variant JSON
- dedupe by canonical URL, SKU, or handle

This belongs in P1 after access diagnosis, because it improves ecommerce
coverage without requiring a frontend first.

### 5. Project-Local HTML Cache

Source reference:

- `F:\datawork\dtae\cache_redis_utils.py`
- `F:\datawork\spider_donsje\3_shoesme_botasaurus.py`

Useful behavior:

- cache by site/task_type/url hash
- read cache before expensive browser fetch
- do not cache challenge pages
- keep cache inside CLM runtime directories

Absorb as a small local cache abstraction. Do not make Redis required yet.

### 6. Frontier / Queue, But Start SQLite-First

Source reference:

- `crawler-mcp-server-v4.0/crawler_core/frontier.py`
- `F:\datawork\dtae` Redis queues

Redis queues are useful later, but a hard Redis dependency would hurt current
portability. CLM should first add a SQLite-backed frontier:

- queued/running/done/failed status
- URL dedupe
- priority, kind, depth, parent_url, payload
- lease token for future multi-worker safety

Redis can become an optional backend only after the SQLite shape is stable.

### 7. Domain Memory

Source reference:

- `crawler-mcp-server-v4.0/crawler_core/domain_memory.py`

Add small per-domain memory:

- last successful mode
- failure streak
- last challenge signal
- preferred impersonation/profile if supported

This gives CLM a real memory path for crawl behavior, separate from employee
memory and project documentation.

### 8. Data Cleaning Helpers

Source reference:

- `dtae/common.py`
- mature spider product scripts

Absorb general helpers only:

- price normalization
- invisible/control character cleanup
- URL completion/canonicalization
- image list normalization
- lightweight HTML description cleanup

Keep site-specific selectors and product field hacks out of core.

## Do Not Absorb Directly

- Hard Redis dependency from `dtae`
- Botasaurus decorators as CLM core architecture
- Site-specific selectors from `01_8a.py`, `3_xenos.py`, or Shoesme scripts
- CSV-first output as the main storage model
- Any CAPTCHA or challenge bypass behavior
- External runtime databases, caches, cookies, or proxy credentials

## Proposed P1 Implementation Order

1. `access_diagnostics` module inside CLM:
   challenge detection, JS-shell detection, structured-data/API hints, and
   human-readable recommendations.
2. `fetch_best_page` executor policy:
   requests/curl_cffi/browser quality scoring and escalation trace.
3. `site_zoo` tests:
   local fixtures for static page, JS shell, JSON-LD, Next/Nuxt data, challenge
   sample, product list, detail page, and variants.
4. `api_intercept` recon skeleton:
   browser network candidate capture with strict redaction and safe ranking.
5. SQLite frontier:
   portable queue state for list/detail/variant workflows.
6. Product task model:
   list/detail/variant state transitions and result aggregation.
7. Domain memory:
   per-domain mode success/failure records.

## Immediate Assignments To Consider

- `LLM-2026-001`: implement CLM `access_diagnostics` with tests and integrate
  challenge code with existing `ANTI_BOT_BLOCKED`.
- `LLM-2026-004`: build `site_zoo` fixture inventory and test plan from
  external examples, without copying private/runtime data.
- Supervisor: design executor escalation state contract before workers touch
  shared executor code.

## Supervisor Decision

Use external crawler projects as strategy references, not as runtime
dependencies. Start P1 with access diagnostics and fetch-mode escalation,
because those directly reduce the current gap between "static page MVP" and
"usable real-world crawler".
