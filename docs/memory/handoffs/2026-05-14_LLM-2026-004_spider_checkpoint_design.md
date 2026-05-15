# Handoff: SCRAPLING-ABSORB-3 Spider / Checkpoint Design

Employee ID: `LLM-2026-004`
Display Name: Worker Delta
Date: 2026-05-14
Status: complete

## Assignment

`SCRAPLING-ABSORB-3 / Spider-Checkpoint Native Design Prep`

## Files Changed

- `docs/plans/2026-05-14_SCRAPLING_ABSORB_3_SPIDER_CHECKPOINT_DESIGN.md`
- `dev_logs/development/2026-05-14_LLM-2026-004_spider_checkpoint_design.md`
- `docs/memory/handoffs/2026-05-14_LLM-2026-004_spider_checkpoint_design.md`

No production code was changed. I did not touch native static/native parser,
executor, or existing runner/frontier code.

## Scrapling Spider Capabilities Extracted

- priority queue with FIFO tie-breaker
- request fingerprint dedupe
- `dont_filter` escape hatch
- snapshot/restore queue state
- atomic checkpoint write pattern
- checkpoint interval and cleanup policy
- request method/body/header/cookie/meta/session identity
- callback-name serialization idea, adapted into CLM route names instead of
  Python callables
- crawl result and stats buckets
- paused/completed distinction
- allow/deny/domain/extension link filtering
- restricted CSS/XPath link discovery scopes
- robots cache, `can_fetch`, crawl-delay, and request-rate extraction

## CLM Native Classes / Files Recommended

Recommended new files:

```text
autonomous_crawler/runners/spider_models.py
autonomous_crawler/runners/spider_runner.py
autonomous_crawler/storage/checkpoint_store.py
autonomous_crawler/tools/link_discovery.py
autonomous_crawler/tools/robots_policy.py
autonomous_crawler/tools/sitemap_discovery.py
```

Recommended classes:

```text
CrawlRequestEnvelope
CrawlItemResult
SpiderRunSummary
CheckpointStore
SpiderRuntimeProcessor
SpiderBatchRunner
LinkDiscoveryRule
LinkDiscoveryHelper
RobotsDirectives
RobotsPolicyHelper
SitemapDiscoveryHelper
```

## Phase Plan

- Phase A: request/result/event models.
- Phase B: SQLite/JSON checkpoint store.
- Phase C: BatchRunner processor and pause/resume flow.
- Phase D: link, robots, and sitemap helpers.

## Test Recommendations

- pause/resume through `max_batches`
- retryable and permanent failure buckets
- checkpoint write failure leaves item failed
- request fingerprint determinism
- URL dedupe and `dont_filter`
- link allow/deny/domain/extension filtering
- robots allow/disallow and crawl-delay evidence
- 1k / 10k / 30k synthetic stress
- 600+ real ecommerce regression after profiles are stable

## Recommended Next Implementers

- LLM-2026-000: own Phase A boundaries and protocol merge decisions.
- LLM-2026-001: implement request/result/event model conversions and tests.
- LLM-2026-002: implement CheckpointStore and parity QA.
- Dedicated runner worker or supervisor: implement Phase C BatchRunner processor
  after Phase A/B are accepted.
- LLM-2026-004: update docs and acceptance checklists after implementation.

## Verification

Required command:

```text
python -m compileall autonomous_crawler
```

Result: completed successfully.
