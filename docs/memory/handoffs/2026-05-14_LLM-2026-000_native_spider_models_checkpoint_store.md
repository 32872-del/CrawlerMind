# Handoff: Native Spider Models And CheckpointStore

Date: 2026-05-14

Employee: LLM-2026-000 / Supervisor Codex

Track: SCRAPLING-ABSORB-3A / SCRAPLING-ABSORB-3B / SCRAPLING-ABSORB-3C / SCRAPLING-ABSORB-3D

## Summary

CLM now has native spider data contracts, an inspectable SQLite checkpoint
store, a `SpiderRuntimeProcessor`, and native link/robots helper modules. The
current long-run foundation can model requests/results, checkpoint item/failure
state, process frontier items through runtime backends, discover/classify links,
and evaluate robots directives.

## Files Changed

- `autonomous_crawler/runners/spider_models.py`
- `autonomous_crawler/runners/spider_runner.py`
- `autonomous_crawler/runners/__init__.py`
- `autonomous_crawler/storage/checkpoint_store.py`
- `autonomous_crawler/tools/link_discovery.py`
- `autonomous_crawler/tools/robots_policy.py`
- `autonomous_crawler/storage/__init__.py`
- `autonomous_crawler/tests/test_spider_models.py`
- `autonomous_crawler/tests/test_checkpoint_store.py`
- `autonomous_crawler/tests/test_link_discovery.py`
- `autonomous_crawler/tests/test_robots_policy.py`
- `PROJECT_STATUS.md`
- `docs/team/TEAM_BOARD.md`
- `docs/plans/2026-05-14_SCRAPLING_ABSORPTION_RECORD.md`
- `docs/team/acceptance/2026-05-14_native_spider_models_ACCEPTED.md`
- `docs/team/acceptance/2026-05-14_native_checkpoint_store_ACCEPTED.md`
- `docs/team/acceptance/2026-05-14_native_spider_runtime_processor_ACCEPTED.md`
- `docs/team/acceptance/2026-05-14_native_link_robots_helpers_ACCEPTED.md`
- `dev_logs/development/2026-05-14_native_spider_models_and_checkpoint_store.md`

## Verified

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
```

## Important Behavior

- `CrawlRequestEnvelope.fingerprint` is deterministic and JSON/body order safe.
- `CrawlRequestEnvelope.to_runtime_request()` carries run/request identity into
  runtime metadata.
- `CrawlItemResult.to_item_process_result()` preserves discovered URLs and
  runtime evidence for BatchRunner.
- `CheckpointStore` stores run/checkpoint/item/failure/event records in SQLite.
- `SpiderRuntimeProcessor` can run static or browser runtime modes and writes
  item checkpoints when a `CheckpointStore` is provided.
- `LinkDiscoveryHelper` returns `CrawlRequestEnvelope` objects, drop counters,
  and runtime events.
- `RobotsPolicyHelper` supports respect/record_only/disabled modes and emits
  `spider.robots_checked` events.
- `CheckpointStore` should be imported from
  `autonomous_crawler.storage.checkpoint_store`, not from
  `autonomous_crawler.storage`, to avoid runner/storage circular imports.

## Next Recommended Work

1. SCRAPLING-ABSORB-3E: add URLFrontier + SpiderRuntimeProcessor +
   CheckpointStore pause/resume smoke.
2. SCRAPLING-ABSORB-3F: add sitemap discovery and robots-delay integration
   into domain rate-limit policy.
3. SCRAPLING-ABSORB-2E: run native-vs-transition dynamic comparison on real
   dynamic/ecommerce training targets.
