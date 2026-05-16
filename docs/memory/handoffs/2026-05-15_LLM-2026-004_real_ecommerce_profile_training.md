# Handoff: REAL-HARDEN-3 Real Ecommerce Profile Training

Employee: `LLM-2026-004`

Date: 2026-05-15

## Completed

- Added real public profile:
  - `autonomous_crawler/tests/fixtures/ecommerce_real_dummyjson_profile.json`
- Added training runner:
  - `run_real_ecommerce_profile_training_2026_05_15.py`
- Ran real training and saved:
  - `dev_logs/training/2026-05-15_real_ecommerce_profile_dummyjson.json`
- Added fixture-only regression coverage to:
  - `autonomous_crawler/tests/test_profile_ecommerce_runner.py`
- Updated:
  - `docs/runbooks/PROFILE_ECOMMERCE_RUNNER.md`

## Result

- Real target: DummyJSON products API.
- Product-like records collected: 75.
- Duplicate rate: 0.0.
- Failed URLs: 0.
- Pagination stopped by configured offset max pages.
- Field completeness for title, price, category, description, and images: 1.0.

## Verification

- `python run_real_ecommerce_profile_training_2026_05_15.py` passed.
- `python -m unittest autonomous_crawler.tests.test_profile_ecommerce_runner -v` passed.
- `python -m compileall autonomous_crawler run_real_ecommerce_profile_training_2026_05_15.py` passed.

## Real Site Adaptation Notes

- DummyJSON is public and stable; it validates profile-driven API pagination but
  not anti-bot handling.
- Real retail sites still need per-site profile discovery for selectors, API
  candidates, pagination limits, language/currency, image normalization, and
  dynamic rendering.
- Runtime code should remain generic. Tatuum, The Sting, BalticBHP, Shopify, or
  Magento specifics should live in profiles/evidence, not in runner/runtime
  modules.
