# Acceptance: CAP-5.1 Strategy Evidence Report

Date: 2026-05-12
Employee: LLM-2026-000
Status: accepted

## Accepted Scope

Accepted supervisor mainline work for a unified Strategy evidence report and reverse-engineering action hints.

## Evidence

- New module: `autonomous_crawler/tools/strategy_evidence.py`
- New tests: `autonomous_crawler/tests/test_strategy_evidence.py`
- Strategy integration: `autonomous_crawler/agents/strategy.py`

## Acceptance Checks

- DOM evidence produces `dom_repeated_items`.
- Browser-observed API evidence produces `observed_api_candidate`.
- Crypto/signature evidence produces `reverse_engineering_hints`.
- API replay mode receives `api_replay_warning` when signature/encryption evidence is present.
- Good DOM still wins and does not receive API replay warning.
- Challenge, transport, fingerprint, and WebSocket evidence are represented.
- Malformed recon payloads do not crash the report builder.

## Verification

```text
python -m unittest autonomous_crawler.tests.test_strategy_evidence autonomous_crawler.tests.test_strategy_js_evidence autonomous_crawler.tests.test_js_crypto_analysis -v
Ran 73 tests
OK

python -m unittest discover -s autonomous_crawler/tests
Ran 968 tests in 46.115s
OK (skipped=4)

python -m compileall autonomous_crawler run_skeleton.py run_baidu_hot_test.py run_results.py run_simple.py clm.py
OK
```

## Remaining Risks

- This is still evidence and action planning, not JS execution or runtime hook implementation.
- Strategy mode selection is still mostly condition-based. The next improvement should be an explicit evidence scoring policy.
