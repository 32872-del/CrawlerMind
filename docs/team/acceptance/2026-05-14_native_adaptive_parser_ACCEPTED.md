# Native Adaptive Parser - Accepted

Date: 2026-05-14
Owner: LLM-2026-000

## Accepted Scope

Accepted as `SCRAPLING-ABSORB-1D`: CLM-native adaptive parser capability.

The implementation absorbs the relevant Scrapling parser behavior into CLM
runtime code without importing Scrapling:

- build serializable element signatures from lxml elements
- calculate structural similarity scores
- relocate a previous element signature when CSS/XPath selectors miss
- find similar repeated nodes from a seed element at the same tree depth
- pass `RuntimeRequest.selector_config` from executor into parser runtime

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

python -m unittest discover -s autonomous_crawler/tests
Ran 1617 tests OK (skipped=5)
```

## Follow-Up

Persist learned element signatures and connect them to site/task memory so
adaptive recovery can happen automatically across long-running crawls and later
training runs.
