# Dev Log: Native Transition Profile Comparison

Date: 2026-05-14

Owner: LLM-2026-000 / Supervisor Codex

Track: SCRAPLING-ABSORB-2B

## Goal

Turn the native-vs-transition comparison helper into a reusable profile-driven
training entrypoint.

## Work Completed

- Added `--suite profile` to the comparison runner.
- Added `--profile <json>` support with `{base_url}` substitution.
- Added a bundled local profile fixture with:
  - product-card catalog
  - JSON-LD/script coexistence
  - local SPA product list
- Added richer comparison evidence:
  - captured XHR preview
  - runtime event types
  - artifact kinds
  - fingerprint risk
  - expectation checks
  - capture/artifact deltas
- Added `clm.py train --round native-vs-transition-profile`.
- Added tests for profile loading, normalization, expectation checks, and CLI
  command printing.

## Smoke Result

```text
python run_native_transition_comparison_2026_05_14.py --suite profile --profile autonomous_crawler\tests\fixtures\native_transition_profile.json
review=false for all bundled scenarios
```

## Verification

```text
python -m unittest autonomous_crawler.tests.test_native_transition_comparison -v
Ran 14 tests
OK

python -m unittest autonomous_crawler.tests.test_clm_cli -v
OK
```

## Remaining Gaps

- Real external dynamic/ecommerce profile files are still pending.
- The current profile file is local-fixture based.
- Profile-driven rules still belong outside runtime modules.
