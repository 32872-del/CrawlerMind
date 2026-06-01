# Round 2 Implementation Spec Completion Note

**Agent**: LLM-2026-006
**Date**: 2026-05-30
**Task**: Upgrade Deep Recon fixtures from evidence assets to CLM backend implementation specs

## 1. Deliverables Checklist

| Deliverable | Status | Location |
|-------------|--------|----------|
| 3x extraction_contract.json | Done | `fixtures/{site}/extraction_contract.json` |
| 3x expected_items_sample.json | Done | `fixtures/{site}/expected_items_sample.json` |
| Backend implementation spec | Done | `docs/plans/2026-05-30_BACKEND_EXTRACTOR_PATTERNS_FROM_006.md` |
| Completion report | Done | This file |

## 2. JSON Parse Validation

All 6 new JSON files parse successfully:

| File | Parse Status | Items/Confidence |
|------|-------------|-----------------|
| `superdry_com/extraction_contract.json` | OK | confidence=0.85 |
| `superdry_com/expected_items_sample.json` | OK | 5 items |
| `nike_com/extraction_contract.json` | OK | confidence=0.80 |
| `nike_com/expected_items_sample.json` | OK | 6 items |
| `marksandspencer_com/extraction_contract.json` | OK | confidence=0.85 |
| `marksandspencer_com/expected_items_sample.json` | OK | 5 items |

Total: 16 items across 3 sites. All items have unified CLM field names.

## 3. Per-Site Completeness

### superdry_com (GTM Extractor)

| CLM Field | Available | Source | Traceability |
|-----------|-----------|--------|-------------|
| title | Yes | GTM `ecommerce.items[0].item_name` | `raw_evidence_gtm_sample.json` |
| highest_price | Yes | GTM `ecommerce.items[0].price` | `raw_evidence_gtm_sample.json` |
| currency | Yes | Hardcoded GBP | Site domain |
| color | Yes | GTM `ecommerce.items[0].item_colour` | `raw_evidence_gtm_sample.json` |
| size | No | — | missing_reason: detail page only |
| description | No | — | missing_reason: detail page only |
| image_url | Yes | HTML `img.tile-image[srcset]` | `raw_evidence_list_page.html` |
| product_url | Yes | HTML `.tile-image-wrapper-link[href]` | `raw_evidence_list_page.html` |
| category_level_1 | Yes | GTM `item_category` | `raw_evidence_gtm_sample.json` |
| category_level_2 | Yes | GTM `item_category2` | `raw_evidence_gtm_sample.json` |

**Executability**: FULLY EXECUTABLE with `requests` mode. Only size/description need detail page.

### nike_com (__NEXT_DATA__ Extractor)

| CLM Field | Available | Source | Traceability |
|-----------|-----------|--------|-------------|
| title | Yes | `copy.title + copy.subTitle` | `raw_evidence_next_data_sample.json` |
| highest_price | Yes | `prices.currentPrice` | `raw_evidence_next_data_sample.json` |
| currency | Yes | `prices.currency` | `raw_evidence_next_data_sample.json` |
| color | Yes | `displayColors.colorDescription` | `raw_evidence_next_data_sample.json` |
| size | No | — | missing_reason: detail page only |
| description | No | — | missing_reason: detail page only |
| image_url | Yes | `colorwayImages.portraitURL` | `raw_evidence_next_data_sample.json` |
| product_url | Yes | `pdpUrl.url` | `raw_evidence_next_data_sample.json` |
| category_level_1 | Yes | `productType` | `raw_evidence_next_data_sample.json` |
| category_level_2 | No | — | missing_reason: in facetNav, not in product data |

**Executability**: EXECUTABLE with `browser` mode. 947 total products with API pagination.

### marksandspencer_com (GraphQL SSR Extractor)

| CLM Field | Available | Source | Traceability |
|-----------|-----------|--------|-------------|
| title | Yes | `products[].title` | `raw_evidence_graphql_sample.json` |
| highest_price | Yes | `products[].price.listPrice.amount` | `raw_evidence_graphql_sample.json` |
| currency | Yes | `products[].price.currency` | `raw_evidence_graphql_sample.json` |
| color | Yes | Parsed from `seoPath` query param | `raw_evidence_graphql_sample.json` |
| size | Yes | `products[].variants[0].size` | `raw_evidence_graphql_sample.json` |
| description | Conditional | Often null in GraphQL | `raw_evidence_graphql_sample.json` |
| image_url | Yes | Constructed from `mediaAssets[0].assetId` | `raw_evidence_graphql_sample.json` |
| product_url | Yes | Constructed from `seoPath` | `raw_evidence_graphql_sample.json` |
| category_level_1 | Yes | `productDefinition` | `raw_evidence_graphql_sample.json` |
| category_level_2 | No | — | missing_reason: in facets[], not in product data |

