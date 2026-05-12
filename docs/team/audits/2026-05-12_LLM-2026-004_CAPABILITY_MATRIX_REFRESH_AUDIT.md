# Capability Matrix Refresh Audit

Employee ID: `LLM-2026-004`
Display Name: Worker Delta
Project role: `ROLE-CAPABILITY-DOC-AUDIT`
Date: 2026-05-12
Status: complete

## Scope

Assignment:

```text
docs/team/assignments/2026-05-12_LLM-2026-004_CAPABILITY_MATRIX_REFRESH_AUDIT.md
```

Allowed write scope was limited to the capability matrix plus this audit, dev
log, and handoff. Production code, `PROJECT_STATUS.md`, and
`docs/team/TEAM_BOARD.md` were read but not edited.

## Documents Updated

Updated documents: 1

- `docs/plans/2026-05-12_CAPABILITY_IMPLEMENTATION_MATRIX.md`

Created audit artifacts:

- `docs/team/audits/2026-05-12_LLM-2026-004_CAPABILITY_MATRIX_REFRESH_AUDIT.md`
- `dev_logs/audits/2026-05-12_16-20_capability_matrix_refresh_audit.md`
- `docs/memory/handoffs/2026-05-12_LLM-2026-004_capability_matrix_refresh_audit.md`

## Refresh Summary

The capability matrix was rewritten from mojibake/garbled Chinese into readable
Chinese and refreshed for 2026-05-12 capability work.

Key status corrections:

- CAP-2.1 changed from effectively "not started" to "initial": JS asset
  inventory, pre-AST static analysis, and JS evidence integration exist.
- CAP-4.2 expanded from basic browser context to config-side fingerprint report
  plus opt-in runtime fingerprint probe.
- CAP-4.4 changed from "not started" to "initial": browser resource
  interception exists but is opt-in.
- CAP-5.1 updated to include Strategy JS evidence advisory.

Honest wording added:

- JS analysis is a static-analysis/string-table foundation, not full AST.
- Fingerprint profile is config-side unless the separate runtime probe is
  explicitly enabled.
- Browser interception requires `constraints.intercept_browser=true`.
- JS evidence is advisory and does not override stronger DOM/API/challenge
  evidence.

## Inconsistencies Found

### Finding 1: Capability matrix was stale and unreadable

Severity: high

The matrix file was mostly mojibake and still described CAP-2.1 and CAP-4.4 as
not started. This directly conflicted with accepted 2026-05-12 work:

- `browser_interceptor.py`
- `js_asset_inventory.py`
- `js_static_analysis.py`
- `js_evidence.py`
- Strategy JS evidence advisory

Action taken: replaced the matrix with readable Chinese and current status.

### Finding 2: CAP-2.1 wording risked overstating AST maturity

Severity: medium

Project assignments and older matrix language used "AST" wording. The delivered
implementation is useful but regex/token/static-analysis based, not parser-backed
AST, control flow, data flow, source-map, or deobfuscation work.

Action taken: matrix now says "JS reverse-engineering foundation / pre-AST
static analysis" and records parser-backed AST as a remaining gap.

### Finding 3: CAP-4.2 needed separation between config-side report and runtime probe

Severity: medium

`browser_fingerprint.py` and `browser_fingerprint_probe.py` are different
capabilities. One reports consistency from `BrowserContextConfig`; the other
launches Playwright to gather runtime evidence. Older wording could collapse
these into a single "fingerprint support" claim.

Action taken: matrix now separates config-side report, opt-in runtime probe, and
remaining gaps. It explicitly says no stealth/spoofing or fingerprint pool is
implemented.

### Finding 4: CAP-4.4 browser interception needed opt-in wording

Severity: medium

Browser interception is powerful and should not be implied as default behavior.
The current code path requires `constraints.intercept_browser=true`.

Action taken: matrix now states browser interception is opt-in and default Recon
does not intercept browser resources.

### Finding 5: CAP-5.1 Strategy JS evidence must remain advisory

Severity: medium

Strategy now reads `recon_report.js_evidence`, but the implementation is
careful: it adds hints and warnings, and only fills a missing endpoint after
`api_intercept` has already been selected.

Action taken: matrix now documents this as advisory strategy evidence reasoning,
not an automatic override system.

### Finding 6: PROJECT_STATUS is mostly current but outside allowed write scope

Severity: low

`PROJECT_STATUS.md` already records the new CAP-2.1/CAP-4.2/CAP-4.4/CAP-5.1
work and test status, including 763 tests. It was not edited because the
assignment only allowed matrix/audit/handoff/log writes.

Risk: if supervisor later wants exact alignment, `PROJECT_STATUS.md` should be
checked after WebSocket MVP lands because current local full-suite test output
differs from the status file.

### Finding 7: TEAM_BOARD has active pending tasks that are newer than the matrix refresh

Severity: low

`TEAM_BOARD.md` correctly shows CAP-5.1 Strategy JS Evidence QA and CAP-1.4
WebSocket Observation MVP as assigned/pending. This matches the current working
tree state. It was not edited.

Risk: once 001/002 are accepted, the board and matrix need a follow-up sync.

## Verification

Required command was run:

```text
python -m unittest discover -s autonomous_crawler/tests
Ran 888 tests in 48.354s
FAILED (failures=3, errors=1, skipped=4)
```

Failures were in the current unaccepted WebSocket observer work:

- `test_websocket_observer.TestObserveWebsocket.test_multiple_ws_connections`
- `test_websocket_observer.TestObserveWebsocket.test_navigation_error`
- `test_websocket_observer.TestObserveWebsocket.test_websocket_with_frames`
- `test_websocket_observer.TestObserveWebsocket.test_to_dict_serialization`

Assessment: this failure is not caused by the matrix documentation refresh. It
is a parallel capability implementation risk from the in-progress CAP-1.4
WebSocket task.

## Remaining Stale-Doc Risks

- Older audit/dev-log/acceptance documents still mention pre-refresh status and
  may say CAP-2.1 or CAP-4.4 were not started at the time they were written.
  Those are historical records and should not be rewritten unless they are
  surfaced as current onboarding docs.
- `PROJECT_STATUS.md` says the latest full test status is 763 tests OK, while
  the current dirty workspace ran 888 tests with WebSocket failures. This should
  be refreshed only after CAP-1.4 WebSocket work is accepted or fixed.
- `TEAM_BOARD.md` has assigned pending tasks; it should be synced after the
  supervisor accepts or rejects CAP-5.1 QA and CAP-1.4 WebSocket.
- README/quick-start docs were not in this assignment's required reading and may
  still not describe the newest advanced capability modules.

## Supervisor Recommendation

Accept the matrix refresh as a documentation correction, with one caveat:

- Do not update public status docs to claim full suite green until the WebSocket
  observer tests are fixed or the in-progress tests are isolated/skipped.

Recommended next supervisor action:

1. Ask the CAP-1.4 WebSocket worker to fix the four failing WebSocket observer
   tests or mark the assignment not accepted.
2. After CAP-1.4 resolution, refresh `PROJECT_STATUS.md` and `TEAM_BOARD.md`
   test/status counts in one supervisor-controlled pass.
3. Keep the matrix wording conservative: static JS analysis, opt-in browser
   interception, config-side fingerprint report, opt-in runtime probe.
