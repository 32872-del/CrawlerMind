# 2026-05-09 16:40 Browser Network Timing And API Replay

## Context

`LLM-2026-002` timing QA showed that public SPA network observation could return too early with `domcontentloaded`. A direct HN Algolia retry confirmed a stronger issue: after timing improved, the observed public API was an Algolia JSON POST search endpoint, but the old classifier treated any POST body containing `query` as GraphQL and Executor could not replay normal JSON POST APIs.

## Changes

- `observe_browser_network()` now defaults to `wait_until="networkidle"`.
- Invalid `wait_until` values fall back to `networkidle`.
- Added optional `render_time_ms` post-load delay.
- Tightened GraphQL detection so Algolia-style JSON POST search bodies stay `kind="json"` unless the query value looks like a GraphQL operation.
- JSON POST API candidates preserve bounded `post_data_preview`.
- Strategy now prefers high-confidence observed browser-network API candidates over browser rendering for SPA pages when no challenge is detected.
- Strategy carries observed JSON POST body as `api_post_data`.
- Executor can replay `api_json` POST requests with the observed body.
- Added mock POST JSON API support for deterministic tests.

## Verification

```text
python -m unittest autonomous_crawler.tests.test_browser_network_observer -v
Ran 60 tests
OK

python -m unittest autonomous_crawler.tests.test_api_intercept -v
Ran 23 tests
OK

python -m unittest autonomous_crawler.tests.test_access_diagnostics -v
Ran 9 tests
OK

python -m unittest discover -s autonomous_crawler/tests
Ran 345 tests
OK (skipped=4)

python -m compileall autonomous_crawler run_skeleton.py run_baidu_hot_test.py run_results.py run_simple.py run_training_round1.py run_training_round2.py run_training_round3.py run_training_round4.py
OK

python run_training_round4.py
5 completed, 0 failed
```

## HN Algolia Result

The public SPA training scenario now completes:

```text
Recon: Network observation status=ok, entries=8, api_candidates=7
Strategy: mode=api_intercept, method=api_json
Executor: replayed Algolia POST JSON API
Result: completed, 10 items, confidence=1.0
```

## Remaining Work

- Add pagination/cursor replay for observed JSON APIs.
- Train on virtualized and infinite-scroll pages.
- Keep Cloudflare/CAPTCHA/login-required targets in diagnosis-only mode unless an authorized flow is supplied.
