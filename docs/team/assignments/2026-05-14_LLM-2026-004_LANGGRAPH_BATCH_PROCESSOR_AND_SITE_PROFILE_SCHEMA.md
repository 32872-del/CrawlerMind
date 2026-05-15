# Assignment: LangGraph Batch Processor And Site Profile Schema

Date: 2026-05-14

Employee: `LLM-2026-004`

Priority: P0

Track: `SCRAPLING-ABSORB-3G / CAP-3.1 / CAP-3.6`

## Mission

Connect the agent workflow to the long-running spider system. CLM should be
able to run a LangGraph crawl as a `BatchRunner` processor and preserve reusable
site/crawl profile data for selectors, API hints, pagination, access config,
and quality overrides.

## Ownership

Primary files:

- `autonomous_crawler/runners/`
- `autonomous_crawler/workflows/crawl_graph.py`
- `autonomous_crawler/storage/checkpoint_store.py`
- `autonomous_crawler/tests/test_spider_runner.py`
- new tests and docs as needed

Avoid editing browser/proxy low-level runtime modules unless a small interface
hook is necessary.

## Requirements

1. Add a processor adapter that can run the existing LangGraph workflow through
   `BatchRunner` / `SpiderRuntimeProcessor` contracts.
2. Define a minimal CLM site profile schema for:
   selectors, API hints, pagination hints, access config, rate limits, quality
   expectations, and training notes.
3. Persist or load the profile through explicit paths; do not hide it in global
   state.
4. Add deterministic tests proving a profile-driven crawl can pause/resume.
5. Update dev log and handoff.

## Acceptance Checks

Run:

```text
python -m unittest autonomous_crawler.tests.test_spider_runner -v
python -m unittest discover -s autonomous_crawler/tests
python -m compileall autonomous_crawler
```

Report:

- adapter design
- profile schema fields
- pause/resume evidence
- known integration gaps with real ecommerce runs
