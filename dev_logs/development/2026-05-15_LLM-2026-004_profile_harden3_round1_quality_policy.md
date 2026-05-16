# 2026-05-15 LLM-2026-004 PROFILE-HARDEN-3 Round 1 Quality Gate Policy

## Summary

- Extended `profile_quality_summary` with policy-driven quality gates.
- Added per-field completeness thresholds for `title`, `price`,
  `description`, `image_urls`, `colors`, `sizes`, and `category`.
- Kept old `required_fields` list compatibility by treating list entries as
  100 percent required fields.
- Added mapping support for `required_fields` and `field_thresholds`, for
  example `{ "title": 0.95, "image_urls": 0.8 }`.
- Added warning/fail modes. Default mode is `warn`; `fail` sets
  `quality_gate.should_fail`.
- Added duplicate key strategy metadata to the quality summary.

## Files Changed

- `autonomous_crawler/runners/profile_ecommerce.py`
- `autonomous_crawler/tests/test_profile_ecommerce_runner.py`
- `autonomous_crawler/tests/fixtures/ecommerce_real_dummyjson_profile.json`
- `autonomous_crawler/tests/fixtures/ecommerce_real_platzi_profile.json`
- `autonomous_crawler/tests/fixtures/ecommerce_real_fakestore_profile.json`

## Verification

- `python -m unittest autonomous_crawler.tests.test_profile_ecommerce_runner -v` passed.

## Notes

- The duplicate rate still depends on `ProductRecord.dedupe_key`, so canonical
  URL mapping remains important for real-site profiles.
- The runner remains non-breaking by default because warning gates do not stop
  old flows.
