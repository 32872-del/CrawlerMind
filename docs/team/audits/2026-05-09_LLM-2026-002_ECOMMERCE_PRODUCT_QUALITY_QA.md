# Audit: Ecommerce Product Quality QA Design

Employee: LLM-2026-002
Date: 2026-05-09

## Scope

QA design for ecommerce product data quality. Derived from spider_text domain
experience. Covers: product schema, price normalization, image dedup, body
cleaning, variant/size handling, category-aware dedup, three-phase task model,
and pre-production smoke test flow.

**No code changes. Design document only.**

## Reference Architecture

From spider_text `fnspider`:

```
Phase 1: Category/List → liebiao table (progress)
Phase 2: Detail → zhuti table (progress)
Phase 3: Variant → bianti table → goods table (final)
```

- `sole_id` = MD5(categories_1 + categories_2 + categories_3 + url)
- Three queues: start_urls → list_queue → more_list_queue
- Handle increment: `model00001_1`, `model00001_2`, `model00001_3`

Current CLM product_tasks.py has: `ProductTask`, `extract_list_tasks`,
`extract_variant_tasks`, `extract_detail_record`. No price normalization,
body cleaning, image filtering, or category-aware dedup.

---

## 1. Product Schema Required Fields

### Schema Definition

| Field | Type | Required | Notes |
|---|---|---|---|
| url | TEXT | yes | Canonical product URL |
| handle | TEXT | yes | Unique product identifier, variant-suffixed |
| title | TEXT | yes | Clean product name |
| price | REAL | yes | Normalized float (e.g., 64.95) |
| image_src | TEXT | yes | JSON array of image URLs |
| sole_id | TEXT UNIQUE | yes | MD5(cat1+cat2+cat3+url) |
| body | TEXT | no | Clean HTML product description |
| categories_1 | TEXT | no | Top-level category |
| categories_2 | TEXT | no | Second-level category |
| categories_3 | TEXT | no | Third-level category |
| option1_name | TEXT | no | e.g., "Color" |
| option1_value | TEXT | no | e.g., "Red" |
| option2_name | TEXT | no | e.g., "Size" |
| option2_value | TEXT | no | e.g., "['18','19','20','21']" |
| option3_name | TEXT | no | Third option axis |
| option3_value | TEXT | no | Third option values |
| size_price | TEXT | no | Per-size price JSON |
| subtitle | TEXT | no | Product subtitle |
| more_info | TEXT | no | Extra metadata JSON |

### Test Cases: Schema Validation

| ID | Input | Expected |
|---|---|---|
| T-SCH-001 | Record missing `url` | Rejected, validation error |
| T-SCH-002 | Record missing `title` | Rejected |
| T-SCH-003 | Record missing `price` | Rejected |
| T-SCH-004 | Record missing `image_src` | Rejected |
| T-SCH-005 | Record missing `handle` | Rejected |
| T-SCH-006 | Record missing `sole_id` | Rejected or auto-generated |
| T-SCH-007 | All required fields present | Accepted |
| T-SCH-008 | `price` is string "64.95" | Auto-coerced to float |
| T-SCH-009 | `image_src` is plain URL string | Auto-wrapped in JSON array |
| T-SCH-010 | Duplicate `sole_id` INSERT | Rejected (UNIQUE constraint) |
| T-SCH-011 | `handle` with spaces/unicode | Accepted as-is (handle is opaque) |

---

## 2. Price Normalization

### Known Patterns

| Pattern | Input | Expected Output |
|---|---|---|
| Dollar | `$129.90` | `129.90` |
| Euro | `€64,95` | `64.95` |
| Pound | `£49.99` | `49.99` |
| PLN | `129,99 zł` | `129.99` |
| Comma decimal | `1.299,95` | `1299.95` |
| Space thousand | `1 299,95` | `1299.95` |
| Plain number | `89.5` | `89.5` |
| Empty | `""` | `None` or validation error |
| Null | `null` | `None` or validation error |
| Garbage | `"Sold out"` | `None` or validation error |
| Range | `€49.99 - €69.99` | `49.99` (take lower) or `None` |
| Free | `"Free"` / `"Gratis"` | `0.0` |
| Negative | `"-5.00"` | `None` (reject negative) |
| Scientific | `"1.29e2"` | `129.0` or reject |
| Currency suffix | `129.90EUR` | `129.90` |

