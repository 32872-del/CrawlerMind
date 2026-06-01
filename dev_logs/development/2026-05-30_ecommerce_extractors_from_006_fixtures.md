# 2026-05-30 Ecommerce Extractors from 006 Fixtures

## Summary

Implemented the first CLM-native ecommerce evidence extractors from 006's
fixture contracts.

## Added

- `autonomous_crawler/tools/ecommerce_extractors.py`
  - GTM `data-gtm` product tile extractor.
  - Nike-style `__NEXT_DATA__` product wall extractor.
  - M&S-style `__NEXT_DATA__` / GraphQL SSR cache extractor.
  - Contract router via `extract_items_from_contract()`.
- `autonomous_crawler/tests/test_ecommerce_extractors.py`
  - Fixture-based tests using 006 training evidence.
  - Happy path and edge path coverage for malformed GTM JSON, missing
    `__NEXT_DATA__`, empty GraphQL products, missing variants, and unsupported
    contracts.
- `autonomous_crawler/runners/managed_actions.py`
  - Added executable `extract_from_contract` managed action.
  - Added bounded validation for `contract`, `evidence`, `source_url`, and
    `max_items` action params.
  - Action results now return `contract-extraction-result/v1` in
    `run_overrides.extraction_result` so the managed loop can carry extracted
    items forward.
- `autonomous_crawler/tests/test_managed_actions.py`
  - Added managed action protocol and execution coverage using the Superdry
    fixture contract.
  - Added failure-path coverage for unsupported parser strategy and missing
    evidence.

## Notes

- The GTM extractor includes a regex fallback for broken or truncated listing
  HTML where lxml cannot preserve all sibling product tile nodes.
- This step wires pure extraction capability into the managed Action Executor.
  The next step is exposing the action in the AI action prompt/workbench bridge
  so a model can choose it during managed crawl repair and rerun.

## Verification

```text
python -m unittest autonomous_crawler.tests.test_ecommerce_extractors -v
python -m unittest autonomous_crawler.tests.test_managed_actions -v
python -m unittest autonomous_crawler.tests.test_product_quality -v
python -m compileall autonomous_crawler run_simple.py run_skeleton.py run_results.py
```

All passed.
