# 2026-05-07 17:05 - OpenAI-Compatible LLM Adapter

## Goal

Add a broad OpenAI-compatible provider adapter so Crawler-Mind can run real
LLM-assisted Planner/Strategy experiments while preserving deterministic
default behavior.

## Changes

- Added `autonomous_crawler/llm/openai_compatible.py`:
  - `OpenAICompatibleConfig`
  - `OpenAICompatibleAdvisor`
  - `build_advisor_from_env()`
  - `LLMConfigurationError`
  - `LLMResponseError`
  - fenced JSON parsing support
- Updated `autonomous_crawler/llm/__init__.py` exports.
- Added `autonomous_crawler/tests/test_openai_compatible_llm.py` with
  fake-client tests using `httpx.MockTransport`.
- Rewrote `run_skeleton.py` as an ASCII-only CLI and added:
  - `--llm`
  - `--no-llm`
  - `CLM_LLM_ENABLED`
  - LLM decision summary output

## Environment Variables

```text
CLM_LLM_BASE_URL
CLM_LLM_MODEL
CLM_LLM_API_KEY
CLM_LLM_PROVIDER
CLM_LLM_TIMEOUT_SECONDS
CLM_LLM_TEMPERATURE
CLM_LLM_MAX_TOKENS
CLM_LLM_ENABLED
```

## Verification

```text
python -m unittest autonomous_crawler.tests.test_openai_compatible_llm -v
Ran 17 tests
OK
```

## Notes

The adapter is opt-in. Normal tests and deterministic crawls do not require an
API key or network access.
