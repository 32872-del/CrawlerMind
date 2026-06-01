# Ecommerce Extractors: 3 New Evidence Patterns

**Date**: 2026-05-30
**Author**: Employee 002 (CLM Backend)
**Related**: `docs/plans/2026-05-30_BACKEND_EXTRACTOR_PATTERNS_FROM_006.md`

## What Was Done

Added 3 new CLM-native ecommerce evidence pattern extractors to `autonomous_crawler/tools/ecommerce_extractors.py`:

### 1. JSON-LD Product / ItemList Extractor

- `extract_jsonld_product_items(html)` — parses `<script type="application/ld+json">` for Product schema
- `extract_jsonld_itemlist_items(evidence)` — handles ItemList containers, pre-parsed dicts/lists
- Contract names: `jsonld_product_extractor`, `jsonld_itemlist_extractor`
- Coverage: schema.org Product markup (~30% of e-commerce sites)

### 2. Shopify Product Grid JSON Extractor

- `extract_shopify_product_grid_items(evidence)` — parses Shopify `/collections/*.json`, product grid inline JSON, and `Shopify.analytics.meta.product`
- Contract name: `shopify_product_grid_extractor`
- Handles `compare_at_price` vs `price` logic (prefers higher/original price)
- Extracts Color/Size from product options array

### 3. Demandware / SFCC Product Tile Extractor

- `extract_demandware_product_tile_items(html)` — DOM tile parsing (`.product-tile[data-pid]`) with JS fallback (`productImpressions` array)
- Contract name: `demandware_product_tile_extractor`
- Handles price from `content` attribute or text content
- JS fallback catches impression data when DOM tiles are absent

## Contract Router Updates

`extract_items_from_contract()` now routes 6 strategies:
1. `gtm_data_attribute_extractor` (existing)
2. `next_data_product_wall_extractor` (existing)
3. `next_data_graphql_ssr_cache_extractor` (existing)
4. `jsonld_product_extractor` (new)
5. `shopify_product_grid_extractor` (new)
6. `demandware_product_tile_extractor` (new)

## Tests Added (29 new tests)

### JsonLdProductExtractorTests (11 tests)
- `test_extract_product_from_html` — happy path
- `test_extract_itemlist_from_html` — ItemList with 2 products
- `test_itemlist_as_dict` — pre-parsed ItemList dict
- `test_product_as_dict` — single Product dict
- `test_list_of_products` — list of Product dicts
- `test_malformed_json_ld_is_skipped` — broken JSON
- `test_missing_script_returns_empty` — no ld+json
- `test_non_product_schema_ignored` — Organization schema ignored
- `test_product_offers_as_list` — offers as array
- `test_product_image_as_string` — image as string vs array
- `test_contract_routes_jsonld` — contract routing

### ShopifyProductGridExtractorTests (8 tests)
- `test_extract_products_from_json` — happy path with compare_at_price
- `test_compare_at_price_preferred` — price logic
- `test_list_of_products` — list input
- `test_missing_optional_fields` — minimal product
- `test_empty_products` — empty list
- `test_malformed_string_returns_empty` — non-JSON string
- `test_analytics_meta_product` — Shopify analytics meta
- `test_contract_routes_shopify` — contract routing

### DemandwareProductTileExtractorTests (7 tests)
- `test_extract_tiles_from_html` — happy path with 2 tiles
- `test_missing_optional_fields` — tile without image/link
- `test_empty_html_returns_empty` — empty string
- `test_no_tiles_returns_empty` — HTML without tiles
- `test_js_fallback_extraction` — productImpressions JS fallback
- `test_non_html_evidence_returns_empty` — non-string evidence
- `test_contract_routes_demandware` — contract routing

## Test Results

```
test_ecommerce_extractors: 42/42 OK (13 existing + 29 new)
test_managed_actions: 17/17 OK
compileall: EXIT=0
```

## Output Field Consistency

All new extractors produce the standard CLM item shape:
```
title, highest_price, currency, color, size, description,
image_url, product_url, category_level_1, category_level_2,
source_evidence, missing_reasons
```

Plus optional: `brand`, `sku`, `product_id`, `original_price`.

## What Was NOT Done

- No external library wrappers added
- No site-specific hardcoded rules in core (fixture data is test-only)
- No git commit (per instruction)
