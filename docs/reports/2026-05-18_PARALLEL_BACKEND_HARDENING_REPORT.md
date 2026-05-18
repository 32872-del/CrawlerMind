# 2026-05-18 Parallel Backend Hardening Report

## What Changed

This round moved CLM from reporting collection losses toward improving backend
throughput and valid-record yield.

External reference:

```text
F:\datawork\spider
```

Absorbed backend patterns:

- staged crawl flow: list/category -> product/detail -> variant/final record
- per-stage de-duplication
- multi-threaded product collection
- progress/failure counters
- good-page-only cache
- bad HTML/challenge detection
- URL normalization
- product image de-noising and stable media keys
- hydration JSON extraction helper
- category path -> level 1/2/3 normalization
- concurrent multi-site execution with a hard limit of 5 sites

## New CLM Modules

```text
autonomous_crawler/runners/threaded_stage_runner.py
autonomous_crawler/runners/multi_site_runner.py
autonomous_crawler/tools/site_hardening.py
```

The dual ecommerce training script now supports:

```text
--workers <N>       # concurrent detail workers per site
--max-sites <N>     # concurrent sites, capped at 5
--catalog-cache-dir # reusable catalog/page cache
--refresh-catalog   # force catalog refresh
```

The reusable product entrypoints now expose the same scale controls:

```text
python clm.py profile-run --profile <profile.json> --workers <N>
python clm.py multi-profile-run --jobs <jobs.json> --max-sites 5 --workers <N>
POST /profile-runs              # body.item_workers
POST /profile-runs/batch        # body.max_sites <= 5, body.default_item_workers
GET  /profile-runs/batch/{id}
```

`BatchRunner` now supports batch-internal concurrent item processing through
`item_workers`. Runtime/network work runs concurrently, while frontier updates
and product checkpoint writes remain serialized to keep SQLite stable.

`NativeFetchRuntime(reuse_httpx_client=True)` keeps an HTTP connection pool for
high-throughput profile runs and closes it explicitly after CLI/API jobs.

## Performance Evidence

Latest multi-site run:

```text
dev_logs/training/2026-05-18_dual_ecommerce_multisite_5min_report.json
dev_logs/training/2026-05-18_dual_ecommerce_multisite_5min.xlsx
```

Configuration:

```text
per-site: 100
workers per site: 16
max concurrent sites: 5
targets: Sephora PL + uvex PL
```

Result:

| Site | Valid Records | Attempts | Acceptance Rate | Records/Minute |
|---|---:|---:|---:|---:|
| Sephora PL | 100 | 142 | 70.42% | 200.28 |
| uvex PL | 100 | 100 | 100.00% | 200.28 |

Multi-site runner:

```text
total_sites: 2
ok_sites: 2
failed_sites: 0
elapsed_seconds: 29.953
```

## Current Meaning

The backend now supports two layers of concurrency:

1. Site-level concurrency: up to 5 websites at once.
2. Site-internal concurrency: configurable product/detail workers per site.
3. Runtime-level HTTP connection reuse for threaded static/API profile runs.

Compared with the previous serial training loop, uvex improved from roughly
50 records/minute to roughly 200 records/minute in the multi-site run. Sephora
improved from roughly 10 records/minute in the first quality-gated run to
roughly 200 records/minute for valid accepted rows in this short cached run,
but its valid-record ratio still needs work because many sitemap candidates
resolve to invalid SFCC detail fragments.

## Remaining Backend Work

The next success-rate improvements should focus on:

- persistent multi-site scheduling across process restarts
- adaptive async scheduling for very large frontier backlogs
- adaptive concurrency per domain based on failure/latency
- domain-level invalid URL blacklists and candidate scoring
- Sephora-specific product candidate discovery from category/API evidence
  rather than relying too heavily on noisy sitemap URLs
- deeper integration between staged list/detail/variant callbacks and generated
  `SiteProfile` flows
