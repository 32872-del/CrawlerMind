# Implementation Plan: Auto-Extraction Contract Generator

**Date**: 2026-05-30
**Author**: Employee 002 (CLM Backend)
**Purpose**: Function-level implementation plan for backend developers building the autocontract generator

---

## 1. Overview

The autocontract generator takes raw site evidence (HTML, network observation, site analysis) and produces an `extraction_contract` that can be passed directly to `extract_items_from_contract()`. This bridges the gap between "site analyzed" and "extraction ready."

```
page evidence / access probe / site analysis
  -> detect structured evidence pattern  (strategy_detection_rules.json)
  -> generate extraction_contract         (contract_schema_examples.json)
  -> run extract_from_contract            (ecommerce_extractors.py)
  -> quality check                        (field coverage, item count)
  -> export or rerun
```

---

## 2. Proposed Function Signatures

### 2.1 Main Entry Point

```python
# File: autonomous_crawler/tools/autocontract.py

def generate_extraction_contract(
    evidence: str | dict | list,
    *,
    site: str,
    source_url: str = "",
    analysis_json: dict | None = None,
) -> dict | None:
    """Auto-detect evidence pattern and generate extraction_contract.

    Args:
        evidence: Raw HTML string, pre-parsed dict, or list of product objects.
        site: Domain name (e.g. "superdry.com").
        source_url: URL the evidence was fetched from.
        analysis_json: Optional site analysis report from analyze_site_for_crawl.

    Returns:
        extraction_contract dict, or None if no strategy matches.

    Raises:
        Nothing — returns None for unrecognizable evidence.
    """
```

### 2.2 Strategy Detection

```python
def detect_strategy(
    evidence: str | dict | list,
    *,
    site: str = "",
    html: str = "",
) -> list[dict]:
    """Detect which extractor strategies can handle the given evidence.

    Returns a ranked list of candidate strategies with confidence scores:
    [
        {"strategy": "jsonld_product_extractor", "confidence": 0.88, "evidence_type": "html"},
        {"strategy": "gtm_data_attribute_extractor", "confidence": 0.85, "evidence_type": "html"},
    ]
    """
```

### 2.3 Strategy-Specific Detectors

```python
def _detect_gtm_strategy(html: str) -> dict | None:
    """Check if HTML contains GTM data-gtm product tiles.
    
    Detection steps:
    1. soup.select('.product-tile[data-gtm]') → must have >0 tiles
    2. json.loads(html_lib.unescape(tile['data-gtm'])) → must parse
    3. _dig(parsed, 'ecommerce', 'items') → must be non-empty list
    4. ecommerce_items[0] must have 'item_name' or 'item_id'
    
    Returns: {"strategy": "gtm_data_attribute_extractor", "confidence": 0.85} or None
    """

def _detect_next_data_wall_strategy(evidence: Any) -> dict | None:
    """Check if evidence has Nike-style productGroupings.
    
    Detection steps:
    1. _coerce_json(evidence) → must be dict or list
    2. _dig(data, 'props', 'pageProps', 'initialState', 'Wall') → must have 'productGroupings'
    3. First product must have copy.title (str) and prices.currentPrice (numeric)
    
    Returns: {"strategy": "next_data_product_wall_extractor", "confidence": 0.88} or None
    """

def _detect_graphql_ssr_strategy(evidence: Any) -> dict | None:
    """Check if evidence has M&S-style GraphQL SSR cache products.
    
    Detection steps:
    1. _coerce_json(evidence) → must be dict
    2. _dig(data, 'props', 'pageProps', 'serverSideGqlResponseFed', ...) → must have results.products
    3. First product must have price.listPrice.amount (numeric) and variants (non-empty list)
    
    Returns: {"strategy": "next_data_graphql_ssr_cache_extractor", "confidence": 0.85} or None
    """

def _detect_jsonld_strategy(html: str) -> dict | None:
    """Check if HTML contains JSON-LD Product schema.
    
    Detection steps:
    1. soup.select('script[type="application/ld+json"]') → must have >0 scripts
    2. json.loads(html_lib.unescape(script.string)) → must parse
    3. Check for @type == 'Product' with non-empty name and offers
    
    Returns: {"strategy": "jsonld_product_extractor", "confidence": 0.88} or None
    """

def _detect_shopify_strategy(evidence: Any, html: str = "") -> dict | None:
    """Check if evidence is Shopify product data.
    
    Detection steps:
    If dict:
      1. evidence.get('products') must be non-empty list
      2. First product must have int id, string handle, list variants with 'price'
    If HTML:
      1. Regex for Shopify.analytics.meta.product = {...};
      2. Regex for "products": [...]
    
    Returns: {"strategy": "shopify_product_grid_extractor", "confidence": 0.87} or None
    """

def _detect_demandware_strategy(html: str) -> dict | None:
    """Check if HTML contains Demandware/SFCC product tiles.
    
    Detection steps:
    1. soup.select('.product-tile[data-pid]') → must have >0 tiles
    2. At least one tile must have .product-tile__name or .pdp-link a (title)
    3. At least one tile must have .product-tile__price .sales .value (price)
    
    Alternative (JS fallback):
    1. Regex for productImpressions = [...]; → must find array with product-like dicts
    
    Returns: {"strategy": "demandware_product_tile_extractor", "confidence": 0.82} or None
    """
```

