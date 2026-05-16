# 2026-05-15 LLM-2026-004 Profile Quality Gates Handoff

## Scope

Task: `PROFILE-HARDEN-2 Profile Quality Gates / Report`

The profile-driven ecommerce runner now emits product-like quality gates as a
structured report while keeping old flows non-breaking.

## Files Changed

- `autonomous_crawler/runners/profile_ecommerce.py`
- `autonomous_crawler/tests/test_profile_ecommerce_runner.py`
- `run_profile_training_2026_05_15.py`
- `run_real_ecommerce_profile_training_2026_05_15.py`
- `docs/runbooks/PROFILE_ECOMMERCE_RUNNER.md`
- `dev_logs/development/2026-05-15_LLM-2026-004_profile_harden_round2_quality_gates.md`
- `dev_logs/training/2026-05-15_profile_ecommerce_training.json`

Round 1 reference:

- `dev_logs/development/2026-05-15_LLM-2026-004_real_ecommerce_profile_training.md`
- `dev_logs/training/2026-05-15_real_ecommerce_profile_dummyjson.json`

## Quality Gate Contract

`profile_quality_summary` now accepts:

- `min_items`
- `required_fields`
- `max_duplicate_rate`
- `max_failed_url_count`
- `fail_on_gate`

It returns `quality_gate` with:

- `mode`: `report` or `fail`
- `passed`
- `should_fail`
- `severity`: `pass`, `warn`, or `fail`
- `checks`: one check each for item count, required fields, duplicate rate,
  and failed URL count

Default behavior is report-only. A failing gate becomes a warning unless the
caller passes `fail_on_gate=True`.

## Profile Files

Current profile examples:

- `autonomous_crawler/tests/fixtures/ecommerce_site_profile.json`: DOM
  list/detail profile.
- `autonomous_crawler/tests/fixtures/ecommerce_api_pagination_profile.json`:
  observed API page pagination profile.
- `autonomous_crawler/tests/fixtures/ecommerce_mixed_hydration_profile.json`:
  mixed SSR + cursor API fallback profile.
- `autonomous_crawler/tests/fixtures/ecommerce_real_dummyjson_profile.json`:
  real public product-like offset API profile.

## Verification

Passed:

- `python -m unittest autonomous_crawler.tests.test_profile_ecommerce_runner -v`
- `python run_profile_training_2026_05_15.py`
- `python -m compileall autonomous_crawler run_profile_training_2026_05_15.py`

## Remaining Risks

- Gate failure is not yet wired into a CLI exit policy except where callers
  choose to use `quality_gate.should_fail`.
- Required field completeness is strict at 100 percent for fields listed in
  `required_fields`; future real-site runs may need configurable minimum
  completeness per field.
- Duplicate detection uses existing `ProductRecord.dedupe_key`; cross-page
  canonical URL normalization still depends on profile/runtime extraction
  quality.
- Real retail sites still need broader profile training beyond DummyJSON.

## Suggested Next Step

Supervisor can assign a follow-up to wire `quality_gate.should_fail` into one
training CLI flag, for example `--fail-on-quality-gate`, without changing the
default report-first behavior.
