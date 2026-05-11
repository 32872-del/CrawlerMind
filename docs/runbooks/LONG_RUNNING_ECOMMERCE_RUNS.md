# Long-Running Ecommerce Runs

This runbook describes how CLM should prepare for ecommerce crawls that may run
for hours or collect tens of thousands of products.

## Current Readiness

CLM has a local foundation for larger ecommerce runs:

- SQLite URL frontier with queued/running/done/failed states.
- Generic `ProductRecord` model.
- SQLite `ProductStore` with batch upsert and run-level stats.
- Product quality validator for URL/title/price/image/body/dedupe checks.
- Local stress evidence for 30,000 synthetic ecommerce records.

This is enough for controlled local stress tests and small real-site training.
It is not yet a production distributed crawler.

## Required Pattern

Large runs should use this loop:

1. Add category/list/detail URLs to the frontier.
2. Claim a bounded batch.
3. Fetch and extract a small batch.
4. Validate product records.
5. Upsert records into `ProductStore`.
6. Mark frontier URLs done or failed.
7. Write a compact progress event.
8. Repeat until the frontier is empty or limits are reached.

Do not hold the entire run in memory and save only at the end.

## Suggested Limits For Training

Start small and expand only after quality passes:

| Stage | Max products | Purpose |
|---|---:|---|
| sample | 5 | selectors/API proof |
| pilot | 100 | pagination and quality drift |
| batch | 1,000 | checkpoint behavior |
| stress | 30,000 synthetic | local throughput/regression |
| real long run | site-specific approval required | supervised operation |

## Checkpoint Requirements

Before any real large run, confirm:

- product records are written every batch
- frontier status is persisted every batch
- failed URLs keep error notes
- duplicate URLs do not explode queue size
- `max_items`, `max_pages`, and per-domain rate limits are configured
- output files are generated from SQLite, not in-memory state
- runtime databases and exports are excluded from Git unless intentionally
  accepted as small training artifacts

## Failure Recovery

On interruption:

1. Keep the runtime SQLite files.
2. Inspect frontier counts by status.
3. Requeue expired/running leases if needed.
4. Resume from queued/failed URLs with a bounded retry count.
5. Export a partial result for human review before expanding again.

## Known Gaps

- Product storage is local SQLite only.
- There is no durable FastAPI job registry yet.
- There is no dashboard for run progress.
- There is no automatic per-domain throttling controller.
- Real long-run ecommerce behavior still needs supervised site-by-site training.

## Supervisor Policy

For now, real ecommerce long runs require supervisor approval. The default
development workflow remains: fixture -> 5-product sample -> 100-product pilot
-> larger controlled run.
