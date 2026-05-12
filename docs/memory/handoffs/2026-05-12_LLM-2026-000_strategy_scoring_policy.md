# Handoff: CAP-5.1 Strategy Scoring Policy

Employee: LLM-2026-000
Date: 2026-05-12
Status: complete

## Summary

Implemented the first conservative StrategyScoringPolicy. It turns normalized strategy evidence into a scorecard for `http`, `api_intercept`, `browser`, `deeper_recon`, and `manual_handoff`.

## Deliverables

- `autonomous_crawler/tools/strategy_scoring.py`
- `autonomous_crawler/tests/test_strategy_scoring.py`
- `autonomous_crawler/agents/strategy.py`
- `dev_logs/development/2026-05-12_18-21_strategy_scoring_policy.md`

## Strategy Output Added

- `crawl_strategy.strategy_scorecard`
- `crawl_strategy.strategy_guardrails`
- `crawl_strategy.strategy_scorecard_warning` when advisory recommendation differs from deterministic routing

## Design Decision

The scorecard is advisory, not authoritative. The current deterministic Strategy mode is preserved to avoid breaking known working routes while the scorecard gathers evidence for future training.

## Verification

```text
python -m unittest discover -s autonomous_crawler/tests
Ran 1020 tests in 69.209s
OK (skipped=4)
```

## Next Step

After worker outputs are formally accepted, decide whether to let scorecard influence mode choice in narrow cases:

1. challenge -> browser/manual review
2. crypto/signature -> deeper_recon warning before API replay
3. WebSocket -> browser/deeper_recon training scenario
4. strong DOM -> lock DOM unless API evidence is very high and safe