### 2.4 Contract Builder

```python
def _build_contract(
    strategy: str,
    *,
    site: str,
    source_url: str,
    evidence_type: str,
    image_template: str = "",
    max_items: int = 100,
) -> dict:
    """Build a standard extraction_contract dict for the given strategy.
    
    Uses the templates from contract_schema_examples.json as base,
    filling in site-specific values.
    """
```

### 2.5 Quality Gate

```python
def validate_contract_quality(
    contract: dict,
    evidence: Any,
    *,
    min_items: int = 1,
) -> dict:
    """Run extraction with the contract and validate output quality.
    
    Returns:
        {"ok": True, "item_count": 15, "field_coverage": {...}, "items": [...]}
        or {"ok": False, "reason": "...", "item_count": 0}
    """
```

---

## 3. Module Structure

```
autonomous_crawler/tools/
  autocontract.py              # NEW — main entry + strategy detection + contract builder
  ecommerce_extractors.py      # EXISTING — extraction functions (no changes for autocontract)
```

The autocontract module imports from ecommerce_extractors.py but does not modify it.

---

## 4. Test Checklist (22 Tests)

### Strategy Detection Tests (11 tests)

| # | Test Name | Input | Expected Strategy | Rationale |
|---|-----------|-------|-------------------|-----------|
| 1 | `test_detect_gtm_from_html` | HTML with `.product-tile[data-gtm]` containing `ecommerce.items` with `item_name` | `gtm_data_attribute_extractor` | Primary GTM detection — must have all 3 steps pass |
| 2 | `test_detect_gtm_rejects_no_tiles` | HTML with `.product-tile` but no `data-gtm` attribute | `None` | CSS class match without data attribute is not GTM |
| 3 | `test_detect_jsonld_from_html` | HTML with `<script type="application/ld+json">` containing `@type: Product` with `name` and `offers.price` | `jsonld_product_extractor` | Standard JSON-LD detection |
| 4 | `test_detect_jsonld_rejects_organization` | HTML with `<script type="application/ld+json">` containing `@type: Organization` | `None` | Non-Product schema should not match |
| 5 | `test_detect_shopify_from_dict` | Dict `{"products": [{"id": 1, "handle": "x", "variants": [{"price": "10"}]}]}` | `shopify_product_grid_extractor` | Shopify JSON API detection |
| 6 | `test_detect_shopify_from_html` | HTML containing `Shopify.analytics.meta.product = {"id": 1, ...}` | `shopify_product_grid_extractor` | Shopify inline analytics detection |
| 7 | `test_detect_demandware_from_html` | HTML with `.product-tile[data-pid]` + `.product-tile__name` + `.product-tile__price` | `demandware_product_tile_extractor` | SFCC DOM tile detection |
| 8 | `test_detect_demandware_from_js` | HTML with `productImpressions = [{"name": "X", "price": "10"}]` | `demandware_product_tile_extractor` | SFCC JS fallback detection |
| 9 | `test_detect_graphql_ssr_from_dict` | Dict with `products` having `price.listPrice.amount` + `variants[].mediaAssets[].assetId` | `next_data_graphql_ssr_cache_extractor` | GraphQL SSR cache detection |
| 10 | `test_detect_next_data_wall_from_dict` | Dict with productGroupings having `copy.title` + `prices.currentPrice` | `next_data_product_wall_extractor` | Nike product wall detection |
| 11 | `test_no_strategy_for_empty_input` | Empty string `""` | `[]` | Empty input should not match any strategy |

