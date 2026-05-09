# 2026-05-09 Spider Text Absorption Plan

## Source Reviewed

External folder:

```text
C:\Users\Administrator\Downloads\spider_text
```

This folder is not a clean library. It is a practical ecommerce crawl workbench:
site-specific scripts, two `fnspider` variants, SQLite goods output, cache/output
folders, proxy/Clash files, Excel export tools, and a strong ecommerce site
adaptation checklist.

## Supervisor Decision

Do not copy the whole folder into Crawler-Mind.

Absorb the experience, schemas, and deterministic rules. Rebuild the useful
parts as small CLM-native modules with tests.

## Useful Ideas To Absorb

### 1. Ecommerce Product Schema

`spider_text` uses a richer product schema than CLM's current generic
`title/price/image/link` model:

```text
url
handle
more_info
title
subtitle
price
body
categories_1
categories_2
categories_3
option1_name
option1_value
option2_name
option2_value
option3_name
option3_value
image_src
size_price
sole_id
```

CLM should add an ecommerce-specific normalized record layer instead of forcing
all ecommerce data through generic item fields.

### 2. Category-Aware Dedupe

Do not dedupe ecommerce records by URL only. The same product URL can appear in
multiple categories and should sometimes be preserved per category.

Recommended key:

```text
categories_1 + categories_2 + categories_3 + url
```

CLM implication: `URLFrontier` needs a future `dedupe_key` or `scope_key`, not
only global URL hash.

### 3. Three-Stage Product Task Model

Old framework pattern:

```text
get_list -> get_content -> get_more_content
category/list -> product or variant discovery -> final detail extraction
```

CLM already has `ProductTask`, but it should mature into explicit task kinds:

```text
category_page
list_page
detail_page
variant_page
```

Scheduling lesson: after a list page yields detail links, detail work should be
prioritized/interleaved. Do not crawl every category/list page first while DB
stays empty.

### 4. Product Quality Rules

Reusable quality checks:

- title is required and should be cleaned
- price is required and normalized to float when available
- image_src is required and should be a non-empty list for ecommerce products
- handle is required
- color/size variants should be normalized consistently
- option2_value should represent all sizes, not only in-stock sizes
- body should be cleaned but remain renderable HTML

### 5. Product Body And Image Normalization

Useful ideas from export/cleanup tools:

- remove `script`, `style`, and `link`
- remove noisy attributes such as `data-*`
- convert or normalize list markup when export format needs it
- cap body length for downstream spreadsheet/export systems
- parse list-like strings safely
- dedupe image URLs
- choose first image or highest-quality image for export views

## Do Not Absorb Directly

- Do not vendor `clash-meta.exe` or proxy yaml files.
- Do not add proxy credentials or proxy pool config to the repo.
- Do not make Botasaurus a core dependency yet. Consider it only as a future
  optional browser provider.
- Do not copy site-specific scripts such as `25_toolstation.py` into CLM core.
  Use them as training examples only.
- Do not import login scripts into the open-source project. Authorized login
  workflows should be designed separately.
- Do not overwrite CLM's bundled fnspider. Compare ideas only.

## Proposed CLM Modules

### Phase 1: Product Quality Foundation

Add:

```text
autonomous_crawler/tools/product_schema.py
autonomous_crawler/tools/product_quality.py
autonomous_crawler/tests/test_product_quality.py
```

Functions/classes:

```text
ProductRecord
build_product_sole_id(record)
normalize_price(value)
parse_list_value(value)
dedupe_product_images(images)
clean_product_body(html, max_len=32767)
validate_product_record(record)
expand_variant_combinations(record)
```

Test with deterministic fixtures only.

### Phase 2: Product Task Scheduling

Upgrade existing `autonomous_crawler/tools/product_tasks.py` with:

```text
category_page/list_page/detail_page/variant_page task kinds
category payload preservation
category-aware dedupe key builder
list-to-detail priority recommendations
```

Later map this to `storage/frontier.py` with `dedupe_key` support.

### Phase 3: Ecommerce Training Fixtures

Add site-zoo fixtures for:

- detail page with color variants
- detail page with size list
- noisy body HTML
- duplicate/low-quality images
- same product URL under two categories
- missing required fields

### Phase 4: Real Ecommerce Training

After deterministic quality tests pass, run a small authorized public ecommerce
training batch with strict limits:

```text
1 category
1 page
1-5 products
```

Acceptance checks:

- DB/result records grow while cache grows
- title/price/image/handle present
- body clean and renderable
- variant/size data normalized
- category-aware dedupe behaves as expected

## Next Recommended Order

1. Finish pagination hardening from API QA.
2. Implement Product Quality Foundation from this plan.
3. Add category-aware frontier/dedupe support.
4. Run the next real-site training batch.
