# Dev Log: Native Dynamic Runtime Comparison

Date: 2026-05-14

Owner: LLM-2026-000 / Supervisor Codex

Track: SCRAPLING-ABSORB-2B

## Goal

Move native-vs-transition training beyond static pages by adding a deterministic
dynamic SPA comparison path for `NativeBrowserRuntime` and
`ScraplingBrowserRuntime`.

## Work Completed

- Extended `run_native_transition_comparison_2026_05_14.py` with
  `--suite static|dynamic|all`.
- Added a local deterministic SPA/API server inside the runner.
- Added dynamic scenario `local_spa_products`.
- Captured selector deltas and XHR counts in comparison output.
- Added `clm.py train --round native-vs-transition-dynamic`.
- Added tests for dynamic state construction, local SPA serving, and dynamic
  comparison JSON shape.
- Ran a real local dynamic smoke and saved evidence to:
  `dev_logs/training/2026-05-14_native_transition_dynamic_smoke.json`.

## Smoke Result

```text
native=executed(200)
transition=executed(200)
html_ratio=1.0
selector deltas: link=0, price=0, title=0
captured_xhr_count: native=1, transition=1
review=false
```

## Verification

```text
python -m unittest autonomous_crawler.tests.test_native_transition_comparison -v
Ran 8 tests
OK
```

## Remaining Gaps

- Real external dynamic/ecommerce sites still need comparison runs.
- Session reuse lifecycle is not implemented.
- Protected-mode and fingerprint behavior still need calibration.
