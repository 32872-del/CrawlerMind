# Handoff: Native Dynamic Runtime Comparison

Date: 2026-05-14

Employee: LLM-2026-000 / Supervisor Codex

Track: SCRAPLING-ABSORB-2B

## Summary

The native-vs-transition comparison runner now supports local dynamic SPA/API
training. This gives CLM a repeatable way to compare `NativeBrowserRuntime`
against `ScraplingBrowserRuntime` before using harder real-world dynamic sites.

## Files Changed

- `run_native_transition_comparison_2026_05_14.py`
- `autonomous_crawler/tests/test_native_transition_comparison.py`
- `clm.py`
- `PROJECT_STATUS.md`
- `docs/team/TEAM_BOARD.md`
- `docs/plans/2026-05-14_SCRAPLING_ABSORPTION_RECORD.md`
- `docs/team/acceptance/2026-05-14_native_dynamic_comparison_ACCEPTED.md`
- `dev_logs/development/2026-05-14_native_dynamic_comparison.md`
- `dev_logs/training/2026-05-14_native_transition_dynamic_smoke.json`

## Verified

```text
python -m unittest autonomous_crawler.tests.test_native_transition_comparison -v
Ran 8 tests
OK

python run_native_transition_comparison_2026_05_14.py --suite dynamic --output dev_logs\training\2026-05-14_native_transition_dynamic_smoke.json
native=executed(200), transition=executed(200), html_ratio=1.0, review=False
```

## Important Behavior

- `--suite dynamic` starts a temporary local SPA/API HTTP server.
- The SPA fetches `/api/products`, renders product cards, and lets both
  runtimes capture rendered DOM selectors and one XHR/API response.
- `clm.py train --round native-vs-transition-dynamic` prints the dynamic
  training command.

## Next Recommended Work

1. Add real dynamic/ecommerce targets to the comparison suite.
2. Implement native browser session reuse lifecycle.
3. Add protected mode fingerprint/runtime comparison.
4. Add browser failure classification and tuning against real training cases.
