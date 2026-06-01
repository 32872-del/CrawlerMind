# 2026-05-30 Auto Extraction Contract Discovery v1

## Summary

This development round moved ecommerce extraction contracts from manual
training artifacts into the CLM workbench flow.

Before this change, `extract_from_contract` could execute a known contract, but
the frontend or caller had to pass both the contract and evidence manually.
After this change, `/site/analyze` can discover supported extraction contracts
from fetched evidence, attach the best contract to the returned profile, and
let managed actions execute it later without resending large HTML/JSON payloads.

## Backend Changes

- Added `autonomous_crawler/tools/extraction_contracts.py`.
- Added automatic detection and validation for:
  - `gtm_data_attribute_extractor`
  - `next_data_product_wall_extractor`
  - `next_data_graphql_ssr_cache_extractor`
  - `jsonld_product_extractor`
  - `jsonld_itemlist_extractor`
  - `shopify_product_grid_extractor`
  - `demandware_product_tile_extractor`
- Updated `analyze_site_for_product_workflow()` to return:
  - `extraction_contract_discovery`
  - `extraction_context`
  - profile constraints containing `extraction_contract`,
    `extraction_contract_discovery`, bounded `extraction_evidence`, and source
    URL metadata.
- Updated managed actions so profile-carried extraction contracts/evidence are
  automatically merged into action context.
- Updated managed state so `extraction_context` can see contracts stored under
  `profile.constraints`.

## Why This Matters

This is a hard-capability step, not just another report. It gives the AI managed
loop a concrete extraction tool discovered during analysis:

```text
/site/analyze
  -> contract discovery
  -> returned profile carries contract/evidence
  -> /runs/test
  -> /managed-actions
  -> extract_from_contract executes
  -> normalized ecommerce items appear in managed state
```

This reduces dependence on fragile generic selectors and gives the LLM a real
tool path it can choose during managed actions.

## Tests

Passed:

```text
python -m unittest autonomous_crawler.tests.test_extraction_contracts autonomous_crawler.tests.test_managed_actions autonomous_crawler.tests.test_ecommerce_extractors -v
python -m unittest autonomous_crawler.tests.test_product_workflow_api.ManagedAIRunTests autonomous_crawler.tests.test_product_workflow_api.ProductWorkflowCoreTests -v
```

Key new regression:

```text
test_analyzed_profile_feeds_contract_extraction_without_manual_extra_context
```

This verifies the real workbench chain:

```text
/site/analyze profile -> /runs/test -> /managed-actions
```

and confirms `extract_from_contract` runs without manual `extra_context`.

## Known Limits

- Current discovery only sees evidence available to `fetch_best_html`; deeper
  browser/XHR evidence should also feed contract discovery next.
- Evidence stored in profile constraints is bounded to 500,000 characters.
- Current contract family covers common ecommerce structures, but more real
  platforms from 005/006 datasets should be converted into native extractors.

## Next Step

Wire contract discovery into live access probe and browser/XHR evidence, so
dynamic sites can produce contracts from rendered DOM, `__NEXT_DATA__`, network
JSON samples, and replayable API responses, not only the initial site-analysis
HTML.