### Normalization Rules

1. Strip all currency symbols: `$ € £ ¥ PLN zł kr SEK DKK NOK CHF`
2. Strip currency codes: `EUR USD GBP PLN SEK DKK NOK CHF`
3. Handle comma-as-decimal: if string has exactly one `,` after last `.`, or
   no `.` at all, treat `,` as decimal separator
4. Handle thousand separators: strip spaces and `.` that appear as thousand
   separators (pattern: `/\d{1,3}(\.\d{3})+/`)
5. Parse remaining string to float
6. Reject if result is negative, zero when original was non-empty, or NaN
7. Return `None` for unparseable values

### Test Cases: Price

| ID | Input | Expected |
|---|---|---|
| T-PRC-001 | `"$129.90"` | `129.90` |
| T-PRC-002 | `"€64,95"` | `64.95` |
| T-PRC-003 | `"£49.99"` | `49.99` |
| T-PRC-004 | `"129,99 zł"` | `129.99` |
| T-PRC-005 | `"1.299,95"` | `1299.95` |
| T-PRC-006 | `"1 299,95"` | `1299.95` |
| T-PRC-007 | `""` | `None` |
| T-PRC-008 | `"Sold out"` | `None` |
| T-PRC-009 | `"€49.99 - €69.99"` | `49.99` or `None` |
| T-PRC-010 | `"Free"` | `0.0` |
| T-PRC-011 | `"-5.00"` | `None` |
| T-PRC-012 | `"129.90EUR"` | `129.90` |
| T-PRC-013 | `"1.299"` (ambiguous) | `1299.0` (assume thousand sep) or `1.299` |
| T-PRC-014 | `null` | `None` |
| T-PRC-015 | `64.95` (already float) | `64.95` |

---

## 3. Image Deduplication and Noise Filtering

### Noise Categories

| Category | URL patterns | Action |
|---|---|---|
| Logo | `*logo*`, `*brand*`, `*favicon*` | Filter out |
| Icon | `*icon*`, `*sprite*` | Filter out |
| Payment | `*payment*`, `*visa*`, `*mastercard*`, `*paypal*` | Filter out |
| Trust badges | `*trustpilot*`, `*trust*`, `*badge*`, `*secure*` | Filter out |
| Size chart | `*size-chart*`, `*size-guide*`, `*maattabel*` | Filter out |
| Placeholder | `*placeholder*`, `*noimage*`, `*no-image*`, `*default*` | Filter out |
| Social | `*facebook*`, `*instagram*`, `*twitter*`, `*pinterest*` | Filter out |
| Tracking pixels | `*pixel*`, `*beacon*`, `*analytics*` | Filter out |
| CDN resize dupes | Same base URL, different `?width=` or `?resize=` | Keep largest |

### Dedup Strategy

1. Normalize URL: strip query params for comparison (keep for fetching)
2. Extract base filename: `image1.jpg` from `https://cdn.example.com/image1.jpg?w=300`
3. Group by base filename
4. Within each group, keep the URL with the largest dimension hint or original
5. Final `image_src` is a JSON array of unique URLs, ordered by appearance

### Test Cases: Images

| ID | Input | Expected |
|---|---|---|
| T-IMG-001 | `["/img/product1.jpg", "/img/product2.jpg"]` | Both kept |
| T-IMG-002 | `["/img/product1.jpg", "/img/product1.jpg"]` | Deduplicated to 1 |
| T-IMG-003 | `["/img/product1.jpg?w=300", "/img/product1.jpg?w=800"]` | Keep `w=800` |
| T-IMG-004 | `["/img/logo.png", "/img/product.jpg"]` | Only `product.jpg` |
| T-IMG-005 | `["/img/payment-visa.png", "/img/product.jpg"]` | Only `product.jpg` |
| T-IMG-006 | `["/img/placeholder.png"]` | Empty array (all filtered) |
| T-IMG-007 | `[]` (empty) | Validation error (image_src required) |
| T-IMG-008 | `["/img/size-chart.jpg", "/img/product.jpg"]` | Only `product.jpg` |
| T-IMG-009 | 15 product images | All kept (no artificial limit) |
| T-IMG-010 | Same image, different CDN domains | Keep both (different sources) |

---

