# Fixture Quality Audit

**Date**: 2026-05-30
**Author**: Employee 002 (CLM Backend)
**Scope**: Real 006 fixtures in `xiaomi_recon_2026_05_28/fixtures/`, inline fixtures in `test_ecommerce_extractors.py`, 006 extractor patterns document

---

## Fixture Inventory

### Real Fixture Directories (from 006 deep recon)

| Site | Directory | Evidence Files | Contract | Expected Items |
|------|-----------|---------------|----------|----------------|
| superdry_com | `xiaomi_recon_2026_05_28/fixtures/superdry_com/` | `raw_evidence_list_page.html`, `raw_evidence_gtm_sample.json` | YES (extraction_contract.json) | YES (expected_items_sample.json) |
| nike_com | `xiaomi_recon_2026_05_28/fixtures/nike_com/` | `raw_evidence_next_data_sample.json`, `raw_evidence_product_card.html`, `raw_evidence_wall_meta.json` | YES | YES |
| marksandspencer_com | `xiaomi_recon_2026_05_28/fixtures/marksandspencer_com/` | `raw_evidence_graphql_sample.json`, `raw_evidence_meta.html`, `raw_evidence_urql_state.json` | YES | YES |

### Inline Fixtures Only (no external files)

| Strategy | Inline Fixture Location | Has External Fixture? |
|----------|------------------------|----------------------|
| jsonld_product_extractor | `_JSONLD_PRODUCT_HTML`, `_JSONLD_ITEMLIST_HTML` in test file | NO |
| shopify_product_grid_extractor | `_SHOPIFY_PRODUCTS_JSON` in test file | NO |
| demandware_product_tile_extractor | `_DEMANDWARE_TILE_HTML` in test file | NO |

---

## Risk Findings

### Risk 1: 3 New Strategies Have No Real-Site Fixtures (HIGH)

**Strategies affected**: `jsonld_product_extractor`, `shopify_product_grid_extractor`, `demandware_product_tile_extractor`

**Finding**: All test data for the 3 new extractors is inline in `test_ecommerce_extractors.py`. No real-site HTML or JSON evidence exists on disk. The 3 original strategies (GTM, NextData, GraphQLSSR) have proper fixture directories with real evidence, contracts, and expected items.

**Impact**: 
- Inline fixtures prove the code works on expected HTML shapes, but don't prove it works on real sites
- Real Shopify stores may have different product JSON shapes (e.g., no `options` array, different variant structure)
- Real SFCC sites may use different CSS class naming than `.product-tile__name`
- Real JSON-LD may have nested `@graph` arrays or multiple `@type` values in one script

**Concrete gap**: The 006 plan (`BACKEND_EXTRACTOR_PATTERNS_FROM_006.md`) recommended creating fixture directories for at least 1 site per strategy. This was never done for the 3 new strategies.

**Mitigation**: Fetch real HTML/JSON from 1 Shopify store, 1 SFCC store, and 1 site with JSON-LD Product markup before autocontract generation can be trusted on live sites.

---

### Risk 2: Demandware JS Fallback Regex Only Matches One Pattern (MEDIUM)

**File**: `ecommerce_extractors.py:689`

**Finding**: The JS fallback regex `productImpressions\s*=\s*(\[.*?\]);` only matches the `productImpressions = [...]` pattern. Real SFCC sites also commonly use:
- `dataLayer.push({ecommerce: {impressions: [...]}})`
- `var productViewObj = {...}`
- `dataLayer.push({event: "productImpression", ecommerce: {...}})`

The inline test `test_js_fallback_extraction` uses the exact pattern the regex matches, so it always passes.

**Impact**: Autocontract generator may correctly detect SFCC via CSS classes (`.product-tile[data-pid]`) but if DOM tiles are absent and only `dataLayer.push` JS is available, the extractor returns empty.

**Mitigation**: Extend regex to match `dataLayer.push({[^}]*impressions` pattern. Add test for `dataLayer.push` variant.

---

### Risk 3: Contract Router Has Hardcoded Brand Logic (MEDIUM)

**File**: `ecommerce_extractors.py:63`

**Finding**: The contract router has `brand="Nike" if site == "nike.com" else ""` hardcoded. This means:
- The brand is set by domain check, not from the contract
- If the contract has a `brand` field in `field_paths`, it's ignored for this strategy
- Non-Nike Next.js sites using product wall extraction get empty brand string

**Impact**: Autocontract generation must either set site to "nike.com" to get brand (wrong) or accept empty brand (suboptimal). The contract schema has `brand: "Hardcoded Nike"` in field_paths but the router doesn't read it.

**Mitigation**: Add `contract.get("field_paths", {}).get("brand", {}).get("path", "")` as fallback. Or add a `brand` key at contract top level.

---

