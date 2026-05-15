# 2026-05-14 LLM-2026-004 Profile-Driven Ecommerce Runner

## Summary

- Added a profile-driven ecommerce helper layer that converts `SiteProfile` data into `SpiderRuntimeProcessor` callbacks.
- Added a deterministic ecommerce profile fixture with list selectors, detail selectors, link discovery hints, access config, rate limits, quality expectations, and training notes.
- Added an offline smoke script that proves profile-driven long-running runner execution can collect product records and resume after a bounded first pass.
- Added tests covering both the smoke path and direct runner callback integration.

## Files Changed

- `autonomous_crawler/runners/profile_ecommerce.py`
- `autonomous_crawler/runners/site_profile.py`
- `autonomous_crawler/runners/__init__.py`
- `autonomous_crawler/tests/fixtures/ecommerce_site_profile.json`
- `autonomous_crawler/tests/test_profile_ecommerce_runner.py`
- `run_profile_ecommerce_runner_smoke_2026_05_14.py`
- `dev_logs/smoke/2026-05-14_profile_ecommerce_runner_smoke.json`

## Smoke Evidence

- Command: `python run_profile_ecommerce_runner_smoke_2026_05_14.py`
- Output: `dev_logs/smoke/2026-05-14_profile_ecommerce_runner_smoke.json`
- Accepted: `true`
- Collected records: 2
- Titles: `Alpha Runner`, `Beta Trail`
- First pass: claimed 1 list page, discovered 2 detail URLs, left frontier as `{"done": 1, "queued": 2}`.
- Resume pass: claimed 2 detail pages, saved 2 product records, finished frontier as `{"done": 3}`.

## Verification

- `python -m unittest autonomous_crawler.tests.test_profile_ecommerce_runner autonomous_crawler.tests.test_spider_runner -v` passed.
- `python -m unittest discover -s autonomous_crawler/tests` passed: 1768 tests, 5 skipped.
- `python -m compileall autonomous_crawler` passed.

## Remaining Gaps

- Fixture profile is static HTML only; real ecommerce runs still need dynamic rendering fallback and browser-backed profile execution.
- API pagination/cursor handling is not yet connected to ecommerce profile execution.
- Quality expectations are recorded in the profile and output evidence, but no generic product quality gate is enforced inside the runner yet.
- Larger real-site regression remains pending, especially 600+ ecommerce pages and 1k/10k/30k synthetic long-run stress.
