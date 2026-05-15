# 2026-05-14 Native Selector Memory

Owner: LLM-2026-000

Track: SCRAPLING-ABSORB-1E

## Summary

Added persistent adaptive selector memory for the CLM-native parser runtime.
This extends the earlier adaptive parser slice from "caller supplies a
signature" to "runtime can learn signatures from successful parses and reuse
them after selector drift."

## Files

- `autonomous_crawler/storage/selector_memory.py`
- `autonomous_crawler/storage/__init__.py`
- `autonomous_crawler/runtime/native_parser.py`
- `autonomous_crawler/tests/test_selector_memory.py`
- `autonomous_crawler/tests/test_native_adaptive_parser.py`

## Behavior

- `SelectorMemoryStore` persists element signatures in SQLite.
- `NativeParserRuntime` can auto-save a successful CSS/XPath match when
  `selector_config.adaptive_auto_save=true` or `adaptive_memory_path` is set.
- On selector miss, `NativeParserRuntime` can load a saved signature from
  memory and relocate the element by structural similarity.
- Recovery counts and last relocation score are stored for future diagnostics.

## Verification

```text
python -m unittest autonomous_crawler.tests.test_selector_memory -v
Ran 4 tests OK

python -m unittest autonomous_crawler.tests.test_native_adaptive_parser -v
Ran 5 tests OK

python -m unittest autonomous_crawler.tests.test_native_parser_runtime -v
Ran 48 tests OK

python -m unittest autonomous_crawler.tests.test_runtime_protocols -v
Ran 5 tests OK

python -m unittest autonomous_crawler.tests.test_native_runtime_parity -v
Ran 100 tests OK (skipped=1)

python -m unittest autonomous_crawler.tests.test_scrapling_executor_routing -v
Ran 13 tests OK

python -m compileall autonomous_crawler run_skeleton.py run_baidu_hot_test.py run_results.py
OK
```

## Next

Wire selector memory into long-running spider/product runs so field-level
selector learning happens automatically during real crawls.
