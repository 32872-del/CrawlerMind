# Extractor Fixture Test Plan from LLM-2026-006

**Date**: 2026-05-30
**Author**: LLM-2026-006
**Purpose**: Test design for 3 CLM extractors based on real fixture data. No backend code changes — this document is the test specification.

## Fixture Index

### Directory Structure

```
fixtures/
├── superdry_com/
│   ├── extraction_contract.json        — parser config, field paths, post-processors
│   ├── expected_items_sample.json      — 5 items, unified CLM fields
│   ├── raw_evidence_list_page.html     — 15KB, 3 product tiles with GTM attributes
│   └── raw_evidence_gtm_sample.json    — 5 parsed GTM product objects
├── nike_com/
│   ├── extraction_contract.json        — parser config, field paths, post-processors
│   ├── expected_items_sample.json      — 6 items, unified CLM fields
│   ├── raw_evidence_next_data_sample.json — 6 products from Wall.productGroupings
│   ├── raw_evidence_product_card.html  — 1 product card DOM excerpt
│   └── raw_evidence_wall_meta.json     — Wall pagination metadata
├── marksandspencer_com/
│   ├── extraction_contract.json        — parser config, field paths, post-processors
│   ├── expected_items_sample.json      — 5 items, unified CLM fields
│   ├── raw_evidence_graphql_sample.json — 5 products + pagination from GraphQL
│   ├── raw_evidence_meta.html          — OG meta tags
│   └── raw_evidence_urql_state.json    — urqlState key index
```

### File Role Summary

| File | Role | Used By |
|------|------|---------|
| `extraction_contract.json` | Defines HOW to extract (selectors, paths, post-processors) | Extractor implementation |
| `expected_items_sample.json` | Defines WHAT to extract (ground truth values) | Test assertions |
| `raw_evidence_*.html` | Real HTML from site crawl | Test input (happy path) |
| `raw_evidence_*.json` | Real parsed data from site crawl | Test input (happy path / synthetic __NEXT_DATA__) |

---

## 1. Superdry `data-gtm` Extractor Tests

### 1.1 Input/Output Specification

**Input**: HTML string containing `.product-tile[data-gtm]` elements
**Output**: `list[dict]` with CLM fields: `title`, `highest_price`, `currency`, `color`, `image_url`, `product_url`, `category_level_1`, `category_level_2`, `brand`, `sku`, `season`, `original_price`
**Null fields**: `size`, `description` (with `missing_reasons`)

### 1.2 Happy Path Tests

| Test Function | Input Fixture | Assertion |
|---------------|--------------|-----------|
| `test_gtm_extracts_correct_count` | `raw_evidence_list_page.html` | Returns 3 products (3 tiles in HTML) |
| `test_gtm_extracts_title` | `raw_evidence_list_page.html` | `items[0]["title"]` == expected from `expected_items_sample.json` |
| `test_gtm_extracts_price` | `raw_evidence_list_page.html` | `items[0]["highest_price"]` is float, matches expected |
| `test_gtm_extracts_currency` | `raw_evidence_list_page.html` | `items[0]["currency"]` == `"GBP"` |
| `test_gtm_extracts_color` | `raw_evidence_list_page.html` | `items[0]["color"]` matches expected (e.g. `"NAVY"`) |
| `test_gtm_extracts_brand` | `raw_evidence_list_page.html` | `items[0]["brand"]` == `"SUPERDRY"` |
| `test_gtm_extracts_sku` | `raw_evidence_list_page.html` | `items[0]["sku"]` matches expected |
| `test_gtm_extracts_category_levels` | `raw_evidence_list_page.html` | `category_level_1` and `category_level_2` match expected |
| `test_gtm_extracts_season` | `raw_evidence_list_page.html` | `items[0]["season"]` matches expected (e.g. `"SS26"`) |
| `test_gtm_extracts_original_price` | `raw_evidence_list_page.html` | `items[0]["original_price"]` is float |
| `test_gtm_extracts_image_url` | `raw_evidence_list_page.html` | `items[0]["image_url"]` starts with `https://images.laguna-live.sd.co.uk` |
| `test_gtm_extracts_product_url` | `raw_evidence_list_page.html` | `items[0]["product_url"]` starts with `https://www.superdry.com/` and ends `.html` |
| `test_gtm_all_items_match_expected` | `raw_evidence_list_page.html` + `expected_items_sample.json` | Loop all 5 expected items, match title+price |
| `test_gtm_from_json_evidence` | `raw_evidence_gtm_sample.json` | Parse 5 GTM objects directly, verify field mapping |

