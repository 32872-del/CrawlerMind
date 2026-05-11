# Assignment: FastAPI Opt-In LLM Advisors

## Assignee

Employee ID: `LLM-2026-001`

Project Role: `ROLE-API` / `ROLE-LLM-INTERFACE`

## Objective

Add opt-in LLM advisor support to the FastAPI crawl path while preserving the
existing deterministic default behavior.

The CLI LLM path is already working. This assignment moves that capability to
the service boundary.

## Required Reading

Start with:

```text
git pull origin main
```

Then read:

```text
docs/runbooks/EMPLOYEE_TAKEOVER.md
docs/team/employees/LLM-2026-001_WORKER_ALPHA.md
PROJECT_STATUS.md
docs/reports/2026-05-08_DAILY_REPORT.md
docs/team/acceptance/2026-05-08_real_llm_baidu_hot_smoke_ACCEPTED.md
docs/decisions/ADR-002-deterministic-fallback-required.md
docs/decisions/ADR-005-llm-planner-strategy-must-be-optional.md
```

Code to inspect:

```text
autonomous_crawler/api/app.py
autonomous_crawler/llm/openai_compatible.py
autonomous_crawler/workflows/crawl_graph.py
run_simple.py
autonomous_crawler/tests/test_api_mvp.py
```

## Allowed Write Scope

You may edit:

```text
autonomous_crawler/api/app.py
autonomous_crawler/tests/test_api_mvp.py
autonomous_crawler/tests/test_openai_compatible_llm.py
dev_logs/development/2026-05-08_HH-MM_fastapi_llm_advisors.md
docs/memory/handoffs/2026-05-08_LLM-2026-001_fastapi_llm_advisors.md
```

Avoid unrelated files. Do not edit docs/status files except your dev log and
handoff note.

## Requirements

1. Existing `POST /crawl` behavior must remain deterministic by default.
2. Add an explicit opt-in request field or config path for LLM usage. Prefer a
   request-level field such as `use_llm: true` plus provider config fields, or
   a small nested `llm` object.
3. Do not require API keys for normal API tests.
4. Provider construction must remain outside core graph nodes.
5. If LLM config is invalid, return a clear 400-style API error instead of
   crashing the background worker.
6. Preserve background job behavior: `POST /crawl` returns quickly and job
   status/result is read through `GET /crawl/{task_id}`.
7. Store final LLM audit fields in the persisted final state:
   `llm_enabled`, `llm_decisions`, `llm_errors`.
8. Keep deterministic fallback behavior if an advisor fails during the run.

## Minimum Tests

Add or update tests proving:

```text
POST /crawl without LLM remains deterministic
POST /crawl with invalid LLM config returns a clear client error
POST /crawl with fake/mock advisor path records llm_enabled and llm_decisions
background job still completes and can be queried
no API key or real network required for tests
```

Run:

```text
python -m unittest autonomous_crawler.tests.test_api_mvp -v
python -m unittest discover -s autonomous_crawler/tests
python -m compileall autonomous_crawler run_skeleton.py run_baidu_hot_test.py run_results.py run_simple.py
```

## Deliverables

- Code changes within allowed scope.
- Focused tests.
- Developer log.
- Handoff note.
- Completion note listing changed files, tests run, known risks, and next
  recommended step.

## Supervisor Notes

This is a service-boundary task, not a new LLM design task. Keep the LLM
interface already accepted in ADR-005. Do not add streaming, multi-provider
registries, Redis, or persistent job registry work in this assignment.
