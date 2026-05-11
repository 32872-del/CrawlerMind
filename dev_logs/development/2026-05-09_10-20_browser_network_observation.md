# 2026-05-09 10:20 Browser Network Observation

## Summary

Added a browser network observation skeleton for future API/XHR/GraphQL
discovery.

## Changes

- Added `autonomous_crawler/tools/browser_network_observer.py`.
- Added mocked Playwright tests in
  `autonomous_crawler/tests/test_browser_network_observer.py`.
- Added explicit Recon opt-in through `constraints.observe_network=true`.
- Network observation records:
  - URL, method, resource type, status code
  - sanitized request/response headers
  - bounded post-data previews
  - optional JSON previews
  - scored API candidates
  - GraphQL signals

## Safety

- No CAPTCHA, Cloudflare, login, or access-control bypass.
- Sensitive headers are redacted.
- Network observation is opt-in and not enabled by default.

## Verification

```text
python -m unittest autonomous_crawler.tests.test_browser_network_observer -v
Ran 11 tests
OK

python -m unittest autonomous_crawler.tests.test_fetch_policy autonomous_crawler.tests.test_api_intercept -v
Ran 24 tests
OK
```
