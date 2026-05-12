# Acceptance: Unified AntiBotReport

Date: 2026-05-12

Employee: LLM-2026-000

Capability IDs:
- CAP-6.2 Evidence/audit
- CAP-5.1 Strategy evidence reasoning
- CAP-2.1 / CAP-2.2 JS and crypto evidence
- CAP-3.3 Proxy evidence
- CAP-1.4 WebSocket evidence
- CAP-4.2 Browser fingerprint evidence

## Accepted Scope

- Added `autonomous_crawler/tools/anti_bot_report.py`.
- Strategy now attaches `crawl_strategy.anti_bot_report`.
- The report consolidates:
  - access diagnostics and access policy decisions
  - HTTP 429 and blocked API candidate evidence
  - transport diagnostics
  - runtime browser fingerprint probe evidence
  - JS anti-bot clues and crypto/signature replay risk
  - WebSocket runtime dependency evidence
  - proxy health / proxy trace evidence with credential redaction
  - strategy warning evidence
- The report returns risk level, risk score, normalized categories, findings,
  recommended action, next steps, guardrails, and evidence sources.

## Verification

```text
python -m unittest autonomous_crawler.tests.test_anti_bot_report -v
Ran 6 tests
OK

python -m unittest autonomous_crawler.tests.test_anti_bot_report autonomous_crawler.tests.test_strategy_evidence autonomous_crawler.tests.test_strategy_scoring -v
Ran 21 tests
OK

python -m unittest autonomous_crawler.tests.test_access_diagnostics autonomous_crawler.tests.test_access_layer autonomous_crawler.tests.test_error_codes -v
Ran 97 tests
OK
```

## Safety Boundary

- Diagnostic/advisory only.
- Does not solve CAPTCHA.
- Does not bypass login or managed challenges.
- Does not execute or replay signed/encrypted APIs.
- Does not enable proxies automatically.
- Redacts proxy credentials, tokens, cookies, and sensitive error messages.

## Follow-up

- Calibrate report scoring on real training cases.
- Add compact AntiBotReport summaries to CLI/API responses.
- Use the report as an input to future controlled strategy escalation rules.
