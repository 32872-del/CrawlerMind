# Handoff: REAL-HARDEN-1 Real Public Dynamic Browser Training

Date: 2026-05-15
Worker: LLM-2026-001
Status: Complete

## What Was Done

Extended browser scenario training harness with 3 real public SPA/doc-site
targets. All produce usable evidence. Virtuoso URL is 404 (follow-up needed).

## Real Target Evidence

| Target | Items | HTML | Status |
|---|---|---|---|
| Vue.js Examples | 57 | 103k | OK |
| React.dev Learn | 51 | 283k | OK |
| TanStack Virtual | 2 | 256k | OK |
| React Virtuoso | 0 | 0 | FAIL (404) |

Evidence: `dev_logs/training/2026-05-15_real_site_training.json`

## Files Changed

| File | Change |
|---|---|
| `run_browser_scenario_training_2026_05_15.py` | Added vue_examples_spa, react_learn_spa, tanstack_virtual_docs scenarios |
| `autonomous_crawler/tests/test_browser_scenario_training.py` | +8 tests for real target configs |

## How to Verify

```bash
python run_browser_scenario_training_2026_05_15.py --public
python -m unittest autonomous_crawler.tests.test_browser_pool autonomous_crawler.tests.test_native_browser_runtime autonomous_crawler.tests.test_browser_scenario_training -v
python -m compileall autonomous_crawler run_browser_scenario_training_2026_05_15.py -q
```

## Follow-up

- Virtuoso demo URL changed — find current URL or replace target
- SPA targets don't scroll yet (no scroll_events for real sites)
- Add ecommerce/search/infinite-scroll real targets
