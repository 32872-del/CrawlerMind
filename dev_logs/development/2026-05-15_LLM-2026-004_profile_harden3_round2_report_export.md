# 2026-05-15 LLM-2026-004 PROFILE-HARDEN-3 Round 2 Report Export

## Summary

- Added `autonomous_crawler/runners/profile_report.py`.
- Added stable `profile-run-report/v1` JSON export through
  `build_profile_run_report`.
- Report payload includes record count, field completeness, quality gate,
  duplicate rate, failed URLs, stop reason, runtime/backend, samples, failures,
  duplicate key strategy, and next actions.
- Updated offline and real profile training scripts to attach the report under
  each profile case.

## Files Changed

- `autonomous_crawler/runners/profile_report.py`
- `autonomous_crawler/runners/__init__.py`
- `run_profile_training_2026_05_15.py`
- `run_real_ecommerce_profile_training_2026_05_15.py`
- `autonomous_crawler/tests/test_profile_ecommerce_runner.py`
- `docs/runbooks/PROFILE_ECOMMERCE_RUNNER.md`
- `dev_logs/training/2026-05-15_profile_ecommerce_training.json`
- `dev_logs/training/2026-05-15_real_ecommerce_profile_dummyjson.json`

## Verification

- `python run_profile_training_2026_05_15.py` passed.
- `python run_real_ecommerce_profile_training_2026_05_15.py` passed.

## Notes

- Markdown rendering helper exists, but current scripts persist JSON reports
  only.
- Report `accepted` means the case has no opt-in hard failure. Warning gates
  remain visible in `quality_gate`.
