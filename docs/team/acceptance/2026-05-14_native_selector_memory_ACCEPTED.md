# Native Selector Memory - Accepted

Date: 2026-05-14
Owner: LLM-2026-000
Track: SCRAPLING-ABSORB-1E

## Accepted Scope

Accepted.

This work adds persistent adaptive selector memory to the CLM-native parser
backend:

- SQLite-backed `SelectorMemoryStore`
- automatic signature save after successful CSS/XPath matches
- automatic signature load on selector miss
- structural relocation through the existing adaptive parser
- success/recovery counters for later diagnostics

The implementation stays on target: it absorbs Scrapling-style adaptive parser
behavior into CLM-owned runtime/storage code without adding site-specific rules
or importing Scrapling as the final backend.

## Verification

```text
python -m unittest autonomous_crawler.tests.test_selector_memory -v
Ran 4 tests OK

python -m unittest autonomous_crawler.tests.test_native_adaptive_parser -v
Ran 5 tests OK

python -m unittest autonomous_crawler.tests.test_native_parser_runtime -v
Ran 48 tests OK

python -m unittest autonomous_crawler.tests.test_native_runtime_parity -v
Ran 100 tests OK (skipped=1)

python -m unittest autonomous_crawler.tests.test_scrapling_executor_routing -v
Ran 13 tests OK
```

## Follow-Up

Connect selector memory to spider/product runs so repeated long-running crawls
can learn and recover field selectors automatically.
