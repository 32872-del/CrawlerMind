# Handoff: Structured Error Codes

Employee: LLM-2026-001
Date: 2026-05-08
Assignment: `2026-05-08_LLM-2026-001_STRUCTURED_ERROR_CODES`

## What Was Done

Implemented first-version structured error codes for the autonomous crawler:

- New `autonomous_crawler/errors.py` module with 11 error code constants,
  `classify_llm_error()` helper, and `format_error_entry()` formatter.
- `LLMResponseError` gains optional `error_code` attribute for precise
  classification of transport vs. response errors.
- Executor, validator, recon, planner, and strategy agents now set `error_code`
  on failure paths.
- API layer exposes `error_code` in job registry, GET /crawl/{id} responses,
  and LLM config validation errors.
- 23 focused tests in `test_error_codes.py`.

## Files Changed

- `autonomous_crawler/errors.py` — new module
- `autonomous_crawler/llm/openai_compatible.py` — LLMResponseError.error_code,
  transport error tagging
- `autonomous_crawler/agents/executor.py` — 4 failure paths with error_code
- `autonomous_crawler/agents/validator.py` — EXTRACTION_EMPTY / VALIDATION_FAILED
- `autonomous_crawler/agents/recon.py` — FETCH_UNSUPPORTED_SCHEME / FETCH_HTTP_ERROR
- `autonomous_crawler/agents/planner.py` — classify_llm_error in except block
- `autonomous_crawler/agents/strategy.py` — classify_llm_error in except block
- `autonomous_crawler/api/app.py` — CrawlResponse.error_code, job registry,
  structured error detail
- `autonomous_crawler/tests/test_error_codes.py` — new test file (23 tests)
- `autonomous_crawler/tests/test_api_mvp.py` — updated 2 assertions for
  structured error detail

## Test Status

215 tests pass (3 skipped). Compile check: OK.

## What Is NOT Changed

- No changes to workflows/crawl_graph.py, storage/, tools/, engines/.
- No changes to existing messages or error_log human-readable content.
- `ANTI_BOT_BLOCKED`, `SELECTOR_INVALID`, `RECON_FAILED` are defined but not
  yet used in any failure path.

## Known Open Issues

- Anti-bot detection does not trigger a failure yet (code is reserved).
- Selector validation does not exist yet (code is reserved).
- No fnspider-specific error code (uses FETCH_HTTP_ERROR as fallback).

## Environment

- No new environment variables.
