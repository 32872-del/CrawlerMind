# Assignment: Sitemap, Robots Delay, And Long-Run Discovery Integration

Date: 2026-05-14

Employee: LLM-2026-004

Track: SCRAPLING-ABSORB-3F

## Goal

Continue native spider absorption by connecting sitemap discovery and robots
delay evidence into long-running crawl planning. This should strengthen CLM's
generic spider backend, not create site-specific crawl rules.

## Read First

- `docs/plans/2026-05-14_SCRAPLING_ABSORPTION_RECORD.md`
- `docs/team/acceptance/2026-05-14_native_link_robots_helpers_ACCEPTED.md`
- `docs/team/acceptance/2026-05-14_native_spider_pause_resume_smoke_ACCEPTED.md`
- `autonomous_crawler/tools/link_discovery.py`
- `autonomous_crawler/tools/robots_policy.py`
- `autonomous_crawler/tools/rate_limit_policy.py`
- `autonomous_crawler/runners/spider_runner.py`
- `autonomous_crawler/storage/frontier.py`
- `autonomous_crawler/tests/test_link_discovery.py`
- `autonomous_crawler/tests/test_robots_policy.py`
- `autonomous_crawler/tests/test_spider_runner.py`

## Write Scope

- `autonomous_crawler/tools/link_discovery.py`
- `autonomous_crawler/tools/robots_policy.py`
- `autonomous_crawler/tools/rate_limit_policy.py`
- `autonomous_crawler/runners/spider_runner.py`
- `autonomous_crawler/tests/test_link_discovery.py`
- `autonomous_crawler/tests/test_robots_policy.py`
- `autonomous_crawler/tests/test_spider_runner.py`
- optional new test:
  `autonomous_crawler/tests/test_sitemap_discovery.py`
- `dev_logs/development/2026-05-14_LLM-2026-004_sitemap_robots_longrun.md`
- `docs/memory/handoffs/2026-05-14_LLM-2026-004_sitemap_robots_longrun.md`

## Required Work

1. Add a CLM-native sitemap parser/discovery helper for deterministic local XML
   fixtures:
   - sitemap index
   - urlset
   - malformed XML fallback
   - same-domain filtering
2. Connect robots crawl-delay/request-rate evidence to the existing
   rate-limit/domain policy layer as structured metadata.
3. Let `SpiderRuntimeProcessor` or surrounding runner enqueue discovered
   sitemap URLs without losing checkpoint/resume behavior.
4. Add tests proving sitemap-seeded frontier + pause/resume still works.
5. Keep the helper generic. No hard-coded ecommerce/site selectors.

## Acceptance

- Sitemap parsing tests pass.
- Robots delay metadata is visible to runner/rate-limit policy.
- Spider pause/resume tests still pass.
- No network dependency required in tests.
- No site-specific rules are introduced.
