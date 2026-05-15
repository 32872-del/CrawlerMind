# Dev Log: Native Spider Models And CheckpointStore

Date: 2026-05-14

Owner: LLM-2026-000 / Supervisor Codex

Track: SCRAPLING-ABSORB-3A / SCRAPLING-ABSORB-3B / SCRAPLING-ABSORB-3C / SCRAPLING-ABSORB-3D / SCRAPLING-ABSORB-3E

## Goal

Absorb the request/result/checkpoint ideas from Scrapling's spider layer into
CLM-owned long-running crawl contracts and persistence.

## Work Completed

- Added `CrawlRequestEnvelope`, `CrawlItemResult`, and `SpiderRunSummary`.
- Added deterministic request fingerprinting with URL/body/header/fragment
  controls.
- Added safe serialization for headers, cookies, proxy URLs, storage-state
  paths, and secret-like fields.
- Added conversion from spider request envelopes to `RuntimeRequest`.
- Added conversion from spider item results to BatchRunner
  `ItemProcessResult`.
- Added `CheckpointStore` with SQLite tables for runs, checkpoints, events,
  failures, and items.
- Added pause/completed run markers and latest checkpoint loading.
- Added `SpiderRuntimeProcessor` to connect URLFrontier items, runtime
  backends, parser/record/discovery callbacks, BatchRunner item results, and
  CheckpointStore item checkpoints.
- Added optional `SpiderCheckpointSink` for BatchRunner checkpoint-hook
  compatibility.
- Added `LinkDiscoveryHelper` with allow/deny/domain/restricted-scope filters,
  URL canonicalization, classification, drop counters, and runtime events.
- Added `RobotsPolicyHelper` with respect/record_only/disabled modes,
  can_fetch, crawl-delay/request-rate extraction, caching, and runtime events.
- Added `run_spider_runtime_smoke_2026_05_14.py`, a public-network-free
  pause/resume smoke that wires `URLFrontier`, `BatchRunner`,
  `SpiderRuntimeProcessor`, `CheckpointStore`, `NativeParserRuntime`, and
  `LinkDiscoveryHelper`.
- Added `clm.py smoke --kind native-spider` and
  `clm.py train --round native-spider-smoke`.
- Added `autonomous_crawler/tests/test_spider_runtime_smoke.py`.
- Added focused tests for model behavior and checkpoint persistence.

## Verification

```text
python -m unittest autonomous_crawler.tests.test_checkpoint_store autonomous_crawler.tests.test_spider_models autonomous_crawler.tests.test_batch_runner -v
Ran 25 tests
OK

python -m unittest autonomous_crawler.tests.test_spider_runner autonomous_crawler.tests.test_checkpoint_store autonomous_crawler.tests.test_spider_models autonomous_crawler.tests.test_batch_runner -v
Ran 30 tests
OK

python -m unittest autonomous_crawler.tests.test_link_discovery autonomous_crawler.tests.test_robots_policy autonomous_crawler.tests.test_spider_runner autonomous_crawler.tests.test_checkpoint_store -v
Ran 22 tests
OK

python -m unittest discover -s autonomous_crawler/tests
Ran 1453 tests in 70.401s
OK (skipped=5)

python -m compileall autonomous_crawler run_native_transition_comparison_2026_05_14.py clm.py
OK

python run_spider_runtime_smoke_2026_05_14.py
accepted=true

python clm.py smoke --kind native-spider
accepted=true

python -m unittest autonomous_crawler.tests.test_spider_runtime_smoke autonomous_crawler.tests.test_spider_runner autonomous_crawler.tests.test_checkpoint_store autonomous_crawler.tests.test_link_discovery autonomous_crawler.tests.test_robots_policy autonomous_crawler.tests.test_batch_runner -v
Ran 33 tests
OK

python -m unittest discover -s autonomous_crawler/tests
Ran 1454 tests in 74.508s
OK (skipped=5)

python -m compileall autonomous_crawler run_native_transition_comparison_2026_05_14.py run_spider_runtime_smoke_2026_05_14.py clm.py
OK
```

## Remaining Gaps

- Real external dynamic/ecommerce comparison training is still pending.
- Sitemap helper is still pending.
- Robots delay is not yet wired into domain rate-limit policy.
- Browser context leasing and profile/session pools are still pending.
