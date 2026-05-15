# Handoff: Native Browser Runtime

Date: 2026-05-14

Employee: LLM-2026-000 / Supervisor Codex

Track: SCRAPLING-ABSORB-2A

## Summary

`engine="native"` browser execution is no longer a deliberate gap. It now
routes through `NativeBrowserRuntime`, a CLM-owned Playwright backend that maps
runtime request/session/proxy/browser config into normalized `RuntimeResponse`
evidence.

## Files Changed

- `autonomous_crawler/runtime/native_browser.py`
- `autonomous_crawler/runtime/__init__.py`
- `autonomous_crawler/agents/executor.py`
- `autonomous_crawler/tests/test_native_browser_runtime.py`
- `autonomous_crawler/tests/test_scrapling_executor_routing.py`
- `PROJECT_STATUS.md`
- `docs/team/TEAM_BOARD.md`
- `docs/plans/2026-05-14_SCRAPLING_ABSORPTION_RECORD.md`
- `docs/team/acceptance/2026-05-14_native_browser_runtime_ACCEPTED.md`
- `dev_logs/development/2026-05-14_native_browser_runtime.md`

## Verified

```text
python -m unittest autonomous_crawler.tests.test_native_browser_runtime autonomous_crawler.tests.test_scrapling_executor_routing -v
Ran 20 tests
OK
```

## Important Behavior

- `NativeBrowserRuntime` does not import Scrapling.
- `RuntimeRequest.mode` is `dynamic` or `protected` for browser execution.
- Request/session headers are merged into Playwright context headers.
- Cookies are added to context when present.
- Storage state and proxy config are passed to Playwright.
- Captured XHR/JSON responses are returned through `RuntimeResponse.captured_xhr`.
- Executor forwards captured XHR into `api_responses`.
- Runtime events and proxy traces are preserved in workflow output.

## Next Recommended Work

1. `SCRAPLING-ABSORB-2B`: add native-vs-transition dynamic comparison scenarios.
2. Run a local real SPA smoke through `preferred_engine="native"`.
3. Add session reuse lifecycle for multi-page browser batches.
4. Calibrate protected mode with fingerprint/runtime evidence.
5. Add browser failure classification for install, timeout, proxy, blocked, and
   challenge-like failures.
