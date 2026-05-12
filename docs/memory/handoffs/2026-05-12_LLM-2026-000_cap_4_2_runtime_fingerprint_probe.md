# Handoff: CAP-4.2 Runtime Fingerprint Probe

Date: 2026-05-12

Employee: `LLM-2026-000`

## Current State

CLM now has an opt-in runtime fingerprint probe:

```text
autonomous_crawler/tools/browser_fingerprint_probe.py
```

To enable during Recon:

```python
{
    "recon_report": {
        "constraints": {
            "probe_fingerprint": True
        }
    }
}
```

The result is written to:

```text
recon_report.browser_fingerprint_probe
```

Captured evidence includes navigator, timezone, screen/viewport, WebGL,
canvas, and bounded font signals. Findings include webdriver exposure,
runtime/config mismatch, mobile/touch inconsistency, and WebGL/canvas risk.

## Verification

```text
python -m unittest autonomous_crawler.tests.test_browser_fingerprint_probe -v
Ran 22 tests
OK
```

## Next Best Move

After worker deliveries are accepted, run a controlled browser training target
with:

```text
constraints.probe_fingerprint=true
constraints.intercept_browser=true
constraints.observe_network=true
```

Then compare fingerprint findings with JS evidence and network observations to
decide whether Strategy should surface a unified anti-bot/browser-risk report.
