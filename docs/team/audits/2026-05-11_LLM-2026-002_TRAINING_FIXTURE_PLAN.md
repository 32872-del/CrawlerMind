# Training Fixture Plan

Employee: LLM-2026-002
Date: 2026-05-11

## Purpose

Abstract real training sites into generic, reusable crawl scenarios for
fixture/test creation. This plan does not reference site-specific selectors
or bypass strategies. Each scenario becomes a self-contained fixture that
future employees can use for training and regression testing.

## Source Material

- `docs/team/training/2026-05-08_REAL_SITE_TRAINING_LADDER.md` — 4-tier ladder
- `docs/process/ECOMMERCE_CRAWL_WORKFLOW.md` — 4 task types, quality checklist
- `dev_logs/training/2026-05-09_ecommerce_training_sample.json` — 5 real sites, 19 records
- `dev_logs/training/2026-05-09_ecommerce_training_summary.md` — site result summary

## Scenario Inventory

Six generic scenarios, derived from the training samples and ladder tiers.

### Scenario 1: Static List + Detail

**Source pattern:** clausporto, uvex (Magento-style static DOM)

| Field | Value |
|---|---|
| Fixture name | `static_list_detail` |
| Input URL type | Category page with product cards linking to detail pages |
| Target fields | title, price, image_src, description, category |
| Expected mode | `static_dom_list_plus_detail` |
| Acceptance criteria | ≥1 product link extracted per list page; all required fields present on detail; price parses to float; at least 1 non-noise image |
| Failure → test | Missing selector → test for empty field detection; wrong selector → test for field mismatch; noise images → test for image filtering |

**Fixture content:**

- `list.html`: 3-5 product cards with `a.product-link`, `img.product-photo`, `span.product-price`
- `detail.html`: Full product page with title, price, description, multiple images (mix of product + noise)
- `detail_noisy_images.html`: Same as detail but images are all logos/icons/tracking pixels
- `detail_missing_fields.html`: Product page missing title or price

**Why generic:** Any static-HTML ecommerce site with list→detail navigation
follows this pattern. The fixture does not encode any real site's selectors.

---

### Scenario 2: Public JSON API (Shopify-style)

**Source pattern:** donsje (public `products.json` endpoint)

| Field | Value |
|---|---|
| Fixture name | `public_json_api` |
| Input URL type | `/products.json` or similar public API returning product list |
| Target fields | title, price, images, variants (color, size), description |
| Expected mode | `public_shopify_json` or `api_intercept` |
| Acceptance criteria | JSON parsed correctly; variants extracted with color/size; price is numeric; images are non-empty array |
| Failure → test | Malformed JSON → test for parse error handling; missing variant fields → test for partial extraction; API returns 403 → test for blocked status |

**Fixture content:**

- `products.json`: 3 products with variants array, each variant having color, size, price, image
- `products_single.json`: 1 product, no variants (single-variant product)
- `products_empty.json`: `{"products": []}` — empty result set
- `products_malformed.json`: Invalid JSON (truncated, syntax error)

**Why generic:** Public JSON APIs are a common crawl target. Shopify's
`products.json` is one instance; many CMS platforms expose similar endpoints.

---

### Scenario 3: Paginated API

**Source pattern:** Generic API with offset/cursor pagination

| Field | Value |
|---|---|
| Fixture name | `paginated_api` |
| Input URL type | API endpoint accepting `?offset=N` or `?cursor=X` |
| Target fields | items (title, price, url), next_cursor/next_offset |
| Expected mode | `api_intercept` with pagination metadata |
| Acceptance criteria | First page returns items; pagination param detected; second page returns different items; termination condition met (empty page or max pages) |
| Failure → test | No termination → test for infinite loop guard; cursor not advancing → test for stuck detection; rate limit 429 → test for backoff |

**Fixture content:**

- `page_0.json`: 5 items, `next_offset=5`
- `page_1.json`: 5 items, `next_offset=10`
- `page_2.json`: 0 items, `next_offset=null` (termination signal)
- `cursor_page_a.json`: 3 items, `next_cursor="abc123"`
- `cursor_page_b.json`: 3 items, `next_cursor=null`

