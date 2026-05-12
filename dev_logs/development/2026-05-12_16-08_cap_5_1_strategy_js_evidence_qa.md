# CAP-5.1 Strategy JS Evidence QA — Dev Log

Date: 2026-05-12
Employee: LLM-2026-001
Assignment: CAP-5.1 Strategy JS Evidence QA

## Files Changed

- `autonomous_crawler/tests/test_strategy_js_evidence.py` — expanded from 3 to 58 tests

## Capability IDs Covered

- CAP-5.1 NLP/evidence-assisted strategy reasoning
- CAP-2.1 JS reverse-engineering evidence
- CAP-5.4 anomaly/risk detection

## Audit Approach

Read-only audit of `strategy.py` `_attach_js_evidence_hints()` and `_build_js_evidence_hints()`.
No production code edited. Tests prove JS evidence is advisory and cannot override
stronger deterministic evidence.

## Key Findings

### 1. JS evidence is correctly advisory

`_attach_js_evidence_hints()` only attaches:
- `strategy["js_evidence_hints"]` — a dict of endpoints, calls, categories, high-score sources
- `strategy["js_evidence_warning"]` — set only when challenge/fingerprint/anti_bot categories present
- Appends to `strategy["rationale"]` — text annotation

None of these change the strategy mode, extraction_method, or selectors.

### 2. JS evidence cannot force mode change

The ONLY place JS evidence can affect strategy behavior is lines 314-319:
```python
if (
    strategy.get("mode") == "api_intercept"
    and not strategy.get("api_endpoint")
    and hints.get("api_endpoints")
):
    strategy["api_endpoint"] = hints["api_endpoints"][0]
    strategy["api_endpoint_source"] = "js_evidence"
```

This requires ALL three conditions:
- Strategy is ALREADY in `api_intercept` mode (determined by deterministic logic)
- `api_endpoint` is empty (no observed candidate URL)
- JS evidence has endpoints

JS evidence cannot switch strategy from http/dom_parse or browser to api_intercept.

### 3. Evidence priority is correct

Verified priority order:
1. Good DOM candidates (item_count >= 2 + title selector) → http/dom_parse
2. High-confidence observed API (score >= 50, browser_network_observation, json/graphql) → api_intercept
3. Browser mode (SPA, challenge, browser rendering) → browser
4. Fallback API (any api_candidates list) → api_intercept
5. Static fallback → http/dom_parse

JS evidence never breaks this ordering.

### 4. Challenge/fingerprint clues are warning-only

When JS evidence contains challenge/fingerprint/anti_bot categories:
- `js_evidence_warning = "challenge_or_fingerprint_clues"` is set
- Rationale gets annotated
- But mode is NOT forced to browser or api_intercept
- Good DOM still wins over challenge JS clues

### 5. Deduplication works correctly

- `_dedupe_strings()` uses `seen` set for O(1) dedup
- Endpoints capped at 10, calls capped at 10
- Categories sorted and deduped via `sorted(set(...))`
- High-score sources capped at 5

### 6. Edge cases are safe

- `js_evidence=None` → no crash
- `js_evidence="not a dict"` → silently ignored
- Non-dict items in `items` list → filtered out
- Empty endpoint strings → filtered by `_dedupe_strings`

## Test Classes (58 tests)

| Class | Count | What it proves |
| --- | --- | --- |
| DomDominanceTests | 3 | Good DOM stays dom_parse with JS endpoints |
| ApiCandidateDominanceTests | 3 | High-score API wins over JS; low-score uses fallback |
| ChallengeSafetyTests | 6 | Challenge/fingerprint clues add warnings, not mode changes |
| DeduplicationTests | 6 | Endpoints/calls deduped, order preserved, limit respected |
| RationaleBoundsTests | 5 | Rationale stays bounded and readable |
| EdgeCaseTests | 8 | None/dict/malformed inputs handled safely |
| EndpointFillTests | 5 | JS fills missing endpoint only in api_intercept mode |
| BuildHintsTests | 8 | _build_js_evidence_hints unit tests |
| AttachHintsUnitTests | 8 | _attach_js_evidence_hints isolated unit tests |
| BrowserModeTests | 3 | Browser mode not downgraded by JS evidence |
| CombinedScenarioTests | 3 | DOM > API > JS priority verified end-to-end |

## Tests Run

```
test_strategy_js_evidence:     58 OK
test_api_intercept:            72 OK
test_access_diagnostics:       72 OK (same suite)
full suite:                   866 OK (5 failures in test_websocket_observer, pre-existing, unrelated)
```

## Verdict

**Strategy JS evidence is safe to accept.** JS evidence is purely advisory:
- Adds hints and warnings to strategy output
- Cannot change mode, selectors, or extraction method
- Cannot override good DOM or high-confidence API candidates
- Challenge/fingerprint clues produce warnings, not routing changes
- Deduplication prevents noise
- Edge cases are handled gracefully

No production code changes needed.
