# Acceptance: CAP-4.2 Runtime Fingerprint Probe

Date: 2026-05-12

Owner: `LLM-2026-000`

Status: accepted

## Capability IDs

- `CAP-4.2` Browser fingerprint consistency and runtime probing
- `CAP-4.1` Playwright/CDP-side browser automation foundation
- `CAP-6.2` Anti-bot strategy evidence

## Completed Outputs

- Added opt-in runtime fingerprint probing with Playwright.
- Added serializable runtime snapshot and finding models.
- Added browser-side sampling for:
  - navigator identity and automation signals;
  - timezone;
  - screen and viewport;
  - WebGL vendor/renderer;
  - canvas hash metadata;
  - bounded font probe.
- Added risk analysis for webdriver exposure, runtime/config mismatch,
  mobile/touch incoherence, invalid runtime shape, WebGL/canvas risk.
- Integrated into Recon behind explicit `constraints.probe_fingerprint=true`.

## Verification

```text
python -m unittest autonomous_crawler.tests.test_browser_fingerprint_probe -v
Ran 22 tests
OK
```

## Remaining Gaps

- Evidence-only; no stealth/spoofing implementation.
- No browser fingerprint pool yet.
- Needs real-site training against browser-protected pages after the current
  worker tasks are accepted.
