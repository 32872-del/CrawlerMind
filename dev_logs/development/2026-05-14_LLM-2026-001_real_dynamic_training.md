# SCRAPLING-ABSORB-2I: Real Dynamic And Protected Training

Date: 2026-05-14
Worker: LLM-2026-001

## Objective

Run the native browser backend through real dynamic/protected training and produce
structured evidence for gap analysis. Prove profile rotation works across scenarios.

## What Was Done

### Modified Files

1. **`run_real_dynamic_training_2026_05_14.py`** — refactored
   - Extracted `_build_result()` helper — single source of truth for result construction
   - Both `run_scenario()` and `run_scenario_with_runtime()` use `_build_result()`
   - Profile rotation via shared runtime when `--profile` flag is used
   - 4 training scenarios: js_rendered, js_scroll, protected_challenge, dynamic_headers

### Created Files

1. **`autonomous_crawler/tests/test_real_dynamic_training.py`** — 25 tests
   - `CheckExpectedTests` (12 tests): min_html_chars, min_selector_hits, failure_category, status_code, combined
   - `BuildResultTests` (6 tests): basic, failed, engine_result, xhr, selectors, expected
   - `ScenarioListTests` (4 tests): count, required keys, unique IDs, HTTPS
   - `RunScenarioWithRuntimeTests` (3 tests): success, error, request fields

2. **`dev_logs/training/2026-05-14_real_dynamic_training.json`** — evidence without profile
3. **`dev_logs/training/2026-05-14_real_dynamic_training_profile.json`** — evidence with profile

## Training Scenarios

| ID | Site | Mode | Risk | Result |
|---|---|---|---|---|
| js_rendered_quotes | quotes.toscrape.com/js/ | dynamic | low-public-training-site | OK (200, 8940 chars, 10 quotes) |
| js_rendered_scroll | quotes.toscrape.com/js/ | dynamic | low-public-training-site | OK (200, 8940 chars, 10 quotes) |
| protected_challenge_like | httpbin.org/status/403 | dynamic | medium-expected-failure | FAIL (403, http_blocked) |
| dynamic_with_headers | httpbin.org/headers | dynamic | low-public-api | OK (200, 1027 chars, 1 XHR) |

## Profile Rotation Evidence

With `--profile` flag, rotation cycles correctly:
- Scenario 1: training-desktop
- Scenario 2: training-mobile
- Scenario 3: training-desktop (wrapped)
- Scenario 4: training-mobile (wrapped)

## Failure Classification

Only expected failure: `http_blocked` on httpbin.org/403. No crashes, no unexpected errors.

## Selector Matching

Uses lxml CSS selectors when available, falls back to string counting. All selector
checks passed on quotes.toscrape.com/js/ (10 .quote, 10 .text, 10 .author, 10 .tag).

## Tests Run

```
python -m unittest autonomous_crawler.tests.test_real_dynamic_training -v
# 25 tests OK

python run_real_dynamic_training_2026_05_14.py
# 3 ok, 1 failed (expected http_blocked)

python run_real_dynamic_training_2026_05_14.py --profile
# 3 ok, 1 failed, profile rotation verified
```

## What Was NOT Changed

- No site-specific extraction rules in core runtime
- No Scrapling import
- No changes to proxy runtime, spider runner, or JS analysis modules
- Training runner is standalone, not wired into production flow
