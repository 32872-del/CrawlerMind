# 2026-05-15 LLM-2026-004 Real Ecommerce Profile Training

## Summary

- Added a real public ecommerce-like SiteProfile for DummyJSON products.
- Added a real profile training script that uses profile hints, not runtime
  site rules.
- Ran a real small-batch training pass against `https://dummyjson.com/products`.
- Added deterministic fixture regression support for unstable network/target
  conditions.
- Updated the profile ecommerce runbook with the real training path.

## Files Changed

- `autonomous_crawler/tests/fixtures/ecommerce_real_dummyjson_profile.json`
- `run_real_ecommerce_profile_training_2026_05_15.py`
- `autonomous_crawler/tests/test_profile_ecommerce_runner.py`
- `docs/runbooks/PROFILE_ECOMMERCE_RUNNER.md`
- `dev_logs/training/2026-05-15_real_ecommerce_profile_dummyjson.json`

## Real Training Result

- Target: `https://dummyjson.com/products`
- Pagination: offset via `limit` / `skip`
- Records collected: 75
- Quality summary:
  - title completeness: 1.0
  - price completeness: 1.0
  - category completeness: 1.0
  - description completeness: 1.0
  - image URL completeness: 1.0
  - duplicate rate: 0.0
  - failed URL count: 0
  - pagination stop reason: `offset_max_pages`

## Verification

- `python run_real_ecommerce_profile_training_2026_05_15.py` passed with `accepted: true`.
- `python -m unittest autonomous_crawler.tests.test_profile_ecommerce_runner -v` passed.
- `python -m compileall autonomous_crawler run_real_ecommerce_profile_training_2026_05_15.py` passed.

## Notes

- DummyJSON is a stable public product-like API, not a protected retail site.
- This proves profile-driven offset pagination and field mapping on a real
  network target.
- Real retail training still needs dynamic rendering, access diagnosis,
  sitemap/list/detail profiles, and site-specific profiles kept outside runtime.
