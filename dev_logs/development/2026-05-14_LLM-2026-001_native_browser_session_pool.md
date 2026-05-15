# SCRAPLING-ABSORB-2F: Native Browser Session and Profile Pool

Date: 2026-05-14
Worker: LLM-2026-001

## Objective

Build CLM-native browser context leasing, persistent session reuse, and profile
pool support so `NativeBrowserRuntime` can absorb the useful Scrapling
browser/session behavior into CLM-owned runtime code.

## What Was Done

### Created Files

1. **`autonomous_crawler/runtime/browser_pool.py`** — browser context pool module
   - `BrowserPoolConfig` — pool configuration (max_contexts, max_requests_per_context, max_context_age_seconds, keepalive_on_release)
   - `BrowserContextLease` — a leased browser context with profile_id, fingerprint, session_mode, request_count, age tracking, and storage state export
   - `BrowserPoolManager` — pool manager with acquire/release/close_all, fingerprint-based context reuse, eviction (oldest, max_requests, max_age), and credential-safe output

2. **`autonomous_crawler/tests/test_browser_pool.py`** — 36 focused tests
   - BrowserPoolConfigTests (6): defaults, from_dict, bounds, safe dict
   - BrowserContextLeaseTests (5): record_use, age_seconds, export_storage_state, error handling
   - FingerprintTests (4): deterministic, differs by locale/session_mode, hex format
   - PoolAcquireReleaseTests (8): create, reuse, mismatch, increment, keepalive, close_all
   - PoolEvictionTests (4): when full, oldest removed, max_requests, max_age
   - PoolSafeDictTests (2): safe dict, redacts user_data_dir
   - NativeBrowserRuntimePoolTests (6): acquire/release, context reuse, no pool_id, persistent, failure release, no pool fields

### Modified Files

1. **`autonomous_crawler/runtime/native_browser.py`**
   - Added import for `BrowserContextLease`, `BrowserPoolManager`
   - Added `__init__` with optional `pool` parameter to `NativeBrowserRuntime`
   - Updated `render()` to support pool integration via `browser_config["pool_id"]`
   - Pool lease acquired before session, released in finally/except blocks
   - `engine_result` now includes `pool`, `pool_id`, `pool_request_count` fields

2. **`autonomous_crawler/runtime/__init__.py`**
   - Added exports: `BrowserContextLease`, `BrowserPoolConfig`, `BrowserPoolManager`

### Design Decisions

1. **Fingerprint-based reuse**: Contexts are keyed by a SHA256 fingerprint of user_agent, viewport, locale, timezone, color_scheme, headless, proxy, channel, args, and session_mode. Same fingerprint = reuse context.

2. **Profile ID is caller-chosen**: The `pool_id` in `browser_config` is a free-form string. Callers can use domain names, session names, or any identifier.

3. **No Scrapling dependency**: All browser lifecycle is handled via Playwright. The pool is a CLM-owned abstraction.

4. **Backward compatible**: `NativeBrowserRuntime()` without a pool parameter behaves exactly as before. Pool integration is opt-in via `browser_config["pool_id"]`.

5. **Eviction policy**: Three eviction triggers:
   - Pool full: evict oldest lease
   - Max requests exceeded: evict on next acquire
   - Max age exceeded: evict on next acquire

6. **Credential safety**: `to_safe_dict()` redacts `user_data_dir` paths, proxy URLs, and sensitive headers.

## Tests Run

```
python -m unittest autonomous_crawler.tests.test_browser_pool -v
# 36 tests, all OK (0.062s)

python -m unittest autonomous_crawler.tests.test_native_browser_runtime -v
# 11 tests, all OK (no regression)

python -m unittest autonomous_crawler.tests.test_browser_context -v
# 71 tests, all OK (no regression)

python -m unittest autonomous_crawler.tests.test_scrapling_browser_runtime_contract -v
# 71 tests, all OK (no regression)

# Combined relevant tests: 180 tests, all OK
```

## What Was NOT Changed

- No changes to `native_static.py`, `native_parser.py`, `planner.py`, `strategy.py`
- No site-specific rules written into runtime modules
- No Scrapling import or dependency
- Existing browser tests pass without modification

## Known Risks

1. **No real Playwright integration test**: All pool tests use mocked Playwright. Real browser context reuse may have edge cases (e.g., context closed by Playwright internally).

2. **Fingerprint collision**: If two different profiles produce the same fingerprint, they'll share a context. The fingerprint includes enough fields to make this unlikely but not impossible.

3. **No cross-request cookie isolation**: Reused contexts share cookies and localStorage. If callers need isolation, they should use different `pool_id` values.

4. **Max context age is wall-clock time**: If the system clock changes, age calculations may be off. This is unlikely in practice.

## Next Steps (for supervisor)

1. Run real browser integration tests with pool to verify context reuse in production
2. Consider adding pool metrics to runtime events (reused_count, evicted_count)
3. Consider adding pool health check (ping contexts periodically)
4. Wire pool into BatchRunner for multi-page spider runs

## Supervisor Acceptance

Accepted on 2026-05-14.

Supervisor cleanup: request counting was adjusted so a reused lease is not
counted during `acquire()`. `NativeBrowserRuntime` records usage once per
render attempt, so the second successful render reports `pool_request_count=2`
instead of double-counting.
