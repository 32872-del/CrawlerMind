# Handoff: FastAPI Opt-In LLM Advisors

Employee: LLM-2026-001
Date: 2026-05-08
Assignment: `2026-05-08_LLM-2026-001_FASTAPI_LLM_ADVISORS`

## What Was Done

Added opt-in LLM advisor support to the FastAPI crawl path:

- `LLMConfig` Pydantic model for request-level LLM configuration.
- `CrawlRequest.llm` optional field (default `None`).
- `_build_advisor_from_config()` validates required fields and builds
  `OpenAICompatibleAdvisor`.
- `POST /crawl` validates LLM config eagerly, returns 400 on missing
  `base_url` or `model`.
- `run_crawl_workflow()` passes advisor to `compile_crawl_graph()`.
- Background job completes and stores `llm_enabled`, `llm_decisions`,
  `llm_errors` in persisted state.
- 11 new tests: 7 endpoint-level, 4 unit-level.

## Files Changed

- `autonomous_crawler/api/app.py` - LLMConfig model, advisor construction,
  workflow wiring
- `autonomous_crawler/tests/test_api_mvp.py` - FastAPILLMOptInTests,
  BuildAdvisorFromConfigTests

## Test Status

38 API tests pass. Full suite: 186 tests (3 skipped). Compile check: OK.

## What Is NOT Changed

- No changes to agents/, tools/, workflows/, storage/.
- No streaming, multi-provider registry, Redis, or persistent job registry.
- Existing deterministic tests unchanged.

## Known Open Issues

- No runtime provider health check at API level.
- httpx unavailability would be caught as generic background failure.

## Environment

- No new environment variables. LLM config is per-request.
