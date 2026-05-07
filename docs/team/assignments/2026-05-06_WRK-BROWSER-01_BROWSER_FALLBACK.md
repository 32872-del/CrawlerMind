# Assignment: Browser Fallback MVP

Assignment ID: 2026-05-06_WRK-BROWSER-01_BROWSER_FALLBACK

Employee ID: `LLM-2026-001`

Project Role: `ROLE-BROWSER`

Status: accepted

Legacy Note: This assignment uses the older role-oriented worker ID format.
The accepted project-truth record is
`docs/team/acceptance/2026-05-06_browser_fallback_ACCEPTED.md`.

Supervisor: `SUP-CODEX-01`

Reference Plan:

```text
docs/plans/2026-05-06_BROWSER_FALLBACK_ASSIGNMENT.md
```

## Objective

Implement the first minimal Playwright browser fallback path for Executor.

When:

```python
crawl_strategy["mode"] == "browser"
```

Executor should fetch rendered HTML through Playwright and return it in
`raw_html`.

## Owned Files

```text
autonomous_crawler/agents/executor.py
autonomous_crawler/tools/browser_fetch.py
autonomous_crawler/tests/test_browser_fallback.py
```

## Avoid Unless Approved

```text
autonomous_crawler/agents/strategy.py
autonomous_crawler/storage/
run_results.py
autonomous_crawler/api/
autonomous_crawler/workflows/crawl_graph.py
```

## Required Tests

Mock-based tests:

1. Browser success path.
2. Browser failure path.
3. Existing HTTP/mock/fnspider paths remain passing.

Do not make the full test suite depend on a real browser install.

## Required Verification

```text
python -m unittest discover autonomous_crawler\tests
python -m compileall autonomous_crawler run_skeleton.py run_baidu_hot_test.py run_results.py
```

## Required Worker Deliverables

1. Code patch.
2. Tests.
3. Developer log:

```text
dev_logs/2026-05-06_HH-MM_browser_fallback_mvp.md
```

4. Updates to:

```text
PROJECT_STATUS.md
docs/reports/2026-05-06_DAILY_REPORT.md
```

## Supervisor Acceptance Checklist

Supervisor will verify:

- Browser mode works through mocked tool path.
- HTTP/mock/fnspider paths are not broken.
- Full tests pass.
- Compile check passes.
- Scope stayed inside assignment.
- Dev log exists.
- Daily report and project status are accurate.

Acceptance record will be written to:

```text
docs/team/acceptance/2026-05-06_browser_fallback_ACCEPTED.md
```
