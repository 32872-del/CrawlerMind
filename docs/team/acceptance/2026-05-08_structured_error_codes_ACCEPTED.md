# 2026-05-08 Structured Error Codes - ACCEPTED

## Assignment

`2026-05-08_LLM-2026-001_STRUCTURED_ERROR_CODES`

## Assignee

Employee ID: `LLM-2026-001`

Project Role: `ROLE-API / ROLE-LLM-INTERFACE`

## Scope Reviewed

Reviewed:

```text
autonomous_crawler/errors.py
autonomous_crawler/llm/openai_compatible.py
autonomous_crawler/agents/executor.py
autonomous_crawler/agents/validator.py
autonomous_crawler/agents/recon.py
autonomous_crawler/agents/planner.py
autonomous_crawler/agents/strategy.py
autonomous_crawler/api/app.py
autonomous_crawler/tests/test_error_codes.py
autonomous_crawler/tests/test_api_mvp.py
dev_logs/development/2026-05-08_16-00_structured_error_codes.md
docs/memory/handoffs/2026-05-08_LLM-2026-001_structured_error_codes.md
```

## Verification

```text
python -m unittest autonomous_crawler.tests.test_error_codes autonomous_crawler.tests.test_api_mvp -v
Ran 61 tests OK

python -m unittest discover -s autonomous_crawler/tests
Ran 215 tests OK (skipped=3)

python -m compileall autonomous_crawler run_skeleton.py run_baidu_hot_test.py run_results.py run_simple.py
OK
```

## Accepted Changes

- Added `autonomous_crawler/errors.py` with first-version machine-readable error
  code constants and helper functions.
- Added structured failure codes across executor, validator, recon, planner,
  strategy, and API job responses.
- Added LLM transport/response error classification through
  `LLMResponseError.error_code`.
- API LLM config validation now returns structured error details.
- Added 23 focused error-code tests.
- Preserved deterministic fallback behavior and existing human-readable logs.

## Risks / Follow-Up

- `ANTI_BOT_BLOCKED`, `SELECTOR_INVALID`, and `RECON_FAILED` are reserved but
  not fully active yet.
- Fnspider-specific failures currently map to `FETCH_HTTP_ERROR`; a narrower
  code can be added after more real site samples.
- API consumers must now expect structured detail objects for LLM config errors.

## Supervisor Decision

Accepted.
