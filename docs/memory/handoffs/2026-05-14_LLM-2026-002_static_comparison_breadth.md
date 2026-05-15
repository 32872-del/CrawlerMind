# Handoff: Static Breadth Comparison & Parser Consistency QA

**Date**: 2026-05-14
**Worker**: LLM-2026-002
**Status**: COMPLETE

## What Was Done

Expanded the SCRAPLING-ABSORB-1 native-vs-transition parity framework with 4 new
fixture HTML scenarios and 34 new tests. The framework now covers 100 tests across
10 fixture HTML documents, proving native parser/fetch parity on diverse HTML shapes
beyond basic product cards.

Also patched the comparison script (`run_native_transition_comparison_2026_05_14.py`)
to serve fixture-based scenarios via a local HTTP server, enabling deterministic
breadth comparison runs without external network access.

## Files Summary

| File | Action | Description |
|------|--------|-------------|
| `autonomous_crawler/tests/fixtures/native_runtime_parity.py` | **MODIFIED** | +4 HTML fixtures, +26 selector factories, +5 batch factories |
| `autonomous_crawler/tests/test_native_runtime_parity.py` | **MODIFIED** | +34 parity tests (4 new classes) |
| `run_native_transition_comparison_2026_05_14.py` | **MODIFIED** | +fixture serving, +`static-fixtures` suite |
| `dev_logs/development/2026-05-14_LLM-2026-002_static_comparison_breadth.md` | **NEW** | Dev log |
| `docs/memory/handoffs/2026-05-14_LLM-2026-002_static_comparison_breadth.md` | **NEW** | This handoff |

## New Fixture Coverage

| Fixture | Shape | Key Behaviors Tested |
|---------|-------|---------------------|
| `JSON_LD_SCRIPT_HTML` | JSON-LD + script + visible elements | Script content isolation, visible-only extraction |
| `CSS_MISS_XPATH_HIT_HTML` | Catalog sections with items | XPath axes (following-sibling, ancestor, positional) |
| `RELATIVE_URL_HTML` | Relative/absolute/protocol-relative URLs | Raw attribute extraction, no URL resolution |
| `NESTED_CATEGORY_DETAIL_HTML` | Category→subcategory→item→detail | Multi-level CSS/XPath, scoped extraction |

## Test Results

```
Focused parity: 100 passed, 1 skipped, 0 failures
compileall:      clean
```

## For Next Worker

1. **Browser parity gap**: NativeBrowserRuntime doesn't exist; SPA comparison
   still uses Scrapling transition adapter only
2. **curl_cffi transport**: breadth tests only exercise httpx path
3. **Text search divergence**: Scrapling `find_by_text` vs lxml `_direct_text`
   may differ on script/JSON-LD text — add explicit divergence tests if needed
4. **Comparison script**: run `python run_native_transition_comparison_2026_05_14.py
   --suite static-fixtures` for deterministic breadth comparison with JSON output
