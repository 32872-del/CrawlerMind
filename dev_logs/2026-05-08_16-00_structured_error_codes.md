# 2026-05-08 16:00 - Structured Error Codes

## Goal

Design and implement first-version structured error codes without major
refactoring. Add machine-readable `error_code` alongside human-readable
messages.

Employee: LLM-2026-001 / Worker Alpha
Project Role: ROLE-API / ROLE-LLM-INTERFACE

## Changes

### New files

- `autonomous_crawler/errors.py`:
  - 11 error code string constants: `LLM_CONFIG_INVALID`,
    `LLM_PROVIDER_UNREACHABLE`, `LLM_RESPONSE_INVALID`,
    `FETCH_UNSUPPORTED_SCHEME`, `FETCH_HTTP_ERROR`, `BROWSER_RENDER_FAILED`,
    `EXTRACTION_EMPTY`, `SELECTOR_INVALID`, `VALIDATION_FAILED`,
    `ANTI_BOT_BLOCKED`, `RECON_FAILED`
  - `classify_llm_error(exc)` — maps exceptions to error codes using
    `isinstance` checks and `LLMResponseError.error_code` attribute
  - `format_error_entry(code, message, **details)` — builds `[CODE] message`
    formatted strings for error_log

- `autonomous_crawler/tests/test_error_codes.py`:
  - 23 tests across 7 test classes covering all error code paths

### Modified files

- `autonomous_crawler/llm/openai_compatible.py`:
  - `LLMResponseError` now accepts optional `error_code` keyword argument
  - Transport-level `httpx.HTTPError` raises tagged with
    `error_code=LLM_PROVIDER_UNREACHABLE`
  - Added import of `LLM_PROVIDER_UNREACHABLE` from `..errors`

- `autonomous_crawler/agents/executor.py`:
  - 4 failure paths now return `error_code` field:
    - fnspider failure → `FETCH_HTTP_ERROR`
    - browser failure → `BROWSER_RENDER_FAILED`
    - unsupported scheme → `FETCH_UNSUPPORTED_SCHEME`
    - HTTP error → `FETCH_HTTP_ERROR`
  - error_log entries use `format_error_entry()` for `[CODE] message` format

- `autonomous_crawler/agents/validator.py`:
  - Failed validation returns `error_code`:
    - No items extracted → `EXTRACTION_EMPTY`
    - Other validation failures → `VALIDATION_FAILED`
  - Successful/retrying results do not set error_code

- `autonomous_crawler/agents/recon.py`:
  - Recon fetch failure returns `error_code`:
    - "unsupported scheme" in error → `FETCH_UNSUPPORTED_SCHEME`
    - Otherwise → `FETCH_HTTP_ERROR`
  - error_log entries use `format_error_entry()` format

- `autonomous_crawler/agents/planner.py`:
  - LLM advisor exception handler now classifies error with
    `classify_llm_error(exc)` and includes code prefix in `llm_errors` entries

- `autonomous_crawler/agents/strategy.py`:
  - Same classification pattern as planner

- `autonomous_crawler/api/app.py`:
  - `CrawlResponse` model gains optional `error_code` field
  - `_new_job_record` includes `error_code` field
  - `_background_crawl` stores `error_code` from final state in job registry
  - `get_crawl` endpoint returns `error_code` from job registry
  - `POST /crawl` returns `error_code: None` in initial response
  - LLM config validation error now returns structured
    `{"error_code": "LLM_CONFIG_INVALID", "message": "..."}` instead of plain
    string

- `autonomous_crawler/tests/test_api_mvp.py`:
  - Updated 2 LLM config validation tests to assert on structured error detail
    dict instead of plain string

### Not modified

- `autonomous_crawler/workflows/crawl_graph.py` — no changes needed; error
  codes flow through state dict automatically
- `autonomous_crawler/storage/result_store.py` — no changes needed; entire
  state dict is serialized as JSON, so `error_code` persists automatically
- agents/base.py, tools/, engines/, docs/team/, docs/decisions/

## Tests

```text
python -m unittest autonomous_crawler.tests.test_error_codes -v
Ran 23 tests in 0.533s OK

python -m unittest discover -s autonomous_crawler/tests
Ran 215 tests in 18.036s OK (skipped=3)

python -m compileall autonomous_crawler run_skeleton.py run_baidu_hot_test.py run_results.py run_simple.py
OK
```

## Design Decisions

1. **String constants, not Enum**: Error codes are plain `str` constants for
   simplicity and JSON serialization. No Enum overhead.

2. **Additive, non-breaking**: `error_code` is a new optional field in state
   dicts. Existing `messages` and `error_log` human-readable content is
   preserved unchanged. The `[CODE]` prefix in error_log entries is additive.

3. **LLM error classification via exception attribute**: `LLMResponseError`
   gains an optional `error_code` attribute. Transport-level httpx errors are
   tagged at raise time. Agent nodes use `classify_llm_error()` to map
   exceptions to codes without modifying their control flow.

4. **Terminal error code in state**: The `error_code` field in the final state
   represents the terminal error that caused workflow failure. LLM errors are
   non-fatal (deterministic fallback), so they are recorded in `llm_errors`
   with code prefixes rather than as a top-level `error_code`.

5. **API structured error detail**: `POST /crawl` validation errors now return
   `{"error_code": "...", "message": "..."}` instead of a plain string. This
   is a minor API contract change for the error path only.

## Known Open Issues

- `ANTI_BOT_BLOCKED`, `SELECTOR_INVALID`, and `RECON_FAILED` codes are defined
  but not yet used in any failure path. Anti-bot detection does not currently
  trigger a failure; selector validation does not exist yet.
- No error code for fnspider-specific failures (uses `FETCH_HTTP_ERROR` as
  general fallback).

## Result

All 10 priority error codes are defined. 7 of 10 are actively used in failure
paths. 3 are reserved for future use. 23 focused tests. 215 total tests pass.
