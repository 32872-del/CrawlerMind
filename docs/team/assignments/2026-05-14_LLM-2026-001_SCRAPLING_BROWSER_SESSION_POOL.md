# Assignment: Native Browser Session and Profile Pool

Date: 2026-05-14

Employee: LLM-2026-001

Track: SCRAPLING-ABSORB-2F

## Goal

Build CLM-native browser context leasing, persistent session reuse, and
profile pool support so `NativeBrowserRuntime` can absorb the useful
Scrapling browser/session behavior into CLM-owned runtime code.

This is a browser-capability task, not a site-rule task. Keep site-specific
logic out of runtime modules.

## Read First

- `docs/plans/2026-05-14_SCRAPLING_ABSORPTION_RECORD.md`
- `autonomous_crawler/runtime/native_browser.py`
- `autonomous_crawler/runtime/models.py`
- `autonomous_crawler/tools/browser_context.py`
- `autonomous_crawler/tools/browser_fingerprint.py`
- `autonomous_crawler/tools/session_profile.py`
- `autonomous_crawler/tests/test_native_browser_runtime.py`
- `autonomous_crawler/tests/test_browser_context.py`
- `autonomous_crawler/tests/test_scrapling_browser_runtime_contract.py`

## Write Scope

- `autonomous_crawler/runtime/native_browser.py`
- `autonomous_crawler/runtime/browser_pool.py` or an equivalent CLM-owned
  helper module
- `autonomous_crawler/tests/test_native_browser_runtime.py`
- `autonomous_crawler/tests/test_browser_context.py`
- `autonomous_crawler/tests/test_native_transition_comparison.py` if browser
  profile evidence needs extension
- `dev_logs/development/2026-05-14_LLM-2026-001_native_browser_session_pool.md`
- `docs/memory/handoffs/2026-05-14_LLM-2026-001_native_browser_session_pool.md`

## Do Not Modify

- `autonomous_crawler/runtime/native_static.py`
- `autonomous_crawler/runtime/native_parser.py`
- `autonomous_crawler/agents/planner.py`
- `autonomous_crawler/agents/strategy.py`
- site-specific training fixtures or real-site profiles

## Acceptance

- Native browser supports ephemeral and persistent session modes cleanly.
- Session mode, storage state, and protected/profile evidence remain visible in
  runtime output.
- Context reuse/lease behavior is deterministic and credential-safe.
- Tests cover persistent contexts, storage-state export, and browser profile
  consistency without requiring site-specific rules.

