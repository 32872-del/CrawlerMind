# Assignment: Durable Batch Registry and Backpressure

Date: 2026-05-18

Employee: LLM-2026-002

Project role: Backend Stability Worker

## Mission

Make long-running and multi-site CLM runs more stable.

The current weakness is not that the crawler cannot start. The weakness is that
large or repeated jobs still need stronger durability, restart recovery, and
adaptive throttling.

## Read First

- `autonomous_crawler/runners/batch_runner.py`
- `autonomous_crawler/runners/profile_longrun.py`
- `autonomous_crawler/api/app.py`
- `autonomous_crawler/storage/checkpoint_store.py`
- `docs/runbooks/RESUMABLE_BATCH_RUNNER.md`
- `docs/runbooks/LONG_RUNNING_ECOMMERCE_RUNS.md`
- `PROJECT_STATUS.md`

## Write Scope

Primary ownership:

- `autonomous_crawler/runners/batch_runner.py`
- `autonomous_crawler/runners/profile_longrun.py`
- a new durable registry helper under `autonomous_crawler/storage/` if needed
- related FastAPI batch endpoints in `autonomous_crawler/api/app.py`
- tests for registry durability, restart recovery, and adaptive throttling
- your `dev_logs/` and `docs/memory/handoffs/` notes

Avoid touching:

- frontend code
- export/template logic
- unrelated runtime adapters

## Requirements

1. Replace the current in-memory batch job registry with a durable store or a
   durable layer over the current store.
2. Preserve running job state across restart or recovery.
3. Add backpressure / throttling evidence for long runs.
   - latency
   - retry pressure
   - failure rate
   - quality loss signals
4. Let the runner use those signals to choose safer worker behavior or at
   least surface a clear recommendation.
5. Keep the existing batch API shape compatible.
6. Add tests for restart recovery and concurrent batch behavior.

## Acceptance

- batch jobs survive restart or can be recovered from durable state
- backpressure signals are visible in job/report output
- concurrency changes do not break existing runs
- tests pass
- compileall passes

## Handoff

Report:

- registry design chosen
- restart behavior
- backpressure schema
- performance or durability limits
- test results

