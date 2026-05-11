# 2026-05-08 18:45 - P1 Fetch Best Page / Mode Escalation

## Goal

Add a local fetch quality policy so Recon can compare fetch modes and record
why a page was selected.

## Changes

- Added `autonomous_crawler/tools/fetch_policy.py`.
- Added `fetch_best_page()` with mode attempts, HTML quality scoring, and
  escalation trace.
- Scoring considers:
  - HTTP status
  - HTML size
  - visible text length
  - DOM candidate signals
  - structured data
  - API hints
  - JS shell findings
  - challenge findings
- Added `fetch_best_html()` in `html_recon.py` for Recon compatibility and
  deterministic mock fixtures.
- Recon now records:
  - `recon_report.fetch.selected_mode`
  - `recon_report.fetch.selected_score`
  - `recon_report.fetch_trace`
- Strategy keeps browser mode when Recon already selected browser-rendered HTML.
- Added a mock JS-shell escalation path:
  `requests` sees shell -> `browser` sees rendered product cards.
- Browser launch is skipped after pure transport-level failures, avoiding slow
  browser retries when no HTML was available.

## Safety Boundary

This is mode selection and diagnosis only. It does not bypass CAPTCHA,
Cloudflare, login walls, or access controls.

## Tests

Focused verification:

```text
python -m unittest autonomous_crawler.tests.test_fetch_policy autonomous_crawler.tests.test_access_diagnostics autonomous_crawler.tests.test_error_codes autonomous_crawler.tests.test_error_paths autonomous_crawler.tests.test_workflow_mvp -v
Ran 87 tests OK

python -m unittest discover -s autonomous_crawler/tests
Ran 232 tests OK (skipped=3)

python -m compileall autonomous_crawler run_skeleton.py run_baidu_hot_test.py run_results.py run_simple.py
OK
```

## Next

- Promote this policy into executor reuse where safe.
- Build site-zoo fixtures for static, SPA, structured data, challenge, product
  list, product detail, and variants.
- Add browser network observation after site-zoo stabilizes.
