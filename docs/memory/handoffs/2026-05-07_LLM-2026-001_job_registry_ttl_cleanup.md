# Handoff: Job Registry TTL Cleanup

Employee: LLM-2026-001
Date: 2026-05-07
Assignment: `2026-05-07_LLM-2026-001_JOB_REGISTRY_TTL_CLEANUP`

## What Was Done

Added TTL-based cleanup for completed/failed in-memory job registry entries.
Old entries are removed after `CLM_JOB_RETENTION_SECONDS` (default 3600s).
Cleanup runs opportunistically on POST /crawl and GET /crawl/{id}. Running jobs
are never removed.

## Files Changed

- `autonomous_crawler/api/app.py` - added `_job_retention_seconds()`,
  `_parse_iso()`, `_cleanup_stale_jobs()`, `updated_at` field, cleanup calls
- `autonomous_crawler/tests/test_api_mvp.py` - added 7 TTL cleanup tests
- `dev_logs/development/2026-05-07_11-00_job_registry_ttl_cleanup.md`
- `docs/memory/handoffs/2026-05-07_LLM-2026-001_job_registry_ttl_cleanup.md`

## Test Status

27 API tests pass. Full suite: 101 tests (3 skipped). Compile check: OK.

## What Is NOT Changed

- No scheduler thread; cleanup is inline/opportunistic.
- No changes to agents, tools, workflows, storage, or docs/decisions.

## Known Open Issues

- Inline cleanup could add latency with many stale entries (acceptable for MVP).
- `_parse_iso` returns 0.0 on malformed timestamps, causing immediate cleanup.

## Environment

- `CLM_JOB_RETENTION_SECONDS` - TTL for completed/failed jobs (default: 3600)