### 1.3 Anomaly / Edge Case Tests

| Test Function | Input | Assertion |
|---------------|-------|-----------|
| `test_gtm_no_tiles_returns_empty` | `<html><body></body></html>` | Returns `[]` |
| `test_gtm_tile_without_data_gtm_skipped` | HTML with `.product-tile` but no `data-gtm` attr | Skips tile, returns `[]` |
| `test_gtm_malformed_json_in_data_gtm` | HTML with `data-gtm="{broken"` | Skips tile, no crash |
| `test_gtm_html_entities_decoded` | HTML with `data-gtm` containing `&quot;` and `&amp;` | JSON parsed correctly |
| `test_gtm_empty_ecommerce_items` | `data-gtm='{"ecommerce":{"items":[]}}'` | Skips tile |
| `test_gtm_missing_ecommerce_key` | `data-gtm='{"other":123}'` | Skips tile |
| `test_gtm_price_is_string` | `data-gtm` with `"price":"29.99"` (string not float) | Handles or converts |
| `test_gtm_multiple_tiles_partial_malformed` | 3 tiles, middle one has bad JSON | Returns 2 products |
| `test_gtm_srcset_parsing` | HTML with multi-width srcset | `image_url` is largest width URL |
| `test_gtm_srcset_single_entry` | HTML with srcset having only 1 URL | `image_url` is that URL |
| `test_gtm_product_url_prepends_base` | HTML with `href="/womens/tops/item.html"` | URL starts with `https://www.superdry.com` |

### 1.4 Required (Must-Pass) Tests

These must pass before the extractor is considered functional:

1. `test_gtm_extracts_correct_count`
2. `test_gtm_extracts_title`
3. `test_gtm_extracts_price`
4. `test_gtm_extracts_color`
5. `test_gtm_extracts_image_url`
6. `test_gtm_extracts_product_url`
7. `test_gtm_no_tiles_returns_empty`
8. `test_gtm_malformed_json_in_data_gtm`
9. `test_gtm_html_entities_decoded`
10. `test_gtm_all_items_match_expected`

### 1.5 Enhancement Tests (Pass Later)

1. `test_gtm_price_is_string` — type coercion
2. `test_gtm_multiple_tiles_partial_malformed` — partial failure tolerance
3. `test_gtm_srcset_single_entry` — edge case

---

## 2. Nike `__NEXT_DATA__` Extractor Tests

### 2.1 Input/Output Specification

**Input**: HTML string containing `<script id="__NEXT_DATA__">` with JSON payload
**Output**: `list[dict]` with CLM fields: `title`, `highest_price`, `currency`, `color`, `image_url`, `product_url`, `category_level_1`, `brand`, `sku`
**Null fields**: `size`, `description`, `category_level_2` (with `missing_reasons`)
**Path**: `props.pageProps.initialState.Wall.productGroupings[].products[]`

### 2.2 Happy Path Tests

| Test Function | Input Fixture | Assertion |
|---------------|--------------|-----------|
| `test_nike_extracts_correct_count` | Synthetic `__NEXT_DATA__` from `raw_evidence_next_data_sample.json` | Returns 6 products |
| `test_nike_extracts_title` | Same | `items[0]["title"]` contains `"Nike Sportswear"` |
| `test_nike_extracts_price` | Same | `items[0]["highest_price"]` == `37.99` |
| `test_nike_extracts_currency` | Same | `items[0]["currency"]` == `"GBP"` |
| `test_nike_extracts_color` | Same | `items[0]["color"]` == `"Chalk/White"` |
| `test_nike_extracts_image_url` | Same | `items[0]["image_url"]` starts with `https://static.nike.com/a/images/` |
| `test_nike_extracts_product_url` | Same | `items[0]["product_url"]` starts with `https://www.nike.com/gb/t/` |
| `test_nike_extracts_sku` | Same | `items[0]["sku"]` matches `productCode` (e.g. `"IF0552-103"`) |
| `test_nike_extracts_category_level_1` | Same | `items[0]["category_level_1"]` == `"APPAREL"` |
| `test_nike_extracts_brand` | Same | `items[0]["brand"]` == `"Nike"` |
| `test_nike_all_items_match_expected` | `expected_items_sample.json` | Loop all 6 expected items, match title+price |
| `test_nike_from_product_card_html` | `raw_evidence_product_card.html` | Parse card DOM, extract title/price/image |

