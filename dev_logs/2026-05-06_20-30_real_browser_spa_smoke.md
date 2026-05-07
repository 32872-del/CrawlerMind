# 2026-05-06 20:30 - Real Browser SPA Smoke Test

## Goal

Add a real browser smoke validation for the Playwright browser fallback path
using a local deterministic SPA fixture. Assignment:
`2026-05-06_LLM-2026-001_REAL_BROWSER_SPA_SMOKE`.

Employee: LLM-2026-001 / Worker Alpha
Project Role: ROLE-BROWSER / Browser Executor Worker

## Changes

- Created `autonomous_crawler/tests/test_real_browser_smoke.py`:
  - `SPA_HTML` fixture: minimal HTML page that renders nothing server-side;
    JavaScript generates all content via `setTimeout` after 100ms
  - `_SPAHandler`: `SimpleHTTPRequestHandler` subclass serving SPA_HTML for
    any GET request; suppresses log output
  - `_find_free_port()`: binds to port 0 to get an available port from the OS
  - `_should_skip()`: returns skip reason if:
    1. env var `AUTONOMOUS_CRAWLER_RUN_BROWSER_SMOKE` is not set
    2. `playwright` is not installed
    3. Playwright browser binaries cannot launch (e.g. not installed)
  - `TestRealBrowserSPA` (3 tests):
    1. `test_browser_sees_js_rendered_content` - verifies Playwright can see
       DOM elements that only exist after JavaScript execution (title, body
       text, list items)
    2. `test_browser_wait_for_selector` - verifies `wait_selector` blocks
       until a specific JS-generated element appears (3rd list item)
    3. `test_screenshot_capture` - verifies screenshot is saved to the
       `screenshots/` directory when `screenshot=True`
  - Each test starts a local `HTTPServer` in a daemon thread, runs the browser
    fetch, asserts results, then shuts down the server in `finally`
  - Tests skip cleanly when Playwright or browser binaries are unavailable

- Did NOT modify: agents/, tools/, browser_fetch.py, executor.py,
  crawl_graph.py, api/, storage/

## Verification

Browser fallback tests (no regression):

```text
python -m unittest autonomous_crawler.tests.test_browser_fallback -v
Ran 14 tests
OK
```

Full test suite:

```text
python -m unittest discover autonomous_crawler\tests
Ran 84 tests (skipped=3)
OK
```

The 3 skipped tests are the real browser smoke tests being skipped because the
env var is not set. This is the expected behavior for the normal suite.

Compile check:

```text
python -m compileall autonomous_crawler run_skeleton.py run_baidu_hot_test.py run_results.py
OK
```

Real browser smoke (with env var):

```text
set AUTONOMOUS_CRAWLER_RUN_BROWSER_SMOKE=1
python -m unittest autonomous_crawler.tests.test_real_browser_smoke -v
Ran 3 tests in 8.998s
OK
```

All 3 tests passed. JS-rendered content was correctly visible to Playwright.
ResourceWarning about unclosed sockets is a Playwright internal issue, not
from our code.

## Result

Real browser smoke validates the Playwright fallback end-to-end against a
local JS-rendered page. The normal test suite skips these 3 tests cleanly
when Playwright or browser binaries are not available. No external website
or network access beyond localhost is required.

## Known Risks

- Playwright browser binaries must be installed (`playwright install chromium`)
  for the smoke tests to actually run. Without them, tests skip.
- ResourceWarning from Playwright internals about unclosed sockets; not
  actionable from our code.
- Each test launches a full headless browser, so the smoke suite takes ~9s.
  This is acceptable for opt-in smoke runs but should not slow the normal suite
  (it doesn't, since tests are skipped by default).

## Next Step

Submit for supervisor acceptance. Await further assignment.
