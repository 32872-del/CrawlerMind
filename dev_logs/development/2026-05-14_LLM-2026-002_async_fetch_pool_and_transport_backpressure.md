# 2026-05-14 LLM-2026-002 — Async Fetch Pool and Transport Backpressure

**Task**: SCRAPLING-ABSORB-1F / CAP-1.3 / CAP-3.3 — async fetch pool with per-domain concurrency
**Worker**: LLM-2026-002
**Status**: COMPLETE

## Summary

Built CLM-native async fetch runtime with bounded per-domain concurrency,
structured backpressure evidence, and proxy retry compatibility. The runtime
uses `httpx.AsyncClient` for async HTTP and `asyncio.Semaphore` for concurrency
control. No Scrapling dependencies.

## Files Changed

| File | Action | Description |
|------|--------|-------------|
| `autonomous_crawler/runtime/native_async.py` | NEW | DomainConcurrencyPool + NativeAsyncFetchRuntime |
| `autonomous_crawler/runtime/__init__.py` | MODIFIED | Added exports |
| `autonomous_crawler/tests/test_native_async_runtime.py` | NEW | 23 tests |
| `dev_logs/development/2026-05-14_LLM-2026-002_async_fetch_pool_and_transport_backpressure.md` | NEW | This dev log |
| `docs/memory/handoffs/2026-05-14_LLM-2026-002_async_fetch_pool_and_transport_backpressure.md` | NEW | Handoff |

## Design

### Separate Module

`NativeAsyncFetchRuntime` lives in `native_async.py`, separate from the
synchronous `NativeFetchRuntime` in `native_static.py`. This avoids mixing
sync/async patterns and keeps the stable sync runtime untouched.

### DomainConcurrencyPool

```
DomainConcurrencyPool(max_per_domain=4, max_global=16)
├── _global_sem: asyncio.Semaphore(16)        # total capacity
├── _domain_sems: {domain: asyncio.Semaphore(4)}  # per-domain capacity
└── _active_per_domain: {domain: int}         # tracking
```

- `acquire(url)` → acquires global then domain semaphore, returns `(domain, sem, at_limit)`
- `release(domain, sem)` → releases both
- `at_limit` flag indicates domain was at capacity when acquire was attempted

### NativeAsyncFetchRuntime

- `name = "native_async"`
- `fetch(request)` — single async fetch with concurrency pool and proxy retry
- `fetch_many(requests, rate_limiter=None)` — concurrent batch via `asyncio.gather`

### Reused from native_static.py

- `_transport_for()`, `_proxy_url_for()`, `_proxy_trace_for()`
- `_RetryConfig`, `_select_proxy_for_attempt()`, `_record_proxy_failure/success()`
- `_response_from_http_response()` (with engine_result override)
- `_PROXY_RETRYABLE_ERRORS`

### Backpressure Events

| Event | When |
|-------|------|
| `pool_acquired` | Concurrency slot acquired, includes active counts |
| `pool_backpressure` | Domain was at concurrency limit |
| `pool_released` | Concurrency slot released |
| `fetch_many_start` | Batch begins, includes pool config |
| `fetch_many_complete` | Batch done, includes ok/fail counts |

### Rate Limiter Integration

`fetch_many()` accepts optional `rate_limiter` parameter. Uses `asyncio.sleep()`
instead of blocking `time.sleep()` for per-domain delays.

## Test Coverage (23 tests)

**TestAsyncFetchBasic (4 tests):**
- Single fetch returns ok RuntimeResponse
- Events include fetch_start, fetch_complete, pool_acquired, pool_released
- Fetch with proxy populates proxy_trace
- Fetch error returns failure

**TestAsyncFetchMany (3 tests):**
- Batch returns all responses
- Batch events (fetch_many_start/complete) in each response
- Partial failure (some succeed, some fail)

**TestDomainConcurrencyPool (5 tests):**
- Acquire/release cycle
- Per-domain limit reached (blocks when full)
- Different domains independent
- Global limit reached (blocks when full)
- Properties accessible

**TestBackpressureEvents (2 tests):**
- Backpressure event when domain at limit
- Pool events in response

**TestAsyncProxyRetry (2 tests):**
- First proxy fail → second proxy success
- All attempts fail

**TestAsyncCredentialSafety (3 tests):**
- Credentials not in events
- Credentials not in response.to_dict()
- Credentials not in error response

**TestAsyncRateLimitIntegration (2 tests):**
- Rate limiter called before each fetch
- Fetch works without rate limiter

**TestAsyncRuntimeProperties (2 tests):**
- Name is "native_async"
- Pool properties accessible

## Test Results

```
test_native_async_runtime:     23 passed, 0 failures
test_native_static_runtime:    14 passed, 0 failures
test_native_proxy_retry:       24 passed, 0 failures
compileall:                    clean
```

## Known Remaining Limits

1. **No async browser runtime** — browser fetch is still sync Playwright
2. **curl_cffi in executor** — curl_cffi has no async API, runs via `run_in_executor`
3. **No adaptive concurrency** — limits are static, not adjusted based on response signals
4. **No connection pooling across requests** — each `fetch()` creates a new `AsyncClient`
5. **No retry on 429/5xx in async path** — only proxy connection errors trigger retry
