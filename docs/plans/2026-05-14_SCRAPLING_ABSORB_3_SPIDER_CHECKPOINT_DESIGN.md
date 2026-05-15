# SCRAPLING-ABSORB-3: Spider / Checkpoint Native Design Prep

Date: 2026-05-14

Owner: LLM-2026-004

Status: design prep

## Goal

This document prepares the CLM-native long-running spider/checkpoint backend.
The goal is not to call Scrapling spider classes as a dependency. The goal is to
absorb the useful ideas from Scrapling 0.4.8 and reshape them around CLM's own
BatchRunner, URLFrontier, runtime event model, checkpoint storage, product
record checkpointing, evidence chain, and training workflow.

Target outcome:

```text
Scrapling spider ideas -> CLM-native SpiderRuntime / BatchRunner backend
```

Non-goal:

```text
CLM SpiderRuntime -> import scrapling.spiders.Scheduler / CheckpointManager
```

## Source Read

Read upstream Scrapling files:

- `scrapling/spiders/scheduler.py`
- `scrapling/spiders/checkpoint.py`
- `scrapling/spiders/request.py`
- `scrapling/spiders/result.py`
- `scrapling/spiders/links.py`
- `scrapling/spiders/robotstxt.py`

Read CLM files:

- `autonomous_crawler/runners/batch_runner.py`
- `autonomous_crawler/runners/__init__.py`
- `autonomous_crawler/storage/frontier.py`
- `autonomous_crawler/runtime/models.py`
- `autonomous_crawler/runtime/protocols.py`
- `autonomous_crawler/models/product.py`

## Scrapling Spider Ideas To Absorb

### Scheduler

Scrapling `Scheduler` provides:

- async priority queue
- higher priority first by storing negative priority
- stable FIFO tie-breaker with `itertools.count`
- URL/request dedupe through request fingerprint
- `dont_filter` escape hatch
- `snapshot()` returning pending requests and seen fingerprints
- `restore()` rebuilding queue state from checkpoint data

CLM absorption:

- keep CLM's SQLite `URLFrontier` as the persistent queue
- add priority/FIFO lease semantics where needed instead of in-memory heap only
- use request fingerprints for request identity, but persist them as explicit
  columns or payload fields
- add snapshot/resume semantics through `CheckpointStore`, not pickle
- preserve `dont_filter` as an explicit request option only for controlled
  discovery paths

### Checkpoint

Scrapling `CheckpointManager` provides:

- checkpoint interval
- atomic write using temp file then rename
- pending requests + seen fingerprint snapshot
- load-or-start-fresh behavior on corrupt/missing checkpoint
- cleanup after successful completion

CLM absorption:

- use SQLite/JSONL checkpoint storage instead of pickle
- checkpoint URL state, item state, run summary, failure buckets, and runtime
  events separately
- keep atomic batch commits
- keep corrupt checkpoint as recoverable evidence rather than silent loss
- support pause/resume and worker restart as first-class operations

### Request

Scrapling `Request` provides:

- URL, session id, callback, priority, `dont_filter`, meta, retry count
- canonicalized fingerprint from method, URL, body, optional kwargs/headers
- domain extraction
- copy support
- pickle support by storing callback name instead of callable

CLM absorption:

- callbacks should become `task_kind`, `processor_name`, or profile route names
  rather than Python callables
- fingerprint should be deterministic and JSON-serializable
- request body, headers, cookies, and meta must be redacted in safe output
- retry count should align with URLFrontier attempts and failure buckets
- session id should align with CLM `session_profile` / access config

### Result / Stats

Scrapling `CrawlStats` and `CrawlResult` provide:

- request counters
- concurrent request counters
- failure/offsite/robots/blocked counters
- cache hit/miss counters
- response status buckets
- response byte counters
- per-session and per-domain stats
- item export helpers
- paused/completed state

CLM absorption:

- extend `BatchRunnerSummary` or create `SpiderRunSummary`
- emit `RuntimeEvent` for progress, checkpoint, retry, robots, link discovery,
  blocked request, and failure bucket events
- keep exports in CLM result/product stores, not in a Scrapling `ItemList`
- preserve paused/completed distinction

