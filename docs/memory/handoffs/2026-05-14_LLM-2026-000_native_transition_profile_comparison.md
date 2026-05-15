# Handoff: Native Transition Profile Comparison

Date: 2026-05-14

Employee: LLM-2026-000 / Supervisor Codex

Track: SCRAPLING-ABSORB-2B

## Summary

`run_native_transition_comparison_2026_05_14.py` now supports reusable
profile-driven comparison runs in addition to the static and dynamic local
training suites.

## Files Changed

- `run_native_transition_comparison_2026_05_14.py`
- `autonomous_crawler/tests/test_native_transition_comparison.py`
- `autonomous_crawler/tests/test_clm_cli.py`
- `autonomous_crawler/tests/fixtures/native_transition_profile.json`
- `clm.py`
- `PROJECT_STATUS.md`
- `docs/plans/2026-05-14_SCRAPLING_ABSORPTION_RECORD.md`
- `docs/team/acceptance/2026-05-14_native_transition_profile_comparison_ACCEPTED.md`
- `dev_logs/training/2026-05-14_native_transition_profile_comparison.json`

## Verified Behavior

- `--suite profile` runs the bundled profile against a temporary local SPA
  server.
- `--profile <json>` accepts a reusable scenario file and resolves
  `{base_url}` placeholders.
- Comparison output now carries richer evidence:
  - XHR preview
  - runtime event types
  - artifact kinds
  - fingerprint risk
  - expectation results
  - capture/artifact deltas

## Verification

```text
python -m unittest autonomous_crawler.tests.test_native_transition_comparison -v
Ran 14 tests
OK

python run_native_transition_comparison_2026_05_14.py --suite profile --profile autonomous_crawler\tests\fixtures\native_transition_profile.json
review=false for bundled profile scenarios

python clm.py train --round native-vs-transition-profile
prints the profile training command
```

## Next Recommended Work

1. Add real dynamic/ecommerce profile files.
2. Keep site-specific rules in profiles, not runtime code.
3. Feed profile evidence into the broader training ladder and capability
   matrix.
