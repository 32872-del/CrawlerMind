# Acceptance: Native SpiderRuntimeProcessor

Date: 2026-05-14

Employee: LLM-2026-000 / Supervisor Codex

Track: SCRAPLING-ABSORB-3C

Status: accepted

## Scope Accepted

Implemented a CLM-native spider processor around the existing BatchRunner:

- `autonomous_crawler/runners/spider_runner.py`
- `autonomous_crawler/runners/__init__.py`
- `autonomous_crawler/tests/test_spider_runner.py`

## What Changed

- Added `SpiderRuntimeProcessor`.
- Added optional `SpiderCheckpointSink`.
- `SpiderRuntimeProcessor` now:
  - builds `CrawlRequestEnvelope` from URLFrontier items
  - converts envelopes to `RuntimeRequest`
  - dispatches to static fetch or browser runtime protocols
  - optionally parses responses through a parser runtime
  - supports selector, record, and discovered-link callback hooks
  - saves item checkpoints through `CheckpointStore`
  - maps runtime failures into retryable BatchRunner `ItemProcessResult`
    values and checkpointed failure buckets
- The processor is generic. Site-specific selectors and record shaping remain
  outside the core through callbacks/profiles.

## Verification

```text
python -m unittest autonomous_crawler.tests.test_spider_runner autonomous_crawler.tests.test_checkpoint_store autonomous_crawler.tests.test_spider_models autonomous_crawler.tests.test_batch_runner -v
Ran 30 tests
OK

python -m unittest discover -s autonomous_crawler/tests
Ran 1442 tests in 69.480s
OK (skipped=5)

python -m compileall autonomous_crawler run_native_transition_comparison_2026_05_14.py clm.py
OK
```

## Acceptance Notes

This completes the first usable native spider processing bridge. It is not yet
the full long-running spider product surface: URLFrontier pause/resume smoke,
LinkDiscoveryHelper, RobotsPolicyHelper, and browser context leasing remain
next-step work.
