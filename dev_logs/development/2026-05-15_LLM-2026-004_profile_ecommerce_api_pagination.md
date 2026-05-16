# 2026-05-15 LLM-2026-004 Profile Ecommerce API Pagination

## Summary

- Hardened profile-driven ecommerce runner for observed API pagination.
- Added profile schema helpers for pagination/API hints.
- Added generic API JSON field mapping to `ProductRecord`.
- Added page/offset/cursor URL generation helpers.
- Added API pagination fixture profile and a 55-product deterministic test.
- Added runbook for authoring and running ecommerce site profiles.

## Files Changed

- `autonomous_crawler/runners/site_profile.py`
- `autonomous_crawler/runners/profile_ecommerce.py`
- `autonomous_crawler/runners/__init__.py`
- `autonomous_crawler/tests/test_profile_ecommerce_runner.py`
- `autonomous_crawler/tests/fixtures/ecommerce_api_pagination_profile.json`
- `docs/runbooks/PROFILE_ECOMMERCE_RUNNER.md`

## Fixture Coverage

- `ecommerce_site_profile.json`: DOM list/detail fixture profile with selectors, link discovery, access config, and product quality expectations.
- `ecommerce_api_pagination_profile.json`: observed API replay fixture with `page` pagination, JSON `items_path`, field mapping, fixed query params, and 50+ product expectation.

## Verification

- `python -m unittest autonomous_crawler.tests.test_profile_ecommerce_runner -v` passed.
- `python -m compileall autonomous_crawler` passed.

## Notes

- API pagination supports `page`, `offset`, and `cursor` hint shapes in runner helpers.
- The focused fixture currently tests `page` mode with 55 simulated products.
- Offset and cursor have helper coverage through code paths but still need dedicated real or synthetic tests.
