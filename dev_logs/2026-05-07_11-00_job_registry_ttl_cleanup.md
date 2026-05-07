# 2026-05-07 11:00 - Job Registry TTL Cleanup

## Goal

Add a cleanup mechanism for completed/failed in-memory job registry entries.
Assignment: `2026-05-07_LLM-2026-001_JOB_REGISTRY_TTL_CLEANUP`.

Employee: LLM-2026-001 / Worker Alpha
Project Role: ROLE-API / API Job Worker

## Changes

- Modified `autonomous_crawler/api/app.py`:
  - Added `_job_retention_seconds()`: reads `CLM_JOB_RETENTION_SECONDS` env var,
    defaults to 3600, falls back on invalid/zero values
  - Added `_parse_iso()`: parses ISO timestamp to epoch seconds, returns 0.0
    on failure (so jobs with missing timestamps get cleaned up)
  - Added `_cleanup_stale_jobs()`: removes completed/failed jobs whose
    `updated_at` is older than the TTL; never removes running jobs
  - Updated `_new_job_record()`: includes `updated_at` field alongside
    `created_at`
  - Updated `_update_job()`: automatically stamps `updated_at` on every update
  - `POST /crawl`: calls `_cleanup_stale_jobs()` before registering
  - `GET /crawl/{task_id}`: calls `_cleanup_stale_jobs()` before lookup

- Modified `autonomous_crawler/tests/test_api_mvp.py`:
  - Added imports for `_cleanup_stale_jobs`, `_job_retention_seconds`
  - Added `TTLcleanupTests` (7 tests):
    1. `test_completed_job_older_than_ttl_is_removed` - stale completed removed
    2. `test_failed_job_older_than_ttl_is_removed` - stale failed removed
    3. `test_running_job_older_than_ttl_is_not_removed` - running never removed
    4. `test_recent_completed_job_remains_queryable` - recent stays
    5. `test_invalid_ttl_env_var_falls_back_to_default` - fallback on "abc"
    6. `test_zero_ttl_env_var_falls_back_to_default` - fallback on "0"
    7. `test_cleanup_preserves_other_jobs` - only stale entries removed

- Did NOT modify: agents/, tools/, workflows/, storage/, docs/team/,
  docs/decisions/

## Verification

API tests:

```text
python -m unittest autonomous_crawler.tests.test_api_mvp -v
Ran 27 tests in 3.078s
OK
```

Full test suite:

```text
python -m unittest discover autonomous_crawler\tests
Ran 101 tests (skipped=3)
OK
```

Compile check:

```text
python -m compileall autonomous_crawler run_skeleton.py run_baidu_hot_test.py run_results.py
OK
```

## Result

Completed and failed jobs are now automatically cleaned up after a configurable
TTL. Cleanup runs opportunistically on POST /crawl and GET /crawl/{id}, so no
scheduler thread is needed. Running jobs are never removed. The TTL defaults to
1 hour and is configurable via `CLM_JOB_RETENTION_SECONDS`.

## Known Risks

- Cleanup runs inline on request handling. With many stale entries, the scan
  could add a small latency spike. Acceptable for the local MVP.
- `_parse_iso` returns 0.0 on failure, which means jobs with missing or
  malformed `updated_at` will be cleaned up immediately on next request. This
  is intentional (better to clean up than to accumulate indefinitely).
- No cleanup on GET /history since it reads from SQLite, not the in-memory
  registry.

## Next Step

Submit for supervisor acceptance. Await further assignment.
