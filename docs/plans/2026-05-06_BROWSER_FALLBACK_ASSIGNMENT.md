# 2026-05-06 Browser Fallback Assignment

## Role

You are assigned to the **Browser / Executor module**.

The current project already has:

- LangGraph workflow.
- HTTP executor.
- Mock fixtures.
- SQLite result store.
- FastAPI MVP.
- Result CLI.
- Error-path hardening.
- Explicit fnspider routing.

Your task is to add the first minimal Playwright browser fallback path.

## Ownership

You own:

```text
autonomous_crawler/agents/executor.py
autonomous_crawler/tools/browser_fetch.py
autonomous_crawler/tests/test_browser_fallback.py
dev_logs/
PROJECT_STATUS.md
docs/reports/2026-05-06_DAILY_REPORT.md
```

Avoid editing unless absolutely necessary:

```text
autonomous_crawler/agents/strategy.py
autonomous_crawler/storage/
run_results.py
autonomous_crawler/api/
autonomous_crawler/workflows/crawl_graph.py
```

If you must touch a shared file, record why in your developer log.

## Goal

When `crawl_strategy["mode"] == "browser"`, Executor should use Playwright to
fetch rendered HTML instead of treating browser mode as future work.

This is a minimal MVP. Do not attempt full visual understanding yet.

## Required Behavior

Implement:

1. Open a page with Playwright.
2. Wait for `domcontentloaded` or configured `wait_until`.
3. Optionally wait for `wait_selector`.
4. Return rendered HTML.
5. Optionally save a screenshot path if screenshot support is easy and clean.
6. On success, Executor returns:

```python
{
    "status": "executed",
    "visited_urls": [final_url],
    "raw_html": {final_url: rendered_html},
    "api_responses": [],
}
```

7. On failure, Executor returns:

```python
{
    "status": "failed",
    "visited_urls": [target_url],
    "raw_html": {},
    "api_responses": [],
    "error_log": [...],
}
```

8. Existing HTTP, mock, and fnspider paths must continue working.

## Suggested Implementation

Add:

```text
autonomous_crawler/tools/browser_fetch.py
```

Suggested shape:

```python
from dataclasses import dataclass

@dataclass
class BrowserFetchResult:
    url: str
    html: str
    status: str
    error: str = ""
    screenshot_path: str = ""

def fetch_rendered_html(
    url: str,
    wait_selector: str = "",
    wait_until: str = "domcontentloaded",
    timeout_ms: int = 30000,
    screenshot: bool = False,
) -> BrowserFetchResult:
    ...
```

Then in `executor.py`:

```python
if mode == "browser":
    result = fetch_rendered_html(...)
    ...
```

Read browser options from `crawl_strategy`, for example:

```python
wait_selector = strategy.get("wait_selector", "")
wait_until = strategy.get("wait_until", "domcontentloaded")
timeout_ms = strategy.get("timeout_ms", 30000)
screenshot = bool(strategy.get("screenshot", False))
```

## Test Requirements

Do not make the full test suite depend on a real browser install or external
network.

Use mocks for required tests:

1. Browser success path:
   - patch `fetch_rendered_html`
   - `mode="browser"`
   - expect `status == "executed"`
   - expect `raw_html` contains returned HTML
   - expect `visited_urls` contains final URL

2. Browser failure path:
   - patch `fetch_rendered_html` to return failure
   - expect `status == "failed"`
   - expect `error_log` includes error

3. Existing path safety:
   - existing HTTP/mock/fnspider tests must still pass

Optional:

- Add a real Playwright smoke test only if it is skipped automatically when
  browser dependencies are unavailable.

## Verification Commands

Run:

```text
python -m unittest discover autonomous_crawler\tests
python -m compileall autonomous_crawler run_skeleton.py run_baidu_hot_test.py run_results.py
```

If safe, also run:

```text
python run_baidu_hot_test.py
```

## Documentation Requirements

Write a developer log:

```text
dev_logs/development/2026-05-06_HH-MM_browser_fallback_mvp.md
```

Required sections:

```text
# 2026-05-06 HH:MM - Browser Fallback MVP

## Goal
## Changes
## Verification
## Result
## Next Step
```

Update:

```text
PROJECT_STATUS.md
docs/reports/2026-05-06_DAILY_REPORT.md
```

## Non-Goals

Do not implement these in this task:

- Visual page understanding.
- Multimodal LLM screenshot analysis.
- API intercept mode.
- Proxy pool.
- Cookie/session manager.
- CAPTCHA handling.
- Background job queue.
- Site mental model.
- Selector self-healing.

This assignment is only for the first browser executor MVP.

## Coordination Notes

Other recent modules:

- Storage/CLI: `run_results.py`
- Error paths: `test_error_paths.py`, extractor hardening, recon fail-fast graph
- Fnspider routing: explicit engine routing in `strategy.py`

Avoid broad refactors. Keep the patch small, testable, and additive.
