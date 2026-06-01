# 2026-05-19 - Access Evidence Pack Bridge

## Goal

Move AI managed mode one step closer to a real observe-decide-act loop by giving
managed decisions compact backend evidence instead of only text diagnostics.

## Changes

- Added `access-evidence/v1` snapshots to `build_run_evidence_pack()`.
- Sampled existing backend state into access evidence:
  - failure buckets
  - recent failures
  - challenge/captcha-like signals
  - runtime events
  - XHR/API candidates
  - browser/runtime artifacts
  - recommended runtime and decision hints
- Updated `inspect_access` managed action to return both an evidence request and
  the current access evidence snapshot.
- Added `managed-action-evidence/v1` to managed action results.
- Updated `managed-step` so the latest access snapshot is persisted back into
  `evidence_pack.access_evidence`.
- Upgraded `inspect_access` to support an optional live browser/XHR probe
  (`live_probe=true` or `CLM_LIVE_ACCESS_PROBE=1`) that produces an
  `access-probe/v1` snapshot and stores it under `probe_snapshot`.
- Folded the latest probe snapshot back into `access_evidence` so future
  managed decisions can see active runtime evidence instead of only historical
  samples.
- Updated frontend task detail data flow so task status can carry the access
  evidence fields.
- Updated the frontend workflow API runbook.

## Verification

```text
python -m unittest autonomous_crawler.tests.test_managed_actions autonomous_crawler.tests.test_product_workflow_api.ManagedAIRunTests.test_status_and_managed_step_include_evidence_pack -v
OK

python -m compileall autonomous_crawler -q
OK

npm --prefix frontend run build
OK
```

## Result

AI managed mode can now inspect a compact crawler evidence packet before
planning repairs. This does not solve hard-site collection by itself, but it
connects the model to actual backend evidence such as access/challenge signals,
runtime events, XHR/API candidates, and missing evidence.

## Next Step

Use the new live access probe to decide whether the backend should expose a
dedicated API for access sampling, then make the frontend show the probe result
more cleanly in Chinese after the existing mojibake-heavy task detail component
is cleaned up.
