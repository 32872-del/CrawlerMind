# 2026-05-15 LLM-2026-004 PROFILE-HARDEN-3 Round 3 Real Profile Batch

## Summary

- Added real public profile batch training script.
- Added two new public product API profiles:
  - Platzi Fake Store API
  - FakeStoreAPI
- Reused the existing DummyJSON profile with richer quality policy.
- Generated batch evidence at
  `dev_logs/training/2026-05-15_profile_real_batch_report.json`.

## Real Targets

- DummyJSON products: 75 records, quality gate pass.
- Platzi Fake Store API: 70 records, quality gate pass.
- FakeStoreAPI: 20 records, useful field evidence, `min_items` warning because
  the public catalog is smaller than 50.

## Files Changed

- `run_profile_real_batch_2026_05_15.py`
- `autonomous_crawler/tests/fixtures/ecommerce_real_platzi_profile.json`
- `autonomous_crawler/tests/fixtures/ecommerce_real_fakestore_profile.json`
- `autonomous_crawler/tests/fixtures/ecommerce_real_dummyjson_profile.json`
- `docs/runbooks/PROFILE_ECOMMERCE_RUNNER.md`
- `dev_logs/training/2026-05-15_profile_real_batch_report.json`

## Verification

- `python run_profile_real_batch_2026_05_15.py` passed.

## Notes

- All site-specific endpoint and field mapping data lives in profile files.
- The fallback fixture runtime exists only in the training script, not runtime.
- FakeStoreAPI is intentionally retained as a small-catalog warning example so
  product reports demonstrate useful gaps, not only pass cases.
