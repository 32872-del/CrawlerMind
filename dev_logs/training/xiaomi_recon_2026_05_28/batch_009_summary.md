# Batch 009 Summary — Sites 81–90

**Generated**: 2026-05-28
**Total**: 10 sites

## Aggregate Stats

| Metric | Value |
|--------|-------|
| Accessible | 8 |
| Partially Blocked | 0 |
| Fully Blocked | 2 |
| Avg Confidence | 0.22 |

## Site Breakdown

| # | Site | Rendering | Access | API Hints | Confidence | Key Finding |
|---|------|-----------|--------|-----------|------------|-------------|
| 81 | calvinklein.com | hybrid | ok | 0 | 0.10 | PVH Corp, 5KB shell, browser timeout |
| 82 | levi.com | hybrid | partial | 0 | 0.15 | requests 5KB / curl_cffi 42KB, browser blocked |
| 83 | wrangler.com | hybrid | partial | 0 | 0.10 | 5KB, browser blocked, challenge detected, taobao links |
| 84 | g-star.com | hybrid | ok | 18 | 0.30 | /global/api/v1/ endpoints, /global/product |
| 85 | scotchandsoda.com | hybrid | partial | 10 | 0.20 | requests 61KB ok, curl_cffi blocked, browser captcha |
| 86 | sandro-paris.com | unknown | blocked | 0 | 0.10 | 502 Bad Gateway, redirects to .cn |
| 87 | reiss.com | hybrid | ok | 80 | 0.35 | api.e.reiss.com (0.7), Next Group CMS, browser 414KB |
| 88 | whistles.com | hybrid | ok | 8 | 0.30 | cquotient.com recommendation API, browser 312KB |
| 89 | karenmillen.com | hybrid | ok | 80 | 0.30 | Boohoo Group, 80 category URLs, browser 323KB |
| 90 | coastfashion.com | hybrid | ok | 80 | 0.30 | Boohoo Group, 80 category URLs, browser 1.4MB |

## New Failure Modes

- **DNS failure** (jack-wills.com): Hostname cannot be resolved. Brand likely defunct/domain expired.

## Platform Patterns Confirmed

- **PVH Corp Group**: calvinklein.com + tommy.com share similar 5KB JS shell architecture
- **Boohoo Group**: karenmillen.com + coastfashion.com both have 80 category URL hints
- **cquotient.com recommendation API**: whistles.com uses same pattern as phase-eight.com and hobbs.co.uk
- **Next Group CMS**: reiss.com uses api.e.reiss.com, same pattern as next.co.uk

## Key API Domains Found

- `api.e.reiss.com` — Reiss product API (Next Group)
- `cquotient.com` — Recommendation API (whistles, phase-eight, hobbs)
- `/global/api/v1/` — G-Star product API endpoints
