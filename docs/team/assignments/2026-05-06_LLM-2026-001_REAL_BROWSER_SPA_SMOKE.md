# Assignment: Real Browser SPA Smoke

Assignment ID: `2026-05-06_LLM-2026-001_REAL_BROWSER_SPA_SMOKE`

Employee ID: `LLM-2026-001`

Project Role: `ROLE-BROWSER`

Status: `accepted`

Supervisor: `LLM-2026-000`

## Objective

Add a real browser smoke validation for the Playwright browser fallback path.

The current browser fallback is covered by mock/unit tests. This assignment
should prove the project can render JavaScript-generated content end to end
without depending on an external website.

Use a local deterministic SPA fixture, not a public web page.

## Required Behavior

Create a smoke test or runnable smoke script that:

1. serves a tiny local HTML page that renders content with JavaScript after page
   load
2. uses the existing browser fallback path to fetch rendered HTML
3. verifies the rendered HTML contains JavaScript-generated content
4. skips cleanly when Playwright or browser binaries are unavailable
5. does not require network access beyond localhost

The normal full test suite must remain usable on machines without Playwright
browsers installed.

## Recommended Design

Prefer one of these approaches:

```text
Option A:
  autonomous_crawler/tests/test_real_browser_smoke.py
  - unittest test skipped unless an env var is set, for example:
    AUTONOMOUS_CRAWLER_RUN_BROWSER_SMOKE=1

Option B:
  run_browser_spa_smoke.py
  - standalone smoke script that reports skipped/pass/fail
  - optional focused test around helper logic only
```

Option A is preferred if it can skip cleanly and avoid slowing the normal suite.

Use Python standard library `http.server` or equivalent lightweight local
server. Avoid adding new dependencies.

## Owned Files

You may create or edit:

```text
autonomous_crawler/tests/test_real_browser_smoke.py
run_browser_spa_smoke.py
dev_logs/2026-05-06_HH-MM_real_browser_spa_smoke.md
PROJECT_STATUS.md
docs/reports/2026-05-06_DAILY_REPORT.md
```

You may read:

```text
autonomous_crawler/tools/browser_fetch.py
autonomous_crawler/agents/executor.py
autonomous_crawler/tests/test_browser_fallback.py
```

## Avoid Unless Approved

Do not edit:

```text
autonomous_crawler/agents/executor.py
autonomous_crawler/tools/browser_fetch.py
autonomous_crawler/workflows/crawl_graph.py
autonomous_crawler/agents/
autonomous_crawler/tools/
autonomous_crawler/api/
autonomous_crawler/storage/
docs/team/
```

This is a smoke validation assignment, not a browser fallback redesign.

## Required Tests

Run:

```text
python -m unittest autonomous_crawler.tests.test_browser_fallback -v
python -m unittest discover autonomous_crawler\tests
python -m compileall autonomous_crawler run_skeleton.py run_baidu_hot_test.py run_results.py
```

If you add `run_browser_spa_smoke.py`, include it in compileall:

```text
python -m compileall autonomous_crawler run_skeleton.py run_baidu_hot_test.py run_results.py run_browser_spa_smoke.py
```

If browser binaries are installed, also run the real smoke:

```text
set AUTONOMOUS_CRAWLER_RUN_BROWSER_SMOKE=1
python -m unittest autonomous_crawler.tests.test_real_browser_smoke -v
```

or:

```text
python run_browser_spa_smoke.py
```

If browser binaries are not installed, report the skip clearly.

## Required Worker Deliverables

1. Smoke test or smoke script.
2. Developer log.
3. Updates to:

```text
PROJECT_STATUS.md
docs/reports/2026-05-06_DAILY_REPORT.md
```

4. Short completion note listing:

```text
files changed
tests run
browser smoke result: pass/skip/fail
known risks
```

## Supervisor Acceptance Checklist

Supervisor will verify:

- normal test suite still passes without browser dependency
- smoke validates JavaScript-rendered local content
- smoke skips cleanly when Playwright/browser is unavailable
- no executor/browser core redesign occurred
- docs and dev log are updated

Acceptance record target:

```text
docs/team/acceptance/2026-05-06_real_browser_spa_smoke_ACCEPTED.md
```
