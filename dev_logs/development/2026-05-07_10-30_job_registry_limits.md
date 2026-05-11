# 2026-05-07 10:30 - Job Registry Concurrency Limits

## Goal

Add a minimal concurrency guard to the FastAPI background job registry.
Assignment: `2026-05-07_LLM-2026-001_JOB_REGISTRY_LIMITS`.

Employee: LLM-2026-001 / Worker Alpha
Project Role: ROLE-API / API Job Worker

## Changes

- Modified `autonomous_crawler/api/app.py`:
  - Added `import os`
  - Added `_max_active_jobs()`: reads `CLM_MAX_ACTIVE_JOBS` env var, defaults
    to 4, falls back to 4 on invalid or zero values
  - Added `_count_active_jobs()`: counts jobs with `status == "running"` under
    the existing `_jobs_lock`
  - `POST /crawl` now checks `_count_active_jobs() >= _max_active_jobs()` before
    registering a new job; returns HTTP 429 with detail `"too many active jobs
    (N max)"` when at the limit

- Modified `autonomous_crawler/tests/test_api_mvp.py`:
  - Added `import threading`
  - Added `ConcurrencyLimitTests` (9 tests):
    1. `test_accepted_when_below_limit` - POST succeeds when active < limit
    2. `test_rejected_when_at_limit` - POST returns 429 when active == limit
    3. `test_completed_jobs_do_not_count_as_active` - completed jobs free slots
    4. `test_failed_jobs_do_not_count_as_active` - failed jobs free slots
    5. `test_count_active_jobs_counts_only_running` - unit test for counter
    6. `test_max_active_jobs_reads_env_var` - reads CLM_MAX_ACTIVE_JOBS
    7. `test_max_active_jobs_defaults_to_4` - default when unset
    8. `test_max_active_jobs_falls_back_on_invalid` - fallback on bad value
    9. `test_max_active_jobs_falls_back_on_zero` - fallback on zero

- Did NOT modify: agents/, tools/, workflows/, storage/, docs/team/,
  docs/decisions/

## Verification

API tests:

```text
python -m unittest autonomous_crawler.tests.test_api_mvp -v
Ran 19 tests in 3.072s
OK
```

Full test suite:

```text
python -m unittest discover autonomous_crawler\tests
Ran 93 tests (skipped=3)
OK
```

Compile check:

```text
python -m compileall autonomous_crawler run_skeleton.py run_baidu_hot_test.py run_results.py
OK
```

## Result

POST /crawl now rejects new requests with HTTP 429 when the number of active
(running) background jobs reaches the configured limit. The limit defaults to
4 and is configurable via `CLM_MAX_ACTIVE_JOBS` environment variable. Completed
and failed jobs do not count toward the limit, so slots are freed as jobs
finish.

## Known Risks

- In-memory registry is still lost on process restart. This assignment did not
  address persistence (out of scope).
- No rate limiting beyond the concurrency cap.

## Supervisor Follow-Up

Supervisor tightened the limit gate after submission by adding
`_try_register_job()`, which checks active jobs and registers the new job under
the same lock.

## Next Step

Submit for supervisor acceptance. Await further assignment.
