# REAL-HARDEN-1: Real Public Dynamic Browser Training

Date: 2026-05-15
Worker: LLM-2026-001

## Summary

Extended the browser scenario training harness with 3 real public SPA/doc-site
targets. All 3 produce usable evidence (rendered_item_count, network_candidates,
profile_health, failure_classification). The Virtuoso demo URL returns 404 —
documented as a follow-up.

## Real Target Results

| Target | URL | Status | Items | HTML | Checks |
|---|---|---|---|---|---|
| Vue.js Examples | vuejs.org/examples/ | OK | 57 | 103k | 2/2 |
| React.dev Learn | react.dev/learn | OK | 51 | 283k | 2/2 |
| TanStack Virtual | tanstack.com/virtual/latest/docs/introduction | OK | 2 | 256k | 2/2 |
| React Virtuoso | virtuoso.dev/infinite-scrolling/ | FAIL | 0 | 0 | 0/1 |

**Virtuoso failure**: HTTP 404 — the URL path `/infinite-scrolling/` no longer
exists on virtuoso.dev. The site appears to have restructured. Follow-up: find
the current Virtuoso demo URL or replace with a different virtualized list demo.

## Changes

| File | Change |
|---|---|
| `run_browser_scenario_training_2026_05_15.py` | Added 3 real target scenarios to `PUBLIC_DEMO_SCENARIOS` |
| `autonomous_crawler/tests/test_browser_scenario_training.py` | Added 8 new tests for real target configs |

## Scenario Design

Each real target scenario stores selectors and expected checks in
`ScenarioDefinition` — no site-specific rules in the runtime. The harness
extracts rendered item counts from HTML via CSS selectors, captures
network_candidates from engine_result, and records profile_health from the
rotator.

Selectors were discovered via `scout_page` MCP tool before being written into
the scenario definitions.

## Evidence

Full evidence saved to:
`dev_logs/training/2026-05-15_real_site_training.json`

Contains 7 scenarios (3 local + 4 public), 6 ok, 1 failed, 11/12 checks passed.

## Test Results

```
python -m unittest autonomous_crawler.tests.test_browser_pool autonomous_crawler.tests.test_native_browser_runtime autonomous_crawler.tests.test_browser_scenario_training -v
# 175 tests OK

python -m compileall autonomous_crawler run_browser_scenario_training_2026_05_15.py -q
# Clean
```

## Remaining Work

1. Find current Virtuoso demo URL or replace with alternative virtual list demo
2. Add scroll training to SPA targets (currently only local fixtures scroll)
3. Add more real targets: ecommerce listings, search results, infinite scroll APIs
4. Profile health comparison across real targets (which profiles work best)
