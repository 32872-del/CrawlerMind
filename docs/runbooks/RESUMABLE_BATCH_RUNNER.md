# Resumable Batch Runner

This runbook describes CLM's generic long-running batch execution primitive.
It is not ecommerce-specific.

## Purpose

The batch runner exists to support any crawl domain that needs durable progress:

- ecommerce products
- ranking lists
- news/article discovery
- job postings
- company directories
- API-backed datasets

The runner owns execution mechanics only:

```text
frontier -> claim batch -> process item -> checkpoint records -> mark done/failed -> report progress
```

Domain-specific extraction remains outside the runner.

## Core Contracts

### Frontier

`URLFrontier` stores URLs and their status:

- `queued`
- `running`
- `done`
- `failed`

The runner claims bounded batches and uses persisted frontier state for resume.

### Processor

A processor is a callable that receives one frontier item and returns an
`ItemProcessResult`.

The processor decides how to fetch, extract, and normalize. It may be a simple
fixture processor, a workflow wrapper, an API replay worker, or a future
site-profile executor.

### Checkpoint

A checkpoint sink persists records produced by successful items.

Current adapter:

- `ProductRecordCheckpoint` -> `ProductStore`

Future adapters can store articles, jobs, ranking entries, or generic JSON rows.

## Current Implementation

Code:

- `autonomous_crawler/runners/batch_runner.py`
- `autonomous_crawler/tests/test_batch_runner.py`
- `run_batch_runner_smoke.py`

Supported behavior:

- empty frontier returns a zero summary
- bounded batch processing
- `max_batches` for partial runs and resume testing
- success -> `mark_done`
- failure -> `mark_failed`
- retryable failure -> requeue
- processor exceptions are captured
- discovered URLs are inserted into the frontier
- checkpoint failure marks the item failed
- product checkpoint stores `ProductRecord` batches

## Local Smoke

```text
python run_batch_runner_smoke.py --items 25 --batch-size 5 --first-pass-batches 2
```

Expected behavior:

- first pass handles 10 items
- 15 items remain queued
- resume pass handles the remaining 15
- final frontier status is `done: 25`
- product checkpoint contains 25 records

The smoke writes a compact JSON summary to:

```text
dev_logs/smoke/2026-05-11_batch_runner_smoke.json
```

Do not commit large runtime databases or large exports.

## Boundaries

The runner must not contain:

- named-site selectors
- hard-coded API endpoints
- Cloudflare/CAPTCHA bypass logic
- login/session/cookie handling
- product-only assumptions in the core loop

Domain-specific behavior belongs in processors, profiles, fixtures, or
checkpoint adapters.

## Next Steps

1. Wrap the existing LangGraph crawl workflow as a processor.
2. Add a generic JSON checkpoint adapter.
3. Add progress events suitable for FastAPI and a future frontend.
4. Add a site/crawl profile layer for selectors, API hints, and pagination.
5. Run two supervised real-site training rounds using this runner.
