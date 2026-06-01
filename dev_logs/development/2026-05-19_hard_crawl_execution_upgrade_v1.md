# 2026-05-19 Hard Crawl Execution Upgrade v1

## Summary

Delivered the first hard-crawl execution diagnostics block for CLM.

This block turns long-run crawl results into a visible coverage funnel so CLM
can explain where data was lost and what recovery should happen next.

## Backend Changes

- Connected `CoverageCounters` / `build_coverage_report()` into
  `ProfileLongRunExecutor`.
- Added `coverage_report` to `ProfileLongRunResult`.
- Exposed `coverage_report` in:
  - `diagnostics`
  - `report`
  - `build_run_evidence_pack()`
- Added `managed_control_loop_count` to `managed_history`.

## Coverage Funnel

The coverage report now gives a structured answer to questions like:

- Did we discover enough catalog URLs?
- Did fetch/access fail?
- Did rendering fail?
- Did parsing/selector extraction fail?
- Did the quality gate drop records?
- Did export/dedupe drop records?

The report returns:

- `losses`
- `main_loss_reason`
- `recommended_recovery`
- stage rates for discovery, fetch, render, parse, quality, export

## Why This Matters

The user has repeatedly asked for higher success rate and higher throughput on
real ecommerce sites. This block gives CLM a real answer to:

```text
why are we short of 5000 rows?
where did the rows disappear?
what should the next rerun change?
```

Instead of only saying "no records", CLM can now show whether the main gap is:

- catalog discovery
- schedule/throughput
- access blocking
- rendering
- parsing/selectors
- quality gate
- export/dedupe

## Verification

Passed:

```text
python -m unittest autonomous_crawler.tests.test_profile_longrun -v
python -m unittest autonomous_crawler.tests.test_coverage_report -v
python -m unittest autonomous_crawler.tests.test_product_workflow_api.ManagedAIRunTests.test_managed_control_loop_runs_probe_actions_and_child_rerun -v
```

## Next Recommended Block

Continue hard-crawl strength with:

- explicit pagination loss accounting
- detail-page vs list-page funnel separation
- API/XHR replay promotion
- multi-worker throughput telemetry
- run-time coverage target checks exposed in status
