# 2026-05-19 Adaptive Throughput v1

## Summary

Delivered a backend execution-strength upgrade: adaptive item worker scheduling
for `BatchRunner` and profile long-runs.

This is not just analysis. It changes runtime behavior so CLM can increase or
decrease per-batch concurrency based on actual batch yield and failures.

## Backend Changes

- Added adaptive worker controls to `BatchRunnerConfig`:
  - `adaptive_item_workers`
  - `min_item_workers`
  - `max_item_workers`
- Added runtime telemetry to `BatchRunnerSummary`:
  - `worker_history`
  - `batch_history`
- Healthy batches with high success and positive record yield scale workers up.
- Failed/blocked batches scale workers down.
- Added the same controls to `ProfileLongRunConfig` and `ProfileRunRequest`.
- Profile long-run diagnostics now include:
  - `diagnostics.throughput.worker_history`
  - `diagnostics.throughput.batch_history`
  - worker min/max/initial settings
- `build_run_evidence_pack()` now includes throughput diagnostics.

## Why This Matters

For large ecommerce sites, fixed concurrency is either too slow or too fragile.
Adaptive workers let CLM push harder when the site is healthy and back off when
failures rise. This is a direct hard-crawl capability improvement, not only a
reporting improvement.

## Verification

Passed:

```text
python -m unittest autonomous_crawler.tests.test_batch_runner -v
python -m unittest autonomous_crawler.tests.test_profile_longrun -v
```

## Next Hard Backend Block

- Detail/list/variant stage split in the production profile runner.
- API/XHR replay promotion from access evidence into executable profile patches.
- Pagination expansion that can fill pending frontier until target coverage is met.
