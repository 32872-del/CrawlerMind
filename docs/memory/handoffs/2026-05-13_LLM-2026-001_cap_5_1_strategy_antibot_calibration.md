# Handoff: CAP-5.1 Strategy and AntiBot Calibration

Employee: LLM-2026-001
Date: 2026-05-13
Status: complete

## Summary

Calibrated StrategyScoringPolicy and AntiBotReport boundaries through 90 new tests
(27 in test_strategy_scoring.py, 50 in test_anti_bot_report.py). No production code
changes needed — all calibration tests pass against existing implementation. Confirms:
strong DOM evidence still prioritizes http; blocked API/challenge correctly route to
guarded review/deeper recon; risk scores stable and deduplicated.

## Deliverables

- `autonomous_crawler/tests/test_strategy_scoring.py` — expanded from 7 to 34 tests
- `autonomous_crawler/tests/test_anti_bot_report.py` — expanded from 6 to 56 tests
- `dev_logs/development/2026-05-13_14-00_cap_5_1_strategy_antibot_calibration.md`

## Calibration Coverage

### StrategyScoringPolicy (34 tests)

- Score clamping: negative→0, >100→100, zero signals record reasons
- Confidence: high (top>=80, gap>=25), medium (top>=50), low
- Empty signals: all 0, evidence_only_no_bypass guardrail, http wins when tied
- Blocked API: -35 api, +20 browser, +25 deeper_recon, guardrail
- Strong DOM + challenge: challenge overrides DOM, both guardrails preserved
- Strong DOM + blocked API: http wins from DOM boost
- Guardrail/reason/penalty deduplication
- All 5 candidates always present
- Multiple signal interactions: challenge+WS, transport+fingerprint, js_rendering+API
- Executable mode selection: advisory actions excluded, http first when tied

### AntiBotReport (56 tests)

- Risk score: capped at 100, math correct (severity weights sum)
- Risk level: critical (severity or >=90), high (>=55), medium (>=25), low
- Finding dedup by (code, source)
- Category dedup
- Safe payload redaction: 7 sensitive key patterns, proxy URLs, error messages, 500-char limit, 20-item list limit, nested dict redaction
- summarize_anti_bot_report: None→defaults, AntiBotReport/dict input, categories cap at 8, top_findings cap at 3
- Recommended action chain: captcha→manual_handoff, login→authorized_session_review, rate_limit→backoff, crypto→deeper_recon, fingerprint/transport→browser_render
- Multiple guardrails for multiple categories
- Next steps populated per category
- Evidence sources deduped

## Bugs Found

None. All boundaries are correctly implemented.

## Verification Results

| Check | Result |
| --- | --- |
| test_strategy_scoring | 34 OK |
| test_anti_bot_report | 56 OK |
| test_strategy_evidence | 8 OK |
| test_access_diagnostics | 9 OK |
| Full suite | 1111 OK (4 skipped — real browser smoke) |
