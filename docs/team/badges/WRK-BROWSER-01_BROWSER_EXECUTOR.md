# Badge: WRK-BROWSER-01

## Identity

Role: Browser / Executor Worker

Mission:

Implement the first Playwright browser fallback path without destabilizing HTTP,
mock, fnspider, storage, or API behavior.

## Primary Ownership

```text
autonomous_crawler/agents/executor.py
autonomous_crawler/tools/browser_fetch.py
autonomous_crawler/tests/test_browser_fallback.py
```

## Shared Files Allowed With Care

```text
PROJECT_STATUS.md
docs/reports/2026-05-06_DAILY_REPORT.md
dev_logs/
```

## Avoid Unless Approved

```text
autonomous_crawler/agents/strategy.py
autonomous_crawler/storage/
run_results.py
autonomous_crawler/api/
autonomous_crawler/workflows/crawl_graph.py
```

## Required Outputs

- Code implementation.
- Mock-based tests that do not require real browser install.
- Developer log.
- Documentation/status updates.

## Required Verification

```text
python -m unittest discover autonomous_crawler\tests
python -m compileall autonomous_crawler run_skeleton.py run_baidu_hot_test.py run_results.py
```

## Non-Goals

- Visual page understanding.
- LLM screenshot analysis.
- API intercept.
- Proxy/Cookie/session manager.
- Background queue.
