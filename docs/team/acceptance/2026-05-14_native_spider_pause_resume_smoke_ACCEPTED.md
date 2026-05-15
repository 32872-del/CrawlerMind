# Acceptance: Native Spider Pause/Resume Smoke

Date: 2026-05-14

Owner: LLM-2026-000 / Supervisor Codex

Track: SCRAPLING-ABSORB-3E

## Accepted Scope

- Added `run_spider_runtime_smoke_2026_05_14.py`.
- Added `autonomous_crawler/tests/test_spider_runtime_smoke.py`.
- Added Easy Mode access through `python clm.py smoke --kind native-spider`.
- Added training command listing through
  `python clm.py train --round native-spider-smoke`.

## Acceptance Evidence

The smoke uses deterministic local HTML fixtures only; it does not access the
public network.

It proves:

- `URLFrontier` seeds a list URL and a deterministic missing detail URL.
- `BatchRunner` can stop after one bounded pass.
- `SpiderRuntimeProcessor` fetches, parses, discovers links, builds records,
  and writes item checkpoints.
- `LinkDiscoveryHelper` discovers and classifies detail links from the list
  fixture while dropping ignored/offsite links.
- `CheckpointStore` records run lifecycle, latest checkpoint, item records,
  request events, and failure buckets.
- A second runner pass resumes the queued frontier and completes the run.

Smoke summary:

```text
first pass: claimed=1, succeeded=1, discovered_urls=2
after first pass frontier: done=1, queued=3
resume pass: claimed=3, succeeded=2, failed=1
final frontier: done=3, failed=1
checkpoint items: 2
checkpoint failures: 1
accepted: true
```

Output evidence:

- `dev_logs/smoke/2026-05-14_spider_runtime_smoke.json`

## Verification

```text
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
- Browser context leasing and profile/session pools are not yet integrated with
  `BatchRunner`.
- Sitemap discovery and robots delay are not yet wired into domain policy.
- `SpiderRuntimeProcessor` is still callback-profile driven; site/crawl profile
  files should become the preferred user-facing configuration surface.
