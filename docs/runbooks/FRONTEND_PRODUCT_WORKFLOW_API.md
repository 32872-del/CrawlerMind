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
  }
}
```

This creates a profile-run job with bounded batches. The response returns a
`task_id` and `run_id`.

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
progress.queued, progress.done, progress.completion, quality
```

Events include job lifecycle and failure snippets. This is currently polling
friendly. A future frontend can wrap it with SSE/WebSocket.

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

## Current Gaps

- Site analysis uses deterministic HTML recon plus menu heuristics. It does not
  yet do a full browser/XHR catalog discovery pass.
- `template_path` is accepted, but advanced template cell placement is not
  implemented yet.
- `/runs/{id}/events` is polling JSON, not SSE/WebSocket streaming yet.
- 托管模式 is represented by `run_mode`, but the repair loop still needs to be
  wired to LLM/profile refinement and retry execution.
