# Handoff: Native-vs-Transition Runtime Parity QA

**Date**: 2026-05-14
**Worker**: LLM-2026-002
**Status**: COMPLETE

## What Was Done

Built a comprehensive parity test framework comparing CLM-native runtime implementations
(NativeParserRuntime, NativeFetchRuntime) against Scrapling transition adapters. The
framework validates that native implementations produce equivalent outputs on identical
inputs, enabling confident absorption of Scrapling capabilities into CLM-owned backends.

## Files Summary

| File | Action | Description |
|------|--------|-------------|
| `autonomous_crawler/tests/fixtures/__init__.py` | **NEW** | Package init for fixtures |
| `autonomous_crawler/tests/fixtures/native_runtime_parity.py` | **NEW** | 7 HTML fixtures + 24 selector factories + 4 batch factories |
| `autonomous_crawler/tests/test_native_runtime_parity.py` | **NEW** | 66 parity tests (parser + static fetch) |
| `dev_logs/development/2026-05-14_LLM-2026-002_native_runtime_parity.md` | **NEW** | Dev log |

## Test Coverage

### Parser Parity (45 active tests)
- CSS multi-node, attribute, first-only, missing selector
- Nested CSS (table cells, nested items, row attributes)
- XPath (titles, prices, links, predicates, nested categories)
- Regex (prices, emails, phones)
- Text search (exact, partial)
- Mixed type batches
- Error handling (invalid CSS/regex, unsupported type, empty/malformed HTML)
- Output shape contract (matched, values, name, selector, ok, serializable)

### Static Fetch Parity (19 active tests)
- Protocol conformance (fetch method, name, FetchRuntime satisfaction)
- 200/403 response parity with Scrapling baseline
- Connection error handling
- Proxy forwarding + credential redaction
- POST JSON method dispatch
- RuntimeEvent emission (fetch_start, fetch_error)
- ProxyTrace population

### Bug Detection (2 tests)
- NativeParserRuntime recover keyword bug (now fixed — test skipped with "appears fixed")
- Native parser functional probe

## Key Finding: GAP-001 Fixed

NativeParserRuntime had a critical bug: `html.fromstring(html_text, recover=True)` raised
TypeError. This was fixed by another worker (LLM-2026-001) by splitting into
`HTMLParser(recover=True)` + `html.fromstring(html_text, parser=parser)`. All 45 parser
parity tests now pass against the fixed native parser.

## Verification Results

```
Parity suite:    66 passed, 1 skipped, 0 failures
Full test suite: 1396 passed, 5 skipped, 0 failures
compileall:      clean
```

## For Next Worker

1. The parity framework can be extended for browser runtime once NativeBrowserRuntime exists
2. curl_cffi transport path in NativeFetchRuntime is not yet parity-tested
3. Text selector semantics may diverge on deeply nested text nodes — add edge case fixtures
4. Transition adapters (scrapling_*) can be deprecated once parity is stable across training rounds
