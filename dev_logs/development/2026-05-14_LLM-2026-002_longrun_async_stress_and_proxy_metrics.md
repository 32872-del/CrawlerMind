# 2026-05-14 LLM-2026-002 — Long-Run Async Stress and Proxy Metrics

**Task**: SCRAPLING-ABSORB-1G / CAP-1.3 / CAP-3.3 / CAP-3.5 — stress testing and metrics
**Worker**: LLM-2026-002
**Status**: COMPLETE

## Summary

Added deterministic stress coverage for the async fetch pool and an inspectable
`AsyncFetchMetrics` report object. Proves 1,000 URL fetch simulation works,
per-domain concurrency is bounded, retry/backoff events are counted, and
proxy failure/recovery flows are measurable.

## Files Changed

| File | Action | Description |
|------|--------|-------------|
| `autonomous_crawler/runtime/native_async.py` | MODIFIED | Added AsyncFetchMetrics dataclass |
| `autonomous_crawler/runtime/__init__.py` | MODIFIED | Added AsyncFetchMetrics to exports |
| `autonomous_crawler/tests/test_async_stress_metrics.py` | NEW | 16 tests: 1000 URL sim, concurrency limits, retry counts, proxy recovery, metrics object |
| `dev_logs/development/2026-05-14_LLM-2026-002_longrun_async_stress_and_proxy_metrics.md` | NEW | This dev log |
| `docs/memory/handoffs/2026-05-14_LLM-2026-002_longrun_async_stress_and_proxy_metrics.md` | NEW | Handoff |

## AsyncFetchMetrics

Frozen dataclass built via `AsyncFetchMetrics.from_responses(responses)`.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `total` | int | Total responses |
| `ok_count` | int | Successful responses |
| `fail_count` | int | Failed responses |
| `domains` | dict[str,int] | Request count per domain |
| `status_codes` | dict[int,int] | Count per HTTP status code |
| `proxy_attempts_total` | int | Total proxy attempts across all requests |
| `proxy_failures` | int | Proxy failure events |
| `proxy_successes` | int | Proxy success events |
| `proxy_retries` | int | Proxy retry events |
| `backpressure_events` | int | Domain concurrency limit hit count |
| `pool_acquired_events` | int | Pool acquire events |
| `event_type_counts` | dict[str,int] | Count of each event type |
| `errors` | list[str] | Error messages (capped at 100) |
| `max_concurrency_per_domain` | dict[str,int] | Peak concurrent requests per domain |

### Usage

```python
responses = await runtime.fetch_many(requests)
metrics = AsyncFetchMetrics.from_responses(responses)
report = metrics.to_dict()  # credential-safe dict
```

## Test Coverage (16 tests)

**TestThousandUrlSimulation (2 tests):**
- 1,000 URLs all succeed, metrics report correct totals
- Metrics has domain counts for all domains

**TestConcurrencyLimits (3 tests):**
- Max concurrency observed respects per-domain limit
- Different domains run in parallel
- Backpressure events appear when domain at limit

**TestRetryBackoffCounts (2 tests):**
- Retry events counted correctly in batch
- All-fail scenario has correct failure/retry counts

**TestProxyFailureRecovery (2 tests):**
- Partial proxy failure with recovery
- Health store called correctly in batch context

**TestAsyncFetchMetrics (5 tests):**
- Empty responses → zero metrics
- Status code counting
- to_dict() structure completeness
- Errors capped at 100
- Max concurrency per domain tracked

**TestThroughputCharacteristics (2 tests):**
- 100 URLs complete within timeout
- Global concurrency limit enforced

## Test Results

```
test_async_stress_metrics:     16 passed, 0 failures
test_native_async_runtime:     23 passed, 0 failures
test_native_static_runtime:    14 passed, 0 failures
test_native_proxy_retry:       24 passed, 0 failures
compileall:                    clean
```

## Acceptance Report

### Throughput metric
- 1,000 URL fetch simulation completes in ~0.4s with mocked responses
- 100 URLs complete in <1s with mocked responses

### Max concurrency observed per domain
- Per-domain limit (default 4) enforced correctly
- Global limit (default 16) enforced across domains
- `max_concurrency_per_domain` field tracks peak concurrency

### Retry/backoff/proxy counts
- `proxy_attempts_total`: total proxy attempts
- `proxy_failures`: connection error events
- `proxy_successes`: successful proxy events
- `proxy_retries`: retry events between attempts
- `backpressure_events`: domain concurrency limit hits

### Remaining bottlenecks before 10,000+ real URL runs
1. **Connection pooling** — each fetch creates a new `AsyncClient`, should reuse
2. **DNS resolution** — no DNS caching, repeated lookups for same domain
3. **Rate limiter integration** — `async_before_request` is optional, not wired by default
4. **Memory** — 10,000 responses in memory simultaneously may be large
5. **No adaptive concurrency** — limits are static, not adjusted based on error rates
6. **No 429/5xx retry** — only proxy connection errors trigger retry
