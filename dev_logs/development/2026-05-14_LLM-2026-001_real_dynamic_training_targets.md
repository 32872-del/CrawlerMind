# SCRAPLING-ABSORB-2E-A: Real Dynamic Training Targets

Date: 2026-05-14
Worker: LLM-2026-001

## Objective

Prepare dynamic/ecommerce training target fixtures for native-vs-transition
comparison and verify browser evidence QA.  Deliver a helper module defining
5-8 scenario types covering the required categories, plus focused tests proving
targets carry wait_selector, wait_until, selectors, capture_xhr, and expected
evidence fields.

## What Was Done

### Created Files

1. **`autonomous_crawler/tests/dynamic_training_targets.py`** — fixture module
   - 8 scenario type definitions covering all required categories
   - `SCENARIO_TYPES` list, `SCENARIO_BY_ID` dict, `CATEGORIES` list
   - Helper functions: `get_scenario()`, `get_scenarios_by_category()`, `build_state()`
   - `build_state()` mirrors the comparison runner's mapping without importing executor

2. **`autonomous_crawler/tests/test_dynamic_training_targets.py`** — 48 focused tests
   - ScenarioCatalogueTests (7): count, categories, unique IDs, lookup
   - ScenarioEvidenceFieldTests (10): all required fields present on every scenario
   - BrowserScenarioEvidenceTests (4): browser-mode carries wait_selector/wait_until/browser_config
   - XhrCaptureScenarioTests (2): XHR scenarios are browser-mode with valid regex
   - ChallengeBlockEvidenceTests (3): challenge scenarios have expected_evidence
   - SessionScenarioTests (2): session scenarios have user_data_dir/storage_state
   - ScrollScenarioTests (2): scroll scenarios have scroll_count/scroll_delay
   - ProtectedInitScriptTests (3): protected scenarios have init_script
   - BuildStateTests (13): build_state maps all fields correctly for both engines
   - ScenarioRoundTripTests (2): scenario->build_state preserves evidence keys

### Scenario Types (8 total)

| ID | Category | Mode | Key Evidence |
|---|---|---|---|
| js_rendered_product_list | js_rendered_list | browser | wait_selector, wait_until, browser_config |
| xhr_api_product_data | xhr_api_data | browser | capture_xhr regex, browser_config |
| lazy_load_infinite_scroll | lazy_load_scroll | browser | scroll_count, scroll_delay in browser_config |
| cookie_session_changes | cookie_session | browser | user_data_dir, storage_state in browser_config |
| challenge_block_evidence | challenge_block | browser | expected_evidence with failure_classification |
| static_fallback_page | static_fallback | http | no browser fields, static mode |
| multi_page_pagination | pagination | browser | max_items, next_page selector |
| protected_dynamic_init_script | protected_init | browser | init_script, fingerprint_report |

### Tests Run

```
python -m unittest autonomous_crawler.tests.test_dynamic_training_targets -v
# 48 tests, all OK (0.002s)

python -m unittest autonomous_crawler.tests.test_native_transition_comparison -v
# 8 tests, all OK (no regression)
```

## What Was NOT Changed

- No executor shared boundary modified
- No site-specific rules written into native runtime
- No public network dependency in tests
- No changes to `run_native_transition_comparison_2026_05_14.py`
- No changes to `native_browser.py` or `scrapling_browser.py`

## Known Risks

- Scenario URLs are example.com placeholders — not real training targets
- `build_state()` is a standalone reimplementation; if the comparison runner's
  `build_state()` drifts, these fixtures may diverge
- No live browser integration — scenarios validate data shape only
- scroll_count/scroll_delay are in browser_config but not yet consumed by all
  runtime paths (NativeBrowserRuntime reads them from request, not config)

## Next Steps (for supervisor)

1. Replace placeholder URLs with real dynamic/ecommerce training targets
2. Run comparison harness against real targets to validate native-vs-transition
3. Calibrate expected_evidence for challenge scenarios based on real results
4. Consider wiring `build_state()` from this module into the comparison runner
   to avoid duplication
