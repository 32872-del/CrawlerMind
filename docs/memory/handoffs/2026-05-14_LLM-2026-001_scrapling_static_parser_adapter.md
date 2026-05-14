# Handoff: Scrapling Static + Parser Adapter

Employee: LLM-2026-001
Date: 2026-05-14
Status: complete

## Summary

Built Scrapling-first runtime adapters for static HTTP fetching and HTML parsing,
plugging into the existing CLM Runtime protocol layer (FetchRuntime, ParserRuntime).
No production workflow code changed — adapters are pure runtime backend modules.

## Changed Files

- `autonomous_crawler/runtime/scrapling_static.py` — new (ScraplingStaticRuntime)
- `autonomous_crawler/runtime/scrapling_parser.py` — new (ScraplingParserRuntime)
- `autonomous_crawler/runtime/__init__.py` — updated exports
- `autonomous_crawler/tests/test_scrapling_static_runtime.py` — new (22 tests)
- `autonomous_crawler/tests/test_scrapling_parser_runtime.py` — new (25 tests)

## Tests Run

```
test_scrapling_static_runtime:  22 OK
test_scrapling_parser_runtime:  25 OK
python -m compileall autonomous_crawler — OK (no errors)
```

## Adapter API Summary

### ScraplingStaticRuntime (FetchRuntime protocol)

```python
class ScraplingStaticRuntime:
    name: str = "scrapling_static"
    def fetch(self, request: RuntimeRequest) -> RuntimeResponse
```

- Maps RuntimeRequest → Scrapling Fetcher.get/post/put/delete
- Headers, cookies, timeout_ms (→seconds), proxy_config forwarded
- Network errors → RuntimeResponse.failure() (never raises)
- Proxy credentials never leak into response
- HTTP 2xx/3xx → ok=True, 4xx/5xx → ok=False

### ScraplingParserRuntime (ParserRuntime protocol)

```python
class ScraplingParserRuntime:
    name: str = "scrapling_parser"
    def parse(self, html: str, selectors: list[RuntimeSelectorRequest], *, url: str = "") -> list[RuntimeSelectorResult]
```

- CSS selector: Scrapling Selector.css() → text/attr extraction
- XPath selector: Scrapling Selector.xpath() → text/attr extraction
- text selector: Selector.find_by_text(partial=True, case_insensitive)
- regex selector: re.findall() on Selector.get_all_text()
- attribute extraction via .attrib mapping
- many=False returns first match only
- Invalid selector → RuntimeSelectorResult with error (never raises)
- Missing Scrapling → all selectors return error result

## Known Risks

1. **Scrapling curl_cffi dependency**: Scrapling's Fetcher uses curl_cffi for TLS fingerprint impersonation. If curl_cffi is missing, Fetcher will fail at runtime. The adapter catches this as a generic Exception.
2. **Regex on get_all_text()**: Regex extraction applies to concatenated text (newlines between elements). Patterns expecting specific whitespace may need tuning.
3. **Text selector scope**: find_by_text searches all descendant elements with text. For very large pages this may be slower than CSS/XPath.
4. **No async support yet**: ScraplingStaticRuntime uses synchronous Fetcher. AsyncFetcher exists in Scrapling but is not wired up.
5. **lxml DeprecationWarning**: `strip_cdata` option produces a DeprecationWarning from lxml. Harmless but noisy in test output.

## Next Integration Recommendation

1. **Executor routing**: Wire ScraplingStaticRuntime into executor.py's mode dispatch so `mode=static` routes to this adapter.
2. **Browser adapter**: ScraplingBrowserRuntime (DynamicFetcher/StealthyFetcher) for `mode=dynamic`.
3. **Site spec integration**: Connect parser adapter to site_spec.json field extraction so selectors from config flow through RuntimeSelectorRequest.
4. **Async variant**: Wrap Scrapling AsyncFetcher for concurrent batch fetching.
5. **Proxy pool integration**: Forward proxy_manager selections through RuntimeRequest.proxy_config.
