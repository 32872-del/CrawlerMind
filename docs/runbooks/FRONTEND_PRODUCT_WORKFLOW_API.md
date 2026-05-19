# Frontend Product Workflow API

Date: 2026-05-18

This runbook defines the first product-facing API flow for a CLM frontend. The
goal is to make the crawler agent usable as:

```text
configure -> analyze site -> select catalog/fields -> test 100 rows -> full run -> monitor -> export
```

## 1. Configure

The frontend should collect:

- LLM provider config: `base_url`, `api_key`, `model`, provider name.
- Crawl config: `item_workers`, timeout, retry, browser/proxy options.
- Export config: format, output path, optional template path, field mapping.

Existing LLM-compatible crawl config still uses the `LLMConfig` shape exposed by
`POST /crawl`.

## 2. Import Catalog

Endpoint:

```text
POST /catalog/import
```

Body:

```json
{
  "catalog": {
    "Women": {
      "Products": {
        "Leggings": "https://shop.test/leggings"
      }
    }
  }
}
```

The importer is compatible with the nested menu style used by:

```text
F:\datawork\spider\0000_data.json
```

Response shape:

```json
{
  "schema_version": "catalog-tree/v1",
  "catalog_tree": [
    {
      "id": "...",
      "label": "Women",
      "url": "",
      "path": ["Women"],
      "children": []
    }
  ],
  "node_count": 3,
  "leaf_count": 1
}
```

Leaf nodes include:

```text
url, path, level1, level2, level3
```

## 3. Analyze Site

Endpoint:

```text
POST /site/analyze
```

Body:

```json
{
  "target_url": "https://shop.test",
  "field_goal": "采集商品标题、原价、颜色、尺码、描述和图片",
  "imported_catalog": {
    "Women": {
      "Leggings": "https://shop.test/leggings"
    }
  }
}
```

The response returns:

- `catalog_tree`: imported catalog if supplied, otherwise agent-discovered menu
  candidates.
- `field_candidates`: canonical ecommerce fields plus detected selectors.
- `profile`: draft `SiteProfile` for test/full runs.
- `recon_summary`: framework/rendering/anti-bot/basic DOM evidence.

## 4. Resolve Fields

Endpoint:

```text
POST /fields/resolve
```

Body:

```json
{
  "available_fields": [
    {"name": "title"},
    {"name": "highest_price"},
    {"name": "colors"}
  ],
  "natural_language": "我要标题、原价和颜色"
}
```

The response returns selected canonical fields such as:

```text
title, highest_price, colors, sizes, description, image_urls
```

Unknown requested fields are returned in `missing_fields` so托管模式 can ask the
LLM/browser/API refinement loop to locate them.

## 5. Test Run

Endpoint:

```text
POST /runs/test
```

Body:

```json
{
  "target_url": "https://shop.test",
  "profile": {},
  "catalog_nodes": [],
  "selected_fields": ["title", "highest_price", "image_urls"],
  "item_workers": 8,
  "test_limit": 100,
  "runtime_dir": "dev_logs/runtime/shop-test",
  "export": {
    "format": "xlsx",
    "output_path": "dev_logs/exports/shop-test.xlsx"
  },
  "llm": {
    "enabled": true,
    "base_url": "https://api.example.com/v1",
    "api_key": "sk-...",
    "model": "model-name",
    "provider": "openai-compatible"
  },
  "managed_ai": {
    "enabled": true,
    "mode": "supervised",
    "pre_run_review": true,
    "post_run_diagnosis": true
  }
}
```

This creates a profile-run job with bounded batches. The response returns a
`task_id` and `run_id`.

`managed_ai` is optional. When omitted or disabled, `/runs/test` and
`/runs/full` remain deterministic. When enabled, `llm.enabled=true`,
`llm.base_url`, and `llm.model` are required.

Supported `managed_ai.mode` values:

```text
analysis_only, supervised, full_managed
```

Current backend behavior:

- `supervised` and `full_managed` run an LLM pre-run plan review before the
  background job starts.
- When `apply_pre_run_patch=true`, an allowlisted profile patch from the
  pre-run review can update seeds, runtime mode, waits, selectors, pagination,
  and quality expectations before execution. Accepted/rejected patch keys are
  exposed as `ai_patch_applications`.
- `supervised` and `full_managed` run an LLM post-run diagnosis after the
  profile runner finishes.
- `supervised` enables runtime supervision in observe mode. Batch-level health
  events are recorded but do not stop the job by themselves.
- `full_managed` enables runtime supervision in managed mode. Consecutive empty
  batches, high failure rates, or very low yield can pause/abort the run and
  expose a recommended next action such as `ai_rerun`.
- Model decisions are recorded in job state and exposed through status/events.

## 6. Full Run

Endpoint:

```text
POST /runs/full
```

The body is the same as `/runs/test`, but the backend creates an unbounded
profile long-run (`max_batches=0`) using selected catalog nodes as seeds.

## 7. Monitor

Endpoints:

```text
GET /runs/{task_id}/status
GET /runs/{task_id}/events
```

Status includes:

```text
status, record_count, accepted, progress.records_saved, progress.failed,
progress.queued, progress.done, progress.completion, quality,
managed_ai, ai_decisions, ai_diagnostics, ai_repair_suggestions,
ai_patch_applications, diagnostics, supervision
```

