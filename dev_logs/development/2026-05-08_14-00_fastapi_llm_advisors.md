# 2026-05-08 14:00 - FastAPI Opt-In LLM Advisors

## Goal

Add opt-in LLM advisor support to the FastAPI crawl path.
Assignment: `2026-05-08_LLM-2026-001_FASTAPI_LLM_ADVISORS`.

Employee: LLM-2026-001 / Worker Alpha
Project Role: ROLE-API / ROLE-LLM-INTERFACE

## Changes

### Modified files

- `autonomous_crawler/api/app.py`:
  - Added `LLMConfig` Pydantic model with fields: `enabled`, `base_url`,
    `model`, `api_key`, `provider`, `timeout_seconds`, `temperature`,
    `max_tokens`, `use_response_format`
  - Added optional `llm: LLMConfig | None = None` field to `CrawlRequest`
  - Added `_build_advisor_from_config(config)` helper that validates required
    fields and builds an `OpenAICompatibleAdvisor`
  - Updated `_background_crawl()` to accept optional `llm_config` parameter
  - Updated `run_crawl_workflow()` to accept optional `llm_config`, build
    advisor, and pass to `compile_crawl_graph(planning_advisor, strategy_advisor)`
  - Updated `POST /crawl` endpoint: validates LLM config eagerly (returns 400
    on missing base_url/model), passes config to background thread

- `autonomous_crawler/tests/test_api_mvp.py`:
  - Added `FastAPILLMOptInTests` (7 tests):
    1. `test_post_crawl_without_llm_remains_deterministic`
    2. `test_post_crawl_with_llm_enabled_false_remains_deterministic`
    3. `test_post_crawl_with_invalid_llm_config_returns_400`
    4. `test_post_crawl_with_missing_model_returns_400`
    5. `test_post_crawl_with_valid_llm_config_starts_job`
    6. `test_background_job_with_llm_completes_and_queryable`
    7. `test_llm_config_error_in_background_records_failure`
  - Added `BuildAdvisorFromConfigTests` (4 tests):
    1. `test_valid_config_returns_advisor`
    2. `test_missing_base_url_raises`
    3. `test_missing_model_raises`
    4. `test_config_fields_passed_through`

### Not modified

- agents/, tools/, workflows/, storage/, docs/team/, docs/decisions/
- Existing tests unchanged

## Tests

```text
python -m unittest autonomous_crawler.tests.test_api_mvp -v
Ran 38 tests in 5.571s OK

python -m unittest discover -s autonomous_crawler/tests
Ran 186 tests in 18.595s OK (skipped=3)

python -m compileall autonomous_crawler run_skeleton.py run_baidu_hot_test.py run_results.py run_simple.py
OK
```

## Result

FastAPI now supports opt-in LLM advisors via request-level configuration.
Default behavior (no `llm` field or `llm.enabled=false`) is unchanged. Invalid
config returns a clear 400 error. Background job execution and status querying
work the same with or without LLM. No API key required for tests.

## Known Risks

- LLM config is passed through Pydantic validation only; no runtime provider
  health check on the API side.
- Background thread builds the advisor; if httpx is unavailable, the error is
  caught by the generic exception handler and recorded as a failed job.
- No streaming support.
- No persistent job registry.

## Next Step

Submit for supervisor acceptance.