**Why generic:** Pagination is a cross-cutting concern. This fixture lets
us test offset and cursor strategies without tying to any specific API.

---

### Scenario 4: JS-Rendered List (Browser Fallback)

**Source pattern:** SPA pages that require browser rendering

| Field | Value |
|---|---|
| Fixture name | `js_rendered_list` |
| Input URL type | SPA page where product list is injected by JavaScript |
| Target fields | title, price, image, link |
| Expected mode | `browser` |
| Acceptance criteria | Browser renders page; product cards appear after JS execution; at least 1 link extracted; network entries captured for API discovery |
| Failure → test | JS timeout → test for render timeout handling; no products after render → test for empty result; challenge page → test for blocked detection |

**Fixture content:**

- `spa_list.html`: Minimal SPA shell with `<div id="app"></div>` and inline JS that injects product cards after 500ms delay
- `spa_api_hints.html`: SPA shell that fetches `/api/products` via XHR; observer should discover the API endpoint
- `spa_challenge.html`: Page that renders a Cloudflare-style challenge div

**Why generic:** SPA rendering is framework-agnostic. The fixture uses
vanilla JS to simulate hydration, not a real React/Vue build.

---

### Scenario 5: Variant + Detail Extraction

**Source pattern:** Products with color/size variants (donsje, uvex)

| Field | Value |
|---|---|
| Fixture name | `variant_detail` |
| Input URL type | Product detail page with variant controls (color swatches, size selectors) |
| Target fields | title, price, colors, sizes, variant_price, image per variant |
| Expected mode | `static_dom_list_plus_detail` or `browser` |
| Acceptance criteria | Main product extracted; all variants extracted; sizes include out-of-stock; variant prices captured; handle has `_N` suffix |
| Failure → test | Missing variant data → test for partial extraction; OOS sizes dropped → test for completeness; variant price mismatch → test for consistency |

**Fixture content:**

- `product_with_variants.html`: Product with 3 colors, 4 sizes each; size selector shows OOS state
- `product_single_variant.html`: Product with no color/size controls (single-variant)
- `product_variant_json.html`: Product page with embedded JSON-LD or `__NEXT_DATA__` containing variant data

**Why generic:** Variant extraction is a common ecommerce requirement.
The fixture covers color, size, OOS state, and price per variant without
encoding any real site's DOM structure.

---

### Scenario 6: Challenge / Login Diagnosis-Only

**Source pattern:** shoesme (Cloudflare), bosch (corporate partial)

| Field | Value |
|---|---|
| Fixture name | `challenge_diagnosis` |
| Input URL type | Page that returns challenge, login, or corporate/non-retail content |
| Target fields | status, notes (no product fields expected) |
| Expected mode | `diagnosis_only` |
| Acceptance criteria | Status is `blocked` or `partial`; notes explain the reason; no product fields fabricated; validator produces no errors for blocked records with notes |
| Failure → test | Missing notes → test for `blocked_without_notes` warning; fabricated fields → test for status consistency; wrong status → test for field mismatch |

**Fixture content:**

- `cloudflare_challenge.html`: HTML with `cf-browser-verification` class and challenge script
- `login_required.html`: HTML with login form, no product content
- `corporate_page.html`: HTML with product family/category content but no retail price
- `access_denied.html`: HTTP 403 response body

**Why generic:** Challenge detection is a safety boundary, not a bypass
strategy. The fixture lets us test that the system correctly identifies
blocked/partial states without attempting to circumvent them.

---

## Mapping: Training Samples → Scenarios

| Training Site | Scenario | Why |
|---|---|---|
| clausporto | 1 (static list+detail) | Static Magento DOM, list→detail flow |
| uvex | 1 (static list+detail) + 5 (variant) | Static DOM with sizes and noisy images |
| donsje | 2 (public JSON API) + 5 (variant) | Shopify products.json with variants |
| shoesme | 6 (challenge diagnosis) | Cloudflare challenge, blocked |
| bosch | 6 (challenge diagnosis) | Corporate page, partial status |

