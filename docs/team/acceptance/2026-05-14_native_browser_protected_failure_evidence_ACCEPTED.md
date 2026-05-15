# Acceptance: Native Browser Protected Evidence And Failure Classification

Date: 2026-05-14

Employee: LLM-2026-000 / Supervisor Codex

Track: SCRAPLING-ABSORB-2D

Status: accepted

## Scope Accepted

Implemented the first protected-browser evidence and failure-classification
slice for the CLM-native browser runtime:

- `autonomous_crawler/runtime/native_browser.py`
- `autonomous_crawler/tests/test_native_browser_runtime.py`
- `PROJECT_STATUS.md`
- `docs/team/TEAM_BOARD.md`
- `docs/plans/2026-05-14_SCRAPLING_ABSORPTION_RECORD.md`

## What Changed

- `NativeBrowserRuntime` now attaches `fingerprint_report` to both successful
  and failed runtime responses.
- Protected mode adds a first native profile-tuning layer through Playwright
  launch flags and a bounded init script.
- Browser failures now include structured `failure_classification` evidence.
- Classification categories currently include:
  - `playwright_missing`
  - `browser_install_or_launch`
  - `navigation_timeout`
  - `proxy_error`
  - `http_blocked`
  - `challenge_like`
  - `unknown`
  - `none`
- Challenge-like rendered pages are classified through the existing challenge
  detector using status, headers, and rendered HTML.
- Failure responses preserve safe context/config/fingerprint evidence instead
  of returning only an opaque error string.

## Verification

```text
python -m unittest autonomous_crawler.tests.test_native_browser_runtime -v
Ran 11 tests
OK

python -m unittest autonomous_crawler.tests.test_native_browser_runtime autonomous_crawler.tests.test_scrapling_executor_routing autonomous_crawler.tests.test_native_transition_comparison -v
Ran 32 tests
OK

python -m unittest discover -s autonomous_crawler/tests
Ran 1422 tests in 69.364s
OK (skipped=5)

python -m compileall autonomous_crawler run_native_transition_comparison_2026_05_14.py clm.py
OK
```

## Acceptance Notes

This is a diagnostic/evidence layer, not a final protected-browser training
result. The runtime now records enough structured evidence for later training
on difficult dynamic/protected pages.

Remaining work:

- real protected/dynamic site training
- profile pool and runtime/config fingerprint comparison
- browser context pool leasing for BatchRunner
- calibration of failure categories on real proxy/browser/provider failures
