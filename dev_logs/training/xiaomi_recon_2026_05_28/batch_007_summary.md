# Batch 007 Summary — Sites 61–70

**Generated**: 2026-05-28
**Total sites**: 10
**Schema**: clm-site-recon-v1

## Aggregate Statistics

| Metric | Count |
|--------|-------|
| Accessible (best_mode found) | 6 |
| Partially blocked | 0 |
| Fully blocked (403/captcha) | 4 |
| avg confidence | 0.20 |

## Site Breakdown

| # | Domain | Status | Best Mode | API Hints | Confidence | Notes |
|---|--------|--------|-----------|-----------|------------|-------|
| 61 | bananarepublic.com | blocked | — | 0 | 0.10 | Gap Inc., 403 all modes |
| 62 | oldnavy.com | blocked | — | 0 | 0.10 | Gap Inc., 403 all modes |
| 63 | uniqlo.com | accessible | requests | 5 | 0.20 | Fast Retailing, bazaarvoice |
| 64 | marksandspencer.com | accessible | requests | 44 | 0.35 | Rich API hints, search/category URLs |
| 65 | tkmaxx.com | accessible | requests | 0 | 0.10 | Probe ok but scout 403 |
| 66 | next.co.uk | accessible | requests | 1 | 0.30 | api.e.next.co.uk, JS shell |
| 67 | asda.com | accessible | curl_cffi | 4 | 0.15 | Browser 619KB, login/region blocks |
| 68 | very.co.uk | blocked | — | 0 | 0.10 | 403 all modes |
| 69 | zalando.co.uk | accessible | requests | 4 | 0.20 | JS shell, catalog URLs |
| 70 | aboutyou.de | accessible | requests | 60 | 0.35 | api.aboutyou.com, excellent API infra |

## Key Observations

1. **aboutyou.de API goldmine**: 60 API hints including api.aboutyou.com, api-internal.aboutyou.com, api-cloud.aboutyou.de/v1. Best API infrastructure found so far.

2. **marksandspencer.com rich hints**: 44 API hints with search template, store finder, and category URLs. Good candidate for catalog exploration.

3. **next.co.uk dedicated API**: api.e.next.co.uk detected - separate API domain for product data.

4. **Gap Inc. wall continues**: bananarepublic.com and oldnavy.com join gap.com in the fully blocked category.

## Failure Mode Distribution

| Mode | Count | Sites |
|------|-------|-------|
| WAF 403 | 3 | bananarepublic, oldnavy, very |
| Inconsistent access | 1 | tkmaxx |
| Accessible | 6 | uniqlo, marksandspencer, next, asda, zalando, aboutyou |
