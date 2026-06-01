# Batch 006 Summary — Sites 51–60

**Generated**: 2026-05-28
**Total sites**: 10
**Schema**: clm-site-recon-v1

## Aggregate Statistics

| Metric | Count |
|--------|-------|
| Accessible (best_mode found) | 4 |
| Partially blocked (requests ok, browser blocked) | 0 |
| Fully blocked (403/captcha all modes) | 6 |
| avg confidence | 0.19 |

## Site Breakdown

| # | Domain | Status | Best Mode | API Hints | Confidence | Notes |
|---|--------|--------|-----------|-----------|------------|-------|
| 51 | arket.com | accessible | requests | 1 | 0.25 | H&M Group, search hint |
| 52 | cos.com | accessible | requests | 1 | 0.30 | H&M Group, /api/geolocation-country |
| 53 | weekday.com | accessible | requests | 1 | 0.25 | H&M Group, shared frontend domain |
| 54 | monki.com | accessible | requests | 1 | 0.25 | H&M Group, 403 on detail pages |
| 55 | ae.com | accessible | requests | 4 | 0.30 | /us/en/s/{search_term_string} |
| 56 | hollisterco.com | blocked | — | 0 | 0.10 | 403 all modes, redirects /shop/eu |
| 57 | urbanoutfitters.com | partial | requests | 0 | 0.15 | requests 63KB, curl_cffi/browser 403 |
| 58 | freepeople.com | blocked | — | 0 | 0.10 | URBN brand, captcha all modes |
| 59 | anthropologie.com | blocked | — | 0 | 0.10 | URBN brand, captcha all modes |
| 60 | gap.com | blocked | — | 0 | 0.10 | Gap Inc. brand, 403 all modes |

## Key Observations

1. **H&M Group clustering**: arket.com, cos.com, weekday.com, monki.com all share `weekday-frontend-prd.prd.mcs.hmgroup.tech` infrastructure. All accessible via requests but limited evidence depth.

2. **URBN Group wall**: urbanoutfitters.com partially accessible via requests but freepeople.com and anthropologie.com are fully blocked with captcha across all modes. Shared WAF/captcha infrastructure.

3. **Gap Inc. WAF**: gap.com returns 403 across all modes with ~290 bytes error pages. Aggressive bot detection.

4. **ae.com search API**: 4 API hints including `/us/en/s/{search_term_string}` template — potential search endpoint.

## Failure Mode Distribution

| Mode | Count | Sites |
|------|-------|-------|
| WAF 403 | 2 | hollisterco, gap |
| Captcha | 2 | freepeople, anthropologie |
| Partial block | 1 | urbanoutfitters |
| Accessible | 5 | arket, cos, weekday, monki, ae |

## Confidence Distribution

- 0.1: 3 sites (fully blocked)
- 0.15: 1 site (partial block)
- 0.25: 3 sites (accessible, low evidence)
- 0.30: 3 sites (accessible, some API hints)
