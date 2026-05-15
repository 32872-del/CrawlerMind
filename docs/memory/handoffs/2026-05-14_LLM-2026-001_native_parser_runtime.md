# Handoff: NativeParserRuntime (SCRAPLING-ABSORB-1)

Employee: LLM-2026-001
Date: 2026-05-14
Status: complete

## Summary

Implemented `NativeParserRuntime` — a CLM-native HTML parser satisfying the
`ParserRuntime` protocol using lxml/cssselect/re.  No Scrapling dependency.
Behaviour is aligned with `ScraplingParserRuntime` (10 parity tests verify).

## Changed Files

- `autonomous_crawler/runtime/native_parser.py` — new (NativeParserRuntime)
- `autonomous_crawler/tests/test_native_parser_runtime.py` — new (48 tests)
- `autonomous_crawler/runtime/__init__.py` — added NativeParserRuntime export

## Tests Run

```
test_native_parser_runtime:                                                  48 OK
test_runtime_protocols + test_native_parser_runtime + test_scrapling_parser:  78 OK
python -m compileall autonomous_crawler:                                     OK
```

## API Summary

```python
class NativeParserRuntime:
    name: str = "native_parser"
    def parse(self, html: str, selectors: list[RuntimeSelectorRequest], *, url: str = "") -> list[RuntimeSelectorResult]
```

- CSS: `cssselect.HTMLTranslator().css_to_xpath()` → lxml xpath
- XPath: native lxml xpath; handles element and attribute-string returns
- Text: iterates `root.iter()`, matches `elem.text` (direct text only) — partial, case-insensitive
- Regex: `re.findall(pattern, " ".join(elem.itertext()))` on full document text
- Attribute: `elem.get(attr)`
- Errors: returns `RuntimeSelectorResult` with error string, never raises

## Key Design Decision

Text selector uses `elem.text` (direct text before first child), NOT
`elem.text_content()` (all descendant text).  This matches Scrapling's
`find_by_text` behaviour which only matches leaf-level text elements.
Using `text_content()` would match parent wrapper elements too, breaking
parity with the Scrapling adapter.

## Dependencies

- `lxml` (html.fromstring, HTMLParser, etree)
- `cssselect` (HTMLTranslator)
- `re` (stdlib)

## Known Risks

1. **lxml DeprecationWarning**: `strip_cdata` option produces a harmless warning from lxml HTMLParser.
2. **Text selector scope**: Only matches elements whose direct `.text` contains the needle.  Elements with mixed content (`<p>Hello <b>World</b></p>`) — "Hello World" won't match the `<p>`.  This matches Scrapling behaviour.

## Next Steps

1. `SCRAPLING-ABSORB-1` acceptance: NativeParserRuntime done, NativeFetchRuntime also done (by another worker).
2. `SCRAPLING-ABSORB-2`: Dual-run training — run native + adapter on real static sites, record differences.
3. `SCRAPLING-ABSORB-3`: Spider scheduler/checkpoint/request/result absorption into BatchRunner.
4. `SCRAPLING-ABSORB-4`: Native browser runtime absorption.