## 4. Body Cleaning

### Cleaning Rules

| Content type | Action |
|---|---|
| `<script>` | Remove entirely |
| `<style>` | Remove entirely |
| `<svg>` | Remove entirely |
| `<button>` | Remove entirely |
| Share/social buttons | Remove (detect by class/text: share, social, facebook, twitter) |
| `<iframe>` | Remove entirely |
| `<noscript>` | Keep content inside |
| `<h2>`, `<h3>` | Keep (section headers) |
| `<p>`, `<ul>`, `<ol>`, `<li>` | Keep |
| `<table>` | Keep |
| `<img>` | Keep if product-relevant, filter noise |
| `<div>`, `<span>` | Keep structure |
| `<a>` | Keep but strip `javascript:` hrefs |
| Collapsible sections | Preserve structure (accordion, details/summary) |

### Truncation Strategy

| Condition | Action |
|---|---|
| body > 50,000 chars | Truncate to 50,000 + `<!-- truncated -->` |
| body is empty after cleaning | Set `body = ""` (valid, not error) |
| body is only whitespace | Set `body = ""` |
| body contains only noise (all filtered) | Set `body = ""` |

### Content Prioritization

When multiple sections exist, prioritize:
1. Description / Omschrijving / 商品描述
2. Specifications / Specificaties / 商品规格
3. Ingredients / Samenstelling / 成分
4. Usage / Gebruik / 使用方式

Sections like "Delivery", "Returns", "Reviews", "Related products" should be
excluded or deprioritized.

### Test Cases: Body

| ID | Input | Expected |
|---|---|---|
| T-BDY-001 | `<p>Product description</p>` | Unchanged |
| T-BDY-002 | `<script>alert('x')</script><p>Text</p>` | `<p>Text</p>` |
| T-BDY-003 | `<style>.x{}</style><p>Text</p>` | `<p>Text</p>` |
| T-BDY-004 | `<button>Share</button><p>Text</p>` | `<p>Text</p>` |
| T-BDY-005 | `<svg>...</svg><p>Text</p>` | `<p>Text</p>` |
| T-BDY-006 | `<h2>Desc</h2><div>Content</div>` | Unchanged |
| T-BDY-007 | 60,000 chars of product HTML | Truncated to 50,000 + marker |
| T-BDY-008 | `""` (empty) | `""` |
| T-BDY-009 | `"   \n  "` (whitespace) | `""` |
| T-BDY-010 | Only `<button>Share</button>` | `""` (all noise) |
| T-BDY-011 | `<details><summary>Specs</summary><p>Data</p></details>` | Unchanged |
| T-BDY-012 | `<p onclick="evil()">Text</p>` | `<p>Text</p>` (strip event handlers) |

---

## 5. Variant / Size Handling

### Variant Model

```
Main product:  handle = "model00001",   option1_value = "Red"
Variant 1:     handle = "model00001_1", option1_value = "Red"
Variant 2:     handle = "model00001_2", option1_value = "Blue"
Variant 3:     handle = "model00001_3", option1_value = "Green"
```

### Field Mapping

| Field | Value | Notes |
|---|---|---|
| `option1_name` | "Color" or localized | e.g., "Kleur" for Dutch |
| `option1_value` | Color name or handle | From variant link or data attribute |
| `option2_name` | "Size" or localized | e.g., "Maat" for Dutch |
| `option2_value` | `['18','19','20','21']` | List string, all sizes including OOS |
| `size_price` | JSON string | Per-size price if different |
| `handle` | `base_N` | Incrementing suffix |

### Rules