### 2.3 Anomaly / Edge Case Tests

| Test Function | Input | Assertion |
|---------------|-------|-----------|
| `test_nike_no_next_data_returns_empty` | `<html><body></body></html>` | Raises `ValueError` or returns `[]` |
| `test_nike_empty_product_groupings` | `__NEXT_DATA__` with `productGroupings: []` | Returns `[]` |
| `test_nike_null_products_in_grouping` | `productGroupings: [{"products": null}]` | Handles `None`, returns `[]` |
| `test_nike_missing_wall_key` | `__NEXT_DATA__` without `Wall` key | Raises or returns `[]` |
| `test_nike_missing_copy_title` | Product with `copy: {}` | Handles gracefully |
| `test_nike_missing_prices` | Product with `prices: {}` | Handles gracefully |
| `test_nike_missing_pdp_url` | Product with `pdpUrl: {}` | `product_url` is `None` |
| `test_nike_missing_colorway_images` | Product with `colorwayImages: {}` | `image_url` is `None` |
| `test_nike_multiple_colorways_per_grouping` | Grouping with 3 products | Returns all 3 as separate items |
| `test_nike_pagination_meta` | `raw_evidence_wall_meta.json` | `totalPages` and `totalResources` parsed |
| `test_nike_large_payload` | 1MB+ `__NEXT_DATA__` | Does not OOM |

### 2.4 Required (Must-Pass) Tests

1. `test_nike_extracts_correct_count`
2. `test_nike_extracts_title`
3. `test_nike_extracts_price`
4. `test_nike_extracts_color`
5. `test_nike_extracts_image_url`
6. `test_nike_extracts_product_url`
7. `test_nike_all_items_match_expected`
8. `test_nike_no_next_data_returns_empty`
9. `test_nike_null_products_in_grouping`
10. `test_nike_missing_wall_key`

### 2.5 Enhancement Tests (Pass Later)

1. `test_nike_from_product_card_html` — DOM fallback
2. `test_nike_pagination_meta` — pagination integration
3. `test_nike_large_payload` — performance
4. `test_nike_multiple_colorways_per_grouping` — completeness

---

## 3. M&S GraphQL SSR Cache Extractor Tests

### 3.1 Input/Output Specification

**Input**: HTML string containing `<script id="__NEXT_DATA__">` with `serverSideGqlResponseFed`
**Output**: `list[dict]` with CLM fields: `title`, `highest_price`, `currency`, `color`, `size`, `image_url`, `product_url`, `category_level_1`, `brand`, `sku`
**Null fields**: `description` (often null), `category_level_2` (with `missing_reasons`)
**Path**: `props.pageProps.serverSideGqlResponseFed.productPageData.search.results.products[]`
**Post-processors**: `parse_query_param` (color from seoPath), `template_expand` (image URL), `prepend_base` (product URL)

### 3.2 Happy Path Tests

| Test Function | Input Fixture | Assertion |
|---------------|--------------|-----------|
| `test_ms_extracts_correct_count` | Synthetic `__NEXT_DATA__` from `raw_evidence_graphql_sample.json` | Returns 5 products |
| `test_ms_extracts_title` | Same | `items[0]["title"]` == `"Satin V-Neck Lace Insert Midi Slip Dress"` |
| `test_ms_extracts_price` | Same | `items[0]["highest_price"]` == `50` |
| `test_ms_extracts_currency` | Same | `items[0]["currency"]` == `"GBP"` |
| `test_ms_extracts_color` | Same | `items[0]["color"]` == `"BLACKMIX"` (parsed from seoPath) |
| `test_ms_extracts_size` | Same | `items[0]["size"]` == `"6 Regular"` (from first variant) |
| `test_ms_extracts_image_url` | Same | `items[0]["image_url"]` starts with `https://assets.digitalcontent.marksandspencer.app/` |
| `test_ms_extracts_product_url` | Same | `items[0]["product_url"]` starts with `https://www.marksandspencer.com/` and contains `/p/clp` |
| `test_ms_extracts_sku` | Same | `items[0]["sku"]` matches `variants[0].skuId` |
| `test_ms_extracts_category_level_1` | Same | `items[0]["category_level_1"]` == `"Dresses"` |
| `test_ms_extracts_brand` | Same | `items[0]["brand"]` == `"M&S"` |
| `test_ms_all_items_match_expected` | `expected_items_sample.json` | Loop all 5 expected items, match title+price |
| `test_ms_total_items_from_response` | `raw_evidence_graphql_sample.json` | `totalItems` == 2493 |

