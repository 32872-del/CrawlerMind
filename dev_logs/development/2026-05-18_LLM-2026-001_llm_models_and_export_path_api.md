# 2026-05-18 LLM-2026-001 — Frontend Support API Round 2

**Task**: Frontend Support API — LLM Models, Export Paths, Config Summary, CORS
**Worker**: LLM-2026-001
**Status**: COMPLETE

## Summary

Added backend API support required by the next frontend version: model-list fetching from OpenAI-compatible providers, LLM config health check, export directory validation and path resolution, workbench config summary, and CORS middleware for local dev.

## Files Changed

| File | Action | Description |
|------|--------|-------------|
| `autonomous_crawler/llm/model_list.py` | NEW | Model list fetching: fetch_model_list, check_provider_health, normalize_models, key redaction |
| `autonomous_crawler/api/app.py` | MODIFIED | Added 5 new endpoints, CORS middleware, version bump to 0.3.0 |
| `autonomous_crawler/tests/test_frontend_support_api.py` | NEW | 35 tests: model list, health, export paths, workbench config, CORS |

## Endpoint Shapes

### POST /llm/models

Fetch model list from an OpenAI-compatible provider.

```json
// Request
{"base_url": "https://api.openai.com", "api_key": "sk-...", "provider": "openai-compatible"}

// Response
{
  "provider": "openai-compatible",
  "models": [{"id": "gpt-4", "label": "gpt-4"}, {"id": "gpt-3.5-turbo", "label": "gpt-3.5-turbo"}],
  "raw_count": 2,
  "status": "ok",
  "error": "",
  "latency_ms": 350.2
}
```

Handles: `{data: [...]}`, `{models: [...]}`, flat list, single object. Deduplicates by id.

### POST /llm/health

Check provider connectivity without chat completion. Returns latency.

```json
// Request
{"base_url": "https://api.openai.com/v1", "api_key": "sk-..."}

// Response
{"status": "ok", "status_code": 200, "latency_ms": 150.0, "normalized_url": "https://api.openai.com", "endpoint": "https://api.openai.com/v1/models", "error": ""}
```

### POST /exports/validate-path

Validate or create a local export directory.

```json
// Request
{"directory": "/path/to/exports", "create": true}

// Response
{"exists": true, "created": true, "writable": true, "normalized_path": "C:\\path\\to\\exports", "error": ""}
```

### POST /exports/resolve-path

Resolve final export file path from directory + run_id + format.

```json
// Request
{"directory": "/tmp/exports", "run_id": "test-abc", "format": "xlsx"}

// Response
{"directory": "C:\\tmp\\exports", "filename": "test-abc.xlsx", "output_path": "C:\\tmp\\exports\\test-abc.xlsx", "format": "xlsx"}
```

Auto-appends missing extension. Supports sqlite→sqlite3 mapping.

### GET /workbench/config

Backend metadata for frontend.

```json
{
  "version": "0.3.0",
  "supported_export_formats": ["json", "csv", "xlsx", "sqlite", "db"],
  "max_active_jobs": 4,
  "default_retention_seconds": 3600,
  "endpoints": {
    "catalog_import": "/catalog/import",
    "site_analyze": "/site/analyze",
    "fields_resolve": "/fields/resolve",
    "runs_test": "/runs/test",
    "runs_full": "/runs/full",
    "runs_status": "/runs/{task_id}/status",
    "runs_events": "/runs/{task_id}/events",
    "exports": "/exports",
    "exports_validate_path": "/exports/validate-path",
    "exports_resolve_path": "/exports/resolve-path",
    "llm_models": "/llm/models",
    "llm_health": "/llm/health",
    "profile_runs": "/profile-runs",
    "jobs": "/jobs",
    "health": "/health"
  }
}
```

## Provider URL Normalization Rules

- `https://api.example.com` → `/v1/models` or `/v1/chat/completions`
- `https://api.example.com/v1` → `/models` or `/chat/completions`
- `https://api.example.com/v1/models` → unchanged
- Trailing slashes stripped

## Redaction Behavior

- API keys masked in all error messages: `sk-abcd1234efgh` → `sk-a...efgh`
- Keys shorter than 8 chars not masked (too short to be meaningful)
- No keys appear in response bodies or error fields

## CORS / Dev Behavior

- CORSMiddleware added with permissive defaults (`*` origins)
- `CLM_CORS_ORIGINS` env var: comma-separated origins, or `*` for all
- Allows all methods and headers for local dev

## Test Results

```
test_frontend_support_api: 35 passed
test_product_workflow_api: 33 passed (existing, unaffected)
compileall:                 clean
```

### Test classes

| Class | Tests | Coverage |
|-------|-------|----------|
| ModelListUnitTests | 14 | endpoint building, model normalization (data/models/list/dedup/empty), label, redaction, to_dict |
| FetchModelListTests | 3 | success, HTTP error with redaction, invalid JSON |
| CheckProviderHealthTests | 2 | ok with latency, error with redaction |
| LLModelsEndpointTests | 2 | success, empty base_url |
| LLMHealthEndpointTests | 2 | ok, empty base_url |
| ExportPathTests | 9 | validate exists/create/not-exists/empty, resolve default/custom/extension/sqlite/empty |
| WorkbenchConfigTests | 2 | config fields, all expected endpoints |
| CORSTests | 1 | preflight headers |
