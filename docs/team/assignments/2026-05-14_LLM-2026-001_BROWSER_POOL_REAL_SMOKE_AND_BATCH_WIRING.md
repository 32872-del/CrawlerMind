# Assignment: Browser Pool Real Smoke And Batch Wiring

Date: 2026-05-14

Employee: LLM-2026-001

Track: SCRAPLING-ABSORB-2G

## Goal

Turn the accepted native browser session/profile pool from mocked unit coverage
into a real backend capability: prove real Playwright context reuse and prepare
it for multi-page spider/batch runs.

This is still Scrapling hard-capability absorption. Do not add site-specific
selectors or training-site rules.

## Read First

- `docs/plans/2026-05-14_SCRAPLING_ABSORPTION_RECORD.md`
- `docs/team/acceptance/2026-05-14_native_browser_session_pool_ACCEPTED.md`
- `autonomous_crawler/runtime/browser_pool.py`
- `autonomous_crawler/runtime/native_browser.py`
- `autonomous_crawler/runners/spider_runner.py`
- `autonomous_crawler/tests/test_browser_pool.py`
- `autonomous_crawler/tests/test_native_browser_runtime.py`

## Write Scope

- `autonomous_crawler/runtime/browser_pool.py`
- `autonomous_crawler/runtime/native_browser.py`
- `autonomous_crawler/runners/spider_runner.py` only if needed for pool injection
- `autonomous_crawler/tests/test_browser_pool.py`
- `autonomous_crawler/tests/test_native_browser_runtime.py`
- optional new focused smoke script:
  `run_browser_pool_smoke_2026_05_14.py`
- `dev_logs/development/2026-05-14_LLM-2026-001_browser_pool_real_smoke.md`
- `docs/memory/handoffs/2026-05-14_LLM-2026-001_browser_pool_real_smoke.md`

## Required Work

1. Add a deterministic real-browser smoke that uses a local HTTP server and
   `NativeBrowserRuntime(pool=BrowserPoolManager(...))`.
2. Prove two sequential requests with the same `pool_id` reuse the same browser
   context and report `pool_request_count=1` then `2`.
3. Add a failure/quarantine behavior for failed contexts, or clearly implement a
   `mark_failed` path so navigation/selector failures do not keep a bad context
   alive blindly.
4. Expose pool event evidence such as `pool_acquire`, `pool_reuse`,
   `pool_release`, and `pool_evict` through runtime events or pool-safe dicts.
5. If feasible without broad refactor, allow `SpiderRuntimeProcessor` or its
   caller to pass a shared pool into native browser runs.

## Acceptance

- Focused tests pass.
- Real local browser smoke passes or is skipped cleanly when Playwright browser
  binaries are not installed.
- No site-specific crawl logic is added.
- No Scrapling import is introduced.
- Pool metrics are credential-safe.
