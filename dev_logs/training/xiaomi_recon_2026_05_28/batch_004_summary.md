# Batch 004 Summary — Sites 31–40

**Generated**: 2026-05-28
**Sites processed**: 10
**Schema**: clm-site-recon-v1

## Results Overview

| # | Site | Status | Rendering | Confidence | Key Finding |
|---|------|--------|-----------|------------|-------------|
| 31 | reiss.com | SPA | spa | 0.35 | api.e.reiss.com (0.7), region block |
| 32 | allsaints.com | Blocked | unknown | 0.15 | curl_cffi 80KB but browser captcha, Demandware |
| 33 | tedbaker.com | Blocked | unknown | 0.15 | 80KB HTML but browser captcha |
| 34 | superdry.com | Accessible | hybrid | 0.4 | Demandware, search API /search?q={query} |
| 35 | jackwills.com | Blocked | unknown | 0.1 | robots.txt block |
| 36 | frenchconnection.com | Blocked | unknown | 0.15 | 403 all modes, captcha, 4 API hints |
| 37 | burberry.com | Partial | spa | 0.3 | 80KB JS shell, api.burberry.com (0.7), captcha |
| 38 | gucci.com | Accessible | spa | 0.2 | 80KB HTML, browser HTTP2 error |
| 39 | louisvuitton.com | Blocked | unknown | 0.1 | 403 all modes, 12KB error page |
| 40 | boohoo.com | Accessible | hybrid | 0.35 | 80 API hints, category faceted URLs, region block |

## Access Distribution

- **Accessible (requests OK)**: 4 (superdry.com, gucci.com, boohoo.com, reiss.com partial)
- **Partially blocked (captcha in browser)**: 3 (allsaints.com, tedbaker.com, burberry.com)
- **Fully blocked (403/robots)**: 3 (jackwills.com, frenchconnection.com, louisvuitton.com)

## Platform Patterns

- **Demandware**: superdry.com, allsaints.com
- **api.e.* subdomain**: reiss.com (api.e.reiss.com)
- **Dedicated API domain**: burberry.com (api.burberry.com)
- **Category faceted URLs**: boohoo.com

## Key Observations

1. **UK fashion sites show mixed accessibility**: Some accessible via requests, others blocked by captcha/WAF
2. **Dedicated API domains are valuable**: burberry.com's api.burberry.com has high confidence for product data
3. **Category faceted URLs**: boohoo.com uses /categories/{name}/facet/priceRange/{min}-{max} pattern
4. **Demandware platform**: Used by superdry.com and allsaints.com, search API pattern /search?q={query}
5. **Captcha is the dominant blocker**: 5 out of 10 sites show captcha challenges in browser mode

## Confidence Distribution

- High confidence (≥0.5): 0 sites
- Medium confidence (0.3-0.4): 4 sites
- Low confidence (<0.3): 6 sites

## Recommended Next Steps

1. Explore boohoo.com category pages for product list extraction
2. Investigate api.burberry.com for product API endpoints
3. Test superdry.com search API for product data
4. Expand to more accessible UK/EU fashion e-commerce sites
