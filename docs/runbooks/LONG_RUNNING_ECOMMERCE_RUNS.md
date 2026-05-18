# Long-Running Ecommerce Runs

This runbook describes how CLM should prepare for ecommerce crawls that may run
for hours or collect tens of thousands of products.

## Current Readiness

CLM has a local foundation for larger ecommerce runs:

- SQLite URL frontier with queued/running/done/failed states.
- Generic `BatchRunner` for bounded claim/process/checkpoint loops, including
  batch-internal concurrent URL processing via `item_workers`.
- Generic `ProductRecord` model.
- SQLite `ProductStore` with batch upsert and run-level stats.
- Product quality validator for URL/title/price/image/body/dedupe checks.
- Local stress evidence for 30,000 synthetic ecommerce records.
- Profile long-run entrypoints for single-site and multi-site execution:
  `clm.py profile-run`, `clm.py multi-profile-run`, `POST /profile-runs`,
  and `POST /profile-runs/batch`.
- Multi-site profile runs are capped at 5 concurrent sites.
- Static/API profile runs can reuse HTTP connection pools during threaded jobs.

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

The generic runner contract is documented in:

```text
docs/runbooks/RESUMABLE_BATCH_RUNNER.md
```

## Suggested Limits For Training

Start small and expand only after quality passes:

| Stage | Max products | Purpose |
|---|---:|---|
| sample | 5 | selectors/API proof |
| pilot | 100 | pagination and quality drift |
| batch | 1,000 | checkpoint behavior |
| stress | 30,000 synthetic | local throughput/regression |
| real long run | site-specific approval required | supervised operation |

## Parallel Profile Commands

Single-site profile run with threaded item processing:

```text
python clm.py profile-run --profile path/to/profile.json --workers 8 --batch-size 40 --runtime-dir dev_logs/runtime/site_a
```

Up to five sites concurrently:

```text
python clm.py multi-profile-run --jobs path/to/jobs.json --max-sites 5 --workers 8 --output dev_logs/runtime/multi_profile_summary.json
```

`jobs.json` shape:

```json
{
  "site_a": {
    "profile_path": "profiles/site_a.json",
    "run_id": "site-a-run",
    "runtime_dir": "dev_logs/runtime/site_a",
    "item_workers": 8
  },
  "site_b": {
    "profile_path": "profiles/site_b.json",
    "run_id": "site-b-run",
    "runtime_dir": "dev_logs/runtime/site_b"
  }
}
```

If a job omits `item_workers`, the CLI `--workers` value is used. The hard
multi-site cap is 5 so one operator request cannot accidentally launch an
unbounded number of sites.

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

## Coverage And Success-Rate Diagnostics

Every real ecommerce long run must report a coverage funnel. Row count alone is
not an acceptance signal. If a site appears to have 5,000 products and CLM only
exports 4,000 usable rows, the report must explain where the other 1,000 were
lost.

Required funnel stages:

| Stage | Question | Typical Root Cause |
|---|---|---|
| inventory | How many products probably exist? | sitemap/API total/category count mismatch |
| discovery | How many product URLs or API items were discovered? | missing category tree, pagination, load more, infinite scroll |
| schedule | How many discovered targets were actually attempted within the run budget? | time budget, sequential fetching, frontier backlog, low concurrency |
| access | How many discovered targets were fetched successfully? | 403/429, timeout, proxy/session/fingerprint, CDN challenge |
| render | How many needed browser rendering and succeeded? | wait strategy, scroll/click automation, XHR capture |
| parse | How many pages produced product-shaped records? | selector drift, JSON-LD/hydration fallback missing |
| quality | How many records passed required fields and media checks? | stale pages, missing price/detail/image, noise assets |
| export | How many unique rows reached the final artifact? | dedupe policy, product-vs-SKU granularity, export failure |

The canonical report shape is `coverage-report/v1`, implemented by:

```text
autonomous_crawler/tools/coverage_report.py
```

Minimum counters for supervised training:

```text
estimated_inventory
discovered_urls
attempted_fetches
time_budget_exhausted
fetched_success
blocked_or_challenged
render_attempted
render_success
parsed_records
quality_passed
quality_failed
exported_unique
duplicate_dropped
catalog_exhausted
```

Acceptance expectations:

- If the target is lower than the real inventory, `exported_unique` should meet
  the requested target with high field completeness.
- If the real inventory is smaller than the requested target, mark
  `catalog_exhausted=true` and report the discovered inventory instead of
  duplicating rows.
- If coverage is below target, the report must include `main_loss_reason` and
  `recommended_recovery`.

Typical recovery mapping:

| Main Loss | Next Action |
|---|---|
| missing_inventory_discovery | expand sitemap/category/API-total/pagination discovery |
| time_budget_or_frontier_pending | cache catalog discovery, parallel fetch, adaptive concurrency, resume pending frontier |
| access_or_transport_loss | transport fallback, browser profile rotation, proxy/session/backoff diagnostics |
| rendering_or_automation_loss | wait strategy, scrolling, load-more clicking, XHR capture |
| parser_or_selector_loss | adaptive selectors, JSON-LD/hydration/API fallback, selector memory |
| quality_gate_loss | invalid-page rejection, media cleanup, replacement URL queue |
| dedupe_or_export_loss | review product/SKU/variant granularity |

## Known Gaps

- Product storage is local SQLite only.
- There is no durable FastAPI job registry yet.
- There is no dashboard for run progress.
- There is no automatic per-domain throttling controller.
- The current runner has a product checkpoint adapter, but no generic JSON
  checkpoint adapter yet.
- Real long-run ecommerce behavior still needs supervised site-by-site training.
- Multi-site API jobs are concurrent in-process jobs; restart durability still
  depends on the per-site runtime SQLite directories and future durable job
  registry work.

## Supervisor Policy

For now, real ecommerce long runs require supervisor approval. The default
development workflow remains: fixture -> 5-product sample -> 100-product pilot
-> larger controlled run.
