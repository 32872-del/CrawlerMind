# Assignment: Frontend Support API Round 2

Date: 2026-05-18

Employee: LLM-2026-001

Project role: Backend Product Workflow Worker

Priority: P0

## Mission

Add the backend API support required by the next frontend version. This is the
backend contract layer for making CLM easier to configure from a browser UI.

- fetch model lists from mainstream OpenAI-compatible providers and relay
  providers
- validate/create local export directories for the web workbench
- provide a simple runtime/config health summary for the frontend
- keep all endpoints provider-neutral and safe to call repeatedly

## Read First

- `autonomous_crawler/api/app.py`
- `autonomous_crawler/llm/openai_compatible.py`
- `autonomous_crawler/runners/product_workflow.py`
- `docs/team/acceptance/2026-05-18_product_workflow_export_status_ACCEPTED.md`
- `docs/team/assignments/2026-05-18_ROUND2_LLM-2026-004_CHINESE_UI_MODEL_EXPORT_POLISH.md`

## Write Scope

Primary ownership:

- `autonomous_crawler/api/app.py`
- `autonomous_crawler/llm/openai_compatible.py`
- a helper under `autonomous_crawler/llm/` or `autonomous_crawler/tools/`
  if cleaner
- focused API tests
- dev log and handoff

Avoid touching frontend files.

## Requirements

1. Add a model-list endpoint.
   - suggested route: `POST /llm/models`
   - request: `base_url`, `api_key`, optional `provider`
   - response: provider, normalized model list, raw count, status, error
   - support OpenAI-compatible `/v1/models` and base URLs that already include
     `/v1`
   - redact keys from all errors and logs
   - handle common relay response shapes, including `data: [{id: ...}]`
   - return stable fields suitable for a dropdown: `id`, `label`, optional
     `owned_by`
2. Add LLM config health endpoint or extend the model endpoint.
   - verify base URL normalization
   - verify response status
   - return latency in milliseconds when possible
   - never require a real chat completion for this check
3. Add local export directory validation.
   - suggested route: `POST /exports/validate-path`
   - request: directory path, optional create flag
   - response: exists, created, writable, normalized path, error
   - reject clearly unsafe empty paths
   - create missing directory only when `create=true`
4. Add export filename helper.
   - suggested route: `POST /exports/resolve-path`
   - request: directory, run_id, format, optional filename
   - response: normalized final output path
   - prevent accidental missing extension
5. Add frontend config summary endpoint.
   - suggested route: `GET /workbench/config`
   - return backend version-ish metadata if available, supported export
     formats, max active jobs, default retention seconds, and supported product
     workflow endpoints
6. Add CORS readiness if not already present.
   - make local frontend development against FastAPI straightforward
   - keep default permissive only for local/dev if configuration exists
7. Keep behavior provider-neutral.
8. Add deterministic tests using mocked HTTP responses and temp directories.
9. Update runbook if the frontend contract changes.

## Acceptance

- frontend can call `/llm/models` and populate a dropdown
- frontend can validate or create an export directory
- frontend can resolve a final export path from a selected directory
- frontend can show backend config/status summary
- no API key leaks in responses
- focused tests pass
- compileall passes

## Handoff

Report:

- endpoint shapes
- provider URL normalization rules
- redaction behavior
- export path behavior
- config summary fields
- CORS/dev behavior
- tests run
