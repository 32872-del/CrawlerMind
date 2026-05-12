# Acceptance: Strategy JS Evidence Advisory

Date: 2026-05-12

Owner: `LLM-2026-000`

Status: accepted

## Capability IDs

- `CAP-5.1` Evidence-assisted strategy reasoning
- `CAP-2.1` JS reverse-engineering evidence
- `CAP-5.4` Strategy anomaly/risk hints

## Completed Outputs

- Strategy now reads `recon_report.js_evidence`.
- Adds bounded advisory hints under `crawl_strategy.js_evidence_hints`.
- Adds `crawl_strategy.js_evidence_warning` when challenge/fingerprint/anti-bot
  categories appear in JS evidence.
- Extends strategy rationale with readable JS evidence notes.
- Can fill a missing `api_endpoint` for an already selected `api_intercept`
  strategy from JS evidence endpoints.
- Does not override strong deterministic choices:
  - good DOM stays DOM;
  - observed API candidates remain stronger than JS string hints;
  - challenge/browser routing remains conservative.

## Verification

```text
python -m unittest autonomous_crawler.tests.test_strategy_js_evidence autonomous_crawler.tests.test_api_intercept autonomous_crawler.tests.test_access_diagnostics -v
python -m unittest discover -s autonomous_crawler/tests
```

Final result:

```text
Ran 763 tests in 50.649s
OK (skipped=4)
```

## Remaining Gaps

- JS evidence does not yet create first-class API candidates in Recon.
- Strategy does not yet generate hook plans.
- Real-site training is still needed to tune confidence thresholds.
