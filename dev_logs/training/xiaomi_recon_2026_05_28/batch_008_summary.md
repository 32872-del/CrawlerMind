# Batch 008 Summary — Sites 71–80

**Generated**: 2026-05-28
**Total sites**: 10
**Schema**: clm-site-recon-v1

## Aggregate Statistics

| Metric | Count |
|--------|-------|
| Accessible (best_mode found) | 8 |
| Partially blocked | 0 |
| Fully blocked (403/captcha) | 2 |
| avg confidence | 0.18 |

## Site Breakdown

| # | Domain | Status | Best Mode | API Hints | Confidence | Notes |
|---|--------|--------|-----------|-----------|------------|-------|
| 71 | otto.de | accessible | requests | 0 | 0.15 | Browser timeout, 289 anchors |
| 72 | zara.com | accessible | requests | 0 | 0.10 | Inditex, ~2112 byte shell |
| 73 | bershka.com | accessible | requests | 0 | 0.10 | Inditex, ~2120 byte shell |
| 74 | pullandbear.com | accessible | requests | 0 | 0.10 | Inditex, ~2128 byte shell |
| 75 | johnlewis.com | accessible | requests | 3 | 0.30 | Search API, Monetate, JS shell |
| 76 | debenhams.com | accessible | requests | 80 | 0.30 | 80 category URLs, browser 4.2MB |
| 77 | nordstrom.com | blocked | — | 0 | 0.10 | 403 all modes, 160 bytes |
| 78 | mango.com | accessible | requests | 2 | 0.30 | api.shop.mango.com |
| 79 | tommy.com | accessible | requests | 0 | 0.15 | PVH Corp, 5KB JS shell |
| 80 | guess.com | accessible | requests | 18 | 0.30 | Demandware, Algolia search |

## Key Observations

1. **Inditex cluster confirmed**: zara.com, bershka.com, pullandbear.com all show identical ~2100 byte SPA shell pattern. 8 Inditex sites total analyzed.

2. **debenhams.com rich catalog**: 80 category URLs found. Browser gets 4.2MB of content. Boohoo Group brand.

3. **guess.com Demandware platform**: 18 API hints including Product-ShowQuickView, Algolia-SearchResultsSlot, Product-ShowVariation. Shared CDN with rag-bone.eu.

4. **mango.com dedicated API**: api.shop.mango.com found. Good candidate for API-based crawling.

5. **nordstrom.com extreme blocking**: Only 160 bytes returned, text/plain content type. Most aggressive WAF seen.

## Failure Mode Distribution

| Mode | Count | Sites |
|------|-------|-------|
| WAF 403 | 1 | nordstrom |
| Inditex SPA | 3 | zara, bershka, pullandbear |
| JS shell | 2 | tommy, otto |
| Accessible | 4 | johnlewis, debenhams, mango, guess |
