# SCRAPLING-ABSORB-2G: Browser Pool Real Smoke And Batch Wiring

Date: 2026-05-14
Worker: LLM-2026-001
Status: COMPLETE

## Deliverables

- Updated `autonomous_crawler/runtime/browser_pool.py` — mark_failed, events
- Updated `autonomous_crawler/runtime/native_browser.py` — pool events, persistent Playwright
- Updated `autonomous_crawler/runners/spider_runner.py` — pool injection
- Updated `autonomous_crawler/tests/test_browser_pool.py` — 54 tests (18 new)
- `run_browser_pool_smoke_2026_05_14.py` — real browser smoke

## Key Additions

| Feature | Location | Purpose |
|---|---|---|
| `mark_failed(profile_id, error)` | browser_pool.py | Quarantine failed contexts |
| `_events` list | browser_pool.py | Pool event tracking |
| `pool_acquire` / `pool_reuse` / `pool_release` / `pool_mark_failed` | native_browser.py | RuntimeEvent evidence |
| Persistent `self._pw` | native_browser.py | Keep Playwright alive for pool reuse |
| `runtime.close()` | native_browser.py | Cleanup for persistent Playwright |
| `pool` parameter | spider_runner.py | Inject pool into SpiderRuntimeProcessor |

## Usage

```python
from autonomous_crawler.runtime import NativeBrowserRuntime, BrowserPoolManager, BrowserPoolConfig

pool = BrowserPoolManager(BrowserPoolConfig(keepalive_on_release=True))
runtime = NativeBrowserRuntime(pool=pool)

request = RuntimeRequest.from_dict({
    "url": "https://example.com",
    "browser_config": {"pool_id": "my-profile"},
})
response = runtime.render(request)
# response.runtime_events includes pool_acquire, pool_release
# response.engine_result["pool_request_count"] == 1

response2 = runtime.render(request)
# response.runtime_events includes pool_reuse, pool_release
# response2.engine_result["pool_request_count"] == 2

# Cleanup
runtime.close()
```

## SpiderRuntimeProcessor with Pool

```python
from autonomous_crawler.runners.spider_runner import SpiderRuntimeProcessor
from autonomous_crawler.runtime import BrowserPoolManager

pool = BrowserPoolManager()
processor = SpiderRuntimeProcessor(
    run_id="test-run",
    browser_runtime=NativeBrowserRuntime(),
    pool=pool,  # injected into browser_runtime._pool
)
```

## Failure Quarantine

When a browser operation fails (navigation timeout, selector miss, etc.):
1. `NativeBrowserRuntime` calls `pool.mark_failed(pool_id, error=str(exc))`
2. The failed context is closed and removed from the pool
3. A `pool_mark_failed` RuntimeEvent is emitted
4. Next request with same `pool_id` creates a fresh context

## Pool Events

Events are in `response.runtime_events` (RuntimeEvent objects) and `pool.to_safe_dict()["events"]` (raw dicts).

## Verification

```bash
python -m unittest autonomous_crawler.tests.test_browser_pool -v  # 54 tests OK
python run_browser_pool_smoke_2026_05_14.py                       # [PASS]
```

## Supervisor Acceptance

Pending.
