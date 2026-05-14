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
Full CLM-native absorption is not complete.
```

Already accepted:

- `autonomous_crawler/runtime/protocols.py`
- `autonomous_crawler/runtime/models.py`
- `autonomous_crawler/runtime/scrapling_static.py`
- `autonomous_crawler/runtime/scrapling_parser.py`
- `autonomous_crawler/runtime/scrapling_browser.py`
- `engine="scrapling"` routing in Planner, Strategy, and Executor
- focused Scrapling runtime tests

Those files are useful as bridges and benchmarks. They should not be treated as
the final backend architecture.

## Absorption Map

| Upstream Scrapling area | CLM native target | Current state | Next action |
|---|---|---|---|
| `scrapling.fetchers.requests.Fetcher` | `NativeFetchRuntime` | transition adapter exists | implement CLM-owned fetch runtime with curl_cffi/httpx strategy, normalized events, retries, headers, cookies, proxy |
| `scrapling.fetchers.requests.AsyncFetcher` | async fetch pool / BatchRunner processor | not absorbed | add async runtime, per-domain concurrency, connection reuse, retry/backoff metrics |
| `scrapling.parser.Selector` / `Selectors` | `NativeParserRuntime` | transition adapter exists | implement lxml/cssselect parser, repeated node detection, field selector scoring, adaptive fallback selectors |
| `scrapling.fetchers.chrome.DynamicFetcher` | `NativeBrowserRuntime` | transition adapter contract exists | absorb wait policy, resource control, XHR capture, artifacts, browser events |
| `scrapling.fetchers.stealth_chrome.StealthyFetcher` | `ProtectedBrowserRuntime` | transition adapter contract exists | absorb protected browser profile, fingerprint consistency evidence, runtime failure classification |
| `scrapling.fetchers.DynamicSession` / `StealthySession` | `SessionProfile` and browser context lifecycle | partially modeled | add session lifecycle, storage state, page reuse policy, cross-request continuity |
| `scrapling.engines.toolbelt.proxy_rotation.ProxyRotator` | `ProxyManager` / `ProxyPoolProvider` | partially modeled | add real provider adapter, health scoring, cooldown, domain sticky routing, BatchRunner metrics |
| `scrapling.engines.toolbelt.fingerprints` | browser fingerprint profile pool | partially modeled | build profile pool, runtime/config comparison, rotation policy |
| `scrapling.spiders.scheduler.Scheduler` | `URLFrontier` and BatchRunner queue policy | CLM has separate frontier | align request claim, priority, failure buckets, per-domain policy |
| `scrapling.spiders.checkpoint.CheckpointManager` | `CheckpointStore` / product checkpoint sinks | CLM has runner checkpoint basics | add URL/item/batch checkpoint recovery and resume tests |
| `scrapling.spiders.request.Request` | CLM crawl request/event model | not aligned | normalize request identity, fingerprint, method/body/header/cookie serialization |
| `scrapling.spiders.result.CrawlResult` / `CrawlStats` | CLM runtime result and metrics | not aligned | add item/event counters, status buckets, export summaries |
| `scrapling.spiders.robotstxt.RobotsTxtManager` | Recon/profile helper | not absorbed | add robots/sitemap evidence and profile hints |
| `scrapling.spiders.links.LinkExtractor` | link discovery/profile generator | not absorbed | add link filters, allow/deny patterns, category/detail URL classification |
| `scrapling.core.storage` | CLM storage / artifact stores | CLM has SQLite stores | evaluate useful cache/checkpoint ideas, keep CLM storage shape |
| `scrapling.cli` / `agent-skill` / MCP ideas | `clm.py` and future CLM MCP | partially modeled | convert diagnostics, training, profile generation into CLM commands/tools |

## Near-Term Milestones

### SCRAPLING-ABSORB-1: Native Static And Parser

Deliverables:

- `NativeFetchRuntime`
- `NativeParserRuntime`
- adapter-vs-native parity tests
- static fixture and real static training comparison

Acceptance:

- no regression in existing `mock://` paths
- native path returns CLM-native `RuntimeResponse` and selector results
- native path matches or exceeds transition adapter on focused tests
- transition adapter remains available as an oracle until training confidence is high

### SCRAPLING-ABSORB-2: Native Browser, Session, Proxy, XHR

Deliverables:

- native browser runtime behavior aligned with current browser tools
- session lifecycle and storage-state policy
- proxy trace and health metrics in runtime events
- XHR capture mapped into evidence/artifacts

Acceptance:

- local SPA smoke
- real SPA/dynamic training run
- runtime events preserved in workflow state
- proxy/session secrets redacted

### SCRAPLING-ABSORB-3: Native Spider And Long Runs

Deliverables:

- BatchRunner processor for CLM workflow/runtime requests
- request/result/event model inspired by Scrapling spiders
- checkpoint store with URL/item/batch resume
- link extractor and robots/sitemap helper integration

Acceptance:

- recoverable long task
- failure buckets visible
- 1,000 / 10,000 / 30,000 synthetic scale checks
- at least one 600+ real ecommerce training regression

## Non-Goals

- Do not stop at `import scrapling`.
- Do not expose Scrapling-specific response objects in CLM state.
- Do not hard-code site rules into runtime modules.
- Do not make users understand Scrapling to use CLM.
- Do not rewrite historical logs; record current truth in active docs and new
  handoffs.

