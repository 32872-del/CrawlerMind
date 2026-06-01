# Batch 010 Summary — Sites 91–100

**Generated**: 2026-05-28
**Total**: 10 sites

## Aggregate Stats

| Metric | Value |
|--------|-------|
| Accessible | 5 |
| Partially Blocked | 0 |
| Fully Blocked | 5 |
| Avg Confidence | 0.16 |

## Site Breakdown

| # | Site | Rendering | Access | API Hints | Confidence | Key Finding |
|---|------|-----------|--------|-----------|------------|-------------|
| 91 | phase-eight.com | hybrid | ok | 6 | 0.30 | cquotient.com recommendation API, actual product URLs |
| 92 | hobbs.co.uk | hybrid | ok | 17 | 0.25 | cquotient.com recommendation API, browser 468KB |
| 93 | allsaints.com | hybrid | blocked | 3 | 0.15 | Demandware, captcha+rate_limited, all modes fail |
| 94 | superdry.com | hybrid | ok | 12 | 0.25 | Demandware Search-ShowAjax endpoint |
| 95 | jack-wills.com | unknown | blocked | 0 | 0.00 | DNS failure - brand defunct |
| 96 | oasis-fashion.com | unknown | blocked | 0 | 0.00 | TLS error on all modes, ERR_CONNECTION_CLOSED |
| 97 | warehousefashion.com | hybrid | ok | 80 | 0.30 | Boohoo Group, 80 category URLs, browser 1.1MB |
| 98 | lkbennett.com | hybrid | ok | 5 | 0.20 | search suggest + product endpoints, browser captcha |
| 99 | tedbaker.com | hybrid | ok | 0 | 0.15 | requests 80KB ok, browser captcha, 0 API hints |
| 100 | boden.co.uk | hybrid | ok | 1 | 0.20 | requests 77KB ok, browser captcha, search endpoint |

## New Failure Modes

- **TLS error** (oasis-fashion.com): SSL UNEXPECTED_EOF_WHILE_READING on all modes. Site may be defunct or geo-blocked at TLS level.

## Platform Patterns Confirmed

- **cquotient.com recommendation API**: phase-eight.com + hobbs.co.uk (same as whistles.com)
- **Demandware**: allsaints.com + superdry.com (same platform as guess.com)
- **Boohoo Group**: warehousefashion.com (same pattern as karenmillen, coastfashion, debenhams, prettylittlething, boohoo)
- **DNS failure**: jack-wills.com (brand defunct, same as earlier findings)
