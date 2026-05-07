# 2026-05-06 19:00 - FastAPI Background Job Execution

## Goal

Convert the FastAPI `/crawl` endpoint from synchronous blocking to background
job execution. Assignment: `2026-05-06_LLM-2026-001_FASTAPI_BACKGROUND_JOBS`.

Employee: LLM-2026-001 / Worker Alpha
Project Role: ROLE-API / API Job Worker

## Changes

- Modified `autonomous_crawler/api/app.py`:
  - Added in-memory job registry (`_jobs` dict with `threading.Lock`)
  - `_register_job()`, `_update_job()`, `_get_job()`, `_remove_job()` helpers
  - `POST /crawl` now generates task_id, registers job as "running", starts
    `threading.Thread(daemon=True)` for background execution, returns immediately
  - `_background_crawl()` runs workflow, persists via `save_crawl_result`,
    updates registry status; catches exceptions and marks job as "failed"
  - `GET /crawl/{task_id}` checks in-memory registry first, then falls back
    to persisted SQLite result, then 404
  - `GET /history` unchanged (reads from SQLite)
  - Bumped version to 0.2.0
  - Used only standard library (`threading`, `uuid`, `datetime`)

- Rewrote `autonomous_crawler/tests/test_api_mvp.py`:
  - `test_post_crawl_returns_immediately_with_running_status` - POST returns
    "running" before workflow completes (uses slow mock)
  - `test_get_crawl_returns_running_task_from_registry` - GET shows running
    task while background thread is blocked
  - `test_background_completion_persists_result` - after thread finishes,
    result is persisted and queryable
  - `test_background_exception_becomes_queryable_failed_task` - workflow
    exception becomes "failed" status with error message
  - `test_get_crawl_returns_404_for_unknown_task` - unchanged
  - `test_history_endpoint_returns_persisted_items` - unchanged
  - `test_get_crawl_falls_back_to_persisted_result` - SQLite fallback
  - `JobRegistryTests` (3 tests) - unit tests for registry helpers

- Did NOT modify: agents/, tools/, crawl_graph.py, browser_fetch.py,
  fnspider routing, storage/result_store.py, run_results.py

## Verification

Full test suite:

```text
python -m unittest discover autonomous_crawler\tests
Ran 81 tests
OK
```

Compile check:

```text
python -m compileall autonomous_crawler run_skeleton.py run_baidu_hot_test.py run_results.py
OK
```

Focused API tests:

```text
python -m unittest autonomous_crawler.tests.test_api_mvp -v
Ran 10 tests
OK
```

## Result

POST /crawl now returns immediately with status "running". Background thread
runs the workflow and persists results. GET /crawl/{task_id} shows running
state from memory, then falls back to SQLite after completion. Failed
background jobs are queryable with error details.

## Known Risks

- In-memory registry is lost on process restart. Jobs that completed in SQLite
  are still accessible, but in-flight jobs are lost.
- No rate limiting or max concurrent jobs guard. A burst of requests could
  spawn many threads.
- Thread daemon=True means background jobs are killed on process exit without
  waiting for completion.
- No job cleanup/TTL for the in-memory registry. Long-running processes will
  accumulate entries.

## Next Step

Submit for supervisor acceptance. Await further assignment.
