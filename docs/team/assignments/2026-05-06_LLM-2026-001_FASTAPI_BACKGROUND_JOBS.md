# Assignment: FastAPI Background Job Execution

Assignment ID: `2026-05-06_LLM-2026-001_FASTAPI_BACKGROUND_JOBS`

Employee ID: `LLM-2026-001`

Project Role: `ROLE-API`

Status: `accepted`

Supervisor: `LLM-2026-000`

## Objective

Convert the FastAPI `/crawl` boundary from a synchronous blocking request into
an initial background-job MVP.

The API should accept a crawl request quickly, return a `task_id` and a
non-final status, then allow clients to query the task through the existing
`GET /crawl/{task_id}` endpoint.

Keep this as a local MVP. Do not introduce Redis, Celery, or external services.

## Required Behavior

1. `POST /crawl` should enqueue/start work in the background and return without
   waiting for the full workflow to finish.
2. Returned response must include:

```text
task_id
status
item_count
is_valid
```

3. Initial status should be one of:

```text
queued
running
accepted
```

Use one consistent label and document it in the test.

4. `GET /crawl/{task_id}` should return a useful task record while work is not
   finished.
5. When the workflow finishes, the final state must still be persisted through
   the existing result store.
6. Existing completed-task reads and `/history` behavior must remain compatible.
7. Background failures must become queryable task failures instead of being
   silently swallowed.

## Recommended Design

Prefer a small in-process job registry in `autonomous_crawler/api/app.py`.

Acceptable implementation:

```text
POST /crawl
  -> create task_id
  -> record queued/running state in memory
  -> submit worker function
  -> return immediately

worker function
  -> run_crawl_workflow(...)
  -> save_crawl_result(final_state)
  -> update in-memory status as completed/failed

GET /crawl/{task_id}
  -> first try persisted result
  -> if missing, return in-memory queued/running/failed task
  -> otherwise 404
```

Use only standard-library concurrency unless there is a clear reason not to.

## Owned Files

```text
autonomous_crawler/api/app.py
autonomous_crawler/tests/test_api_mvp.py
```

## Allowed If Necessary

```text
autonomous_crawler/storage/result_store.py
```

Only touch storage if the API cannot expose pending/failed jobs cleanly from
`app.py`. Keep changes minimal and add focused tests.

## Avoid Unless Approved

```text
autonomous_crawler/agents/
autonomous_crawler/tools/
autonomous_crawler/workflows/crawl_graph.py
run_baidu_hot_test.py
run_results.py
```

Do not change crawler behavior, extractor behavior, strategy rules, browser
fallback, or fnspider routing in this assignment.

## Required Tests

Update or add tests covering:

1. `POST /crawl` returns before the workflow result is saved.
2. `GET /crawl/{task_id}` can show a pending/running task.
3. Background completion persists the final state.
4. Background exception becomes a queryable failed task.
5. Existing `GET /history` still returns persisted history.

Tests must not depend on network access or real browser installation.

## Required Verification

Run:

```text
python -m unittest discover autonomous_crawler\tests
python -m compileall autonomous_crawler run_skeleton.py run_baidu_hot_test.py run_results.py
```

If the full suite emits the known browser warning, that is acceptable only if
all tests pass.

## Required Worker Deliverables

1. Code patch.
2. Tests.
3. Developer log:

```text
dev_logs/development/2026-05-06_HH-MM_fastapi_background_jobs.md
```

4. Updates to:

```text
PROJECT_STATUS.md
docs/reports/2026-05-06_DAILY_REPORT.md
```

5. Short completion note listing:

```text
files changed
tests run
known risks
```

## Supervisor Acceptance Checklist

Supervisor will verify:

- `/crawl` no longer blocks on normal request handling.
- Pending/running job state is queryable.
- Completed jobs are still persisted in SQLite.
- Failed background jobs are visible through the API.
- Scope stayed inside the assignment.
- Full tests pass.
- Compile check passes.
- Dev log and docs are updated.

Acceptance record target:

```text
docs/team/acceptance/2026-05-06_fastapi_background_jobs_ACCEPTED.md
```
