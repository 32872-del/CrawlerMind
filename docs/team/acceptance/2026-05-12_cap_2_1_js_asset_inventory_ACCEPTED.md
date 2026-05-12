# Acceptance: CAP-2.1 JS Asset Inventory

Date: 2026-05-12

Assignee: `LLM-2026-002`

Supervisor: `LLM-2026-000`

Status: accepted

## Capability IDs

- `CAP-2.1` Frontend JS reverse engineering / AST foundation
- `CAP-2.2` Hook technique preparation
- `CAP-5.1` NLP-assisted selector/API reasoning support

## Accepted Outputs

- Added `autonomous_crawler/tools/js_asset_inventory.py`.
- Added `autonomous_crawler/tests/test_js_asset_inventory.py`.
- Extracts external, inline, module, nomodule, and typed script assets from HTML.
- Detects sourcemap hints in inline scripts.
- Analyzes JS text for signature/token/encryption/challenge/fingerprint/bundler clues.
- Extracts API endpoint candidates, GraphQL strings, WebSocket URLs, and sourcemap references.
- Produces ranked `JsAssetReport` records and an inventory summary.

## Verification

```text
python -m unittest autonomous_crawler.tests.test_js_asset_inventory -v
python -m unittest autonomous_crawler.tests.test_transport_diagnostics autonomous_crawler.tests.test_browser_interceptor autonomous_crawler.tests.test_js_asset_inventory -v
python -m unittest discover -s autonomous_crawler/tests
```

Result:

```text
Ran 647 tests in 50.284s
OK (skipped=4)
```

## Remaining Gaps

- No AST parsing yet.
- No deobfuscation or source-map download pipeline yet.
- No execution of untrusted JS, by design.
- Needs integration with browser JS captures so captured bundles can be analyzed automatically.
