# Daily Report - 2026-05-11

## Theme

Today focused on turning ecommerce crawl lessons into durable project
foundation work instead of hard-coding rules for individual sites. Later in the
day, the project also shifted toward lower-friction first use through CLM Easy
Mode.

## Completed

- Accepted the worker product storage foundation.
- Accepted the worker product quality foundation after supervisor cleanup.
- Added clean product quality tests for price parsing, partial records, blocked
  records, image quality, dedupe warnings, and `ProductRecord` inputs.
- Rewrote the ecommerce workflow document in readable UTF-8 Chinese/English
  friendly structure after detecting the old file was mojibake.
- Added a long-running ecommerce runbook.
- Recorded supervisor acceptance for product store, product quality, and
  long-running ecommerce operation policy.
- Added generic resumable `BatchRunner` MVP for long-running work. This keeps
  queue/checkpoint mechanics generic and leaves domain extraction in processors
  or profiles.
- Added `run_batch_runner_smoke.py`, a local no-network smoke that processes 25
  synthetic records in two passes to prove pause/resume behavior.
- Ran a two-round real-site training batch:
  - round 1: five public targets with 50 records each
  - round 2: Tatuum, The Sting, and BalticBHP with 200 product records each
  - total: 850 exported rows
- Partitioned `dev_logs/` into development, audits, training, smoke, stress,
  and runtime sections.
- Added `clm.py` Easy Mode CLI:
  - `python clm.py init`
  - `python clm.py check`
  - `python clm.py crawl ...`
  - `python clm.py smoke --kind runner`
  - `python clm.py train`
- Updated README and Windows/Linux/macOS/Chinese quick starts so `clm.py` is
  the primary user path.
- Accepted Easy Mode quick-start docs and Easy Mode docs audit.
- Conditionally accepted Easy Mode CLI tests because the worker handoff claims
  59 tests, while the current repository file contains 7 tests.

## Current Product State

Crawler-Mind now has a stronger ecommerce base:

- generic `ProductRecord`
- SQLite `ProductStore`
- category-aware dedupe
- product quality validation
- local 30,000-record stress evidence
- generic batch runner with frontier-backed resume
- real-site training evidence at 850 rows
- clear rule that named-site collection logic belongs in profiles/training
  artifacts, not in the core engine

This supports the next phase: real ecommerce training with checkpointed storage
and controlled expansion from 5-product samples to larger pilot runs.

Crawler-Mind also now has a clearer first-use path. A new user can install
dependencies, run `python clm.py init`, run `python clm.py check`, and run a
mock crawl with a JSON or Excel output file without learning the older
development scripts first.

## Main Limitation

- The production loop exists as a generic runner, but it is not yet wired to
  the full LangGraph workflow or real site/crawl profiles.
- Easy Mode is useful but still thin: it wraps existing behavior and needs more
  polished error handling, richer `check` output, and stronger tests before a
  public release.

## Next Recommended Work

1. Resolve Easy Mode CLI test inconsistency: either correct the worker handoff
   to match the current 7 tests or restore/add the intended missing cases.
2. Wrap the LangGraph crawl workflow as a `BatchRunner` processor.
3. Convert the 2026-05-09 ecommerce samples into deterministic fixtures/tests.
4. Add runtime site/crawl profile files for selectors, API hints, pagination,
   and quality overrides.
5. Run a 100-product pilot on an approved ecommerce target before attempting a
   larger real run.
6. Add progress reporting that can later feed FastAPI and the planned frontend.
7. Convert the real-site extraction differences discovered today into profile
   fixtures: sitemap product discovery, embedded option sizes, visible radio
   sizes, empty-200 fetch fallback, and Tatuum color extraction.