### Link Extractor

Scrapling `LinkExtractor` provides:

- allow/deny regex filters
- allow/deny domain filters
- CSS/XPath restricted extraction scopes
- tag/attribute selection
- canonicalization and fragment policy
- ignored file extension filter
- custom process hook
- URL-only `matches()` helper for sitemap dispatch

CLM absorption:

- implement CLM-native `LinkDiscoveryHelper`
- classify discovered URLs as `category`, `list`, `detail`, `asset`, `api`, or
  `unknown`
- keep allow/deny/domain/extension filters profile-driven
- keep site rules in profiles, not core runtime
- return `RuntimeEvent` evidence for dropped/offsite/asset URLs

### Robots

Scrapling `RobotsTxtManager` provides:

- per-domain robots cache
- fetch-on-first-use
- graceful failure to empty parser
- `can_fetch()`
- crawl-delay and request-rate extraction
- concurrent prefetch for seed domains

CLM absorption:

- implement CLM-native `RobotsPolicyHelper`
- store robots evidence in checkpoint/profile artifacts
- feed crawl-delay and request-rate into `DomainRateLimiter`
- expose robots disallow as failure bucket / skipped bucket, not opaque error
- keep policy mode explicit: `respect`, `record_only`, or `disabled`

## CLM Native Target Mapping

| Scrapling idea | CLM target | Notes |
|---|---|---|
| `Scheduler` priority queue | `URLFrontier` + `SpiderQueuePolicy` | persistent SQLite queue remains source of truth |
| request fingerprint | `CrawlRequestEnvelope.fingerprint` | deterministic, safe, JSON-visible |
| `CheckpointManager` | `CheckpointStore` | SQLite/JSONL, not pickle |
| `CheckpointData.requests` | `CheckpointStore.pending_requests` or frontier rows | recoverable and inspectable |
| `CheckpointData.seen` | frontier hash table / checkpoint fingerprints | persistent dedupe |
| `Request.callback` | `task_kind` / `processor_name` | no callable serialization |
| `Request.sid` | `session_id` / `session_profile_id` | maps to CLM access/session layer |
| `CrawlStats` | `SpiderRunSummary` + `RuntimeEvent` | CLM-owned metrics |
| `CrawlResult.paused` | `SpiderRunSummary.status` | `completed`, `paused`, `failed`, `partial` |
| `ItemList` export | ProductStore / ResultStore / export CLI | CLM-owned export paths |
| `LinkExtractor` | `LinkDiscoveryHelper` | profile-driven filters |
| `RobotsTxtManager` | `RobotsPolicyHelper` | feeds rate-limit and evidence |

## Minimal Implementable Interface Draft

### File Layout

Recommended new CLM files:

```text
autonomous_crawler/runners/spider_runner.py
autonomous_crawler/runners/spider_models.py
autonomous_crawler/storage/checkpoint_store.py
autonomous_crawler/tools/link_discovery.py
autonomous_crawler/tools/robots_policy.py
autonomous_crawler/tests/test_spider_models.py
autonomous_crawler/tests/test_checkpoint_store.py
autonomous_crawler/tests/test_spider_runner.py
autonomous_crawler/tests/test_link_discovery.py
autonomous_crawler/tests/test_robots_policy.py
```

No `scrapling.spiders.*` imports should appear in these files.

### Request / Result / Event Models

```python
@dataclass(frozen=True)
class CrawlRequestEnvelope:
    request_id: str
    run_id: str
    url: str
    method: str = "GET"
    priority: int = 0
    kind: str = "page"
    depth: int = 0
    parent_url: str = ""
    session_id: str = ""
    session_profile_id: str = ""
    headers: dict[str, str] = field(default_factory=dict)
    cookies: dict[str, str] = field(default_factory=dict)
    params: dict[str, Any] = field(default_factory=dict)
    data: Any = None
    json: Any = None
    meta: dict[str, Any] = field(default_factory=dict)
    dont_filter: bool = False
    retry_count: int = 0
    max_retries: int = 3
    fingerprint: str = ""

    def canonical_url(self) -> str: ...
    def compute_fingerprint(
        self,
        *,
        include_headers: bool = False,
        include_body: bool = True,
        keep_fragments: bool = False,
    ) -> str: ...
    def to_runtime_request(self) -> RuntimeRequest: ...
    def to_safe_dict(self) -> dict[str, Any]: ...
```

