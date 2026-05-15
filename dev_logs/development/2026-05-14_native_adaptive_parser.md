# 2026-05-14 Native Adaptive Parser

Owner: LLM-2026-000

## Summary

Implemented a CLM-native adaptive parser slice as part of Scrapling capability
absorption. This is not a Scrapling wrapper. The new code rebuilds the useful
parser-side behavior inside CLM runtime modules:

- element structural signatures
- similarity scoring
- relocation when a saved selector no longer matches
- same-depth repeated-node discovery from a seed element
- executor propagation of `RuntimeRequest.selector_config` into parser runtime

## Files

- `autonomous_crawler/runtime/adaptive_parser.py`
- `autonomous_crawler/runtime/native_parser.py`
- `autonomous_crawler/runtime/models.py`
- `autonomous_crawler/runtime/protocols.py`
- `autonomous_crawler/runtime/scrapling_parser.py`
- `autonomous_crawler/runtime/__init__.py`
- `autonomous_crawler/agents/executor.py`
- `autonomous_crawler/tests/test_native_adaptive_parser.py`

## Verification

```text
python -m unittest autonomous_crawler.tests.test_native_adaptive_parser -v
Ran 4 tests OK

python -m unittest autonomous_crawler.tests.test_native_parser_runtime -v
Ran 48 tests OK

python -m unittest autonomous_crawler.tests.test_runtime_protocols -v
Ran 5 tests OK

python -m unittest autonomous_crawler.tests.test_scrapling_executor_routing -v
Ran 13 tests OK

python -m unittest autonomous_crawler.tests.test_native_runtime_parity -v
Ran 100 tests OK (skipped=1)

python -m compileall autonomous_crawler run_skeleton.py run_baidu_hot_test.py run_results.py
OK

python -m unittest discover -s autonomous_crawler/tests
Ran 1617 tests OK (skipped=5)
```

## Notes

This slice gives CLM the parser-side foundation for pages where class names or
DOM wrappers drift between runs. The next useful parser step is to persist and
reuse learned signatures across runs rather than requiring them to be supplied
through `selector_config` or `RuntimeSelectorRequest.signature`.