### 3.3 Anomaly / Edge Case Tests

| Test Function | Input | Assertion |
|---------------|-------|-----------|
| `test_ms_no_next_data_returns_empty` | `<html><body></body></html>` | Raises or returns `[]` |
| `test_ms_empty_products_array` | `results.products: []` | Returns `[]` |
| `test_ms_missing_variants` | Product with `variants: []` | `size`, `sku` are `None` |
| `test_ms_null_description` | Product with `description: null` | `description` is `None`, `missing_reason` set |
| `test_ms_seopath_no_color_param` | `seoPath: "/dress/p/clp123"` | `color` is `None` |
| `test_ms_seopath_malformed` | `seoPath: null` | `product_url` is `None`, no crash |
| `test_ms_missing_media_assets` | Variant with `mediaAssets: []` | `image_url` is `None` |
| `test_ms_missing_price_data` | Product with `price: {}` | `highest_price` is `None` |
| `test_ms_missing_list_price` | `price.listPrice: null` | `highest_price` is `None` |
| `test_ms_color_parsing_edge_cases` | `seoPath` with `color=BLUE%2FMIX` | URL-decoded correctly |
| `test_ms_multiple_variants` | Product with 5 variants | First variant used for size/sku |
| `test_ms_pagination_structure` | `raw_evidence_graphql_sample.json` | `pagination.limit` and `pagination.offset` parsed |

### 3.4 Required (Must-Pass) Tests

1. `test_ms_extracts_correct_count`
2. `test_ms_extracts_title`
3. `test_ms_extracts_price`
4. `test_ms_extracts_color`
5. `test_ms_extracts_size`
6. `test_ms_extracts_image_url`
7. `test_ms_extracts_product_url`
8. `test_ms_all_items_match_expected`
9. `test_ms_no_next_data_returns_empty`
10. `test_ms_empty_products_array`
11. `test_ms_null_description`

### 3.5 Enhancement Tests (Pass Later)

1. `test_ms_total_items_from_response` — pagination
2. `test_ms_multiple_variants` — variant selection strategy
3. `test_ms_color_parsing_edge_cases` — URL encoding
4. `test_ms_pagination_structure` — pagination integration

---

## 4. Cross-Cutter Tests (All Extractors)

### 4.1 Fixture File Integrity

| Test Function | Assertion |
|---------------|-----------|
| `test_all_contracts_parseable` | All 3 `extraction_contract.json` load via `json.load` |
| `test_all_expected_samples_parseable` | All 3 `expected_items_sample.json` load via `json.load` |
| `test_all_raw_evidence_exists` | Every file listed in `contract.evidence_files` exists on disk |
| `test_expected_items_have_required_fields` | Every item in `expected_items_sample.json` has all 12 CLM fields |
| `test_expected_items_missing_reasons_present` | Every `None` field has a corresponding `missing_reasons` entry |

### 4.2 Contract Compliance

| Test Function | Assertion |
|---------------|-----------|
| `test_contract_has_parser_strategy` | Every contract has `parser_strategy.name` and `parser_strategy.entry_selector` |
| `test_contract_has_field_paths` | Every contract has `field_paths` with at least `title`, `highest_price` |
| `test_contract_has_evidence_files` | Every contract lists at least 1 evidence file |
| `test_contract_confidence_in_range` | Every `confidence` is between 0.0 and 1.0 |

---

## 5. Test Priority Matrix

### Must-Pass (Blocker — extractor not shippable without these)

| Category | Count | Sites |
|----------|-------|-------|
| Happy path field extraction | 18 | All 3 |
| All-items-match expected | 3 | All 3 |
| Empty/null input handling | 6 | All 3 |
| Fixture integrity | 5 | Cross |
| **Total** | **32** | |

### Enhancement (Pass before production, not blocking initial merge)

