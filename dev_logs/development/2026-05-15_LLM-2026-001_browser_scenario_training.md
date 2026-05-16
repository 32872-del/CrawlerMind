# SCRAPLING-HARDEN-2B: Browser Scenario Training

Date: 2026-05-15
Worker: LLM-2026-001

## Summary

Created a browser scenario training harness with 3 deterministic local fixtures
for scroll, virtualized list, and mobile viewport scenarios. The harness runs
the CLM NativeBrowserRuntime through each scenario and collects structured
evidence including profile health, scroll events, rendered item counts, and
failure classifications.

## Deliverables

### Fixture HTML Files (3)

| File | Purpose | Key Features |
|---|---|---|
| `tests/fixtures/browser_scenarios/infinite_scroll.html` | Infinite scroll with IntersectionObserver | 50 items across 5 pages, sentinel-based loading |
| `tests/fixtures/browser_scenarios/virtualized_list.html` | Virtualized list (10k items) | Viewport-driven rendering, 50px row height |
| `tests/fixtures/browser_scenarios/mobile_viewport.html` | Mobile card layout | Touch events, responsive CSS, horizontal nav |

All fixtures expose `window.__scroll_events`, `window.__rendered_count`, and a
hidden `<pre id="__training_state">` element for DOM-based state extraction.

### Training Runner

`run_browser_scenario_training_2026_05_15.py`:
- `FixtureServer`: Minimal HTTP server for local fixtures (context manager)
- `ScenarioDefinition`: Dataclass with scroll/mobile fields
- `LOCAL_SCENARIOS`: 3 fixture scenarios
- `PUBLIC_DEMO_SCENARIOS`: 1 public demo (React Virtuoso)
- `build_evidence()`: Collects profile_health, scroll_events, network_candidates, etc.
- `run_scenario()`: Runs single scenario, extracts training state from HTML
- `_run_scroll_training()`: Second render pass with DOM-aware scroll init_script
- `run_training()`: Orchestrates all scenarios with fixture server
- CLI: `--profile`, `--public`, `--scenario`, `--output`

### Tests

`autonomous_crawler/tests/test_browser_scenario_training.py` — 55 tests:
- ScenarioDefinitionTests (3)
- FixtureServerTests (3)
- ExtractTrainingStateTests (4)
- CheckExpectedTests (9)
- BuildEvidenceTests (6)
- RunScenarioTests (7)
- ScrollTrainingTests (4)
- ScenarioListTests (8)
- ProfileHealthEvidenceTests (2)
- FixtureIntegrityTests (9)

## Key Design Decisions

1. **DOM-based state extraction**: Since NativeBrowserRuntime doesn't expose
   `page.evaluate()`, fixtures write scroll/viewport data to a hidden
   `<pre id="__training_state">` element. The runner parses this from HTML.

2. **Scroll training via init_script**: The scroll script waits for
   `DOMContentLoaded` before scrolling, ensuring the target element exists.
   `render_time_ms` is set to accommodate all scroll iterations.

3. **No site-specific rules in runtime**: All scenario differences (selectors,
   scroll targets, mobile profiles) live in `ScenarioDefinition` instances,
   not in the runtime code.

## Test Results

```
python -m unittest autonomous_crawler.tests.test_browser_pool autonomous_crawler.tests.test_native_browser_runtime autonomous_crawler.tests.test_real_dynamic_training -v
# 137 tests OK

python -m unittest autonomous_crawler.tests.test_browser_scenario_training -v
# 55 tests OK

python -m compileall autonomous_crawler run_browser_scenario_training_2026_05_15.py -q
# Clean

python run_browser_scenario_training_2026_05_15.py
# 3/3 scenarios passed, 5/5 checks passed
```

Full suite: 1903 tests OK (5 skipped).

## Training Evidence

Local fixture results:
- **infinite_scroll**: 50 rendered items, 10 scroll events
- **virtualized_list**: 18 rendered items, 16 scroll events
- **mobile_viewport**: 8 rendered items

Evidence saved to `dev_logs/training/2026-05-15_browser_scenario_training.json`.

## Remaining Work

1. **Real site training**: Public demo (React Virtuoso) not yet run in CI.
   Need to add more real-world scenarios with anti-bot, lazy-load, SPA routing.
2. **init_script timing**: The scroll init_script starts before page load.
   If a fixture's JS takes long to initialize, scrolling may race. Consider
   adding a configurable initial delay.
3. **Profile rotation evidence**: Training runner creates rotator with
   desktop+mobile profiles but doesn't yet compare health scores across
   scenarios. Could add cross-scenario health aggregation.
