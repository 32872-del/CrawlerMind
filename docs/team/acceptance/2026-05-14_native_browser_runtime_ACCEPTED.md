# Acceptance: Native Browser Runtime Shell

Date: 2026-05-14

Employee: LLM-2026-000 / Supervisor Codex

Track: SCRAPLING-ABSORB-2A

Status: accepted

## Scope Accepted

Implemented the first CLM-native browser runtime backend:

- `autonomous_crawler/runtime/native_browser.py`
- `autonomous_crawler/runtime/__init__.py`
- `autonomous_crawler/agents/executor.py`
- `autonomous_crawler/tests/test_native_browser_runtime.py`
- `autonomous_crawler/tests/test_scrapling_executor_routing.py`

## What Changed

- Added `NativeBrowserRuntime`, a Playwright-backed `BrowserRuntime` that does
  not import or call Scrapling.
- Added `NativeBrowserConfig` and config resolution for:
  - dynamic/protected mode shape
  - wait selector state
  - render delay
  - resource blocking
  - blocked domains
  - XHR/JSON capture
  - optional JS response preview capture
  - optional screenshots
  - init scripts
  - CDP URL / executable / channel / extra launch flags
- Mapped CLM request/session/access fields into browser context execution:
  - request headers
  - session headers
  - cookies
  - storage state
  - proxy configuration
  - locale/timezone/viewport/user agent
- Executor now routes `engine="native"` + `mode="browser"` through
  `NativeBrowserRuntime.render()`.
- Executor preserves native browser evidence:
  - runtime events
  - selector results
  - captured XHR previews
  - artifacts
  - proxy trace
  - runtime engine details

## Verification

```text
python -m unittest autonomous_crawler.tests.test_native_browser_runtime autonomous_crawler.tests.test_scrapling_executor_routing -v
Ran 20 tests
OK
```

## Acceptance Notes

This accepts the native browser shell and executor route. It does not yet claim
full parity with Scrapling dynamic/protected behavior.

Remaining work:

- run local real SPA smoke through `engine="native"`
- add native-vs-transition dynamic comparison runner/scenarios
- tune wait/resource/XHR behavior against real training cases
- add session reuse lifecycle for multi-page runs
- align protected mode with runtime fingerprint profile evidence
- classify browser runtime failures for challenge, timeout, browser install,
  proxy, and blocked response cases
