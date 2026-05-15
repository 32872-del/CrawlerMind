# Acceptance: Native LinkDiscovery And RobotsPolicy Helpers

Date: 2026-05-14

Employee: LLM-2026-000 / Supervisor Codex

Track: SCRAPLING-ABSORB-3D

Status: accepted

## Scope Accepted

Implemented CLM-native link discovery and robots policy helpers:

- `autonomous_crawler/tools/link_discovery.py`
- `autonomous_crawler/tools/robots_policy.py`
- `autonomous_crawler/tests/test_link_discovery.py`
- `autonomous_crawler/tests/test_robots_policy.py`

## What Changed

- Added `LinkDiscoveryRule`, `LinkDiscoveryResult`, and
  `LinkDiscoveryHelper`.
- Link discovery supports:
  - allow/deny regex rules
  - allow/deny domain rules
  - CSS/XPath restricted extraction scopes
  - tag/attribute selection
  - ignored extension filtering
  - duplicate/offsite/drop counters
  - URL canonicalization
  - profile-driven URL classification
- JSON API links are retained by default and can be classified as `api`.
- Added `RobotsPolicyHelper` and `RobotsDirectives`.
- Robots policy supports:
  - `respect`
  - `record_only`
  - `disabled`
  - cached robots fetch/parse
  - `can_fetch`
  - crawl-delay and request-rate extraction
  - runtime event emission

## Verification

```text
python -m unittest autonomous_crawler.tests.test_link_discovery autonomous_crawler.tests.test_robots_policy -v
Ran 11 tests
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

## Acceptance Notes

This completes the first native link/robots helper layer. The next step is to
wire these helpers into a URLFrontier + SpiderRuntimeProcessor pause/resume
smoke so discovery, checkpoints, and frontier state are exercised together.
