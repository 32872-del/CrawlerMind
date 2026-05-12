# Handoff: CAP-2.1 JS Asset Inventory And Signature Clue MVP

Employee: LLM-2026-002
Date: 2026-05-12
Assignment: `2026-05-12_LLM-2026-002_CAP-2.1_JS_ASSET_INVENTORY`

## What Was Done

Implemented a JS Asset Inventory MVP that extracts script assets from HTML
and analyzes JS text for suspicious keywords, API endpoints, GraphQL strings,
WebSocket URLs, and sourcemap references. Outputs a ranked "where to look
next" report.

## Files Changed

| File | Change |
|---|---|
| `autonomous_crawler/tools/js_asset_inventory.py` | Created. JS asset extraction and analysis. |
| `autonomous_crawler/tests/test_js_asset_inventory.py` | Created. 65 tests. |
| `dev_logs/development/2026-05-12_13-00_cap_2_1_js_asset_inventory.md` | Dev log. |
| `docs/memory/handoffs/2026-05-12_LLM-2026-002_cap_2_1_js_asset_inventory.md` | This handoff. |

## Capability IDs Covered

- CAP-2.1: JS AST 逆向 foundation
- CAP-2.2: Hook technique preparation (keyword catalog)
- CAP-5.1: NLP-assisted API reasoning (endpoint ranking)

## Key API

```python
from autonomous_crawler.tools.js_asset_inventory import (
    extract_script_assets,      # HTML → list[ScriptAsset]
    extract_inline_scripts,     # HTML → list[str]
    analyze_js_text,            # JS text → analysis dict
    build_js_inventory,         # HTML → ranked list[JsAssetReport]
    build_inventory_summary,    # reports → summary dict
)
```

## How Output Feeds Future Work

- **AST work**: keyword hits identify files with signature/token logic for
  function-level extraction.
- **Hook work**: endpoint candidates and WebSocket URLs are interception
  targets for CDP hooks.
- **GraphQL replay**: graphql_strings reveal query shapes for API replay.
- **Sourcemap recovery**: sourcemap refs enable original source reading.
- **Bundle analysis**: bundler keywords (webpack/vite) indicate structure.

## Remaining Gaps

- External script content not fetched (only inline analyzed)
- No AST parsing (regex-only)
- No minification/deobfuscation
- No Wasm detection (CAP-2.3)
- No site-specific rules
