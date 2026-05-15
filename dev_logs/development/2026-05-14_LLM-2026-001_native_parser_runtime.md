# NativeParserRuntime — SCRAPLING-ABSORB-1

Date: 2026-05-14
Employee: LLM-2026-001

## Summary

Implemented `NativeParserRuntime` — a CLM-owned HTML parser that satisfies the
`ParserRuntime` protocol using lxml/cssselect/re.  No Scrapling dependency.

## Deliverables

### New files

- `autonomous_crawler/runtime/native_parser.py` — NativeParserRuntime
- `autonomous_crawler/tests/test_native_parser_runtime.py` — 48 tests

### Modified files

- `autonomous_crawler/runtime/__init__.py` — added NativeParserRuntime export

## Implementation

`NativeParserRuntime.parse()` uses:

- **lxml.html.fromstring** with `HTMLParser(recover=True)` for robust HTML parsing
- **cssselect.HTMLTranslator().css_to_xpath()** for CSS→XPath conversion, then lxml xpath
- **lxml xpath** for native xpath selectors; handles both element and attribute string returns
- **Direct text matching** (`elem.text`) for text pseudo-selector — matches only leaf-level text nodes to replicate Scrapling's `find_by_text(partial=True, case_sensitive=False, clean_match=True)`
- **re.findall** on `itertext()`-concatenated text for regex extraction
- **elem.get(attr)** for attribute extraction

Error handling: all selector failures return `RuntimeSelectorResult` with error string, never raise.

## Test Results

```
test_native_parser_runtime: 48 OK
test_runtime_protocols + test_native_parser_runtime + test_scrapling_parser_runtime: 78 OK
python -m compileall autonomous_crawler: OK
```

### Test categories (48 tests)

- CSS extraction (6): titles, prices, href, data-id, many=False, selector miss
- XPath extraction (6): titles, attribute, predicate, direct attribute, many=False, miss
- Text extraction (6): exact, partial, no match, case-insensitive, empty selector, many=False
- Regex extraction (5): prices, year, no match, invalid regex, many=False
- Error handling (8): invalid CSS, unsupported type, empty HTML, malformed HTML, multiple selectors, URL passthrough, invalid xpath
- Protocol (2): isinstance check, name check
- Credential safety (1): no secrets in errors
- Deep text (2): nested text concatenation, deeply nested
- Ordering (1): document order preserved
- Special chars (2): unicode, HTML entities
- Parity (10): native vs scrapling on CSS, XPath, text, regex, empty HTML

## Parity with ScraplingParserRuntime

10 dedicated parity tests verify identical behaviour on the same fixture HTML.
Key alignment: text selector uses direct `.text` (not `text_content()`) to
match Scrapling's leaf-level element matching.
