# Handoff: Job Registry Concurrency Limits

Employee: LLM-2026-001
Date: 2026-05-07
Assignment: `2026-05-07_LLM-2026-001_JOB_REGISTRY_LIMITS`

## What Was Done

Added a concurrency guard to the FastAPI background job registry. `POST /crawl`
now rejects with HTTP 429 when active jobs reach the configured limit
(`CLM_MAX_ACTIVE_JOBS`, default 4). Completed and failed jobs do not count.

## Files Changed

- `autonomous_crawler/api/app.py` - added `_max_active_jobs()`,
  `_count_active_jobs()`, and 429 check in POST /crawl
- `autonomous_crawler/tests/test_api_mvp.py` - added 9 concurrency limit tests
- `dev_logs/2026-05-07_10-30_job_registry_limits.md`
- `docs/memory/handoffs/2026-05-07_LLM-2026-001_job_registry_limits.md`

## Test Status

19 API tests pass. Full suite: 93 tests (3 skipped). Compile check: OK.

## What Is NOT Changed

- No persistence for the job registry (still in-memory).
- No rate limiting beyond the concurrency cap.
- No changes to agents, tools, workflows, storage, or docs/decisions.

## Known Open Issues

- ADR-003 notes that concurrency limits should be added before long-running
  service use. This satisfies that follow-up partially.
- No cleanup/TTL for completed jobs in the in-memory registry.

## Supervisor Follow-Up

Supervisor tightened the implementation after submission so active-job counting
and job registration happen under the same `_jobs_lock` through
`_try_register_job()`.

## Environment

- `CLM_MAX_ACTIVE_JOBS` - max concurrent active background jobs (default: 4)