**Executability**: EXECUTABLE with `browser` mode. 2493 total dresses. Richest data (has sizes).

## 4. Field Coverage Summary

| Field | Superdry | Nike | M&S | Coverage |
|-------|----------|------|-----|----------|
| title | Yes | Yes | Yes | 3/3 |
| highest_price | Yes | Yes | Yes | 3/3 |
| currency | Yes | Yes | Yes | 3/3 |
| color | Yes | Yes | Yes | 3/3 |
| size | No | No | **Yes** | 1/3 |
| description | No | No | Partial | 0.5/3 |
| image_url | Yes | Yes | Yes | 3/3 |
| product_url | Yes | Yes | Yes | 3/3 |
| category_level_1 | Yes | Yes | Yes | 3/3 |
| category_level_2 | Yes | No | No | 1/3 |

**Key finding**: M&S is the only site with `size` in listing page data. This is because GraphQL SSR cache includes variant data.

## 5. What Needs Browser/API Replay

| Need | Sites | Reason | Fix |
|------|-------|--------|-----|
| size field | Superdry, Nike | Not in listing page data | Fetch detail page, extract from variant JSON or DOM |
| description field | All 3 | Not in listing page (or null for M&S) | Fetch detail page, extract from JSON-LD or meta |
| category_level_2 | Nike, M&S | In separate facet/filter data | Parse facetNav or category breadcrumbs |
| Full catalog pagination | All 3 | Only first page captured | Implement pagination loop per site |

## 6. Patterns for CLM Backend Absorption

The backend spec document (`docs/plans/2026-05-30_BACKEND_EXTRACTOR_PATTERNS_FROM_006.md`) contains:

1. **GTM Data Attribute Extractor** — full implementation with `re` + `json` parsing
2. **__NEXT_DATA__ Product Wall Extractor** — full implementation with path navigation
3. **GraphQL SSR Cache Extractor** — full implementation with variant extraction
4. **Site profile registry** — maps domains to extractors and config
5. **12 unit test recommendations** — covering each extractor and utility
6. **Fixture-based integration test pattern** — load raw evidence, validate against expected

## 7. Risks and Uncertainties

| Item | Status |
|------|--------|
| GTM structure varies across sites | Documented; path made configurable |
| __NEXT_DATA__ path varies per site | Documented; stored in site profiles |
| Image CDN templates may change | Documented; stored in site profiles |
| Anti-scraping may escalate | Documented; fallback to browser mode |
| __NEXT_DATA__ may be removed in future Next.js | Documented; fallback to HTML DOM |

## 8. File Inventory

```
fixtures/
├── superdry_com/
│   ├── extraction_contract.json          (4.5KB) — NEW
│   ├── expected_items_sample.json        (4.6KB) — NEW
│   ├── extraction_spec.json              (2.2KB) — existing
│   ├── expected_extraction.json          (3.8KB) — existing
│   ├── raw_evidence_gtm_sample.json      (3.4KB) — existing
│   └── raw_evidence_list_page.html       (15KB)  — existing
├── nike_com/
│   ├── extraction_contract.json          (4.6KB) — NEW
│   ├── expected_items_sample.json        (7.7KB) — NEW
│   ├── extraction_spec.json              (2.2KB) — existing
│   ├── expected_extraction.json          (5.5KB) — existing
│   ├── raw_evidence_next_data_sample.json (9.9KB) — existing
│   ├── raw_evidence_product_card.html    (3.8KB) — existing
│   └── raw_evidence_wall_meta.json       (605B)  — existing
├── marksandspencer_com/
│   ├── extraction_contract.json          (5.0KB) — NEW
│   ├── expected_items_sample.json        (5.2KB) — NEW
│   ├── extraction_spec.json              (2.4KB) — existing
│   ├── expected_extraction.json          (5.7KB) — existing
│   ├── raw_evidence_graphql_sample.json  (33KB)  — existing
│   ├── raw_evidence_meta.html            (234B)  — existing
│   └── raw_evidence_urql_state.json      (735B)  — existing
├── DEEP_RECON_FIXTURE_COMPLETION_NOTE.md          — existing
└── ROUND2_IMPLEMENTATION_SPEC_COMPLETION_NOTE.md  — NEW (this file)

docs/plans/
└── 2026-05-30_BACKEND_EXTRACTOR_PATTERNS_FROM_006.md  — NEW
```

## 9. Summary

| Metric | Value |
|--------|-------|
| extraction_contract.json files | 3/3 |
| expected_items_sample.json files | 3/3 |
| Total expected items | 16 (5+6+5) |
| Unified CLM fields per item | 10 |
| Fields with raw evidence | 8/10 (80%) |
| Fields missing (detail page only) | 2/10 (20%) |
| Backend spec sections | 7 |
| Recommended unit tests | 12 |
| Extractor patterns documented | 3 |
