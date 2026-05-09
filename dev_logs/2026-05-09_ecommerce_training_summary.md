# 2026-05-09 Ecommerce Training Summary

Generated at: 2026-05-09T18:11:28
Excel: `dev_logs/2026-05-09_ecommerce_training_sample.xlsx`
JSON: `dev_logs/2026-05-09_ecommerce_training_sample.json`

## Site Results

- shoesme: rows=1, ok=0, partial=0, blocked=1, failed=0, with_price=0, with_images=0, with_description=0
- donsje: rows=5, ok=5, partial=0, blocked=0, failed=0, with_price=5, with_images=5, with_description=5
- clausporto: rows=5, ok=5, partial=0, blocked=0, failed=0, with_price=5, with_images=5, with_description=5
- uvex: rows=5, ok=5, partial=0, blocked=0, failed=0, with_price=5, with_images=5, with_description=5
- bosch: rows=3, ok=0, partial=3, blocked=0, failed=0, with_price=0, with_images=3, with_description=3

## Notes

- Shoesme returned a Cloudflare challenge and was recorded as diagnosis-only.
- Donsje exposed a public Shopify `products.json` endpoint with variants, sizes, color, images, and prices.
- Clausporto and uvex were collected through static Magento-style list/detail pages.
- Bosch.de is a corporate product/service page, so rows are partial and price/color/size are intentionally blank.
- This run is low-volume training evidence, not a full-site crawl.
