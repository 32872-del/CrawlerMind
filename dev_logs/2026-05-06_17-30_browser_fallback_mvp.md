# 2026-05-06 17:30 - Browser Fallback MVP

## Goal

Add the first minimal Playwright browser fallback path to the executor, so that
when `crawl_strategy["mode"] == "browser"` the workflow renders JS-heavy pages
instead of returning empty HTML. Priority 4 from the short-term plan.

## Changes

- Added `autonomous_crawler/tools/browser_fetch.py`:
  - `BrowserFetchResult` dataclass (url, html, status, error, screenshot_path)
  - `fetch_rendered_html()` using Playwright chromium headless
  - Supports `wait_selector`, `wait_until` (domcontentloaded/load/networkidle),
    `timeout_ms`, and `screenshot` options
  - Graceful fallback when playwright is not installed
  - Screenshots saved to `autonomous_crawler/tools/runtime/screenshots/`

- Modified `autonomous_crawler/agents/executor.py`:
  - Added `mode == "browser"` branch after fnspider check and before mock checks
  - Reads strategy options: wait_selector, wait_until, timeout_ms, screenshot
  - Returns rendered HTML on success, error_log on failure
  - Existing HTTP/mock/fnspider paths unchanged

- Added `autonomous_crawler/tests/test_browser_fallback.py` (16 tests):
  - `TestBrowserSuccessPath` (4 tests): rendered HTML, strategy option passing,
    screenshot path, redirect following
  - `TestBrowserFailurePath` (3 tests): timeout, crash, playwright not installed
  - `TestExistingPathsUnchanged` (3 tests): mock catalog, mock ranking, unsupported scheme
  - `TestBrowserFetchUnit` (4 tests): direct browser_fetch module tests with mocked
    Playwright (success, exception, wait_for_selector, screenshot)

- Updated `PROJECT_STATUS.md`: test count, completed items, next tasks
- Updated `docs/reports/2026-05-06_DAILY_REPORT.md`
- Updated `docs/plans/2026-05-05_SHORT_TERM_PLAN.md`: Priority 4 marked done

## Verification

Full test suite:

```text
python -m unittest discover autonomous_crawler\tests
Ran 74 tests
OK
```

Compile check:

```text
python -m compileall autonomous_crawler run_skeleton.py run_baidu_hot_test.py run_results.py
OK
```

Focused browser tests:

```text
python -m unittest autonomous_crawler.tests.test_browser_fallback -v
Ran 16 tests
OK
```

## Result

The executor now has four execution paths: HTTP, browser (Playwright), mock, and
fnspider. Browser mode is activated when strategy sets `mode="browser"` (SPA or
anti-bot detected by recon). All existing tests continue to pass.

## Next Step

Priority 5: LLM Integration Design - optional LLM Planner/Strategy with
deterministic fallback. Or coordinate with Storage/CLI Codex on shared
interfaces.