```python
@dataclass
class CrawlItemResult:
    ok: bool
    request_id: str
    url: str
    status_code: int = 0
    records: list[Any] = field(default_factory=list)
    discovered_requests: list[CrawlRequestEnvelope] = field(default_factory=list)
    runtime_events: list[RuntimeEvent] = field(default_factory=list)
    artifacts: list[RuntimeArtifact] = field(default_factory=list)
    error: str = ""
    retry: bool = False
    failure_bucket: str = ""
    metrics: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def success(...): ...
    @classmethod
    def failure(...): ...
    def to_item_process_result(self) -> ItemProcessResult: ...
```

```python
@dataclass
class SpiderRunSummary:
    run_id: str
    status: str = "completed"  # completed | paused | failed | partial
    batches: int = 0
    claimed: int = 0
    succeeded: int = 0
    failed: int = 0
    retried: int = 0
    skipped: int = 0
    records_saved: int = 0
    discovered_urls: int = 0
    robots_disallowed: int = 0
    offsite_dropped: int = 0
    blocked_requests: int = 0
    checkpoint_writes: int = 0
    checkpoint_errors: int = 0
    response_status_count: dict[str, int] = field(default_factory=dict)
    failure_buckets: dict[str, int] = field(default_factory=dict)
    frontier_stats: dict[str, int] = field(default_factory=dict)
    events: list[RuntimeEvent] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]: ...
```

Recommended `RuntimeEvent.type` values:

```text
spider.run_started
spider.batch_claimed
spider.request_started
spider.request_succeeded
spider.request_failed
spider.request_retried
spider.request_skipped
spider.links_discovered
spider.robots_checked
spider.checkpoint_saved
spider.checkpoint_loaded
spider.checkpoint_failed
spider.run_paused
spider.run_completed
```

### CheckpointStore

```python
class CheckpointStore:
    def __init__(self, db_path: str | Path | None = None) -> None: ...
    def initialize(self) -> None: ...

    def start_run(self, run_id: str, config: dict[str, Any]) -> None: ...
    def save_batch_checkpoint(
        self,
        *,
        run_id: str,
        batch_id: str,
        frontier_items: list[dict[str, Any]],
        summary: SpiderRunSummary,
        events: list[RuntimeEvent],
    ) -> None: ...
    def save_item_checkpoint(
        self,
        *,
        run_id: str,
        request: CrawlRequestEnvelope,
        result: CrawlItemResult,
    ) -> None: ...
    def save_failure(
        self,
        *,
        run_id: str,
        request: CrawlRequestEnvelope,
        bucket: str,
        error: str,
        retryable: bool,
    ) -> None: ...
    def load_latest(self, run_id: str) -> dict[str, Any] | None: ...
    def list_failures(self, run_id: str, bucket: str = "") -> list[dict[str, Any]]: ...
    def mark_paused(self, run_id: str, reason: str = "") -> None: ...
    def mark_completed(self, run_id: str) -> None: ...
```

Suggested tables:

```text
spider_runs(run_id, status, config_json, started_at, updated_at, completed_at)
spider_checkpoints(id, run_id, batch_id, summary_json, frontier_stats_json, created_at)
spider_request_events(id, run_id, request_id, url, event_type, event_json, created_at)
spider_failures(id, run_id, request_id, url, bucket, error, retryable, attempts, created_at)
spider_items(id, run_id, request_id, record_type, record_json, dedupe_key, created_at)
```

Checkpoint storage should be append-friendly and inspectable. Avoid pickle.

### Spider Batch Processor

