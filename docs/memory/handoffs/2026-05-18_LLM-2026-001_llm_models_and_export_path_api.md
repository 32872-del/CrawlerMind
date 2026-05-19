---
worker: LLM-2026-001
date: 2026-05-18
task: FRONTEND-SUPPORT-API-ROUND2
status: COMPLETE
---

# Handoff: Frontend Support API Round 2

## What was delivered

### 1. Model List Endpoint (`POST /llm/models`)

- Request: `base_url`, `api_key` (optional), `provider`
- Response: `provider`, `models[]` (id, label, owned_by), `raw_count`, `status`, `error`, `latency_ms`
- Handles `{data: [...]}`, `{models: [...]}`, flat list, single object
- Deduplicates by model id
- API keys redacted from all errors

### 2. LLM Health Check (`POST /llm/health`)

- Uses `/v1/models` GET (no chat completion)
- Returns: `status`, `status_code`, `latency_ms`, `normalized_url`, `endpoint`, `error`
- URL normalization: strips trailing `/v1`

### 3. Export Path Validation (`POST /exports/validate-path`)

- Request: `directory`, `create` (bool)
- Response: `exists`, `created`, `writable`, `normalized_path`, `error`
- Creates missing dir only when `create=true`

### 4. Export Path Resolution (`POST /exports/resolve-path`)

- Request: `directory`, `run_id`, `format`, `filename` (optional)
- Response: `directory`, `filename`, `output_path`, `format`
- Auto-appends missing extension; sqlite→sqlite3 mapping

### 5. Workbench Config (`GET /workbench/config`)

- Returns: version, supported formats, max_active_jobs, retention, all endpoint paths

### 6. CORS Middleware

- Permissive defaults for local dev (`*` origins)
- `CLM_CORS_ORIGINS` env var for production tightening

## Files changed

- `autonomous_crawler/llm/model_list.py` (NEW) — fetch_model_list, check_provider_health, normalize_models
- `autonomous_crawler/api/app.py` (MODIFIED) — 5 endpoints, CORS, version 0.3.0
- `autonomous_crawler/tests/test_frontend_support_api.py` (NEW) — 35 tests

## Tests: 35 passed

ModelListUnitTests (14), FetchModelListTests (3), CheckProviderHealthTests (2), LLModelsEndpointTests (2), LLMHealthEndpointTests (2), ExportPathTests (9), WorkbenchConfigTests (2), CORSTests (1). Compileall clean.

## Key notes for frontend

- `/llm/models` returns empty list with `status="ok"` when provider has no models — check `raw_count`
- `/exports/resolve-path` does not check if directory exists — use `/exports/validate-path` first
- `/workbench/config` `endpoints` dict gives frontend all available routes
- API keys never appear in responses — all error messages are redacted
