# SCRAPLING-ABSORB-2F: Native Browser Session and Profile Pool

Date: 2026-05-14
Worker: LLM-2026-001
Status: COMPLETE

## Deliverables

- `autonomous_crawler/runtime/browser_pool.py` — browser context pool module
- `autonomous_crawler/tests/test_browser_pool.py` — 36 focused tests (all pass)
- Updated `autonomous_crawler/runtime/native_browser.py` — pool integration
- Updated `autonomous_crawler/runtime/__init__.py` — pool exports

## Key Classes

| Class | Purpose |
|---|---|
| `BrowserPoolConfig` | Pool configuration (max_contexts, max_requests, max_age, keepalive) |
| `BrowserContextLease` | Leased context with profile_id, fingerprint, request_count, age |
| `BrowserPoolManager` | Acquire/release/close_all, fingerprint-based reuse, eviction |

## Usage

```python
from autonomous_crawler.runtime import NativeBrowserRuntime, BrowserPoolManager, BrowserPoolConfig

# Create pool
pool = BrowserPoolManager(BrowserPoolConfig(
    max_contexts=8,
    max_requests_per_context=50,
    keepalive_on_release=True,
))

# Create runtime with pool
runtime = NativeBrowserRuntime(pool=pool)

# Render with pool reuse
request = RuntimeRequest.from_dict({
    "url": "https://example.com",
    "browser_config": {"pool_id": "my-profile"},
})
response = runtime.render(request)
# response.engine_result["pool_id"] == "my-profile"
# response.engine_result["pool_request_count"] == 1

# Second request reuses same context
response2 = runtime.render(request)
# response2.engine_result["pool_request_count"] == 2

# Cleanup
pool.close_all()
```

## Pool Behavior

- **Acquire**: If a lease exists with matching fingerprint and is healthy, reuse it. Otherwise create new.
- **Release**: If keepalive=True and context is healthy, keep in pool. Otherwise close.
- **Eviction**: Oldest lease evicted when pool full. Max requests/age exceeded on next acquire.
- **Fingerprint**: SHA256 of user_agent, viewport, locale, timezone, color_scheme, headless, proxy, channel, args, session_mode.

## Integration Points

- `NativeBrowserRuntime.__init__(pool=None)` — optional pool
- `browser_config["pool_id"]` — opt-in per request
- `engine_result["pool"]`, `engine_result["pool_id"]`, `engine_result["pool_request_count"]` — pool evidence in output

## Backward Compatibility

- `NativeBrowserRuntime()` without pool behaves exactly as before
- All existing tests pass (180 relevant tests, 0 failures)
- No Scrapling dependency

## Next Steps

- Run real browser integration tests with pool
- Consider pool metrics in runtime events
- Wire pool into BatchRunner for spider runs

## Supervisor Acceptance

Accepted on 2026-05-14 with a small supervisor cleanup: reused lease acquisition
no longer increments request count; render completion records the actual usage.
