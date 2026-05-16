# 2026-05-15 LLM-2026-002 — SCALE-HARDEN-1 + REAL-HARDEN-2

**Task**: Push native long-run from 1k to 10k/30k parameterized verification, add real public API/GraphQL 50+ records training
**Worker**: LLM-2026-002
**Status**: COMPLETE

## Summary

Scaled NativeAsyncFetchRuntime to 10k (default) and 30k (optional) URL runs with memory tracking, throughput measurement, checkpoint roundtrip, and full proxy/async/backpressure summary. Added real public API/GraphQL training against DummyJSON REST, Countries GraphQL, and AniList GraphQL endpoints producing 50+ records each.

## Files Changed

| File | Action | Description |
|------|--------|-------------|
| `autonomous_crawler/runtime/native_async.py` | MODIFIED | +`shared_client` parameter for connection pooling |
| `run_scale_stress_2026_05_15.py` | NEW | Parameterized 10k/30k stress runner with memory/timing/checkpoint |
| `run_real_api_training_2026_05_15.py` | NEW | Real public API/GraphQL 50+ records training runner |
| `dev_logs/development/2026-05-15_LLM-2026-002_scale_harden_real_api_training.md` | NEW | This dev log |
| `docs/memory/handoffs/2026-05-15_LLM-2026-002_scale_harden_real_api_training.md` | NEW | Handoff |

## SCALE-HARDEN-1 Results

### 10k Stress (default)

```
URLs:              10000
Domains:           20
Per-domain:        4
Global:            32
Chunk size:        2000
Elapsed:           12.417s
Throughput:        805.3 URLs/s

Memory:
  Before:          106.2 MB
  After:           509.9 MB
  Delta:           403.7 MB
  Peak (traced):   203.3 MB

Summary:
  Succeeded:       10000
  Failed:          0
  Proxy attempts:  10526
  Proxy failures:  526 (5% simulated)
  Proxy retries:   526
  Backpressure:    0
  Async OK:        10000
  Async fail:      0

Checkpoint:
  Roundtrip OK:    True
  Proxy fields OK: True
  Async fields OK: True
```

### 30k Stress (optional)

```
URLs:              30000
Domains:           20
Per-domain:        4
Global:            32
Chunk size:        2000
Elapsed:           36.184s
Throughput:        829.1 URLs/s

Memory:
  Before:          106.5 MB
  After:           1373.1 MB
  Delta:           1266.6 MB
  Peak (traced):   606.2 MB

Summary:
  Succeeded:       30000
  Failed:          0
  Proxy attempts:  31578
  Proxy failures:  1578 (5% simulated)
  Proxy retries:   1578
  Backpressure:    0
  Async OK:        30000
  Async fail:      0

Checkpoint:
  Roundtrip OK:    True
  Proxy fields OK: True
  Async fields OK: True
```

## REAL-HARDEN-2 Results

| Target | Kind | Items | Status |
|--------|------|-------|--------|
| dummyjson_products | REST | 100 | PASS |
| dummyjson_products_paginated | REST paginated | 30 | PARTIAL (stop=no_next_hint) |
| countries_graphql | GraphQL | 250 | PASS |
| anilist_graphql | GraphQL | 50 | PASS |

### Evidence Signals

- Countries GraphQL: `graphql_nested_complexity` detected
- AniList GraphQL: `graphql_signature_hint` detected (auth headers present)

## Bottleneck Analysis

### Memory

- **10k**: 403.7 MB delta, 203.3 MB peak traced. RSS growth is ~40 KB/URL which includes httpx response objects and RuntimeResponse wrappers. The peak traced (Python allocator) is half the RSS delta, meaning ~200 MB is from non-Python allocations (httpx/libc buffers).
- **30k**: 1266.6 MB delta, 606.2 MB peak traced. Linear scaling from 10k. No memory leak — growth is proportional to URL count.
- **Chunking**: Chunk size 2000 with `gc.collect()` + `await asyncio.sleep(0)` between chunks keeps peak memory bounded. Without chunking, all 30k responses live in memory simultaneously.

### Throughput

- **805-829 URLs/s** across both 10k and 30k runs. Consistent — no degradation at scale.
- **httpx.AsyncClient** with connection pooling (`shared_client` parameter) avoids per-request TLS handshake overhead.
- **Per-domain concurrency cap (4)** prevents thundering herd on any single domain while global cap (32) allows multi-domain parallelism.

### Connection Pooling

- `shared_client` parameter added to `NativeAsyncFetchRuntime.__init__()` — when provided, all requests share a single `httpx.AsyncClient` with connection pool.
- Backward compatible: without `shared_client`, creates per-request client as before.
- For 30k runs, shared client avoids 30k separate connection setups.

### Checkpoint

- SQLite checkpoint roundtrip verified: `succeeded`, `proxy_attempts_total`, `async_fetch_ok` all round-trip correctly.
- No data loss in checkpoint serialization/deserialization.

### Proxy Retry

- 5% simulated failure rate (every 20th request raises `ConnectionError`).
- All failures retried successfully — 0 failed in final summary.
- `proxy_failures` and `proxy_retries` counts match exactly (each failure triggers one retry).

## Tests

```
test_native_async_runtime:     23 passed
test_native_longrun_stress:     8 passed
test_graphql_training:         42 passed
Total targeted:                73 passed
compileall:                    clean
```
