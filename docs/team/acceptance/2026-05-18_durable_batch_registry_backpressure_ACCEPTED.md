# Acceptance: Durable Batch Registry and Backpressure

Date: 2026-05-18

Employee: LLM-2026-002

Assignment: `docs/team/assignments/2026-05-18_LLM-2026-002_DURABLE_BATCH_REGISTRY_AND_BACKPRESSURE.md`

Status: accepted

## Accepted Scope

- Added SQLite-backed `BatchRegistry`.
- Routed API job helpers through durable registry functions.
- Added startup recovery for stale running jobs.
- Added `BackpressureMonitor` with latency, retry, failure, quality-loss, and
  recommendation signals.
- Integrated backpressure into batch/profile long-run execution.
- Added focused registry and backpressure tests.

## Verification

```text
python -m unittest autonomous_crawler.tests.test_product_workflow_api autonomous_crawler.tests.test_api_mvp autonomous_crawler.tests.test_batch_registry autonomous_crawler.tests.test_backpressure autonomous_crawler.tests.test_batch_runner autonomous_crawler.tests.test_profile_longrun -v
Ran 147 tests in 28.784s
OK

python -m compileall autonomous_crawler clm.py -q
OK
```

## Follow-Up Requirements

- Add frontend-visible long-run diagnostics that explain whether failures are
  caused by access blocking, selector loss, pagination gaps, quality loss, or
  transport pressure.
- Add a recovery smoke proving a real API/profile batch can be listed and
  recovered after app restart.

