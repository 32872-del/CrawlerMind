# 2026-05-14 - Sitemap / Robots Long-Run Integration

Employee ID: `LLM-2026-004`

Assignment: `SCRAPLING-ABSORB-3F`

## Work Completed

- Added CLM-native sitemap parsing to `autonomous_crawler/tools/link_discovery.py`.
- Added deterministic sitemap coverage for:
  - `urlset`
  - `sitemapindex`
  - malformed XML fallback
  - strict same-domain filtering
- Connected robots crawl-delay/request-rate directives to
  `RateLimitPolicy.decide()` metadata.
- Added optional `robots_policy`, `rate_limit_policy`, `sitemap_helper`, and
  `sitemap_rule` integration to `SpiderRuntimeProcessor`.
- Added a pause/resume test proving sitemap-seeded frontier discovery survives
  two BatchRunner passes and checkpoint status changes.

## Boundaries

- No site-specific crawl rules were added.
- No network dependency was added to tests.
- Existing checkpoint/pause/resume behavior remains intact.
- Sitemap parsing is local XML text parsing only; fetching remains the caller's
  runtime responsibility.

## Verification

Focused:

```text
python -m unittest autonomous_crawler.tests.test_link_discovery autonomous_crawler.tests.test_robots_policy autonomous_crawler.tests.test_spider_runner -v
Ran 22 tests
OK
```

Compile:

```text
python -m compileall autonomous_crawler
```

Result: completed successfully.