Events include job lifecycle, failure snippets, export events, and AI decision
events such as:

```text
ai_pre_run_review
ai_post_run_diagnosis
supervision_pause
supervision_abort
supervision_repair_after_run
```

This is currently polling friendly. A future frontend can wrap it with
SSE/WebSocket.

## 7.1 AI Repair Rerun

Endpoint:

```text
POST /runs/{task_id}/ai-rerun
```

Use this after a test/full product run has AI diagnostics. The backend reads
`ai_diagnostics.next_run_overrides`, applies bounded run/profile changes, and
starts a child product run.

If the run has runtime `supervision` but no LLM `next_run_overrides`, the backend
still builds a deterministic repair plan. For example, consecutive empty batches
produce overrides that switch to dynamic browser mode, enable API capture,
extend waits, and add conservative title selector fallback. Frontend users can
then click one repair rerun button instead of rebuilding the task manually.

Body:

```json
{
  "run_kind": "test",
  "apply_diagnostics": true,
  "extra_overrides": {
    "item_workers": 8,
    "access_config": {
      "mode": "dynamic",
      "wait_until": "networkidle"
    },
    "selectors": {
      "title": "h1.product-title"
    },
    "export": {
      "format": "csv"
    }
  },
  "managed_ai": {
    "enabled": true,
    "mode": "supervised",
    "pre_run_review": true,
    "post_run_diagnosis": true,
    "apply_pre_run_patch": true
  },
  "llm": {
    "enabled": true,
    "base_url": "https://api.example.com/v1",
    "api_key": "sk-...",
    "model": "model-name"
  }
}
```

Supported `run_kind`:

```text
test, full
```

The response returns a new `task_id`, plus:

```text
parent_task_id, repair_source, patch_application
```

The child run status also includes `parent_task_id`, `repair_source`, and
`ai_patch_applications`, so the workbench can show exactly which AI suggestions
were accepted or rejected.

## 8. Export

Endpoint:

```text
POST /exports
```

Body:

```json
{
  "run_id": "full-abc123",
  "runtime_dir": "dev_logs/runtime/shop-test",
  "format": "xlsx",
  "output_path": "dev_logs/exports/shop-test.xlsx",
  "field_mapping": {
    "title": "Title",
    "highest_price": "Price"
  }
}
```

Supported formats:

```text
json, csv, xlsx, sqlite, db
```

The current template behavior is data-first. `template_path` is accepted by the
API, but exact cell-coordinate writing should be a follow-up `TemplateSpec`
slice.

An optional `template` object controls xlsx layout:

```json
{
  "template": {
    "sheet_name": "Products",
    "start_row": 3,
    "start_column": 2,
    "field_to_column": {"title": "Product Name", "highest_price": "Price"},
    "columns": ["title", "highest_price", "colors"]
  }
}
```

## 9. LLM Model List

Endpoint:

```text
POST /llm/models
```

Body:

```json
{
  "base_url": "https://api.openai.com",
  "api_key": "sk-...",
  "provider": "openai-compatible"
}
```

Response:

```json
{
  "provider": "openai-compatible",
  "models": [{"id": "gpt-4", "label": "gpt-4"}, {"id": "gpt-3.5-turbo", "label": "gpt-3.5-turbo"}],
  "raw_count": 2,
  "status": "ok",
  "error": "",
  "latency_ms": 350.2
}
```

Handles common relay shapes: `{data: [...]}`, `{models: [...]}`, flat list.
API keys are redacted from all error messages.

## 10. LLM Health Check

Endpoint:

```text
POST /llm/health
```

Body: same as `/llm/models`.

Response:

```json
{
  "status": "ok",
  "status_code": 200,
  "latency_ms": 150.0,
  "normalized_url": "https://api.openai.com",
  "endpoint": "https://api.openai.com/v1/models",
  "error": ""
}
```

Uses `/v1/models` GET — no chat completion required.

## 11. Export Path Validation

Endpoint:

```text
POST /exports/validate-path
```

Body:

```json
{"directory": "/path/to/exports", "create": true}
```

Response:

```json
{"exists": true, "created": true, "writable": true, "normalized_path": "/abs/path", "error": ""}
```

## 12. Export Path Resolution

Endpoint:

```text
POST /exports/resolve-path
```

Body:

```json
{"directory": "/tmp/exports", "run_id": "test-abc", "format": "xlsx", "filename": ""}
```

Response:

```json
{"directory": "/tmp/exports", "filename": "test-abc.xlsx", "output_path": "/tmp/exports/test-abc.xlsx", "format": "xlsx"}
```

Auto-appends missing extension. Empty filename defaults to `{run_id}.{ext}`.

## 13. Workbench Config

Endpoint:

```text
GET /workbench/config
```

Response includes: version, supported export formats, max active jobs, default
retention seconds, and all available endpoint paths.

## Current Gaps

- Site analysis uses deterministic HTML recon plus menu heuristics. It does not
  yet do a full browser/XHR catalog discovery pass.
- `template_path` is accepted, but advanced template cell placement is not
  implemented yet.
- `/runs/{id}/events` is polling JSON, not SSE/WebSocket streaming yet.
- 托管模式 is represented by `run_mode`, but the repair loop still needs to be
  wired to LLM/profile refinement and retry execution.
