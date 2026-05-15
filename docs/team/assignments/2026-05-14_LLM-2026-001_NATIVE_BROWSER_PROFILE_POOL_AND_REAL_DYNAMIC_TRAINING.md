# Assignment: Native Browser Profile Pool And Real Dynamic Training

Date: 2026-05-14

Employee: `LLM-2026-001`

Priority: P0

Track: `SCRAPLING-ABSORB-2H / CAP-4.2`

## Mission

Continue absorbing Scrapling dynamic/protected browser capability into CLM's
native backend. Build the next browser-profile layer on top of the accepted
`NativeBrowserRuntime` and `BrowserPoolManager`, then prove it with real dynamic
training evidence.

## Ownership

Primary files:

- `autonomous_crawler/runtime/native_browser.py`
- `autonomous_crawler/runtime/browser_pool.py`
- `autonomous_crawler/tests/test_native_browser_runtime.py`
- `autonomous_crawler/tests/test_browser_pool.py`
- new focused tests if needed

Do not modify proxy runtime, spider runner, or JS analysis modules except for
small integration hooks agreed by existing interfaces.

## Requirements

1. Add a CLM-native browser profile pool abstraction or extend the existing
   pool so profiles can rotate by configurable profile identity:
   user agent, viewport, locale, timezone, storage state mode, resource policy,
   and protected-mode flag.
2. Emit profile selection evidence in `engine_result` without leaking local
   filesystem paths or secrets.
3. Add real dynamic/profile training smoke coverage. Prefer deterministic local
   profile tests plus one optional external smoke that skips cleanly if network
   or browser binaries are unavailable.
4. Keep all behavior generic. No hardcoded site rules.
5. Update dev log and handoff.

## Acceptance Checks

Run:

```text
python -m unittest autonomous_crawler.tests.test_browser_pool autonomous_crawler.tests.test_native_browser_runtime -v
python -m unittest discover -s autonomous_crawler/tests
python -m compileall autonomous_crawler
```

Report:

- files changed
- tests run
- profile evidence shape
- known gaps before production protected-site use
