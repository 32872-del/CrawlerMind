# Acceptance: CAP-5.1 Strategy and AntiBot Calibration

Date: 2026-05-14

Employee: LLM-2026-001

## Accepted Scope

- Expanded `autonomous_crawler/tests/test_strategy_scoring.py`.
- Expanded `autonomous_crawler/tests/test_anti_bot_report.py`.
- Added handoff and development log for CAP-5.1 calibration.
- Confirmed strategy scoring remains conservative:
  - strong DOM evidence can keep `http` as the executable path
  - challenge evidence remains guarded and advisory
  - blocked API evidence does not encourage unsafe replay
  - risk score, categories, guardrails, and summaries are stable and bounded

## Verification

```text
python -m unittest autonomous_crawler.tests.test_strategy_scoring autonomous_crawler.tests.test_anti_bot_report -v
Ran 82 tests
OK

python -m unittest autonomous_crawler.tests.test_strategy_evidence autonomous_crawler.tests.test_access_diagnostics -v
Ran 17 tests
OK

python -m unittest discover -s autonomous_crawler/tests
Ran 1111 tests
OK (skipped=4)
```

## Acceptance Notes

- No production code change was required for this worker task.
- The tests are valuable calibration coverage and safe to keep.
- Some handoff text has encoding artifacts, but the technical content is clear.

## Follow-up

- Calibrate on real training cases before allowing the scorecard to influence
  final executable mode more aggressively.