### Contract Generation Tests (6 tests)

| # | Test Name | Input | Expected | Rationale |
|---|-----------|-------|----------|-----------|
| 12 | `test_generate_contract_gtm` | Superdry HTML from fixture | Contract with `parser_strategy.name == "gtm_data_attribute_extractor"`, `site == "superdry.com"`, `evidence_files` non-empty | Full contract generation from real fixture |
| 13 | `test_generate_contract_jsonld` | HTML with JSON-LD Product | Contract with `parser_strategy.name == "jsonld_product_extractor"`, `field_paths` has title, highest_price, currency | Contract generation with correct field mapping |
| 14 | `test_generate_contract_shopify` | Shopify products dict | Contract with `parser_strategy.name == "shopify_product_grid_extractor"`, price logic documented in field_paths | Contract generation with price comparison note |
| 15 | `test_generate_contract_returns_none_for_blog` | HTML with article content, no product patterns | `None` | Non-product page should return None |
| 16 | `test_generate_contract_includes_pagination` | Superdry HTML + analysis_json with pagination info | Contract has `pagination_strategy` with `demandware_query_params` type | Pagination strategy propagation |
| 17 | `test_contract_routes_correctly_after_generation` | Generated contract + same evidence | Extracts items via `extract_items_from_contract()` | End-to-end: generate → extract |

### Quality Gate Tests (3 tests)

| # | Test Name | Input | Expected | Rationale |
|---|-----------|-------|----------|-----------|
| 18 | `test_quality_gate_passes` | Contract + evidence that extracts 5+ items | `{"ok": True, "item_count": >= 5}` | Happy path quality check |
| 19 | `test_quality_gate_fails_empty` | Contract + empty HTML evidence | `{"ok": False, "reason": "no items extracted"}` | Empty extraction caught |
| 20 | `test_quality_gate_warns_low_coverage` | Contract + evidence with most fields missing | `{"ok": True, "warnings": [...]}` | Low field coverage warning |

### Edge Case Tests (2 tests)

| # | Test Name | Input | Expected | Rationale |
|---|-----------|-------|----------|-----------|
| 21 | `test_multiple_strategies_ranked` | HTML with both JSON-LD Product AND `.product-tile[data-gtm]` | List with `jsonld_product_extractor` first (higher confidence) | Both detected; ranked by confidence |
| 22 | `test_evidence_type_mismatch_graceful` | HTML evidence passed to `shopify_product_grid_extractor` (expects dict/list) | Returns empty items, no crash | Wrong evidence type handled gracefully |

---

## 5. Integration Points

### 5.1 With Managed Action Executor

```python
# In managed_actions.py, the extract_from_contract action can call:
from autonomous_crawler.tools.autocontract import generate_extraction_contract

# When no contract is provided by the AI, auto-detect:
if not contract:
    contract = generate_extraction_contract(evidence, site=site, source_url=source_url)
```

### 5.2 With Site Analysis Pipeline

```python
# In analyze_site_for_crawl results, add contract suggestion:
analysis = analyze_site_for_crawl(url)
contract = generate_extraction_contract(
    analysis["best_page_html"],
    site=analysis["site"],
    source_url=analysis["best_page_url"],
    analysis_json=analysis,
)
if contract:
    analysis["suggested_extraction_contract"] = contract
```

