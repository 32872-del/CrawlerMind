# REAL-HARDEN-4: Dynamic/Virtual List Training Enhancement

Date: 2026-05-15
Worker: LLM-2026-001

## Summary

Extended browser scenario training harness with 3 new public dynamic list targets
and added `stop_reason` field to all training evidence.

## Changes

| File | Change |
|---|---|
| `run_browser_scenario_training_2026_05_15.py` | Added `stop_reason` parameter to `build_evidence()`, computed in `run_scenario()`; added 3 new public scenarios |
| `autonomous_crawler/tests/test_browser_scenario_training.py` | +8 tests for stop_reason and new scenario configs |

## New Targets

| Target | Type | Items | HTML | Status | stop_reason |
|---|---|---|---|---|---|
| ScrapeThisSite AJAX | Click-driven AJAX | 6 year links | 15k | OK | completed |
| DummyJSON Products | SSR product list | 0 | 44k | OK | no_items_matched |
| ScrapeThisSite Countries | Static country list | 250 | 205k | OK | completed |

## stop_reason Values

- `completed` — scenario finished successfully
- `navigation_timeout` — page didn't load (e.g., 404, network issue)
- `render_failed` — response not ok
- `runtime_error` — exception during render
- `scroll_error` — scroll training failed
- `scroll_no_items` — scroll ran but no items found
- `no_items_matched` — page loaded but selectors didn't match

## Evidence

`dev_logs/training/2026-05-15_real_harden4_dynamic_list_training.json`

## Test Results

```
python -m unittest autonomous_crawler.tests.test_browser_scenario_training -v
# 72 tests OK

python -m unittest autonomous_crawler.tests.test_browser_scenario_training autonomous_crawler.tests.test_browser_pool -v
# 189 tests OK
```

## Remaining Risks

1. DummyJSON Products page uses client-side rendering — CSS selectors need adjustment
2. ScrapeThisSite AJAX loads data on click (not scroll) — training only captures initial HTML
3. React Virtuoso 404 persists — documented in prior handoff
