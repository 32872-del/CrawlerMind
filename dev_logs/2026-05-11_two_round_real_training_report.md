# 2026-05-11 Two-Round Real Training Report

Generated at: 2026-05-11T07:32:30.583811+00:00
JSON: `dev_logs\2026-05-11_two_round_real_training.json`
Excel: `dev_logs\2026-05-11_two_round_real_training.xlsx`

## Summary

- total rows: 850

| source | rows | ok | partial | dup_urls | with_price | with_description | with_images | with_category_1 | with_colors | with_sizes |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| balticbhp | 200 | 200 | 0 | 0 | 200 | 200 | 200 | 200 | 144 | 5 |
| dummyjson | 50 | 50 | 0 | 0 | 50 | 50 | 50 | 50 | 0 | 0 |
| github_cpython_issues | 50 | 50 | 0 | 0 | 0 | 49 | 0 | 50 | 0 | 0 |
| hn_algolia | 50 | 50 | 0 | 0 | 0 | 50 | 0 | 50 | 0 | 0 |
| jsonplaceholder | 50 | 50 | 0 | 0 | 0 | 50 | 0 | 50 | 0 | 0 |
| quotes_to_scrape | 50 | 50 | 0 | 45 | 0 | 50 | 0 | 50 | 0 | 0 |
| tatuum | 200 | 200 | 0 | 0 | 200 | 200 | 200 | 200 | 0 | 158 |
| thesting | 200 | 200 | 0 | 0 | 200 | 200 | 200 | 200 | 200 | 200 |

## Notes

- Round 1 uses five public training targets and collects at least 50 records per source.
- Round 2 uses public product sitemap/detail pages for the three requested ecommerce sites.
- Round 2 target was 200 records per ecommerce site; Tatuum, The Sting, and BalticBHP each reached 200.
- BalticBHP exposed a real-world fetch pitfall: one mixed Accept-Language header returned HTTP 200 with an empty body. The script falls back to a normal browser HTML header and curl_cffi for empty public HTML responses.
- Tatuum and The Sting required cleaner size parsing from embedded option config / visible radio size values; generic UI button text is no longer accepted as a size.
- Known gap: Tatuum product pages do expose color information, but this run did not extract it reliably. Treat this as a profile/variant extraction follow-up rather than filling synthetic values.
- The run does not bypass login, CAPTCHA, Cloudflare, or access controls.
- Site-specific findings should become future profiles/fixtures, not core crawler rules.
