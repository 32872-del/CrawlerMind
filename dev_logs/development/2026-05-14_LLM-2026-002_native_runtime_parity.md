# 2026-05-14 LLM-2026-002 — Native-vs-Transition Runtime Parity QA

**Task**: SCRAPLING-ABSORB-1 / Native-vs-Transition Parity QA
**Worker**: LLM-2026-002
**Status**: COMPLETE

## Summary

Built a comprehensive parity test framework comparing CLM-native runtime implementations
(NativeParserRuntime, NativeFetchRuntime) against Scrapling transition adapters
(ScraplingParserRuntime, ScraplingStaticRuntime). The framework validates that native
implementations produce equivalent outputs to the Scrapling adapters on identical inputs.

## Files Changed

| File | Action | Description |
|------|--------|-------------|
| `tests/fixtures/__init__.py` | CREATE | Package init for fixtures directory |
| `tests/fixtures/native_runtime_parity.py` | CREATE | Shared HTML fixtures + selector request factories |
| `tests/test_native_runtime_parity.py` | CREATE | 66 parity tests across parser and static fetch |

## Parity Behaviors Covered

### Parser Parity (NativeParserRuntime vs ScraplingParserRuntime)
- **CSS multi-node extraction**: product names, prices, brands (3 products)
- **CSS attribute extraction**: href, src, data-sku, data-currency, data-row
- **CSS first-only mode**: `many=False` returns single result
- **CSS missing selector**: returns empty values, matched=0
- **Nested CSS**: table cells, nested item names, table row attributes
- **XPath extraction**: titles, prices, link attributes, predicates
- **XPath nested**: category headers from nested divs
- **Regex extraction**: prices ($X.XX), emails, phone numbers
- **Text search**: exact match, partial match on direct element text
- **Mixed type batch**: CSS + XPath + regex in one parse call
- **Error handling**: invalid CSS, invalid regex, unsupported type, empty HTML, malformed HTML, minimal HTML
- **Credential safety**: no plaintext proxy credentials in error outputs
- **Output shape contract**: matched (int), values (list), name preserved, selector preserved, ok property, serializable

### Static Fetch Parity (NativeFetchRuntime vs ScraplingStaticRuntime)
- **Protocol conformance**: has fetch(), has name, satisfies FetchRuntime
- **200 response**: ok=True, status_code, body, html, text, headers, final_url
- **403 response**: ok=False contract matches Scrapling behavior
- **Connection error**: returns failure with error message
- **Proxy forwarding**: proxy config passed to httpx client
- **Credential redaction**: no plaintext passwords in response or events
- **POST JSON**: method dispatch with json body
- **RuntimeEvents**: fetch_start and fetch_error events emitted
- **ProxyTrace**: RuntimeProxyTrace populated in response

### Protocol Conformance
- NativeParserRuntime satisfies ParserRuntime protocol
- NativeFetchRuntime satisfies FetchRuntime protocol
- Both have required `name` attribute and method signatures

## Tests Skipped Due to Native Bugs

**1 test skipped**: `test_native_parser_recover_keyword_bug`

Originally documented GAP-001: `html.fromstring(html_text, recover=True)` caused
`TypeError: fromstring() got an unexpected keyword argument 'recover'` on the installed
lxml version. This bug has since been fixed by splitting into
`HTMLParser(recover=True)` + `html.fromstring(html_text, parser=parser)`.

The bug detection test now correctly reports: "recover bug appears to be fixed".

**All 45 parser parity tests are ACTIVE** (not skipped) — NativeParserRuntime is
fully functional and achieves parity with ScraplingParserRuntime.

## Test Results

```
Parity suite:    66 tests, 1 skipped, 0 failures
Full test suite: 1396 tests, 5 skipped, 0 failures
compileall:      clean
```

## Native Absorption Risks

1. **lxml HTMLParser deprecation warning**: `strip_cdata` option is deprecated. Non-blocking
   but will need cleanup when lxml removes it.

2. **Text selector semantics**: NativeParserRuntime's `_direct_text()` matches only
   `elem.text` (text before first child), while Scrapling's `find_by_text()` may include
   descendant text. Parity tests confirm alignment on current fixtures, but edge cases
   with deeply nested text nodes could diverge.

3. **Regex extraction scope**: Native regex runs on full concatenated text
   (`elem.itertext()`), matching Scrapling's `get_all_text()` + `re.findall()`. This is
   consistent but means regex results may include text from hidden elements (display:none).

4. **Transport selection**: NativeFetchRuntime defaults to httpx. curl_cffi transport is
   available but not parity-tested (Scrapling uses its own Fetcher which may differ from
   curl_cffi directly).

## Next Steps

1. **Integration parity**: Test native runtimes in the executor pipeline end-to-end
   (not just unit-level parity)
2. **curl_cffi transport parity**: Add parity tests for curl_cffi transport path in
   NativeFetchRuntime
3. **Browser parity**: Once NativeBrowserRuntime exists, extend parity framework
4. **Performance benchmarks**: Compare native vs scrapling parse/fetch latency
5. **Remove transition adapters**: Once parity is stable across N training rounds,
   scrapling_* adapters can be deprecated