### 5.3 With AI Managed Crawl Loop

The AI can call `generate_extraction_contract` as part of the `analyze_site` or `resolve_fields` action, producing a contract that's immediately usable for extraction without manual contract authoring.

---

## 6. Error Handling Rules

| Condition | Behavior |
|-----------|----------|
| Evidence is empty/None | Return None (no contract) |
| Evidence is HTML but no patterns detected | Return None |
| Evidence is dict/list but wrong shape | Return None |
| Strategy detected but evidence type mismatch | Return None (don't force wrong extractor) |
| Multiple strategies detected | Return highest-confidence one; log alternatives |
| Contract generated but extraction produces 0 items | `validate_contract_quality` returns `{"ok": False}` |
| Contract generated but extraction produces < min_items | `validate_contract_quality` returns warning |

---

## 7. Priority Implementation Order

| Phase | Task | Effort | Dependencies |
|-------|------|--------|-------------|
| P0 | `detect_strategy()` with GTM + JSON-LD + Shopify detection | 4h | None |
| P0 | `_build_contract()` for detected strategies | 2h | detect_strategy |
| P0 | `generate_extraction_contract()` main entry | 2h | detect_strategy + _build_contract |
| P0 | 11 strategy detection tests | 2h | generate_extraction_contract |
| P1 | Demandware + NextData + GraphQLSSR detection | 3h | P0 complete |
| P1 | `validate_contract_quality()` | 2h | generate_extraction_contract |
| P1 | 8 contract generation + quality tests | 2h | P1 code complete |
| P2 | Integration with managed_actions.py | 2h | P0 complete |
| P2 | Integration with analyze_site_for_crawl | 2h | P0 complete |
| P3 | Edge case tests (mismatch, multiple strategies) | 2h | P0+P1 complete |

**Total estimated effort**: ~23 hours for full implementation + tests

---

## 8. Data Flow Diagram

```
User URL
  |
  v
analyze_site_for_crawl(url)  -- or browser fetch
  |
  v
Best page HTML + network evidence
  |
  v
detect_strategy(evidence, site)  -- applies strategy_detection_rules.json
  |
  +-- No match --> return None (manual contract needed)
  |
  +-- Match found:
      |
      v
  _build_contract(strategy, site, source_url, ...)
      |
      v
  validate_contract_quality(contract, evidence)
      |
      +-- ok=False --> try next strategy or return None
      |
      +-- ok=True:
          |
          v
      extraction_contract ready
          |
          v
      extract_items_from_contract(evidence, contract)  -- existing extractor
          |
          v
      CLM items (title, price, image, ...)
```

---

## 9. Known Limitations to Document

1. **Shopify currency is hardcoded to "USD"** — autocontract should add currency hint from page locale
2. **Nike product wall is site-specific** — autocontract should only generate for nike.com
3. **M&S image_template is hardcoded** — autocontract should extract from existing image URLs or contract
4. **Demandware JS regex only matches `productImpressions =`** — extend to `dataLayer.push` pattern
5. **No pagination support in autocontract** — contracts only extract from single page; pagination is separate
6. **Confidence scores are heuristic** — should be calibrated against real extraction success rates
7. **Contract router hardcodes brand for Nike** — should read from contract.brand or field_paths.brand

---

## 10. Backlog: Patterns Not Yet Supported

| Pattern | Sites | Priority | Notes |
|---------|-------|----------|-------|
| Open Graph / meta tag product data | ~10% | P2 | og:title, product:price:amount on detail pages |
| Microdata (itemprop) | ~5% (declining) | P3 | Older schema.org implementation |
| React/Vue hydration state | ~10% | P2 | window.__INITIAL_STATE__ in non-Next.js SPAs |
| JSON API response interception | ~15% | P1 | XHR/fetch API calls for product data |
| dataLayer.push impressions | ~8% | P2 | GA tracking without GTM data-gtm attributes |
