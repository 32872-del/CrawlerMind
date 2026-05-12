# CAP-5.1 Strategy Scoring Policy — Dev Log

Date: 2026-05-12
Employee: LLM-2026-000
Assignment: CAP-5.1 StrategyScoringPolicy

## Capability IDs Covered

- CAP-5.1 Strategy evidence reasoning
- CAP-6.2 Evidence/audit
- CAP-2.2 Signature/encryption replay-risk planning
- CAP-1.4 WebSocket evidence consumption
- CAP-4.2 Fingerprint evidence consumption

## Files Changed

- `autonomous_crawler/tools/strategy_scoring.py` — new conservative scorecard policy
- `autonomous_crawler/agents/strategy.py` — attaches `strategy_scorecard`, `strategy_guardrails`, and advisory mismatch warning
- `autonomous_crawler/tests/test_strategy_scoring.py` — focused scorecard tests

## What Changed

Added a conservative `StrategyScoringPolicy` layer that consumes `StrategyEvidenceReport` and scores:

- `http`
- `api_intercept`
- `browser`
- `deeper_recon`
- `manual_handoff`

The scorecard is attached to every strategy as:

```text
crawl_strategy.strategy_scorecard
crawl_strategy.strategy_guardrails
```

When scorecard guidance differs from deterministic routing, Strategy now records:

```text
crawl_strategy.strategy_scorecard_warning
```

## Important Boundary

This is advisory-first. It does not replace the deterministic Strategy mode yet.

Preserved behavior:

- Good DOM remains DOM parsing.
- Observed API remains usable.
- Challenge evidence favors browser/manual review and penalizes unsafe API replay.
- Crypto/signature evidence emits replay-risk guidance but does not execute JS.

## Verification

```text
python -m unittest autonomous_crawler.tests.test_strategy_scoring autonomous_crawler.tests.test_strategy_evidence autonomous_crawler.tests.test_strategy_js_evidence -v
Ran 73 tests
OK

python -m unittest autonomous_crawler.tests.test_api_intercept autonomous_crawler.tests.test_access_diagnostics autonomous_crawler.tests.test_fetch_policy autonomous_crawler.tests.test_workflow_mvp -v
Ran 101 tests
OK

python -m unittest discover -s autonomous_crawler/tests
Ran 1020 tests in 69.209s
OK (skipped=4)

python -m compileall autonomous_crawler run_skeleton.py run_baidu_hot_test.py run_results.py run_simple.py clm.py
OK
```

## Notes

Full suite emitted non-failing ResourceWarnings around sqlite/socket cleanup in broader browser/proxy tests. Track separately; not caused by this scoring module.
