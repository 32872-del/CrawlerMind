# Acceptance: Native Dynamic Runtime Comparison Harness

Date: 2026-05-14

Employee: LLM-2026-000 / Supervisor Codex

Track: SCRAPLING-ABSORB-2B

Status: accepted

## Scope Accepted

Implemented and verified a deterministic dynamic comparison harness:

- `run_native_transition_comparison_2026_05_14.py`
- `autonomous_crawler/tests/test_native_transition_comparison.py`
- `clm.py`
- `dev_logs/training/2026-05-14_native_transition_dynamic_smoke.json`

## What Changed

- The native-vs-transition comparison runner now supports:
  - `--suite static`
  - `--suite dynamic`
  - `--suite all`
- Dynamic suite starts a local deterministic SPA/API server.
- Dynamic scenario compares:
  - `engine="native"` / `NativeBrowserRuntime`
  - `engine="scrapling"` / `ScraplingBrowserRuntime`
- Evidence includes:
  - final URL
  - status code
  - backend name
  - HTML length
  - selector match counts
  - selector errors
  - captured XHR count
  - review flag
- `clm.py train --round native-vs-transition-dynamic` now prints the dynamic
  training command.

## Smoke Evidence

```text
python run_native_transition_comparison_2026_05_14.py --suite dynamic --output dev_logs\training\2026-05-14_native_transition_dynamic_smoke.json

native=executed(200)
transition=executed(200)
html_ratio=1.0
selector_delta title/price/link = 0
captured_xhr_count native = 1
captured_xhr_count transition = 1
review = false
```

## Verification

```text
python -m unittest autonomous_crawler.tests.test_native_transition_comparison -v
Ran 8 tests
OK
```

## Acceptance Notes

This accepts the local dynamic comparison harness and one deterministic SPA/API
smoke. It does not yet claim real-world dynamic-site parity.

Next work:

- add real dynamic/ecommerce comparison scenarios
- record wait/resource/XHR differences and tune `NativeBrowserRuntime`
- add session reuse lifecycle and protected profile/fingerprint calibration
