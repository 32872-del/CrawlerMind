# Acceptance: Long-Run Operations Round 2

Date: 2026-05-18

Employee: LLM-2026-002

Assignment: `docs/team/assignments/2026-05-18_ROUND2_LLM-2026-002_LONGRUN_DIAGNOSTICS_AND_RECOVERY_SMOKE.md`

Status: accepted with follow-up

## Accepted Scope

- Added long-run bottleneck classification:
  access blocking, selector loss, pagination gap, transport pressure, retry
  pressure, and quality loss.
- Added Chinese-friendly recommendation text for frontend display.
- Added job list/detail endpoints and job operation endpoints for cancel,
  pause, and resume.
- Added registry recovery tests proving reopened durable jobs remain visible and
  recoverable.
- Added diagnostics/backpressure persistence into profile reports.

## Verification

```text
python -m unittest autonomous_crawler.tests.test_frontend_support_api autonomous_crawler.tests.test_job_operations_api autonomous_crawler.tests.test_longrun_diagnostics autonomous_crawler.tests.test_registry_recovery autonomous_crawler.tests.test_product_workflow_api autonomous_crawler.tests.test_api_mvp autonomous_crawler.tests.test_batch_registry autonomous_crawler.tests.test_backpressure autonomous_crawler.tests.test_profile_longrun -v
Ran 218 tests in 48.227s
OK

python -m compileall autonomous_crawler clm.py -q
OK
```

## Follow-Up

- Pause is currently best-effort. The API sets `pause_requested`, but the
  runner still needs registry polling or a shared control flag between batches
  before this becomes a true live pause.
- Diagnostics are useful, but mid-run diagnostic snapshots and SSE/WebSocket
  streaming remain future work.

