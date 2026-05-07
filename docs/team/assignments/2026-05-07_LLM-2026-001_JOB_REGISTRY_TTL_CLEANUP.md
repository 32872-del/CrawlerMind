# Assignment: Job Registry TTL Cleanup

Assignment ID: `2026-05-07_LLM-2026-001_JOB_REGISTRY_TTL_CLEANUP`

Employee ID: `LLM-2026-001`

Project Role: `ROLE-API`

Status: `assigned`

Supervisor: `LLM-2026-000`

## Objective

Add a small cleanup mechanism for completed/failed in-memory job registry
entries.

The registry now limits active jobs, but completed/failed entries can
accumulate forever in a long-running process.

## Required Behavior

1. Completed and failed jobs should remain queryable briefly.
2. Old completed/failed jobs should be removed after a configurable TTL.
3. Running jobs must never be removed by TTL cleanup.
4. Existing active-job limit behavior must remain unchanged.
5. No external services or new dependencies.

## Recommended Design

Keep this inside:

```text
autonomous_crawler/api/app.py
autonomous_crawler/tests/test_api_mvp.py
```

Suggested env var:

```text
CLM_JOB_RETENTION_SECONDS
```

Suggested default:

```text
3600
```

Use existing timestamps or add `updated_at`.

Cleanup can run opportunistically during `POST /crawl` or `GET /crawl/{id}`.
Do not add a scheduler thread.

## Owned Files

```text
autonomous_crawler/api/app.py
autonomous_crawler/tests/test_api_mvp.py
dev_logs/2026-05-07_HH-MM_job_registry_ttl_cleanup.md
docs/memory/handoffs/2026-05-07_LLM-2026-001_job_registry_ttl_cleanup.md
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

## Required Tests

Add tests for:

1. completed job older than TTL is removed
2. failed job older than TTL is removed
3. running job older than TTL is not removed
4. recent completed job remains queryable
5. invalid TTL env var falls back to default
6. existing concurrency limit tests still pass

Run:

```text
python -m unittest autonomous_crawler.tests.test_api_mvp -v
python -m unittest discover autonomous_crawler\tests
python -m compileall autonomous_crawler run_skeleton.py run_baidu_hot_test.py run_results.py
```

## Acceptance Target

```text
docs/team/acceptance/2026-05-07_job_registry_ttl_cleanup_ACCEPTED.md
```
