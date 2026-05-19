# Assignment: Long-Run Operations Round 2

Date: 2026-05-18

Employee: LLM-2026-002

Project role: Backend Stability Worker

Priority: P0

## Mission

Turn the durable registry and backpressure layer into user-visible long-run
operations support.

When a long crawl slows down or loses data quality, CLM should explain why in
terms that the frontend and user can act on.

## Read First

- `autonomous_crawler/storage/batch_registry.py`
- `autonomous_crawler/runners/backpressure.py`
- `autonomous_crawler/runners/batch_runner.py`
- `autonomous_crawler/runners/profile_longrun.py`
- `autonomous_crawler/api/app.py`
- `docs/team/acceptance/2026-05-18_durable_batch_registry_backpressure_ACCEPTED.md`

## Write Scope

Primary ownership:

- `autonomous_crawler/runners/backpressure.py`
- `autonomous_crawler/runners/profile_longrun.py`
- `autonomous_crawler/api/app.py`
- tests for diagnostics and recovery
- optional smoke script if useful
- dev log and handoff

Avoid touching frontend files and export/template logic.

## Requirements

1. Add a long-run diagnostics summary.
   It should classify likely bottlenecks such as:
   - access blocking
   - selector loss
   - pagination gap
   - transport pressure
   - retry pressure
   - quality loss
2. Surface diagnostics in profile-run status/report payloads.
3. Add a recovery smoke or focused test proving durable jobs can be listed and
   recovered after registry reopen.
4. Add job list/detail operations for the frontend.
   - ensure `GET /jobs` is documented and tested
   - include kind, status, created/updated/completed timestamps, and safe
     summary fields
   - support filters by status and kind
5. Add pause/resume/cancel semantics where feasible.
   - if real pause/resume cannot be fully wired yet, expose clear status fields
     and document what is implemented
   - suggested routes: `POST /jobs/{task_id}/cancel`,
     `POST /profile-runs/{task_id}/pause`, `POST /profile-runs/{task_id}/resume`
   - do not fake successful control if backend cannot honor it
6. Add recommendation text that the frontend can show directly.
   - Chinese-friendly message field is preferred, or a stable code plus English
     summary that 004 can translate
7. Add long-run report persistence check.
   - confirm backpressure/diagnostics are included in saved profile reports
   - add tests around report serialization
8. Keep existing API response fields backward compatible.

## Acceptance

- diagnostics appear in API status/report data
- recovery behavior is covered by a smoke or focused test
- job list/detail data is frontend-ready
- pause/cancel/resume behavior is either implemented or explicitly rejected
  with stable error messages
- backpressure/diagnostics survive report serialization
- existing focused tests still pass
- compileall passes

## Handoff

Report:

- diagnostics schema
- recovery proof
- API fields added
- job operation endpoints
- pause/resume/cancel state
- tests run
- remaining long-run observability gaps
