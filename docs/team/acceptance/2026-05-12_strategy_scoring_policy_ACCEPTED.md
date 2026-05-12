# Acceptance: CAP-5.1 Strategy Scoring Policy

Date: 2026-05-12
Employee: LLM-2026-000
Status: accepted

## Accepted Scope

Accepted first-stage conservative strategy scorecard policy.

## Evidence

- `autonomous_crawler/tools/strategy_scoring.py`
- `autonomous_crawler/tests/test_strategy_scoring.py`
- `autonomous_crawler/agents/strategy.py`

## Acceptance Checks

- Strong DOM evidence scores `http` highest.
- Browser-observed API evidence scores `api_intercept` highest when DOM is absent.
- Challenge evidence recommends `manual_handoff` and executable browser mode.
- Signature/crypto evidence penalizes naive API replay and recommends deeper recon.
- WebSocket evidence increases browser/deeper-recon scores.
- Strategy attaches scorecard but does not override deterministic mode.
- Strategy emits a mismatch warning when advisory and deterministic routing differ.

## Verification

```text
python -m unittest autonomous_crawler.tests.test_strategy_scoring autonomous_crawler.tests.test_strategy_evidence autonomous_crawler.tests.test_strategy_js_evidence -v
Ran 73 tests
OK

python -m unittest discover -s autonomous_crawler/tests
Ran 1020 tests in 69.209s
OK (skipped=4)
```

## Remaining Risks

- Scorecard is not yet allowed to drive final mode selection.
- Weight values are intentionally simple and need real-site calibration.
- Manual handoff/deeper recon are advisory action labels, not executable workflow branches yet.