## Mapping: Training Ladder → Scenarios

| Ladder Tier | Scenarios |
|---|---|
| Tier 1 (Safe Public) | 1, 2, 3 |
| Tier 2 (Browser-Rendered) | 4 |
| Tier 3 (Scroll/Virtualization) | (future, not in this plan) |
| Tier 4 (Diagnosis-Only) | 6 |

Scenario 5 (variant) spans Tier 1 and Tier 2 depending on whether
variants are in static HTML or require JS rendering.

## Implementation Order

### Round 1: Static + API (Tier 1)

1. **Scenario 1** — `static_list_detail` fixture + tests
2. **Scenario 2** — `public_json_api` fixture + tests
3. **Scenario 3** — `paginated_api` fixture + tests

These require no browser, are deterministic, and can run in CI.

### Round 2: Browser + Diagnosis (Tier 2 + 4)

4. **Scenario 4** — `js_rendered_list` fixture + tests (requires Playwright)
5. **Scenario 5** — `variant_detail` fixture + tests
6. **Scenario 6** — `challenge_diagnosis` fixture + tests

These require browser or mock browser responses.

## Fixture Location

All fixtures go in:

```
autonomous_crawler/tests/fixtures/
├── static_list_detail/
│   ├── list.html
│   ├── detail.html
│   ├── detail_noisy_images.html
│   └── detail_missing_fields.html
├── public_json_api/
│   ├── products.json
│   ├── products_single.json
│   ├── products_empty.json
│   └── products_malformed.json
├── paginated_api/
│   ├── page_0.json
│   ├── page_1.json
│   ├── page_2.json
│   ├── cursor_page_a.json
│   └── cursor_page_b.json
├── js_rendered_list/
│   ├── spa_list.html
│   ├── spa_api_hints.html
│   └── spa_challenge.html
├── variant_detail/
│   ├── product_with_variants.html
│   ├── product_single_variant.html
│   └── product_variant_json.html
└── challenge_diagnosis/
    ├── cloudflare_challenge.html
    ├── login_required.html
    ├── corporate_page.html
    └── access_denied.html
```

## Test Structure

Each scenario gets a test file:

```
autonomous_crawler/tests/
├── test_static_list_detail.py
├── test_public_json_api.py
├── test_paginated_api.py
├── test_js_rendered_list.py
├── test_variant_detail.py
└── test_challenge_diagnosis.py
```

Each test file should:

1. Load fixture HTML/JSON
2. Run the appropriate extraction function
3. Assert on field presence, format, and value
4. Run `validate_product_record()` on extracted records
5. Assert on issue codes (no errors for clean records, expected warnings for edge cases)

## Safety Rules

- No real URLs in fixtures (use `example.test` domain)
- No real cookies, tokens, or API keys
- No Cloudflare bypass scripts — only challenge detection
- No login credential handling — only login page detection
- No site-specific selectors in core code — only in fixtures/tests
- Fixtures must be self-contained (no external dependencies)

## Acceptance Criteria for This Plan

- [ ] Each scenario has at least 2 fixture files
- [ ] Each scenario has a test file with ≥5 test cases
- [ ] All fixtures use `example.test` domain
- [ ] No real bypass logic in any fixture
- [ ] `validate_product_record()` passes on clean fixture records
- [ ] `validate_product_record()` produces expected issues on edge-case records
- [ ] Fixture plan reviewed by supervisor before implementation

## Summary

| Scenario | Fixture Name | Round | Tier | Test Count Target |
|---|---|---|---|---|
| Static list+detail | `static_list_detail` | 1 | 1 | ≥8 |
| Public JSON API | `public_json_api` | 1 | 1 | ≥8 |
| Paginated API | `paginated_api` | 1 | 1 | ≥6 |
| JS rendered list | `js_rendered_list` | 2 | 2 | ≥5 |
| Variant detail | `variant_detail` | 2 | 1-2 | ≥8 |
| Challenge diagnosis | `challenge_diagnosis` | 2 | 4 | ≥6 |

**Total: 6 scenarios, 18+ fixture files, 41+ test cases**
