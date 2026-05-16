# 2026-05-15 LLM-2026-004 Profile Harden Round 2 Quality Gates

## Summary

- Added report-first profile quality gates to `profile_quality_summary`.
- Gate checks now cover `min_items`, `required_fields`, `duplicate_rate`, and
  `failed_url_count`.
- Existing runner flows remain compatible because gates default to report mode.
- Added opt-in failure signaling through `fail_on_gate=True`, which sets
  `quality_gate.should_fail` without raising from the helper.
- Updated profile training scripts so generated training JSON includes gate
  evidence from profile `quality_expectations`.

## Files Changed

- `autonomous_crawler/runners/profile_ecommerce.py`
- `autonomous_crawler/tests/test_profile_ecommerce_runner.py`
- `run_profile_training_2026_05_15.py`
- `run_real_ecommerce_profile_training_2026_05_15.py`
- `docs/runbooks/PROFILE_ECOMMERCE_RUNNER.md`
- `dev_logs/training/2026-05-15_profile_ecommerce_training.json`

## Quality Gate Behavior

- Default mode: `report`
- Passing gate: `passed: true`, `severity: pass`, `should_fail: false`
- Report-only failing gate: `passed: false`, `severity: warn`,
  `should_fail: false`
- Opt-in failing gate: `passed: false`, `severity: fail`,
  `should_fail: true`

## Training Result

- Offline profile library training was rerun.
- Profiles covered:
  - `fixture-ecommerce-profile`
  - `fixture-ecommerce-api-pagination`
  - `fixture-ecommerce-mixed-hydration`
- Total records: 135
- All three profile quality gates passed.

## Verification

- `python -m unittest autonomous_crawler.tests.test_profile_ecommerce_runner -v` passed.
- `python run_profile_training_2026_05_15.py` passed and refreshed training
  evidence.

## Notes

- Round 1 real ecommerce profile training remains documented separately in
  `dev_logs/development/2026-05-15_LLM-2026-004_real_ecommerce_profile_training.md`.
- Gate enforcement is intentionally caller-controlled. The current runner does
  not globally stop jobs on warning gates.