### Risk 4: Shopify Extractor Hardcodes Currency to USD (MEDIUM)

**File**: `ecommerce_extractors.py:513`

**Finding**: `extract_shopify_product_grid_items()` always outputs `currency="USD"` regardless of the store's actual currency. The test fixtures don't test non-USD currencies.

**Impact**: Autocontract generator for international Shopify stores (e.g., UK store using GBP, EU store using EUR) will produce items with wrong currency. The contract schema has `currency: {"path": "Hardcoded USD"}` which documents this limitation but doesn't fix it.

**Mitigation**: Autocontract generator should detect currency from page locale or store settings. Extractor should accept optional `currency` parameter from contract.

---

### Risk 5: No Malformed Contract Tests for Router (LOW)

**File**: `test_ecommerce_extractors.py`

**Finding**: The contract routing tests (e.g., `test_contract_routes_superdry_html`, `test_contract_routes_nike_json`) verify correct dispatch but don't test:
- `parser_strategy` is a string instead of dict → `strategy` becomes `{}`, `strategy_name` becomes `""` → `UnsupportedExtractorContract` raised
- `parser_strategy.name` is empty string → same behavior as above
- `evidence` type doesn't match strategy expectation (e.g., int for demandware which expects str) → handled by `isinstance(evidence, str)` check, returns `[]`
- `source_url` is missing from contract → `_text(contract.get("source_url"))` returns `""` → no crash

The router handles most edge cases gracefully (returns empty list or raises clear error), but there are no tests proving this.

**Impact**: Autocontract generator may produce malformed contracts that crash instead of returning empty items.

**Mitigation**: Add tests for: empty strategy name, string parser_strategy, integer evidence for HTML-only strategies.

---

### Risk 6: GTM Fixture Tests Load from Real Files but Only Superdry (LOW)

**Finding**: `test_superdry_extracts_products_from_html` loads from `xiaomi_recon_2026_05_28/fixtures/superdry_com/raw_evidence_list_page.html` and asserts exactly 3 products with specific field values. This is a good real-fixture test, but:
- Only tests Superdry (one GTM implementation)
- GTM structure varies by site (some use `ecommerce.items[]`, others `items[]`, `products[]`)
- The test doesn't verify behavior on truncated/broken HTML (the regex fallback path)

**Impact**: Autocontract generator for other GTM sites may encounter different GTM structures that the Superdry fixture doesn't cover.

**Mitigation**: Add a test with a non-Superdry GTM structure (different item key names) or synthetic HTML with broken tiles to test the regex fallback.

---

### Risk 7: NextData Product Wall Is Nike-Specific but Not Gated (INFO)

**Finding**: The `next_data_product_wall_extractor` only works with Nike's product data shape (copy.title, prices.currentPrice, displayColors). The test file confirms this with nike_com fixtures. But the extractor name and contract router don't restrict it to Nike — any evidence with productGroupings is accepted.

**Impact**: If autocontract generator detects `__NEXT_DATA__` with `productGroupings` on a non-Nike site, it may generate a `next_data_product_wall_extractor` contract that produces empty items.

**Mitigation**: Autocontract generator should check for Nike-specific shape before selecting this strategy. Or document that this strategy is site-specific.

---

## Fixture Quality Summary

| Check | superdry_com | nike_com | marksandspencer_com | jsonld (inline) | shopify (inline) | demandware (inline) |
|-------|-------------|----------|--------------------|-----------------|--------------------|---------------------|
| Has raw evidence | PASS | PASS | PASS | N/A (inline) | N/A (inline) | N/A (inline) |
| Has expected items | PASS | PASS | PASS | N/A (assertions only) | N/A (assertions only) | N/A (assertions only) |
| Has extraction_contract.json | PASS | PASS | PASS | NO | NO | NO |
| Contract matches extractor | PASS | PASS | PASS | N/A | N/A | N/A |
| Tests pass | PASS | PASS | PASS | PASS | PASS | PASS |
| Real-site HTML | PASS | PASS | PASS | NO (synthetic) | NO (synthetic) | NO (synthetic) |
| Multiple sites tested | NO (Superdry only) | NO (Nike only) | NO (M&S only) | NO | NO | NO |
| Edge cases covered | PARTIAL | PARTIAL | PARTIAL | YES (8+ tests) | YES (6+ tests) | YES (5+ tests) |

---

## Recommendations

1. **P0**: Create fixture directories for at least 1 real Shopify store, 1 real SFCC/Demandware store, and 1 site with JSON-LD Product markup
2. **P1**: Extend Demandware JS regex to handle `dataLayer.push` pattern
3. **P1**: Add contract `brand` field fallback in router
4. **P2**: Add currency detection from page locale for Shopify
5. **P2**: Add malformed contract edge-case tests
6. **P3**: Add non-Superdry GTM fixture to test structural variations
