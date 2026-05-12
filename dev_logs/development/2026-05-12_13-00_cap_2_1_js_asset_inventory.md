# 2026-05-12 13:00 - CAP-2.1 JS Asset Inventory And Signature Clue MVP

## Goal

Implement a JS Asset Inventory MVP that identifies which JS files matter
before deeper AST/hook work starts. Extract script assets from HTML and
analyze JS text for suspicious keywords, API endpoints, GraphQL strings,
WebSocket URLs, and sourcemap references. Output a ranked report.

## Capability IDs

- CAP-2.1: JS AST 逆向 (JS asset inventory, keyword detection, endpoint extraction)
- CAP-2.2: Hook technique preparation (signature/token/encrypt keyword catalog)
- CAP-5.1: NLP-assisted selector/API reasoning support (API endpoint ranking)

## Changes

| File | Change |
|---|---|
| `autonomous_crawler/tools/js_asset_inventory.py` | Created. JS asset extraction and analysis module. |
| `autonomous_crawler/tests/test_js_asset_inventory.py` | Created. 65 tests. |

## Implementation

### Data Models

- `ScriptAsset`: url, inline_id, type_attr, is_module, is_nomodule, is_inline,
  size_estimate, sourcemap_hint
- `KeywordHit`: keyword, category, context_preview
- `JsAssetReport`: asset, score, reasons, endpoint_candidates, keyword_hits,
  graphql_strings, websocket_urls, sourcemap_refs

### Extraction Functions

- `extract_script_assets(html, base_url)`: parse <script> tags from HTML,
  resolve relative URLs, detect module/nomodule/type attributes, extract
  inline sourcemap hints
- `extract_inline_scripts(html)`: extract inline JS text from <script> tags

### Analysis Functions

- `analyze_js_text(js_text)`: unified analysis returning keyword hits,
  endpoint candidates, GraphQL strings, WebSocket URLs, sourcemap refs
- `_find_keyword_hits(js_text)`: keyword + regex pattern matching across
  8 categories (signature, encryption, token, challenge, anti_bot,
  fingerprint, verification, bundler)
- `_find_api_endpoints(js_text)`: regex for /api/, /v\d/, graphql, /ajax,
  /rest, /service paths
- `_find_graphql_strings(js_text)`: regex for query/mutation/subscription
  strings and brace-delimited GraphQL operations
- `_find_websocket_urls(js_text)`: regex for ws:// and wss:// URLs
- `_find_sourcemap_refs(js_text)`: regex for sourceMappingURL references

### Scoring

- `score_asset(asset, analysis)`: scores based on keyword categories
  (signature=30, encryption=28, token=25, challenge=22, anti_bot=20,
  fingerprint=18, verification=15, bundler=5), endpoint count (*8),
  GraphQL count (*15), WebSocket count (*12), sourcemap refs (+10),
  module bonus (+3), inline bonus (+2)

### Pipeline

- `build_js_inventory(html, base_url, inline_scripts)`: extract → analyze →
  score → sort. Returns ranked list of JsAssetReport.
- `build_inventory_summary(reports)`: aggregate summary with total_assets,
  scored_assets, top_assets, all endpoints/keywords/graphql/ws/sourcemaps.

## Keyword Categories

| Category | Keywords |
|---|---|
| signature | signature, sign, signed, hmac, sha256, sha1, md5 |
| encryption | encrypt, decrypt, encrypted, crypto |
| token | token, nonce, wbi, x-bogus, xbogus |
| challenge | captcha, recaptcha, hcaptcha, turnstile, geetest |
| anti_bot | anti-bot, antibot |
| fingerprint | fingerprint, canvas fingerprint, webgl fingerprint |
| verification | verify, verified |
| bundler | webpack, __webpack_require__, vite, __vite_ssr_import__, define |

## Tests

65 tests covering:
- Script asset extraction (external, inline, module, nomodule, sourcemap,
  empty HTML, JSON payload, no scripts)
- Inline script extraction
- JS analysis (signature/token/challenge keywords, API endpoints, GraphQL,
  WebSocket, sourcemaps, empty text)
- Keyword hit detection (categories, context preview, dedup, wbi)
- API endpoint extraction (api paths, graphql, versioned, data URI excluded)
- GraphQL string extraction (query, mutation, plain string)
- WebSocket URL extraction (wss, ws, non-ws)
- Sourcemap reference extraction (standard, URL, none)
- Asset scoring (each category, module bonus, sourcemap bonus, empty)
- Full inventory pipeline (all fixture types, ranking, base URL resolution,
  to_dict serialization)
- Summary generation (fields, counts, empty)
- Context extraction (find, not found, truncation)

## Verification

```text
python -m unittest autonomous_crawler.tests.test_js_asset_inventory -v
Ran 65 tests
OK

python -m unittest discover -s autonomous_crawler/tests
Ran 646 tests (skipped=4)
OK
```

## How Output Feeds Future AST/Hook Work

1. **Keyword hits** identify which JS files contain signature/token/encryption
   logic. Future AST work can target these files for function extraction.
2. **Endpoint candidates** give API URLs to probe. Future hook work can
   intercept calls to these endpoints.
3. **GraphQL strings** reveal query/mutation shapes for replay.
4. **WebSocket URLs** identify real-time data channels.
5. **Sourcemap refs** point to source maps that enable original source reading.
6. **Bundler keywords** (webpack/vite) indicate bundle structure for chunk
   splitting analysis.
7. **Challenge keywords** identify anti-bot code locations for future CDP
   hook targeting.

## Remaining Gaps

- External script content is not fetched; only inline scripts are analyzed
  for content. A future `fetch_and_analyze_external()` could download and
  analyze external JS files.
- No AST parsing yet; all analysis is regex-based. AST would enable function
  name extraction, call graph analysis, and dead code elimination.
- No minification/deobfuscation support; minified JS may have reduced regex
  match quality.
- No Wasm detection; Wasm binary analysis is a separate capability (CAP-2.3).
- No site-specific rules or profiles; all analysis is generic.
