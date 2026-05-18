# 2026-05-18 Dual Ecommerce 10-Minute Training Report

## Purpose

This supervised training run tested the new coverage and quality diagnostics on
two real ecommerce targets:

- `https://www.sephora.pl/`
- `https://uvex.com.pl/`

The question was not whether CLM can eventually collect 2,000 rows. The question
was: within a short 10-minute budget, how many valid records can CLM collect,
what is the success rate, and where is time being spent.

## Artifacts

```text
dev_logs/training/2026-05-18_dual_ecommerce_10min_report.json
dev_logs/training/2026-05-18_dual_ecommerce_10min.xlsx
dev_logs/runtime/dual_ecommerce_10min_2026_05_18_checkpoint.json
```

## Result Summary

| Site | Valid Records | Attempts | Acceptance Rate | Records/Minute | Main Loss |
|---|---:|---:|---:|---:|---|
| Sephora PL | 121 | 232 | 52.16% | 10.26 | time budget/frontier pending + quality rejection |
| uvex PL | 340 | 340 | 100.00% | 50.98 | time budget/frontier pending |

Total valid records: `461`.

The run did not meet the requested 2,000 records per site. That is expected for
this short training budget, but the diagnostics now explain why.

## Time Analysis

Sephora:

- catalog discovery: `6.958s`
- fetch/parse loop: `293.274s`
- accepted: `121`
- rejected by quality gate: `111`

uvex:

- catalog discovery: `100.038s`
- fetch/parse loop: `289.685s`
- accepted: `340`
- rejected by quality gate: `0`

The total wall time was higher than exactly 10 minutes because the script's
per-site budget started after catalog discovery. This revealed an important
backend issue: catalog discovery itself must be measured and budgeted. Future
runs should either include catalog discovery in the wall-clock budget or cache
catalog discovery between runs.

## Sephora Diagnosis

Sephora inventory discovery worked well:

- product sitemap URLs discovered: `24,642`
- category URLs discovered: `669`

The bottleneck was not discovery. The bottleneck was valid-product yield:

- attempted: `232`
- valid accepted: `121`
- quality rejected: `111`
- invalid page rejected: `111`

Repeated rejection reasons:

```text
invalid_title: 111
unparsable_price: 111
missing_body: 111
empty_images: 111
missing_handle: 111
```

Interpretation:

The SFCC `Product-Detail?pid=...` endpoint can return valid product fragments,
but many numeric PID candidates from sitemap URLs resolve to not-found shells.
Those pages used to be incorrectly accepted. They are now rejected by the
quality gate.

Next fixes:

- Improve Sephora PID extraction and candidate filtering before detail fetch.
- Add replacement queue so rejected records do not consume the final target.
- Prefer P-prefixed product IDs and validate endpoint content before parsing.
- Add SFCC-specific API/product availability hints into profile evidence, not
  into core runtime.

## uvex Diagnosis

uvex quality was strong:

- attempted: `340`
- accepted: `340`
- quality rejected: `0`
- acceptance rate: `100%`

The bottleneck was throughput and catalog discovery overhead:

- catalog discovery alone took about `100s`
- valid product fetch/parse averaged about `0.85s` per product
- discovered active product URLs: `919`

Interpretation:

uvex does not currently look blocked. The current implementation is too
sequential: category crawling and product detail requests are single-threaded.
The site likely needs parallel fetch, cached catalog discovery, and resumable
frontier scheduling rather than anti-bot work as the next step.

Next fixes:

- Cache category/product URL discovery.
- Use native async fetch pool for detail pages.
- Resume from pending frontier rather than rescanning category pages every run.
- Mark true catalog exhaustion if all 919 active products are collected and the
  user target is higher than site inventory.

## Backend Changes Made

New generic coverage diagnostics:

```text
autonomous_crawler/tools/coverage_report.py
```

New report schema:

```text
coverage-report/v1
```

Coverage stages:

- inventory
- discovery
- schedule
- access
- render
- parse
- quality
- export

Product quality was strengthened:

- invalid title pattern support
- required price/image/description/category can be hard errors
- noise-only images can fail when images are required

The dual ecommerce training script now:

- rejects invalid product records before accepting them
- cleans noisy product images
- records quality issue counts
- records timing buckets
- includes coverage reports per site
- supports time-budget arguments

## Next Development Priority

P0 should be throughput and recovery, not more one-off site rules:

1. Cache catalog discovery and reuse it across resumes.
2. Add async/parallel product detail fetching for static product pages.
3. Add replacement queues so failed/invalid records are replenished until the
   valid target is reached.
4. Move the real-site script closer to `ProfileLongRunExecutor` so quality,
   checkpoint, coverage, and report behavior are shared by all long runs.
5. Add strict wall-clock budgeting that includes catalog discovery.

