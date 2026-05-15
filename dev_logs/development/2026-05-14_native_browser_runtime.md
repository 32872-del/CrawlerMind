# Dev Log: Native Browser Runtime

Date: 2026-05-14

Owner: LLM-2026-000 / Supervisor Codex

Track: SCRAPLING-ABSORB-2A

## Goal

Continue Scrapling capability absorption by turning the browser runtime path
into a CLM-native backend instead of leaving `engine="native"` browser mode as
an explicit failure.

## Work Completed

- Added `NativeBrowserRuntime` in `autonomous_crawler/runtime/native_browser.py`.
- Exported `NativeBrowserRuntime` from `autonomous_crawler/runtime/__init__.py`.
- Routed `engine="native"` + `mode="browser"` in `executor.py` through the new
  runtime.
- Preserved runtime events, captured XHR, artifacts, selector evidence, proxy
  trace, and backend details in executor output.
- Added mocked Playwright tests for:
  - config resolution
  - missing Playwright failure
  - browser protocol compatibility
  - context/session/proxy/header mapping
  - XHR response preview capture
  - resource blocking
  - executor routing and structured failure
- Updated project status, team board, absorption record, and acceptance record.

## Verification

```text
python -m unittest autonomous_crawler.tests.test_native_browser_runtime autonomous_crawler.tests.test_scrapling_executor_routing -v
Ran 20 tests
OK
```

## Current Capability

CLM now has a native browser runtime shell capable of Playwright rendering,
wait policy, headers/cookies/storage-state, proxy launch config, XHR/JSON
capture, optional screenshots, and workflow evidence preservation.

## Remaining Gaps

- No real native browser SPA smoke has been run yet.
- No native-vs-transition dynamic comparison runner exists yet.
- Session reuse is request-level only; there is no long-lived browser context
  lifecycle for multi-page crawl batches yet.
- Protected mode currently has config shape, not real calibrated behavior.
- Browser failure classification needs a dedicated pass.