| Category | Count | Sites |
|----------|-------|-------|
| Edge case field handling | 8 | All 3 |
| Pagination | 3 | All 3 |
| Performance | 1 | Nike |
| DOM fallback | 1 | Nike |
| **Total** | **13** | |

---

## 6. Synthetic __NEXT_DATA__ Construction

For Nike and M&S tests, the raw evidence JSON files need to be wrapped in a synthetic `__NEXT_DATA__` HTML structure:

```python
import json

def make_next_data_html(page_props: dict) -> str:
    """Wrap pageProps in a synthetic __NEXT_DATA__ script tag."""
    payload = json.dumps({
        'props': {'pageProps': page_props},
        'page': '/test',
        'query': {},
        'buildId': 'test'
    })
    return f'<html><head><script id="__NEXT_DATA__" type="application/json">{payload}</script></head><body></body></html>'
```

### Nike synthetic construction:
```python
with open('fixtures/nike_com/raw_evidence_next_data_sample.json') as f:
    products = json.load(f)

html = make_next_data_html({
    'initialState': {
        'Wall': {
            'productGroupings': [{'products': products, 'cardType': 'default'}],
            'pageData': {'totalPages': 40, 'totalResources': 947}
        }
    }
})
```

### M&S synthetic construction:
```python
with open('fixtures/marksandspencer_com/raw_evidence_graphql_sample.json') as f:
    gql_data = json.load(f)

html = make_next_data_html({
    'serverSideGqlResponseFed': {
        'productPageData': {
            'search': {
                'results': gql_data
            }
        }
    }
})
```

---

## 7. Fixture File → Test Function Mapping

### superdry_com

| Evidence File | Used By Tests |
|---------------|--------------|
| `raw_evidence_list_page.html` | `test_gtm_extracts_*`, `test_gtm_no_tiles_*`, `test_gtm_tile_without_*`, `test_gtm_srcset_*`, `test_gtm_product_url_*` |
| `raw_evidence_gtm_sample.json` | `test_gtm_from_json_evidence` |
| `extraction_contract.json` | `test_contract_*` |
| `expected_items_sample.json` | `test_gtm_all_items_match_expected`, `test_expected_items_*` |

### nike_com

| Evidence File | Used By Tests |
|---------------|--------------|
| `raw_evidence_next_data_sample.json` | `test_nike_extracts_*`, `test_nike_all_items_match_expected` (wrapped in synthetic `__NEXT_DATA__`) |
| `raw_evidence_product_card.html` | `test_nike_from_product_card_html` |
| `raw_evidence_wall_meta.json` | `test_nike_pagination_meta` |
| `extraction_contract.json` | `test_contract_*` |
| `expected_items_sample.json` | `test_nike_all_items_match_expected`, `test_expected_items_*` |

### marksandspencer_com

| Evidence File | Used By Tests |
|---------------|--------------|
| `raw_evidence_graphql_sample.json` | `test_ms_extracts_*`, `test_ms_all_items_match_expected`, `test_ms_total_items_*`, `test_ms_pagination_*` (wrapped in synthetic `__NEXT_DATA__`) |
| `raw_evidence_meta.html` | Not directly used by extractor tests (metadata only) |
| `raw_evidence_urql_state.json` | Not directly used by extractor tests (metadata only) |
| `extraction_contract.json` | `test_contract_*` |
| `expected_items_sample.json` | `test_ms_all_items_match_expected`, `test_expected_items_*` |

---

## 8. Test Execution Order

```
Phase 1: Fixture integrity (5 tests)
  ↓ if all pass
Phase 2: Contract compliance (4 tests)
  ↓ if all pass
Phase 3: Happy path extraction (18 tests)
  ↓ if all pass
Phase 4: Expected value matching (3 tests)
  ↓ if all pass
Phase 5: Null/empty input handling (6 tests)
  ↓ if all pass
→ Extractor is shippable

Phase 6: Edge cases (8 tests) — can be async
Phase 7: Pagination (3 tests) — can be async
Phase 8: Performance (1 test) — can be async
```

---

## 9. Summary

| Metric | Value |
|--------|-------|
| Total test functions designed | 45 |
| Must-pass tests | 32 |
| Enhancement tests | 13 |
| Fixture files referenced | 14 |
| Extractors covered | 3 |
| Failure scenarios covered | 11 |
| Synthetic helpers needed | 1 (`make_next_data_html`) |
