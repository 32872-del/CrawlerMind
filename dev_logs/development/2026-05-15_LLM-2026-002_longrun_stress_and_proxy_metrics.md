# 2026-05-15 LLM-2026-002 — SCRAPLING-HARDEN-1: Native Long-Run Stress + Async Metrics

**Task**: SCRAPLING-HARDEN-1 — prove CLM-native async fetch + spider + checkpoint can support large-scale crawls
**Worker**: LLM-2026-002
**Status**: COMPLETE

## Summary

Proved CLM-native async fetch pool supports 10k URL runs with metrics flowing
into SpiderRunSummary. Added async/proxy/backpressure fields to SpiderRunSummary
(backward compatible), wired event aggregation in record_item(), built 1k stress
tests with checkpoint resume verification, and created an optional 10k runner.

## Files Changed

| File | Action | Description |
|------|--------|-------------|
| `autonomous_crawler/runners/spider_models.py` | MODIFIED | +10 async/proxy/backpressure fields to SpiderRunSummary, +`_aggregate_events()`, +`aggregate_async_metrics()`, updated `as_dict()` |
| `autonomous_crawler/tests/test_native_longrun_stress.py` | NEW | 8 tests: 1k stress + summary, proxy retry metrics, checkpoint resume, credential safety, concurrency under load |
| `run_native_longrun_stress_2026_05_15.py` | NEW | Optional runner script (1k default, 10k supported) |
| `dev_logs/development/2026-05-15_LLM-2026-002_longrun_stress_and_proxy_metrics.md` | NEW | This dev log |
| `docs/memory/handoffs/2026-05-15_LLM-2026-002_longrun_stress_and_proxy_metrics.md` | NEW | Handoff |

## SpiderRunSummary New Fields

All backward compatible (default to 0 or empty dict):

| Field | Type | Description |
|-------|------|-------------|
| `proxy_attempts_total` | int | Total proxy attempts across all items |
| `proxy_failures` | int | Proxy failure events |
| `proxy_successes` | int | Proxy success events |
| `proxy_retries` | int | Proxy retry events |
| `backpressure_events` | int | Domain concurrency limit hits |
| `pool_acquired_events` | int | Pool acquire events |
| `pool_released_events` | int | Pool release events |
| `async_fetch_ok` | int | Successful async fetches |
| `async_fetch_fail` | int | Failed async fetches |
| `max_concurrency_per_domain` | dict[str,int] | Peak concurrent requests per domain |

## Aggregation Mechanism

`SpiderRunSummary.record_item()` now calls `_aggregate_events()` which scans
each result's `runtime_events` for proxy/pool/async event types and increments
the corresponding counters. No changes to SpiderRuntimeProcessor needed — the
events flow through naturally via `record_item()`.

## Stress Results

### 1k URLs

```
URLs:           1,000
Domains:        10
Elapsed:        0.893s
Throughput:     1,120 URLs/s
Succeeded:      1,000
Failed:         0
Proxy attempts: 1,052
Proxy failures: 52
Proxy retries:  52
Checkpoint:     roundtrip OK, proxy fields OK
Credential leak: none
```

### 10k URLs

```
URLs:           10,000
Domains:        10
Elapsed:        3.677s
Throughput:     2,720 URLs/s
Succeeded:      10,000
Failed:         0
Proxy attempts: 10,526
Proxy failures: 526
Proxy retries:  526
Checkpoint:     roundtrip OK, proxy fields OK
Credential leak: none
```

## Test Results

```
test_native_async_runtime:     23 passed
test_spider_runner:            11 passed
test_checkpoint_store:          6 passed
test_native_longrun_stress:     8 passed
compileall:                    clean
```

## Known Remaining Bottlenecks

1. **No connection pooling** — each fetch creates new AsyncClient
2. **Memory** — 10k responses held in memory simultaneously
3. **No adaptive concurrency** — limits are static
4. **No 429/5xx retry** — only proxy connection errors trigger retry
5. **SQLite single-writer** — checkpoint writes are serialized
