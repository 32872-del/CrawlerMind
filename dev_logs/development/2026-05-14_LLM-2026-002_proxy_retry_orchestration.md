# 2026-05-14 LLM-2026-002 — Proxy Retry Orchestration

**Task**: CAP-3.3 / SCRAPLING-ABSORB-1E — proxy retry orchestration
**Worker**: LLM-2026-002
**Status**: COMPLETE

## Summary

Moved proxy health from passive diagnostics into active runtime behavior.
NativeFetchRuntime now retries with alternative healthy proxies when a selected
proxy fails, recording structured evidence events. All proxy URLs remain
credential-safe in every output path.

## Files Changed

| File | Action | Description |
|------|--------|-------------|
| `autonomous_crawler/runtime/native_static.py` | MODIFIED | Retry loop, _RetryConfig, proxy selection/health recording, _do_fetch dispatch, _fetch_httpx proxy_url param |
| `autonomous_crawler/tests/test_native_proxy_retry.py` | NEW | 24 tests: first-fail-then-success, all unavailable, max attempts, credential safety, error classification, pool provider integration |
| `dev_logs/development/2026-05-14_LLM-2026-002_proxy_retry_orchestration.md` | NEW | This dev log |
| `docs/memory/handoffs/2026-05-14_LLM-2026-002_proxy_retry_orchestration.md` | NEW | Handoff |

## Design

### Retry Loop in `fetch()`

```
fetch(request):
    retry_cfg = _RetryConfig.from_proxy_config(request.proxy_config)
    for attempt in range(retry_cfg.max_attempts):
        proxy_url = _select_proxy_for_attempt(request, retry_cfg, attempt)
        try:
            response = _do_fetch(request, transport, proxy_url)
        except _PROXY_RETRYABLE_ERRORS:
            _record_proxy_failure(retry_cfg, proxy_url, error)
            continue  # next attempt
        except Exception:
            return failure  # non-proxy error, no retry
        _record_proxy_success(retry_cfg, proxy_url)
        return success
    return failure  # all attempts exhausted
```

### Configuration (via `request.proxy_config`)

- `retry_on_proxy_failure` (bool): enable retry behavior
- `max_proxy_attempts` (int): max number of proxy attempts (default 1)
- `pool_provider`: ProxyPoolProvider for alternative proxy selection
- `health_store`: ProxyHealthStore for failure/success recording

### Structured Events

| Event Type | When |
|-----------|------|
| `fetch_start` | Includes transport, method, url, redacted proxy, max_proxy_attempts |
| `proxy_attempt` | Each attempt begins |
| `proxy_failure_recorded` | Connection error recorded to health store |
| `proxy_retry` | Retrying with next proxy |
| `proxy_success_recorded` | Success recorded to health store |
| `fetch_complete` | Successful fetch done |
| `fetch_error` | Non-proxy error or all attempts exhausted |

### Error Classification

Only connection-level errors trigger retry (`_PROXY_RETRYABLE_ERRORS`):
- `ConnectionError`, `ConnectionRefusedError`, `ConnectionResetError`
- `TimeoutError`
- `httpx.ConnectError`, `httpx.ConnectTimeout`, `httpx.ReadTimeout`, `httpx.WriteTimeout`, `httpx.PoolTimeout`

Application errors (`ValueError`, `KeyError`, etc.) do not trigger retry.

## Test Coverage (24 tests)

**First proxy fail → second proxy success (5 tests):**
- Returns ok response
- Correct event sequence (fetch_start → proxy_attempt → proxy_failure_recorded → proxy_retry → proxy_attempt → proxy_success_recorded → fetch_complete)
- Failure recorded to health store
- Success recorded to health store
- pool.report_result called for both failure and success

**All proxies unavailable / cooldown (3 tests):**
- Returns failure response with "all N proxy attempts failed"
- Correct event counts (N proxy_attempt, N-1 proxy_retry, N proxy_failure_recorded, 0 proxy_success_recorded)
- health_store.record_failure called for all attempts

**Max attempts exhaustion (3 tests):**
- Single attempt: no retry events
- Three attempts: correct attempt/retry counts
- Default max_attempts is 1 (no retry without config)

**Credential safety (4 tests):**
- Credentials not in any event.to_dict() output
- Credentials not in response.to_dict() output
- Credentials not in error response output
- Credentials not in all-attempts-failed response output

**Error classification (4 tests):**
- ConnectError triggers retry
- ConnectTimeout triggers retry
- ReadTimeout triggers retry
- ValueError does NOT trigger retry

**Pool provider integration (3 tests):**
- pool.select called for retry attempts
- No pool provider → falls back to request proxy
- pool.select exception → falls back to request proxy

**Various connection errors (2 tests):**
- ConnectionResetError triggers retry
- PoolTimeout triggers retry

## Test Results

```
test_native_proxy_retry:       24 passed, 0 failures
test_native_static_runtime:    14 passed, 0 failures
test_proxy_health_lifecycle:   24 passed, 0 failures
test_transport_diagnostics:    10 passed, 0 failures
compileall:                    clean
```

## Credential Safety Evidence

All test paths verify no plaintext credentials appear in:
- Event `to_dict()` output (all 24 tests with credentials)
- `RuntimeResponse.to_dict()` output (4 dedicated tests)
- Error response output (1 dedicated test)
- All-attempts-failed response output (1 dedicated test)
