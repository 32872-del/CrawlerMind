# Batch 005 Summary — Sites 41–50

**Generated**: 2026-05-28
**Sites processed**: 10
**Schema**: clm-site-recon-v1

## Results Overview

| # | Site | Status | Rendering | Confidence | Key Finding |
|---|------|--------|-----------|------------|-------------|
| 41 | prettylittlething.com | Accessible | hybrid | 0.35 | 80 API hints, category URLs, login required |
| 42 | shein.com | Blocked | spa | 0.15 | geetest captcha, 80KB HTML |
| 43 | asos.com | Accessible | spa | 0.25 | 4 API hints, category URLs, timeout |
| 44 | debenhams.com | Accessible | hybrid | 0.3 | 80 API hints, category offer URLs, region block |
| 45 | houseoffraser.co.uk | Accessible | unknown | 0.2 | 80KB HTML, browser HTTP2 error |
| 46 | flannels.com | Accessible | unknown | 0.2 | 80KB HTML, browser HTTP2 error |
| 47 | selfridges.com | Accessible | hybrid | 0.35 | 36 API hints, api.selfridges.com, brand directory |
| 48 | harveynichols.com | Accessible | spa | 0.35 | 26 API hints, api.randemretail.online, /api/v2/ endpoint |
| 49 | matchesfashion.com | Blocked | unknown | 0.15 | 14KB HTML, browser captcha |
| 50 | farfetch.com | Partial | spa | 0.25 | curl_cffi best, api.farfetch.net, JS shell |

## Access Distribution

- **Accessible (requests OK)**: 7 (prettylittlething, asos, debenhams, houseoffraser, flannels, selfridges, harveynichols)
- **Partially blocked**: 1 (farfetch.com - curl_cffi works)
- **Fully blocked (captcha)**: 2 (shein.com, matchesfashion.com)

## Platform Patterns

- **api.randemretail.online**: harveynichols.com
- **api.selfridges.com**: selfridges.com
- **api.farfetch.net**: farfetch.com
- **HTTP2 protocol error**: houseoffraser.co.uk, flannels.com
- **geetest captcha**: shein.com

## Key Observations

1. **UK luxury/multi-brand retailers mostly accessible**: selfridges, harveynichols, debenhams all accessible via requests
2. **Dedicated API domains are common**: api.selfridges.com, api.randemretail.online, api.farfetch.net
3. **HTTP2 protocol errors**: houseoffraser.co.uk and flannels.com share this browser issue
4. **geetest captcha**: shein.com uses geetest instead of standard captcha
5. **Category offer URLs**: debenhams.com uses /categories/ with offer-specific slugs

## Confidence Distribution

- High confidence (≥0.5): 0 sites
- Medium confidence (0.3-0.4): 4 sites
- Low confidence (<0.3): 6 sites

## Recommended Next Steps

1. Investigate api.selfridges.com for product API endpoints
2. Explore harveynichols.com /api/v2/ endpoint for product data
3. Test debenhams.com category pages for product lists
4. Continue expanding to more accessible e-commerce sites
