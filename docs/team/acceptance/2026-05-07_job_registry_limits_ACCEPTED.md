# 2026-05-07 Job Registry Concurrency Limits - ACCEPTED

## Assignment

`docs/team/assignments/2026-05-07_LLM-2026-001_JOB_REGISTRY_LIMITS.md`

## Assignee

Employee ID: `LLM-2026-001`

Project Role: `ROLE-API`

## Scope Reviewed

Reviewed:

```text
autonomous_crawler/api/app.py
autonomous_crawler/tests/test_api_mvp.py
dev_logs/2026-05-07_10-30_job_registry_limits.md
docs/memory/handoffs/2026-05-07_LLM-2026-001_job_registry_limits.md
PROJECT_STATUS.md
docs/reports/2026-05-07_DAILY_REPORT.md
```

Supervisor tightened the submitted implementation by making active-job counting
and registration atomic under the same `_jobs_lock`.

## Verification

```text
python -m unittest autonomous_crawler.tests.test_api_mvp -v
Ran 20 tests
OK

python -m unittest discover autonomous_crawler\tests
Ran 94 tests
OK (skipped=3)

python -m compileall autonomous_crawler run_skeleton.py run_baidu_hot_test.py run_results.py
OK
```

## Accepted Changes

- Added `CLM_MAX_ACTIVE_JOBS` configurable active-job limit.
- Added active job counting for `running` jobs.
- Added `_try_register_job()` so limit check and job registration happen under
  one lock.
- `POST /crawl` returns HTTP 429 when active jobs reach the configured limit.
- Completed and failed jobs do not count as active.
- API tests cover limit behavior, env parsing, fallback defaults, and atomic
  registration.

## Risks / Follow-Up

- Registry is still in-memory and lost on restart.
- Completed/failed registry entries do not have TTL cleanup yet.
- This is a concurrency cap, not request rate limiting.

## Supervisor Decision

Accepted.
