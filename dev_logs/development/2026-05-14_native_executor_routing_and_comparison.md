# 2026-05-14 - Native Executor Routing And Runtime Comparison

Owner: LLM-2026-000

Track: SCRAPLING-ABSORB-1B

## Work Completed

- Added explicit `engine="native"` support to Planner and Strategy validation.
- Added Strategy generation for user-requested CLM-native runtime backend.
- Added Executor routing for `engine="native"` static HTTP runtime path.
- Wired `NativeFetchRuntime` and `NativeParserRuntime` into the executor
  runtime contract path.
- Kept native browser runtime as an explicit unimplemented gap instead of
  pretending browser absorption is complete.
- Added native runtime routing tests alongside existing Scrapling runtime
  routing tests.
- Added `run_native_transition_comparison_2026_05_14.py`, a developer helper
  for comparing native and Scrapling transition static runtime output.
- Added `clm.py train --round native-vs-transition` command hint.
- Ran a smoke comparison against `https://example.com/`.

## Smoke Result

Output:

```text
dev_logs/training/2026-05-14_native_transition_comparison_smoke.json
```

Summary:

- native: executed, HTTP 200, 528 HTML chars, title/link selectors matched
- transition: executed, HTTP 200, 528 HTML chars, title/link selectors matched
- HTML ratio native/transition: 1.0
- selector delta: 0
- review required: false

## Verification

```text
python -m unittest autonomous_crawler.tests.test_native_transition_comparison autonomous_crawler.tests.test_scrapling_executor_routing -v
Ran 16 tests
OK

python -m unittest discover -s autonomous_crawler/tests
Ran 1402 tests in 68.248s
OK (skipped=5)

python -m compileall autonomous_crawler run_skeleton.py run_baidu_hot_test.py run_results.py run_simple.py clm.py
OK

python run_native_transition_comparison_2026_05_14.py --scenario example_home_static --output dev_logs\training\2026-05-14_native_transition_comparison_smoke.json
native=executed(200), transition=executed(200), html_ratio=1.0, review=False
```

## Next

- Run the comparison script on the full built-in static scenario list.
- Add more static ecommerce/list-page comparison targets.
- Start SCRAPLING-ABSORB-2: CLM-native browser/session/proxy/XHR runtime.
- Start SCRAPLING-ABSORB-3A: spider request/result/event models.

