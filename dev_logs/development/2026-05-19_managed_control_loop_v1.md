# 2026-05-19 Managed Control Loop v1

## Summary

Delivered the first product-level AI managed control loop for CLM.

This is a larger integration slice, not a single helper endpoint. It connects:

- run observation
- evidence pack creation
- optional access probe
- managed action planning/execution
- optional repaired child run
- frontend-visible timeline/status/events

## Backend Changes

- Added `ManagedControlLoopRequest`.
- Added `POST /runs/{task_id}/managed-control-loop`.
- Added `_execute_managed_control_loop_for_job()`.
- Added `managed_control_loops` and `latest_managed_control_loop` to run status.
- Added `managed_control_loop_completed` events.
- Added `access_probe_completed` events.
- Added `managed_control_loop` to `/workbench/config` endpoint map.

## Runtime Flow

The new endpoint runs:

```text
observe -> access_probe -> plan_act -> optional repair_rerun
```

The response uses `managed-control-loop/v1` and returns:

- `evidence_before`
- `evidence_after`
- `access_probe`
- `action_record`
- `child_run`
- `timeline`

This gives the frontend one main AI control button instead of asking users to
manually jump between probe, managed actions, managed step, and rerun endpoints.

## Verification

Passed:

```text
python -m unittest autonomous_crawler.tests.test_product_workflow_api.ManagedAIRunTests.test_managed_control_loop_runs_probe_actions_and_child_rerun -v
python -m unittest autonomous_crawler.tests.test_product_workflow_api.ProductWorkflowAPITests.test_access_probe_endpoint_returns_snapshot_layers -v
python -m unittest autonomous_crawler.tests.test_managed_actions -v
```

## Current Limitations

- This is still polling JSON, not SSE/WebSocket streaming.
- The loop exposes bounded LLM trace summaries, not raw hidden reasoning.
- The quality of repairs still depends on evidence quality from the crawler
  backend, so the next big backend block should strengthen catalog discovery,
  pagination, detail-page coverage, and API/XHR replay.

## Next Recommended Block

Build the hard-crawl execution improvement block:

- catalog coverage funnel
- pagination/detail-page loss diagnostics
- API/XHR replay candidate promotion
- long-run progress and coverage accounting
- faster multi-worker execution controls
