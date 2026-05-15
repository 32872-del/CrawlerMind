# 2026-05-14 LLM-2026-002 — Static Breadth Comparison & Parser Consistency QA

**Task**: SCRAPLING-ABSORB-1C-A — native-vs-transition static breadth comparison
**Worker**: LLM-2026-002
**Status**: COMPLETE

## Summary

Expanded the native-vs-transition parity framework from 66 to 100 tests by adding
4 new fixture HTML scenarios and 34 new tests covering JSON-LD coexistence,
CSS-miss/XPath-hit, relative URL extraction, and deep nested category hierarchies.
Also patched the comparison script to serve fixture-based local scenarios.

## Files Changed

| File | Action | Description |
|------|--------|-------------|
| `autonomous_crawler/tests/fixtures/native_runtime_parity.py` | MODIFIED | +4 HTML fixtures, +26 selector factories, +5 batch factories |
| `autonomous_crawler/tests/test_native_runtime_parity.py` | MODIFIED | +34 parity tests across 4 new test classes |
| `run_native_transition_comparison_2026_05_14.py` | MODIFIED | +fixture HTML map, +`build_static_fixture_scenarios()`, +`static-fixtures` suite |
| `dev_logs/development/2026-05-14_LLM-2026-002_static_comparison_breadth.md` | NEW | This dev log |
| `docs/memory/handoffs/2026-05-14_LLM-2026-002_static_comparison_breadth.md` | NEW | Handoff |

## New Fixture Scenarios

### 1. JSON-LD / Script Coexistence (`JSON_LD_SCRIPT_HTML`)
- `<script type="application/ld+json">` with ItemList and Organization schemas
- Inline `<script>` with `window.__INITIAL_STATE__` data
- Visible `<article class="product">` elements with title, price, link, img
- **Verifies**: script content does not pollute CSS/XPath extraction

### 2. CSS Miss / XPath Hit (`CSS_MISS_XPATH_HIT_HTML`)
- Catalog sections with items having name, price, stock spans
- XPath axes needed: `following-sibling`, `ancestor`, positional `[last()]`
- **Verifies**: XPath extracts what CSS cannot (ancestor traversal, axis-based selection)

### 3. Relative URL / Image (`RELATIVE_URL_HTML`)
- `<base href>` + links with `/absolute`, `./relative`, `../parent`, `//protocol-relative`, `#fragment`
- Images with `/path`, `./path`, `../path`, `//cdn`, `data:` URI
- **Verifies**: raw attribute values returned as-is, no URL resolution

### 4. Nested Category / Detail Hierarchy (`NESTED_CATEGORY_DETAIL_HTML`)
- 2 categories → 3 subcategories → 5 product items with detail links
- Category/subcategory names, product IDs, prices, thumbnails
- **Verifies**: multi-level CSS extraction, XPath scoped to subcategory

## New Test Classes

| Class | Tests | Coverage |
|-------|-------|----------|
| `ParityParserJsonLdCoexistenceTests` | 8 | Visible vs script content, CSS+XPath, full batch |
| `ParityParserCssMissXPathHitTests` | 7 | CSS baseline, XPath axes, CSS-miss verification, mixed batch |
| `ParityParserRelativeUrlTests` | 7 | CSS/XPath href/src/alt, non-empty verification, batch |
| `ParityParserNestedCategoryDetailTests` | 12 | Category/subcategory/detail links/prices/images/IDs, XPath scoped, batch |

## Comparison Script Changes

- Added `FIXTURE_HTML_MAP` mapping URL paths to fixture HTML strings
- `_LocalSpaHandler.do_GET()` now serves fixture pages from the map
- Added `build_static_fixture_scenarios(base_url)` — 5 scenarios (product-catalog,
  json-ld-script, css-miss-xpath-hit, relative-url, nested-category-detail)
- New `--suite static-fixtures` option for deterministic local comparison runs

## Test Results

```
Focused parity: 100 passed, 1 skipped, 0 failures
compileall:      clean
```

## Coverage Gaps

1. **No native browser runtime parity** — NativeBrowserRuntime doesn't exist yet;
   SPA comparison still requires Scrapling transition adapter
2. **curl_cffi transport** — not tested in breadth scenarios (only httpx path)
3. **Text search on JSON-LD page** — script text matching behavior may differ
   between parsers (Scrapling's `find_by_text` vs lxml direct text)
4. **Selector count mismatch scenario** — no test where CSS returns fewer matches
   than XPath on the same visible elements (values parity still checked, but
   delta not explicitly asserted)