```python
class SpiderRuntimeProcessor:
    def __init__(
        self,
        runtime: FetchRuntime | BrowserRuntime,
        parser: ParserRuntime | None = None,
        link_discovery: LinkDiscoveryHelper | None = None,
        robots_policy: RobotsPolicyHelper | None = None,
        checkpoint_store: CheckpointStore | None = None,
    ) -> None: ...

    def __call__(self, item: FrontierItem) -> ItemProcessResult: ...
    def build_request(self, item: FrontierItem) -> CrawlRequestEnvelope: ...
    def process_request(self, request: CrawlRequestEnvelope) -> CrawlItemResult: ...
    def discover_links(
        self,
        request: CrawlRequestEnvelope,
        response: RuntimeResponse,
    ) -> list[CrawlRequestEnvelope]: ...
```

```python
class SpiderBatchRunner(BatchRunner):
    def pause(self, reason: str = "") -> SpiderRunSummary: ...
    def resume(self, run_id: str) -> SpiderRunSummary: ...
```

Implementation note: Phase C can start by composition around existing
`BatchRunner` instead of subclassing it. Subclassing should happen only if the
base runner gains event hooks.

### Link / Robots / Sitemap Helpers

```python
@dataclass(frozen=True)
class LinkDiscoveryRule:
    allow: tuple[str, ...] = ()
    deny: tuple[str, ...] = ()
    allow_domains: tuple[str, ...] = ()
    deny_domains: tuple[str, ...] = ()
    restrict_css: tuple[str, ...] = ()
    restrict_xpath: tuple[str, ...] = ()
    tags: tuple[str, ...] = ("a", "area")
    attrs: tuple[str, ...] = ("href",)
    deny_extensions: tuple[str, ...] = DEFAULT_DENY_EXTENSIONS
    keep_fragment: bool = False
    classify: dict[str, str] = field(default_factory=dict)
```

```python
class LinkDiscoveryHelper:
    def extract(self, html: str, *, base_url: str, rules: LinkDiscoveryRule) -> list[CrawlRequestEnvelope]: ...
    def matches(self, url: str, rules: LinkDiscoveryRule) -> bool: ...
    def classify_url(self, url: str, rules: LinkDiscoveryRule) -> str: ...
```

```python
class RobotsPolicyHelper:
    def can_fetch(self, url: str, *, user_agent: str = "*") -> bool: ...
    def get_delay_directives(self, url: str, *, user_agent: str = "*") -> RobotsDirectives: ...
    def prefetch(self, urls: list[str], *, user_agent: str = "*") -> None: ...
    def to_events(self, url: str) -> list[RuntimeEvent]: ...
```

```python
@dataclass(frozen=True)
class RobotsDirectives:
    can_fetch: bool
    crawl_delay_seconds: float | None = None
    request_rate: tuple[int, int] | None = None
    source_url: str = ""
    error: str = ""
```

Sitemap helper can be added after robots:

```python
class SitemapDiscoveryHelper:
    def discover_sitemaps(self, base_url: str) -> list[str]: ...
    def parse_sitemap(self, sitemap_url: str) -> list[CrawlRequestEnvelope]: ...
```

## Phase Plan

### Phase A: Request / Result / Event Model

Deliverables:

- `spider_models.py`
- `CrawlRequestEnvelope`
- `CrawlItemResult`
- `SpiderRunSummary`
- event type constants or helper constructors
- fingerprint implementation compatible with URLFrontier canonicalization

Acceptance:

- deterministic fingerprint tests for method, URL, body, headers option,
  fragments option, and JSON/body sorting
- redaction tests for headers, cookies, proxy/session fields, and errors
- conversion tests to/from `RuntimeRequest` and `ItemProcessResult`

### Phase B: CheckpointStore

Deliverables:

- `storage/checkpoint_store.py`
- SQLite tables for runs, checkpoints, request events, failures, and optional
  item checkpoint rows
- atomic transaction per batch/item
- pause/completed markers
- failure bucket queries

Acceptance:

- save/load latest checkpoint
- corrupt/missing checkpoint handled as inspectable failure state
- checkpoint write failure leaves frontier item failed, not done
- repeated run resume is idempotent

### Phase C: BatchRunner Processor

Deliverables:

- `SpiderRuntimeProcessor`
- optional `SpiderBatchRunner` wrapper
- event hook integration around existing `BatchRunner`
- product checkpoint compatibility through existing `ProductRecordCheckpoint`
- runtime response to records/discovered requests mapping

