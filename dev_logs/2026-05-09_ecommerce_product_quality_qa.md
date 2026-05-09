# 2026-05-09 Ecommerce Product Quality QA Design

## Summary

QA design audit for ecommerce product data quality. Derived from spider_text
fnspider domain experience (three-phase list/detail/variant model, category-
aware sole_id dedup, goods SQLite schema).

## Design Areas (8)

1. **Product schema required fields**: url, handle, title, price, image_src,
   sole_id are mandatory. 11 test cases.

2. **Price normalization**: 15 patterns covering $, €, £, PLN, comma decimal,
   thousand separators, empty, garbage, range, free, negative. 15 test cases.

3. **Image dedup and noise filtering**: logo, icon, payment, trust badges,
   size chart, placeholder, social, tracking pixels. CDN resize dedup by base
   filename. 10 test cases.

4. **Body cleaning**: Remove script/style/svg/button/share/iframe. Preserve
   renderable HTML. Truncation at 50,000 chars. 12 test cases.

5. **Variant/size**: handle suffix `_1`, `_2`, `_3`. option1 = color,
   option2 = size list string. All sizes including OOS. size_price JSON.
   10 test cases.

6. **Category-aware dedup**: sole_id = MD5(cat1+cat2+cat3+url). Same URL
   different category = both kept. URL normalization edge cases. 7 test cases.

7. **Three-phase task model**: list → detail → variant with anti-starvation
   rules. Priority detail over list. Liveliness checks. 8 test cases.

8. **Smoke test flow**: 4 stages — micro (1/1/1), 50-item smoke, DB integrity,
   operational checks. 20+ pass criteria.

## Key Risks

1. **Anti-starvation** (high): List crawling can dominate while detail
   processing starves, leaving DB at 0. spider_text warns about this explicitly.

2. **Price ambiguity** (medium): `"1.299"` is ambiguous (1299 vs 1.299).
   Need locale-aware or site-specific rules.

3. **URL normalization** (medium): Tracking params cause false dedup misses.

## Total: 93 test cases across 8 areas

## Deliverables

- `docs/team/audits/2026-05-09_LLM-2026-002_ECOMMERCE_PRODUCT_QUALITY_QA.md`
- `dev_logs/2026-05-09_ecommerce_product_quality_qa.md`
