# Acceptance: Generic Resumable Batch Runner MVP

Date: 2026-05-11

Accepted by: LLM-2026-000 Supervisor Codex

## Accepted Artifacts

- `autonomous_crawler/runners/batch_runner.py`
- `autonomous_crawler/runners/__init__.py`
- `autonomous_crawler/tests/test_batch_runner.py`
- `run_batch_runner_smoke.py`
- `docs/runbooks/RESUMABLE_BATCH_RUNNER.md`

## Acceptance Notes

This work is accepted as a generic long-running execution primitive, not an
ecommerce-specific crawler. The runner owns frontier mechanics and checkpoint
coordination only. Domain behavior remains in processors, profiles, fixtures,
or checkpoint adapters.

Accepted behavior:

- empty frontier summary
- bounded batch processing
- partial run and resume with `max_batches`
- success, failure, retry, and processor exception paths
- discovered URL insertion
- checkpoint sink support
- product checkpoint adapter for the current ecommerce training use case

## Verification

```text
python -m unittest autonomous_crawler.tests.test_batch_runner -v
Ran 10 tests
OK

python run_batch_runner_smoke.py --items 25 --batch-size 5 --first-pass-batches 2
accepted: true
first pass: 10 records
resume pass: 15 records
final frontier: done=25
```

## Follow-Ups

- Add a generic JSON checkpoint adapter.
- Wrap the LangGraph workflow as a processor.
- Add progress events for FastAPI and the future frontend.
- Use this runner in the next two supervised real-site training rounds.
