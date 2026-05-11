# Handoff: Resumable Batch Runner QA

Employee: LLM-2026-001
Date: 2026-05-11
Assignment: `2026-05-11_LLM-2026-001_RESUMABLE_RUNNER_QA`

## What Was Done

QA audit of the resumable batch runner infrastructure for long-running
ecommerce crawls. Read-only review of:

- `autonomous_crawler/storage/frontier.py` — URL frontier with lease-based claiming
- `autonomous_crawler/storage/product_store.py` — SQLite product store
- `docs/runbooks/LONG_RUNNING_ECOMMERCE_RUNS.md` — operational runbook
- `docs/process/ECOMMERCE_CRAWL_WORKFLOW.md` — workflow definition

Identified 12 findings across frontier, product store, and the gap between
them. No code changes made.

## Key Findings

| # | Finding | Severity |
|---|---------|----------|
| F-RR001 | `_mark` silently accepts zero matches | medium |
| F-RR002 | **No retry limit — infinite re-queue loop** | **high** |
| F-RR003 | Lease expiration race condition | medium |
| F-RR004 | Separate databases — no atomicity | medium |
| F-RR005 | No batch-level progress tracking | medium |
| F-RR006 | `mark_done` by URL fragile | low |
| F-RR007 | No per-domain concurrency control | medium |
| F-RR008 | WAL mode not configured | low |
| F-RR009 | Redundant lease_token re-fetch | info |
| F-RR010 | No max frontier size guard | medium |
| F-RR011 | Attempts never resets on success | info |
| F-RR012 | No run-level isolation | low |

**Highest risk: F-RR002.** `mark_failed(retry=True)` re-queues URLs without
checking `attempts`. A permanently-failing URL loops forever. Fix: add
`max_retries` parameter (default 3).

## Files Changed

- `docs/team/audits/2026-05-11_LLM-2026-001_RESUMABLE_RUNNER_QA.md` — new audit report
- `docs/memory/handoffs/2026-05-11_LLM-2026-001_resumable_runner_qa.md` — this handoff

## What Is NOT Changed

- No implementation files modified (frontier.py, product_store.py).
- No tests added.
- No dependencies changed.
- No runtime behavior changed.

## Recommended Next Steps

1. **Add `max_retries` to `mark_failed()`** — blocks safe long runs.
2. **Add progress events table** — required for operational visibility.
3. **Use `BEGIN IMMEDIATE` in `next_batch()`** — blocks multi-worker support.
4. **Design batch-progress checkpoint** — required for reliable crash resume.
5. **Return structured result from `_mark()`** — improves debuggability.
6. **Add domain-aware batching** — required for polite crawling.
7. **Add frontier size limit** — safety net for runaway URL discovery.

## Test Gaps

12 specific test cases identified in the audit document. Priority tests:
- Retry limit enforcement (demonstrates infinite loop bug)
- Concurrent `next_batch` overlap detection
- Crash recovery between product save and mark_done
- Batch progress queryability
