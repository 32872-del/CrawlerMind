# CAP-5.1 Strategy and AntiBot Calibration — Dev Log

Date: 2026-05-13
Employee: LLM-2026-001
Assignment: CAP-5.1 Strategy and AntiBot calibration

## Files Changed

- `autonomous_crawler/tests/test_strategy_scoring.py` — expanded from 7 to 34 tests
- `autonomous_crawler/tests/test_anti_bot_report.py` — expanded from 6 to 56 tests

## Capability IDs Covered

- CAP-5.1 Strategy scoring policy calibration
- CAP-6.2 AntiBot report boundary calibration

## What Was Calibrated

### test_strategy_scoring.py (7 → 34 tests)

New test classes added:

| Class | Tests | What it proves |
| --- | --- | --- |
| ScoreClampingTests | 4 | Negative scores clamped to 0, score>100 clamped, zero-score signals still record reasons |
| ConfidenceThresholdTests | 4 | high (top>=80, gap>=25), medium (top>=50), low, empty→low |
| EmptySignalsTests | 3 | All candidates at 0, evidence_only_no_bypass guardrail present, http wins when tied |
| BlockedApiPenaltyTests | 3 | api_intercept -35, browser +20, deeper_recon +25, guardrail added |
| StrongDomVsChallengeInteractionTests | 3 | Challenge overrides DOM boost, challenge+crypto both guardrails, DOM+blocked API→http wins |
| GuardrailDedupTests | 1 | Duplicate guardrails deduped in output |
| CandidateReasonDedupTests | 2 | Duplicate reasons/penalties deduped in to_dict() |
| AllCandidatesPresentTests | 2 | All 5 candidates always present, count is exactly 5 |
| MultipleSignalInteractionTests | 3 | challenge+WS, transport+fingerprint, js_rendering+observed_api |
| ExecutableModeSelectionTests | 2 | Advisory actions cannot be executable mode, http is first when tied |

### test_anti_bot_report.py (6 → 56 tests)

New test classes added:

| Class | Tests | What it proves |
| --- | --- | --- |
| RiskScoreCappingTests | 2 | Score capped at 100, math is correct (2×24=48) |
| RiskLevelThresholdTests | 5 | critical (severity or >=90), high (severity or >=55), medium (severity or >=25), low, score>=90→critical |
| FindingDedupTests | 1 | Findings deduplicated by (code, source) |
| CategoryDedupTests | 1 | Categories list has no duplicates |
| SafePayloadRedactionTests | 10 | password, token, api_key, apikey, authorization, cookie, proxy_url, error, 500-char limit, list truncation, nested redaction |
| SummarizeReportTests | 6 | None→defaults, AntiBotReport input, dict input, categories cap at 8, top_findings cap at 3, invalid type→defaults |
| RecommendedActionTests | 6 | rate_limit→backoff, login→authorized_session_review, crypto→deeper_recon, fingerprint→browser_render, scorecard fallback, executable mode |
| MultipleGuardrailsTests | 3 | crypto+challenge both guardrails, proxy guardrail, 4 base guardrails always present |
| NextStepsTests | 4 | challenge, empty→standard HTTP, rate limit, proxy |
| EvidenceSourcesTests | 2 | Sources from findings, sources deduped |
| FindingSerializationTests | 2 | to_dict has all fields, evidence redacted |

## Bugs Found

None. All calibration tests pass against existing production code. The scoring policy and anti-bot report boundaries are correctly implemented.

## Key Calibration Findings

1. **Score clamping works correctly**: `to_dict()` clamps negative scores to 0, `_bounded_score()` clamps signal scores to [0,100].
2. **Confidence thresholds are stable**: high/medium/low boundaries match specification.
3. **Strong DOM priority preserved**: Even with challenge+crypto, DOM boost (+20 http, -15 api) still applies. Challenge overrides via post-processing (-60 api, +70 manual_handoff).
4. **Blocked API penalties correct**: -35 api, +20 browser, +25 deeper_recon, guardrail added.
5. **Risk score math correct**: SEVERITY_WEIGHT sum capped at 100.
6. **Deduplication works**: Findings by (code, source), categories by value, guardrails by value, reasons/penalties by value.
7. **Safe payload redaction comprehensive**: 7 sensitive key patterns, proxy URLs, error messages, 500-char string limit, 20-item list limit.
8. **Recommended action priority chain correct**: captcha→manual_handoff, login→authorized_session_review, rate_limit→backoff, crypto→deeper_recon, fingerprint/transport/runtime→browser_render, high/critical→manual_handoff, scorecard→standard_http.

## Tests Run

```
test_strategy_scoring:   34 OK
test_anti_bot_report:    56 OK
test_strategy_evidence:   8 OK
test_access_diagnostics:  9 OK
full suite:            1111 OK (4 skipped — real browser smoke)
```