Acceptance:

- pause/resume over `max_batches`
- retryable and permanent failure buckets
- discovered URL routing to frontier with kind/depth/priority
- checkpoint writes for records and request events
- no site-specific selectors in processor core

### Phase D: Link / Robots / Sitemap Helpers

Deliverables:

- `tools/link_discovery.py`
- `tools/robots_policy.py`
- optional `tools/sitemap_discovery.py`
- profile-driven allow/deny/restrict rules
- robots delay evidence feeding rate-limit policy

Acceptance:

- allow/deny/domain/extension tests
- restricted CSS/XPath extraction tests
- offsite and asset-drop counters
- robots allow/disallow tests with local fixture
- crawl-delay/request-rate mapped into events

## Directly Absorb vs. Adapt

### Directly Absorb As Design Ideas

- priority plus FIFO tie-breaker
- request fingerprint dedupe
- `dont_filter` escape hatch
- checkpoint interval and atomic checkpoint writes
- paused/completed run distinction
- stats buckets for status, robots, blocked, failed, cache, sessions, domains
- link allow/deny/domain/extension filtering
- robots cache and delay/request-rate extraction

### Adapt To CLM Style

- Scrapling in-memory scheduler -> CLM persistent `URLFrontier`
- pickle checkpoint -> SQLite/JSON inspectable `CheckpointStore`
- callback callable -> `task_kind`, `processor_name`, or profile route
- Scrapling `ItemList` export -> CLM `ResultStore`, `ProductStore`, and export
  commands
- Scrapling response object -> CLM `RuntimeResponse`
- log-only stats -> CLM `RuntimeEvent` and handoff/report evidence
- robots parser fetch function -> CLM fetch runtime plus policy mode
- generic link extractor -> CLM profile-driven link discovery and URL
  classification

## Acceptance Test Recommendations

### Unit

- request fingerprint canonicalizes URL, method, JSON/body, optional headers,
  and fragment policy
- URL dedupe respects `dont_filter`
- priority ordering preserves FIFO for equal priority
- checkpoint store atomic write and load latest checkpoint
- checkpoint failure records failure bucket and does not mark item done
- robots disallow produces skipped/failure bucket event
- link extractor drops denied domains, ignored extensions, and offsite URLs

### Runner

- pause/resume by running `max_batches=1`, then resuming same run
- retryable failure requeues with attempts increment
- permanent failure lands in failure bucket
- discovered detail URLs are added with `kind="detail"` and depth increment
- product records pass through `ProductRecordCheckpoint`
- runtime events survive summary and checkpoint serialization

### Scale

- 1,000 synthetic URLs: completes with stable stats and no duplicate records
- 10,000 synthetic URLs: resume after forced interruption
- 30,000 synthetic ecommerce records: ProductStore + checkpoint + export path
- failure-bucket stress: mix 200/404/429/blocked/timeout/parser-error buckets

### Real Training

- 600+ real ecommerce regression once site profiles are stable
- verify category/list/detail/variant URL classification
- verify category-aware product dedupe
- verify blocked/challenge pages are not treated as successful products
- verify robots/rate-limit evidence is recorded when enabled

## Implementation Ownership Recommendation

- LLM-2026-000: own Phase A model boundaries and final merge into runtime
  protocols.
- LLM-2026-001: implement request/result/event models plus conversion tests,
  because this touches runtime/native parser handoff surfaces.
- LLM-2026-002: implement CheckpointStore and parity QA, including pause/resume
  and failure bucket tests.
- LLM-2026-004: keep documentation, source tracking, and acceptance checklist
  aligned after code lands.
- Supervisor or dedicated runner worker: implement Phase C BatchRunner processor
  after Phase A/B are accepted.

## Guardrails

- Do not import Scrapling spider runtime in CLM native spider backend.
- Do not expose Scrapling-specific objects in workflow state, result store, or
  API output.
- Do not hard-code ecommerce or site-specific rules in runner/spider core.
- Do not bypass robots, login, CAPTCHA, Cloudflare, or authorization controls by
  default.
- Do not persist cookies, API keys, proxy credentials, or storage-state contents
  in checkpoint/event tables.
