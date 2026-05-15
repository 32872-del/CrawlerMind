# SCRAPLING-ABSORB-2G: Browser Pool Real Smoke And Batch Wiring

Date: 2026-05-14
Worker: LLM-2026-001

## Objective

Turn the accepted native browser session/profile pool from mocked unit coverage
into a real backend capability: prove real Playwright context reuse, add failure
quarantine, expose pool runtime events, and wire pool into spider/batch runs.

## What Was Done

### Modified Files

1. **`autonomous_crawler/runtime/browser_pool.py`**
   - Added `mark_failed(profile_id, error)` method — closes and removes failed contexts from pool
   - Added `_events: list[dict]` field for event tracking
   - Added `_record_event(event_type, profile_id, **data)` helper
   - Events recorded: `pool_acquire`, `pool_reuse`, `pool_release`, `pool_evict`, `pool_mark_failed`
   - Updated `to_safe_dict()` to include events list

2. **`autonomous_crawler/runtime/native_browser.py`**
   - Added persistent Playwright instance (`self._pw`, `self._pw_cm`) for pool mode
   - Pool mode keeps Playwright alive across calls so pooled contexts remain valid
   - Non-pool mode still uses `with sync_playwright()` per call (backward compatible)
   - Added `close()` method for cleanup
   - Emit `RuntimeEvent` types: `pool_acquire`, `pool_reuse`, `pool_release`, `pool_mark_failed`
   - Exception handler calls `mark_failed()` instead of `release()` to quarantine bad contexts

3. **`autonomous_crawler/runners/spider_runner.py`**
   - Added `pool: BrowserPoolManager | None = None` parameter to `SpiderRuntimeProcessor.__init__`
   - Injects pool into `browser_runtime._pool` when both are provided

4. **`autonomous_crawler/tests/test_browser_pool.py`**
   - Added `PoolMarkFailedTests` (7 tests): removes lease, closes context/browser, noop for missing, prevents reuse, records event, truncates error
   - Added `PoolEventTests` (7 tests): acquire, reuse, release (closed/keepalive), eviction, safe_dict includes events, full lifecycle
   - Added `NativeBrowserRuntimePoolEventTests` (4 tests): acquire event, reuse event, release event, mark_failed on exception

### Created Files

1. **`run_browser_pool_smoke_2026_05_14.py`** — deterministic real-browser smoke
   - Starts local HTTP server on random port
   - Creates `NativeBrowserRuntime(pool=BrowserPoolManager(...))`
   - Two sequential requests with same `pool_id`
   - Verifies: pool_request_count=1 then 2
   - Verifies: pool_acquire, pool_release, pool_reuse events
   - Skips cleanly when Playwright binaries not installed

## Key Design Decisions

1. **Persistent Playwright for pool mode**: When pool is active, the Playwright instance is kept alive across `render()` calls. This is required because pooled contexts belong to the Playwright event loop — closing Playwright invalidates all contexts. Non-pool mode retains the original per-call lifecycle.

2. **mark_failed quarantines**: Failed contexts are immediately closed and removed from the pool. The next request with the same `pool_id` will create a fresh context rather than reusing the bad one.

3. **Error truncation**: `mark_failed` truncates error messages to 200 chars in events to avoid leaking sensitive data or bloating event logs.

4. **SpiderRuntimeProcessor pool injection**: Uses `hasattr(browser_runtime, "_pool")` check rather than `isinstance` to avoid coupling to NativeBrowserRuntime specifically.

## Tests Run

```
python -m unittest autonomous_crawler.tests.test_browser_pool -v
# 54 tests OK

python -m unittest autonomous_crawler.tests.test_native_browser_runtime -v
# 11 tests OK

python run_browser_pool_smoke_2026_05_14.py
# [PASS] Browser pool smoke test passed
```

## Pool Event Evidence

Events are exposed in two places:
- `RuntimeResponse.runtime_events` — RuntimeEvent objects with type, message, data
- `BrowserPoolManager.to_safe_dict()["events"]` — raw event dicts with timestamp

Event types:
| Event | When | Key Data |
|---|---|---|
| `pool_acquire` | New context created | profile_id, fingerprint |
| `pool_reuse` | Existing context reused | profile_id, fingerprint |
| `pool_release` | Context released | profile_id, reason (keepalive/closed) |
| `pool_evict` | Oldest context evicted | profile_id, reason (pool_full) |
| `pool_mark_failed` | Context quarantined | profile_id, error (truncated) |

## What Was NOT Changed

- No site-specific crawl logic added
- No Scrapling import or dependency
- No changes to native_static.py, native_parser.py, planner.py, strategy.py
- Credential-safe: error messages truncated, no raw credentials in events

## Known Risks

1. **Persistent Playwright lifecycle**: The Playwright instance stays alive until `runtime.close()` is called. If the caller forgets to close, there may be resource leaks. This is acceptable for long-running spider/batch processes.

2. **Context invalidation**: If a pooled context is closed externally (e.g., by Playwright internal error), the pool will try to reuse it and fail. The `mark_failed` path handles this gracefully.

3. **No cross-process pool sharing**: The pool is in-process only. Multiple workers cannot share a pool.

## Next Steps

1. Consider adding pool health check (periodic ping)
2. Consider adding `max_pool_idle_seconds` for auto-cleanup
3. Wire pool into BatchRunner for multi-worker spider runs
