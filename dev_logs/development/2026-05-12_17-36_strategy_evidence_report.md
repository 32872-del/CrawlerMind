# CAP-5.1 Strategy Evidence Report — Dev Log

Date: 2026-05-12
Employee: LLM-2026-000
Assignment: CAP-5.1 StrategyEvidenceReport + reverse-engineering action hints

## Capability IDs Covered

- CAP-5.1 Strategy evidence reasoning
- CAP-2.1 JS reverse-engineering evidence consumption
- CAP-2.2 signature/encryption entry-point localization
- CAP-1.2 transport diagnostics as strategy evidence
- CAP-1.4 WebSocket evidence as strategy input
- CAP-4.2 runtime fingerprint evidence as strategy input
- CAP-6.2 anti-bot/access diagnostics evidence

## Files Changed

- `autonomous_crawler/tools/strategy_evidence.py` — new unified evidence report module
- `autonomous_crawler/agents/strategy.py` — attaches evidence report and reverse-engineering hints
- `autonomous_crawler/tests/test_strategy_evidence.py` — new focused tests

## What Changed

Added a normalized `StrategyEvidenceReport` layer that converts Recon output into ranked strategy evidence:

- DOM repeated-item evidence
- observed API candidates
- JS endpoint/category evidence
- crypto/signature/encryption evidence
- transport diagnostics
- browser fingerprint runtime probe
- challenge/access diagnostics
- WebSocket summary evidence

Strategy now attaches:

- `crawl_strategy.strategy_evidence`
- `crawl_strategy.reverse_engineering_hints` when crypto/signature clues exist
- `crawl_strategy.api_replay_warning="signature_or_encryption_evidence"` when API replay may need runtime signature/encryption inputs

## Boundary

This is advisory and evidence-only. It does not execute JavaScript, recover keys, solve challenges, force API replay, or override stronger deterministic routing decisions.

Good DOM still wins. Browser/challenge routing remains conservative. JS and crypto evidence explain risk and next actions.

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

## Follow-ups

- Let Strategy consume `websocket_summary` more actively after CAP-1.4 worker delivery is formally accepted.
- Add profile-driven strategy scoring so evidence can influence mode choice through explicit scoring rules, not scattered conditionals.
- Add JS sandbox/hook implementation later for the hints emitted here.
