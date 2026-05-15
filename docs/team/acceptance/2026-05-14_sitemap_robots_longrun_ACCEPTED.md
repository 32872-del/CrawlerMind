# Acceptance: Sitemap Robots Long-Run Integration

Date: 2026-05-14

Employee: `LLM-2026-004`

Assignment: `SCRAPLING-ABSORB-3F`

Status: accepted

## Verdict

Accepted. Sitemap parsing, robots directives, and long-run processor metadata
now form a CLM-native spider capability that supports checkpointed discovery
without adding site-specific crawl rules.

## Accepted Evidence

- `SitemapDiscoveryHelper` parses `urlset`, `sitemapindex`, malformed XML
  fallback, and same-domain filtering.
- `RobotsPolicyHelper` exposes crawl-delay and request-rate metadata.
- `RateLimitPolicy.decide()` can consume robots-derived metadata.
- `SpiderRuntimeProcessor` accepts optional robots, rate-limit, sitemap helper,
  and sitemap rule components.
- Pause/resume smoke verifies sitemap-seeded frontier work survives across two
  BatchRunner passes and checkpoint state changes.

## Verification

```text
python -m unittest autonomous_crawler.tests.test_link_discovery autonomous_crawler.tests.test_robots_policy autonomous_crawler.tests.test_spider_runner -v
python -m unittest discover -s autonomous_crawler/tests
```

Latest supervisor verification:

```text
Ran 1670 tests in 81.984s
OK (skipped=5)
```

## Follow-Up

- Add real sitemap training cases.
- Persist sitemap/robots summary metrics into run reports.
- Combine sitemap discovery with site profile generation.
