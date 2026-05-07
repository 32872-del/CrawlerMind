# 2026-05-07 Job Registry TTL Cleanup - ACCEPTED

## Assignment

`docs/team/assignments/2026-05-07_LLM-2026-001_JOB_REGISTRY_TTL_CLEANUP.md`

## Assignee

Employee ID: `LLM-2026-001`

Project Role: `ROLE-API`

## Scope Reviewed

Reviewed:

```text
autonomous_crawler/api/app.py
autonomous_crawler/tests/test_api_mvp.py
dev_logs/2026-05-07_11-00_job_registry_ttl_cleanup.md
docs/memory/handoffs/2026-05-07_LLM-2026-001_job_registry_ttl_cleanup.md
```

## Verification

```text
python -m unittest autonomous_crawler.tests.test_api_mvp -v
Ran 27 tests
OK

python -m unittest discover autonomous_crawler\tests
Ran 101 tests
OK (skipped=3)

python -m compileall autonomous_crawler run_skeleton.py run_baidu_hot_test.py run_results.py
OK
```

## Accepted Changes

- Added `CLM_JOB_RETENTION_SECONDS` configurable retention period.
- Added `updated_at` timestamps to job records.
- `_update_job()` now refreshes `updated_at` on status changes.
- Added opportunistic cleanup on `POST /crawl` and `GET /crawl/{task_id}`.
- Completed and failed jobs older than the TTL are removed.
- Running jobs are never removed by TTL cleanup.
- Added 7 focused API tests for TTL behavior and env fallback.

## Risks / Follow-Up

- The in-memory registry is still lost on process restart.
- Cleanup scans the in-memory registry inline during request handling; this is
  acceptable for the local MVP.
- Malformed timestamps are treated as stale and cleaned up.

## Supervisor Decision

Accepted.
