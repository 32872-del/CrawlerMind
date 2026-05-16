# Handoff: SCRAPLING-HARDEN-2B Browser Scenario Training

Date: 2026-05-15
Worker: LLM-2026-001
Status: Complete

## What Was Done

Created a browser scenario training harness with 3 deterministic local fixtures
and a runner script that exercises the NativeBrowserRuntime through scroll,
virtualized list, and mobile viewport scenarios.

## Files Changed/Created

| File | Status |
|---|---|
| `run_browser_scenario_training_2026_05_15.py` | Created |
| `autonomous_crawler/tests/test_browser_scenario_training.py` | Created (55 tests) |
| `autonomous_crawler/tests/fixtures/browser_scenarios/infinite_scroll.html` | Created |
| `autonomous_crawler/tests/fixtures/browser_scenarios/virtualized_list.html` | Created |
| `autonomous_crawler/tests/fixtures/browser_scenarios/mobile_viewport.html` | Created |

## How to Verify

```bash
# Run all acceptance tests
python -m unittest autonomous_crawler.tests.test_browser_pool autonomous_crawler.tests.test_native_browser_runtime autonomous_crawler.tests.test_real_dynamic_training -v
python -m unittest autonomous_crawler.tests.test_browser_scenario_training -v
python -m compileall autonomous_crawler run_browser_scenario_training_2026_05_15.py -q

# Run training
python run_browser_scenario_training_2026_05_15.py
```

## Key Technical Notes

1. **DOM-based state extraction**: Fixtures write JS state to
   `<pre id="__training_state">` since the runtime doesn't expose
   `page.evaluate()`. Parsed via regex from HTML.

2. **Scroll training**: Uses init_script with `DOMContentLoaded` listener
   + `render_time_ms` to give scrolling time to complete before HTML capture.

3. **No site-specific runtime rules**: All differences in ScenarioDefinition.

## Known Limitations

- Public demo scenario (React Virtuoso) defined but not yet run in CI
- Scroll init_script races with page JS if page has slow initialization
- No cross-scenario health aggregation
