# Handoff: CAP-5.1 Strategy JS Evidence QA

Employee: LLM-2026-001
Date: 2026-05-12
Status: complete

## Summary

Audited and tested Strategy consumption of `recon_report.js_evidence`. Expanded
test file from 3 to 58 tests proving JS evidence is advisory and cannot override
stronger deterministic evidence. No production code edited.

## Deliverables

- `autonomous_crawler/tests/test_strategy_js_evidence.py` — 58 tests across 11 classes
- `dev_logs/development/2026-05-12_16-08_cap_5_1_strategy_js_evidence_qa.md`

## Key Findings

1. **JS evidence is advisory-only**: `_attach_js_evidence_hints()` adds `js_evidence_hints`, `js_evidence_warning`, and rationale text — none change mode, selectors, or extraction_method.

2. **Cannot force mode change**: JS endpoints only fill a missing `api_endpoint` when strategy is ALREADY `api_intercept` mode with empty endpoint. Cannot switch from http or browser to api_intercept.

3. **Evidence priority correct**: DOM > high-confidence API > browser > fallback API > static. JS evidence never breaks this ordering.

4. **Challenge clues are warning-only**: challenge/fingerprint/anti_bot categories set `js_evidence_warning` and annotate rationale, but do not force browser or api_intercept mode. Good DOM still wins.

5. **Deduplication works**: endpoints and calls deduped via `seen` set, capped at 10 each. Categories sorted+deduped. High-score sources capped at 5.

6. **Edge cases safe**: None/non-dict/malformed inputs handled gracefully, no crashes.

## Test Coverage

| Requirement | Tests | Status |
| --- | --- | --- |
| DOM stays dom_parse with JS endpoints | DomDominanceTests (3) | PASS |
| High-confidence API > JS hints | ApiCandidateDominanceTests (3) | PASS |
| Challenge clues → warning, not routing | ChallengeSafetyTests (6) | PASS |
| Deduplication | DeduplicationTests (6) | PASS |
| Rationale bounded | RationaleBoundsTests (5) | PASS |
| Edge cases | EdgeCaseTests (8) | PASS |
| Endpoint fill safety | EndpointFillTests (5) | PASS |
| Unit tests for helpers | BuildHintsTests (8), AttachHintsUnitTests (8) | PASS |
| Browser mode safety | BrowserModeTests (3) | PASS |
| Combined scenarios | CombinedScenarioTests (3) | PASS |

## Recommendation

**Accept.** JS evidence consumption is safe, conservative, and explainable. No production bugs found. No code changes needed.
