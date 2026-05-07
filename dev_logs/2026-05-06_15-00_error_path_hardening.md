# 2026-05-06 15:00 - Error-Path Hardening

## Goal

Harden the autonomous crawler workflow against error conditions. This is
Priority 3 from the short-term plan: test unsupported URL scheme, HTTP
failure/timeout, empty HTML, invalid selectors, retry exhaustion, and ensure
failures persist.

## Changes

- Added `autonomous_crawler/tests/test_error_paths.py` with 30 new tests
  across 8 test classes:
  - `TestUnsupportedURLScheme` - ftp, file, mailto schemes in executor and recon
  - `TestHTTPFailure` - connection error, HTTP 500, timeout (mocked), recon fetch failure
  - `TestEmptyHTML` - empty dict, empty string, whitespace, None value
  - `TestInvalidSelectors` - nonexistent container, mismatched fields, empty selectors, malformed CSS
  - `TestRetryExhaustion` - max retries reached, zero max, below max, low completeness
  - `TestValidatorEdgeCases` - missing extracted_data, duplicate URLs, missing prices
  - `TestGraphErrorPropagation` - 4 end-to-end graph tests with error conditions
  - `TestFailurePersistence` - recon_failed and failed states persist to SQLite with error_log

- Fixed `autonomous_crawler/agents/extractor.py`:
  - Skip `None` or non-string HTML values in raw_html loop
  - Wrap `soup.select()` in try/except for malformed CSS selectors
  - Wrap `container.select_one()` in try/except in `_extract_value()`

- Hardened `autonomous_crawler/workflows/crawl_graph.py`:
  - Added `_route_after_recon()` conditional edge router
  - Graph now exits early with `recon_failed` when recon fails
  - Previously continued through strategy/executor/extractor/validator uselessly

- Updated `PROJECT_STATUS.md`: test count 28->58, marked error-path task done, added completed item

## Verification

Full test suite:

```text
python -m unittest discover autonomous_crawler\tests
Ran 58 tests
OK
```

Focused error-path tests:

```text
python -m unittest autonomous_crawler.tests.test_error_paths -v
Ran 30 tests
OK
```

Compile check:

```text
python -m compileall autonomous_crawler
OK
```

## Result

The workflow now handles all tested error paths without crashing. Failed states
(recon_failed, failed) persist to SQLite with error logs intact. The graph
short-circuits on recon failure instead of running the full pipeline on bad data.

## Next Step

Priority 4: Browser Fallback Prototype. Or coordinate with Storage/CLI Codex
on shared interfaces before starting browser work.
