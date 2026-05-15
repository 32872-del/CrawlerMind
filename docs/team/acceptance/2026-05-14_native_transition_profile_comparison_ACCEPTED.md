# Acceptance: Native Profile Comparison Harness

Date: 2026-05-14

Employee: LLM-2026-000 / Supervisor Codex

Track: SCRAPLING-ABSORB-2B

Status: accepted

## Scope Accepted

Expanded the native-vs-transition comparison helper into a reusable profile
comparison entrypoint:

- `run_native_transition_comparison_2026_05_14.py`
- `autonomous_crawler/tests/test_native_transition_comparison.py`
- `autonomous_crawler/tests/fixtures/native_transition_profile.json`
- `clm.py`

## What Changed

- Added `--suite profile`.
- Added `--profile <json>` support with `{base_url}` placeholder replacement.
- Added a bundled local profile fixture containing:
  - product-card catalog
  - JSON-LD/script coexistence
  - local SPA product list
- Comparison summaries now include:
  - captured XHR count and preview
  - runtime event types
  - artifact kinds
  - fingerprint risk
  - expectation results
  - captured XHR and artifact deltas
- `clm.py train --round native-vs-transition-profile` now prints the new
  profile comparison command.

## Verification

```text
python -m unittest autonomous_crawler.tests.test_native_transition_comparison -v
Ran 14 tests
OK

python run_native_transition_comparison_2026_05_14.py --suite profile --profile autonomous_crawler\tests\fixtures\native_transition_profile.json
profile comparison completed, review=false for all bundled scenarios

python -m unittest autonomous_crawler.tests.test_clm_cli -v
profile round command prints correctly
```

## Acceptance Notes

This accepts the reusable profile comparison entrypoint and profile-driven
training evidence. It does not yet claim real external dynamic/ecommerce
profile parity.

Next work:

1. Add real dynamic/ecommerce profile files.
2. Keep profile rules outside runtime modules.
3. Use profile evidence to calibrate the real training ladder.
