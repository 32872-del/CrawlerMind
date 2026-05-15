# Acceptance: Native Executor Routing And Runtime Comparison

Date: 2026-05-14

Employee: LLM-2026-000

Track: SCRAPLING-ABSORB-1B

## Result

Accepted as supervisor mainline work.

## Accepted Deliverables

- `autonomous_crawler/agents/planner.py`
- `autonomous_crawler/agents/strategy.py`
- `autonomous_crawler/agents/executor.py`
- `autonomous_crawler/tests/test_scrapling_executor_routing.py`
- `autonomous_crawler/tests/test_native_transition_comparison.py`
- `run_native_transition_comparison_2026_05_14.py`
- `clm.py`
- `dev_logs/development/2026-05-14_native_executor_routing_and_comparison.md`
- `dev_logs/training/2026-05-14_native_transition_comparison_smoke.json`

## Capability Accepted

CLM can now explicitly route static runtime execution through its own native
fetch/parser backend:

```text
preferred_engine="native" -> Strategy engine="native" -> Executor NativeFetchRuntime + NativeParserRuntime
```

Accepted behavior:

- Planner advisor validation accepts `crawl_preferences.engine="native"`.
- Strategy advisor validation accepts `engine="native"`.
- `preferred_engine="native"` generates a `native_runtime` strategy.
- Executor static path returns normalized `raw_html`, `engine_result`,
  `runtime_events`, and proxy trace.
- Native selector evidence is attached to `engine_result.selector_results`.
- Native runtime failures return structured error output.
- Native browser path remains explicit as not implemented until
  SCRAPLING-ABSORB-2.
- Developer comparison script records native-vs-transition evidence without
  changing production defaults.

## Verification

Focused:

```text
python -m unittest autonomous_crawler.tests.test_native_transition_comparison autonomous_crawler.tests.test_scrapling_executor_routing -v
Ran 16 tests
OK
```

Full:

```text
python -m unittest discover -s autonomous_crawler/tests
Ran 1406 tests in 67.517s
OK (skipped=5)
```

Compile:

```text
python -m compileall autonomous_crawler run_skeleton.py run_baidu_hot_test.py run_results.py run_simple.py clm.py
OK
```

Smoke:

```text
python run_native_transition_comparison_2026_05_14.py --scenario example_home_static --output dev_logs\training\2026-05-14_native_transition_comparison_smoke.json
native=executed(200), transition=executed(200), html_ratio=1.0, review=False
```

## Follow-up

- Run full native-vs-transition static scenario comparison.
- Add static ecommerce/list-page comparison cases.
- Start native browser/session/proxy/XHR absorption.
- Start spider request/result/event model implementation.
