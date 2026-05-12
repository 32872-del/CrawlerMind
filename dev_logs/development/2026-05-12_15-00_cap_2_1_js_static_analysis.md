# 2026-05-12 15:00 - CAP-2.1 JS Static Analysis: String Table MVP

## Goal

Extend the JS Asset Inventory with deeper regex-based static analysis: string
literal extraction, function declaration/assignment detection, suspicious call
identification, and a ranked report. Deterministic, dependency-light, no AST
parser, no JS execution.

## Capability IDs

- CAP-2.1: JS AST 逆向 (string table, function extraction, suspicious call detection)
- CAP-2.2: Hook technique preparation (suspicious keyword catalog for calls)
- CAP-5.1: NLP-assisted API reasoning (endpoint/URL string ranking)

## Changes

| File | Change |
|---|---|
| `autonomous_crawler/tools/js_static_analysis.py` | Created. String table, function/call clues, ranked report. |
| `autonomous_crawler/tests/test_js_static_analysis.py` | Created. 54 tests. |

## Implementation

### Data Models

- `StringEntry`: value, kind (quoted/template/url), is_endpoint, is_url
- `FunctionClue`: name, kind (declaration/arrow/assignment/method), suspicious, suspicion_reason
- `CallClue`: call_expression, matched_keyword, category, context
- `StaticAnalysisReport`: string_count, endpoint_strings, url_strings, suspicious_functions, suspicious_calls, score, reasons

### String Extraction

- `extract_strings(js_text, max_strings)`: extracts double-quoted, single-quoted,
  and template literal strings. Deduplicates by value. Flags URL and API path
  strings. Template interpolation `${...}` replaced with `<expr>`.
- `extract_endpoint_strings(js_text)`: extracts URLs, API paths, and WebSocket URLs.

### Function Extraction

- `extract_functions(js_text)`: detects function declarations (`function name()`),
  arrow functions (`const name = () =>`), assignments (`var name = function()`),
  and method shorthand (`name() {}`). Flags suspicious names containing
  sign/encrypt/token/captcha/fingerprint keywords.

### Suspicious Call Extraction

- `extract_suspicious_calls(js_text)`: matches call expressions containing
  suspicious keywords. Also matches `object.method()` where the object name
  contains a keyword (e.g., `hcaptcha.getResponse()`). Provides context snippet.
- Categories: signature, encryption, token, challenge, fingerprint, verification, anti_bot

### Scoring

- `score_static_analysis(entries, functions, calls)`: scores based on endpoint
  strings (*6, max 30), suspicious function categories (12-25 each), suspicious
  call categories (15-30 each), and large string table bonus (+5 if >100).

### Pipeline

- `analyze_js_static(js_text)`: full pipeline returning StaticAnalysisReport.

## Key Design Decisions

1. **Regex-only**: No AST parser dependency. Regex handles minified and multiline JS.
2. **Object-method matching**: Added `_SUSPICIOUS_OBJ_CALL_RE` for patterns like
   `hcaptcha.getResponse()` where the keyword is in the object name, not the method.
3. **Template literal handling**: Interpolation replaced with `<expr>` to extract
   the surrounding string structure without executing JS.
4. **Deduplication**: All extractors deduplicate by value/name to avoid noise.

## Tests

54 tests covering:
- String extraction (double/single quoted, template literals, interpolation,
  empty string skip, URL flagging, endpoint flagging, empty JS, dedup, max limit)
- Endpoint extraction (HTTPS, API path, WebSocket, empty)
- Function extraction (declarations, arrow, assignment, method, kind detection,
  suspicious flagging, encryption flagging, non-suspicious, empty)
- Suspicious call extraction (hmac, token, encrypt, verify, captcha, fingerprint,
  normal function excluded, category assignment, context present, empty)
- Scoring (endpoint strings, suspicious func signature, suspicious call high score,
  empty analysis, large string table bonus)
- Full pipeline (multiline JS, endpoints, suspicious funcs/calls, minified JS,
  harmless JS, empty JS, comments only, Bilibili-style, to_dict, fixture tests,
  score nonzero, reasons present)

## Verification

```text
python -m unittest autonomous_crawler.tests.test_js_static_analysis -v
Ran 54 tests
OK

python -m unittest discover -s autonomous_crawler/tests
Ran 753 tests (skipped=4)
OK
```

## Examples

### Extracted Strings
From `MULTILINE_JS`:
- `"https://api.example.com/v1"` (URL)
- `"wss://stream.example.com/events"` (URL)
- `"6LeIxAcTAAAAAJcZVRqyHh71UMIEGNQ_MXjiZKhI"` (quoted)

### Extracted Functions
- `signRequest` (arrow, suspicious: signature)
- `encryptPayload` (arrow, suspicious: encryption)
- `verifyResponse` (declaration, suspicious: verification)

### Extracted Calls
- `hmacSHA256` (category: signature, context: `...var signature = hmacSHA256(data + nonce, key)...`)
- `aesEncrypt` (category: encryption)
- `grecaptcha.getResponse` (category: challenge)

## Remaining Gaps

- No AST parsing; regex may miss nested or complex patterns
- No minification/deobfuscation; obfuscated code may evade regex
- No control-flow or data-flow analysis
- No Wasm detection (CAP-2.3)
- No site-specific rules or profiles
- External script content not fetched (only inline analyzed by js_asset_inventory)
