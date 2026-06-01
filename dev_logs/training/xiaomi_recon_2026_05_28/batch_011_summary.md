# Batch 011 Summary — Sites 101–110

**Generated**: 2026-05-28
**Total**: 10 sites

## Aggregate Stats

| Metric | Value |
|--------|-------|
| Accessible | 4 |
| Partially Blocked | 0 |
| Fully Blocked | 6 |
| Avg Confidence | 0.12 |

## Site Breakdown

| # | Site | Rendering | Access | API Hints | Confidence | Key Finding |
|---|------|-----------|--------|-----------|------------|-------------|
| 101 | nobodychild.com | hybrid | ok | 0 | 0.15 | JS shell (15KB), curl_cffi/browser both 66KB |
| 102 | ghost.co.uk | hybrid | ok | 1 | 0.20 | search endpoint, browser captcha |
| 103 | rixo.co.uk | hybrid | ok | 0 | 0.15 | requests 80KB, browser captcha |
| 104 | reformation.com | hybrid | ok | 1 | 0.20 | thereformation.com/search, browser captcha |
| 105 | lipsy.co.uk | unknown | blocked | 0 | 0.05 | Redirects to next.co.uk, 403 all modes |
| 106 | sisterjane.com | hybrid | ok | 4 | 0.20 | production endpoint, search, browser captcha |
| 107 | vovoclothing.com | unknown | blocked | 0 | 0.00 | DNS failure - brand defunct |
| 108 | chiachilondon.com | unknown | blocked | 0 | 0.00 | DNS failure - brand defunct |
| 109 | self-portrait.com | hybrid | ok | 0 | 0.15 | requests 79KB, browser captcha |
| 110 | andotherstories.com | unknown | blocked | 0 | 0.00 | robots.txt blocks all crawling, H&M Group |

## New Failure Modes

- **robots.txt block** (andotherstories.com): H&M Group brand explicitly blocks all crawling via robots.txt. New failure category.
- **Redirect to parent** (lipsy.co.uk): Brand site redirects to parent platform (next.co.uk) which returns 403.

## Platform Patterns Confirmed

- **H&M Group**: andotherstories.com shares same group as arket, cos, weekday, monki
- **Next Group**: lipsy.co.uk redirects to next.co.uk (same platform as reiss.com)
