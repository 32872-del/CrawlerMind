# 2026-05-08 FastAPI Opt-In LLM Advisors - ACCEPTED

## Assignment

`docs/team/assignments/2026-05-08_LLM-2026-001_FASTAPI_LLM_ADVISORS.md`

## Assignee

Employee ID: `LLM-2026-001`

Project Role: `ROLE-API / ROLE-LLM-INTERFACE`

## Scope Reviewed

Reviewed:

```text
autonomous_crawler/api/app.py
autonomous_crawler/tests/test_api_mvp.py
dev_logs/development/2026-05-08_14-00_fastapi_llm_advisors.md
docs/memory/handoffs/2026-05-08_LLM-2026-001_fastapi_llm_advisors.md
```

## Verification

```text
python -m unittest autonomous_crawler.tests.test_api_mvp -v
Ran 38 tests in 5.571s OK

python -m unittest discover -s autonomous_crawler/tests
Ran 186 tests in 18.595s OK (skipped=3)

python -m compileall autonomous_crawler run_skeleton.py run_baidu_hot_test.py run_results.py run_simple.py
OK
```

## Accepted Changes

- Added request-level `LLMConfig` Pydantic model to the FastAPI crawl API.
- Added optional `llm` field to `CrawlRequest`.
- Validates `llm.base_url` and `llm.model` eagerly and returns a clear 400 on
  missing values when `llm.enabled=true`.
- Builds the OpenAI-compatible advisor inside the API boundary and passes it to
  the crawl graph compiler.
- Persists `llm_enabled`, `llm_decisions`, and `llm_errors` in the background
  job final state.
- Preserved deterministic default behavior when no LLM config is supplied.
- Added 11 new API tests covering deterministic default behavior, invalid
  config rejection, valid config startup, and background query flow.

## Risks / Follow-Up

- No runtime provider health check at API level.
- LLM config is request-scoped only; no persistent provider registry yet.
- No streaming support.
- No persistent job registry.

## Supervisor Decision

Accepted.