1. Handle suffix increments per variant: `_1`, `_2`, `_3`
2. All sizes captured, including out-of-stock
3. If no explicit color, use handle as option1_value
4. If no sizes, omit option2 fields (don't set to empty)
5. Main product AND variants all go to goods table
6. `sole_id` includes category path, so same URL in different categories = different records

### Test Cases: Variants

| ID | Scenario | Expected |
|---|---|---|
| T-VAR-001 | Product with 3 color variants | 4 records (main + 3 variants) |
| T-VAR-002 | Handle for variant 2 | `model00001_2` |
| T-VAR-003 | Sizes including OOS | `['S','M','L','XL']` (all) |
| T-VAR-004 | No color info | `option1_value = handle` |
| T-VAR-005 | No sizes | `option2_name` and `option2_value` omitted |
| T-VAR-006 | Size-specific pricing | `size_price = '{"S": 49.99, "M": 49.99}'` |
| T-VAR-007 | Same product, 2 categories | 2 records with different sole_id |
| T-VAR-008 | Variant with no price | Inherit main product price or `None` |
| T-VAR-009 | option2_value format | Must be list string: `['18','19']` |
| T-VAR-010 | Handle with unicode | Accepted (handle is opaque) |

---

## 6. Category-Aware Deduplication

### Current Design (from spider_text)

```
sole_id = MD5(categories_1 + categories_2 + categories_3 + url)
```

Same URL + different category path = different sole_id = both kept.

### Dedup Rules

| Scenario | same URL | same category | Action |
|---|---|---|---|
| Same product, same category | yes | yes | Dedup (same sole_id) |
| Same product, different category | yes | no | Keep both (different sole_id) |
| Different product, same category | no | yes | Keep both (different URL) |
| Same product, no category | yes | both empty | Dedup (same sole_id) |

### Edge Cases

1. **URL normalization**: `https://example.com/product` vs
   `https://example.com/product?ref=nav` — should these be the same?
   - Recommendation: normalize URL before hashing (strip tracking params)

2. **Category case sensitivity**: `"Shoes"` vs `"shoes"` — should be normalized

3. **Empty categories**: product without categories uses empty strings in hash.
   Two category-less products with same URL will dedup correctly.

4. **Category ordering**: categories must be consistently ordered (1, 2, 3).
   Swapping cat1 and cat2 would produce different sole_id for same product.

### Test Cases: Category Dedup

| ID | Scenario | Expected |
|---|---|---|
| T-DED-001 | Same URL, same cat1/cat2/cat3 | Dedup (1 record) |
| T-DED-002 | Same URL, different cat1 | Keep both (2 records) |
| T-DED-003 | Same URL, no categories | Dedup (1 record) |
| T-DED-004 | Same URL with `?ref=nav` vs without | Depends on URL normalization |
| T-DED-005 | Same URL, cat1="Shoes" vs cat1="shoes" | Depends on case normalization |
| T-DED-006 | Different URL, same categories | Keep both |
| T-DED-007 | sole_id collision (MD5) | Accept (extremely unlikely) |

---

## 7. Three-Phase Task Model

### Phase Boundaries

```
Phase 1: Category/List
  Input: category URLs
  Output: product detail URLs → list_queue
  Progress: liebiao table
  Validation: at least 1 product URL extracted per category

Phase 2: Detail
  Input: product URLs from list_queue
  Output: product records + variant URLs → more_list_queue
  Progress: zhuti table
  Validation: required fields present, price normalized, image_src non-empty

Phase 3: Variant
  Input: variant URLs from more_list_queue
  Output: variant records → goods table
  Progress: bianti table
  Validation: handle has suffix, option1_value set
```

### Anti-Starvation Rules

The spider_text document warns: "不要一直只跑目录页。应优先或穿插处理商品详情。"

| Rule | Description |
|---|---|
| Priority | Detail tasks (Phase 2) should be prioritized over list tasks (Phase 1) |
| Interleave | After each list page, process N detail pages before next list page |
| Monitor | If `liebiao` table grows but `goods` table stays at 0, alert |
| Timeout | If no goods after 10 minutes of list crawling, pause and investigate |

### Liveliness Checks

| Check | Condition | Action |
|---|---|---|
| List stuck | 0 new URLs in 5 minutes | Log warning, skip category |
| Detail stuck | 0 new goods in 10 minutes | Log error, check selectors |
| Variant stuck | 0 new variants in 5 minutes | Log warning, continue |
| DB path drift | DB file not growing | Check file path, permissions |
| Cache growing, DB not | Cache dir size increases, goods count flat | Check detail parser |

### Test Cases: Three-Phase Model

| ID | Scenario | Expected |
|---|---|---|
| T-3PH-001 | 1 category with 10 products | 10 goods records after all phases |
| T-3PH-002 | 1 category, 0 products on list | 0 goods, log warning |
| T-3PH-003 | Detail page returns empty fields | Record rejected or partial |
| T-3PH-004 | Same product in 2 categories | 2 goods records (different sole_id) |
| T-3PH-005 | List queue grows, goods stays 0 | Liveliness check triggers |
| T-3PH-006 | Variant page returns same data as main | Both records saved (different handle) |
| T-3PH-007 | Phase 1 produces 1000 URLs | Phase 2 processes them (not blocked) |
| T-3PH-008 | Detail parse throws exception | Logged, not crash, continue next |

---

## 8. Pre-Production Smoke Test Flow

### Stage 1: Micro Sample (1 category / 1 page / 1 product)

**Goal:** Verify the pipeline works end-to-end.

| Step | Action | Pass criteria |
|---|---|---|
| 1.1 | Select 1 category URL | URL is accessible |
| 1.2 | Fetch 1 list page | HTML returned, no challenge/403 |
| 1.3 | Extract product links | At least 1 link found |
| 1.4 | Fetch 1 product detail | HTML returned |
| 1.5 | Extract fields | All required fields present |
| 1.6 | Normalize price | Float value, no currency symbols |
| 1.7 | Filter images | No logos/placeholders |
| 1.8 | Clean body | No script/style/svg |
| 1.9 | Write to DB | Record exists in goods table |
| 1.10 | Verify sole_id | MD5(cat1+cat2+cat3+url) matches |

**Exit:** All 10 steps pass.

### Stage 2: Small Smoke (50 items)

**Goal:** Verify consistency across multiple products.

| Check | Pass criteria |
|---|---|
| Record count | >= 40 items (allow 20% extraction failure) |
| Required fields | 100% of records have url, title, price, image_src, sole_id |
| Price validity | 100% of prices are positive floats |
| Image validity | 100% of image_src are non-empty JSON arrays |
| sole_id uniqueness | 0 duplicates |
| Body cleanliness | 0 records contain `<script>` or `<style>` |
| Variant handles | If variants exist, handles have `_N` suffix |
| option2_value format | If sizes exist, format is `['a','b']` |
| Category coverage | At least 1 category populated |

### Stage 3: DB Integrity Checks

| Check | Query/Method |
|---|---|
| No NULL required fields | `SELECT COUNT(*) FROM goods WHERE url IS NULL OR title IS NULL OR price IS NULL` |
| Price range sanity | `SELECT MIN(price), MAX(price) FROM goods` — check for outliers |
| Duplicate sole_id | `SELECT sole_id, COUNT(*) FROM goods GROUP BY sole_id HAVING COUNT(*) > 1` |
| Empty images | `SELECT COUNT(*) FROM goods WHERE image_src = '[]' OR image_src IS NULL` |
| Body script leak | `SELECT COUNT(*) FROM goods WHERE body LIKE '%<script%'` |
| Variant consistency | Check handles with `_N` suffix have matching base handle |

### Stage 4: Operational Checks

| Check | Pass criteria |
|---|---|
| Cache != DB drift | Cache file count roughly correlates with goods count |
| No Cloudflare cache | No challenge pages in cache |
| DB path correct | DB file in project directory, not user home |
| Run time reasonable | 50 items in < 5 minutes |
| No memory leak | Process memory stable over run |

---

## Summary

### Finding Count by Area

| Area | Findings | Highest Severity |
|---|---|---|
| Schema required fields | 11 test cases | medium (missing field rejection) |
| Price normalization | 15 test cases | medium (comma-decimal ambiguity) |
| Image dedup | 10 test cases | medium (noise filtering coverage) |
| Body cleaning | 12 test cases | medium (truncation strategy) |
| Variant/size | 10 test cases | low (format consistency) |
| Category dedup | 7 test cases | medium (URL normalization) |
| Three-phase model | 8 test cases | high (anti-starvation) |
| Smoke test flow | 4 stages, 20+ checks | high (liveliness monitoring) |

### Highest Severity: high

1. **Anti-starvation in three-phase model** (T-3PH-005): If list crawling
   dominates and detail processing starves, DB stays at 0 while cache grows.
   This is the most common real-world failure mode from spider_text experience.

2. **Liveliness monitoring**: Need real-time checks that goods count is growing
   proportional to cache/URL count.

### Total Test Cases: 93

Across 8 areas: schema (11), price (15), image (10), body (12), variant (10),
category dedup (7), three-phase (8), smoke flow (20+ checks across 4 stages).

### No Code Changed

This is a read-only QA design document.
