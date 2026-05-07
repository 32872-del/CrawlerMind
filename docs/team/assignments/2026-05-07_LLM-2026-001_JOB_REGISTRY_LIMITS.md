# Assignment: Job Registry Concurrency Limits

Assignment ID: `2026-05-07_LLM-2026-001_JOB_REGISTRY_LIMITS`

Employee ID: `LLM-2026-001`

Project Role: `ROLE-API`

Status: `accepted`

Supervisor: `LLM-2026-000`

## Objective

Add a minimal concurrency guard to the FastAPI background job registry.

The current API starts one daemon thread per `/crawl` request. This is
acceptable for a local MVP but can grow without bound. This assignment should
add a small, testable limit without introducing Redis, Celery, or a durable
queue.

## Required Behavior

1. Configure a max number of active background jobs.
2. When active jobs are at the limit, `POST /crawl` should reject the request
   with a clear HTTP error.
3. Completed or failed jobs should no longer count as active.
4. Existing `/crawl/{task_id}` and `/history` behavior must remain compatible.
5. Tests must not require network access or browser binaries.

## Recommended Design

Keep this inside:

```text
autonomous_crawler/api/app.py
```

Use a small constant or environment-variable-backed helper, for example:

```text
CLM_MAX_ACTIVE_JOBS
```

Prefer a default suitable for local development, such as 4.

Use existing in-memory registry and lock. Avoid broader API redesign.

## Owned Files

```text
autonomous_crawler/api/app.py
autonomous_crawler/tests/test_api_mvp.py
dev_logs/2026-05-07_HH-MM_job_registry_limits.md
docs/memory/handoffs/2026-05-07_LLM-2026-001_job_registry_limits.md
```

## Allowed Docs

```text
PROJECT_STATUS.md
docs/reports/2026-05-07_DAILY_REPORT.md
```

## Avoid Unless Approved

```text
autonomous_crawler/agents/
autonomous_crawler/tools/
autonomous_crawler/workflows/
autonomous_crawler/storage/
docs/team/
docs/decisions/
```

Do not introduce external services or new dependencies.

## Required Tests

Add or update tests for:

1. request accepted when active job count is below limit
2. request rejected when active job count reaches limit
3. completed/failed jobs do not count as active
4. existing history and persisted fallback behavior still pass

Run:

```text
python -m unittest autonomous_crawler.tests.test_api_mvp -v
python -m unittest discover autonomous_crawler\tests
python -m compileall autonomous_crawler run_skeleton.py run_baidu_hot_test.py run_results.py
```

## Required Worker Deliverables

1. Code patch.
2. Tests.
3. Developer log.
4. Handoff note.
5. Short completion note:

```text
files changed
tests run
limit behavior
known risks
```

## Supervisor Acceptance Checklist

Supervisor will verify:

- concurrency limit works
- completed/failed jobs are not counted as active
- tests pass
- no storage/worker graph redesign occurred
- docs and handoff exist

Acceptance record target:

```text
docs/team/acceptance/2026-05-07_job_registry_limits_ACCEPTED.md
```
