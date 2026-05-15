# Handoff: Sitemap / Robots Long-Run Integration

Employee ID: `LLM-2026-004`
Display Name: Worker Delta
Date: 2026-05-14
Status: complete

## Assignment

`docs/team/assignments/2026-05-14_LLM-2026-004_SITEMAP_ROBOTS_LONGRUN_INTEGRATION.md`

## Files Changed

- `autonomous_crawler/tools/link_discovery.py`
- `autonomous_crawler/tools/rate_limit_policy.py`
- `autonomous_crawler/runners/spider_runner.py`
- `autonomous_crawler/tests/test_link_discovery.py`
- `autonomous_crawler/tests/test_robots_policy.py`
- `autonomous_crawler/tests/test_spider_runner.py`
- `dev_logs/development/2026-05-14_LLM-2026-004_sitemap_robots_longrun.md`
- `docs/memory/handoffs/2026-05-14_LLM-2026-004_sitemap_robots_longrun.md`

## What Changed

- Added `SitemapDiscoveryRule`, `SitemapDiscoveryResult`, and
  `SitemapDiscoveryHelper`.
- Sitemap helper parses local XML text and supports:
  - sitemap index
  - URL set
  - malformed XML fallback event
  - strict same-domain filtering
  - deterministic `CrawlRequestEnvelope` output
- `RateLimitPolicy.decide()` now accepts optional robots directives and exposes:
  - `robots_crawl_delay_seconds`
  - `robots_request_rate`
  - `robots_source_url`
  - `robots_mode`
- `SpiderRuntimeProcessor` can optionally:
  - emit robots checked events
  - emit rate-limit checked events with robots metadata
  - skip robots-disallowed requests into `robots_disallowed` failure bucket
  - parse sitemap responses and enqueue discovered sitemap/page URLs through
    the existing BatchRunner discovery path

## Tests Added

- URL set sitemap parsing with same-domain filtering.
- Sitemap index parsing with nested sitemap URLs.
- Malformed sitemap XML fallback.
- Robots directives feeding rate-limit metadata.
- Sitemap-seeded frontier pause/resume smoke using local fixtures.
- Processor-visible robots/rate-limit runtime events.

## Verification

Focused tests:

```text
python -m unittest autonomous_crawler.tests.test_link_discovery autonomous_crawler.tests.test_robots_policy autonomous_crawler.tests.test_spider_runner -v
Ran 22 tests
OK
```

Required compile:

```text
python -m compileall autonomous_crawler
```

Result: completed successfully.

## Notes

- I did not add site-specific ecommerce or target rules.
- Sitemap fetching is intentionally not embedded in the helper; runtime fetches
  XML and the helper parses it.
- The current BatchRunner discovery interface still stores one
  `discovered_kind` and `discovered_priority` per result. Sitemap tests use
  homogeneous discovered request kinds. A future runner enhancement should
  preserve per-request payload metadata when discovered requests have mixed
  kinds or priorities.
