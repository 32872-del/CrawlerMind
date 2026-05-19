# 2026-05-18 LLM-2026-001 — Product Workflow Export and Status

**Task**: Product Workflow Export and Status Hardening
**Worker**: LLM-2026-001
**Status**: COMPLETE

## Summary

Strengthened the product workflow backend for frontend workbench use: added a richer export template model for xlsx, improved task status payloads with current stage / last error / progress summary / quality indicator, and kept all existing defaults working.

## Files Changed

| File | Action | Description |
|------|--------|-------------|
| `autonomous_crawler/runners/product_workflow.py` | MODIFIED | Added `ExportTemplate` dataclass, template-aware xlsx export via openpyxl, status helper functions |
| `autonomous_crawler/api/app.py` | MODIFIED | Added `template` field to `ExportRequest`, imported `ExportTemplate`, enriched `/runs/{id}/status` response |
| `autonomous_crawler/tests/test_product_workflow_api.py` | MODIFIED | Added 19 new tests (14→33): ExportTemplate, xlsx template export, status helpers, status endpoint |

## Export Template Model

### ExportTemplate dataclass

```python
@dataclass(frozen=True)
class ExportTemplate:
    sheet_name: str = "Sheet1"
    start_row: int = 1
    start_column: int = 1
    field_to_column: dict[str, str] = field(default_factory=dict)
    columns: list[str] = field(default_factory=list)
```

- `sheet_name`: target worksheet name
- `start_row` / `start_column`: where to begin writing (1-based)
- `field_to_column`: maps data field names to header labels (e.g., `{"title": "Product Name"}`)
- `columns`: explicit column order; if empty, uses `field_to_column` keys, then all row keys

### How it works

1. If `template` has any non-default layout (field_to_column, columns, start_row > 1, start_column > 1), uses openpyxl for precise cell placement.
2. Otherwise, falls back to pandas `to_excel()` — the existing default path.
3. `ExportSpec.template` field added; `ExportTemplate.from_dict()` parses from API payload.

### API contract

`POST /exports` now accepts an optional `template` object:

```json
{
  "run_id": "full-abc123",
  "format": "xlsx",
  "output_path": "output.xlsx",
  "template": {
    "sheet_name": "Products",
    "start_row": 3,
    "start_column": 2,
    "field_to_column": {"title": "Product Name", "highest_price": "Price"},
    "columns": ["title", "highest_price", "colors"]
  }
}
```

When `template` is omitted or empty, default behavior is preserved.

## Task Status Improvements

### New fields in `/runs/{task_id}/status` response

| Field | Type | Description |
|-------|------|-------------|
| `current_stage` | string | `starting`, `crawling`, `finishing`, `finished`, `stopped` |
| `last_error` | string | Most recent error snippet (truncated to 200 chars) |
| `progress_summary` | string | Human-readable one-liner (e.g., "Running (75%) — 20 saved, 2 failed, 5 queued") |
| `quality_indicator` | string | `pass`, `warn`, `fail`, `unknown` based on field coverage or success rate |

### Status helper functions

- `_derive_current_stage(status, queued, done, failed, total_known)` — maps status + progress to a stage label
- `_extract_last_error_snippet(job, profile_run)` — finds most recent error from job.error, profile_run.failures, or runner_summary.last_error
- `_build_progress_summary(status, saved, done, failed, queued, completion)` — builds a human-readable summary
- `_derive_quality_indicator(quality, saved, failed)` — pass/warn/fail based on field_coverage or success rate

All new fields are also available inside the `progress` object for backward compatibility.

## Test Results

```
test_product_workflow_api: 33 passed (was 14, +19 new)
compileall:                 clean
```

### New test classes

| Class | Tests | Coverage |
|-------|-------|----------|
| ExportTemplateTests | 7 | from_dict defaults/full/clamps, to_dict, xlsx template offset, default export, columns order |
| StatusHelperTests | 11 | current_stage (5), last_error (4), progress_summary (3), quality_indicator (4) |
| StatusEndpointTests | 1 | status endpoint includes new fields |

## Known Limitations

1. **openpyxl dependency** — template xlsx export requires openpyxl (already a transitive dep via pandas, but explicit import needed)
2. **No cell-level formatting** — template controls layout only, not fonts/colors/borders
3. **No template file reading** — `template_path` still accepted but not used for cell-coordinate reading; the new `template` dict is the primary mechanism
4. **Quality indicator is heuristic** — uses field_coverage if available, otherwise success rate; no deep field-level quality analysis

## Frontend Contract Notes

- `/runs/{id}/status` response is backward compatible — all existing fields preserved, new fields added at top level and inside `progress`
- `POST /exports` is backward compatible — `template` is optional
- Frontend can use `current_stage` for step indicators, `progress_summary` for display, `quality_indicator` for color coding, `last_error` for error banners
