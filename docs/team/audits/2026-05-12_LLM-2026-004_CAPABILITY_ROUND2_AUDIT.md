# Capability Round 2 Audit

Employee ID: `LLM-2026-004`
Display Name: Worker Delta
Project role: `ROLE-CAPABILITY-AUDIT`
Date: 2026-05-12
Status: complete

## Scope

Audited the second capability sprint after 001/002 delivery:

- `CAP-4.2 Browser fingerprint profile and consistency`
- `CAP-2.1 Frontend JS reverse engineering / AST foundation`
- `CAP-1.2 TLS/transport diagnostics` context from the capability matrix

This audit checks whether the new modules move CLM closer to a top crawler
developer tool. It is not a documentation tidiness review.

## Files Reviewed

- `docs/plans/2026-05-12_CAPABILITY_IMPLEMENTATION_MATRIX.md`
- `docs/team/assignments/2026-05-12_LLM-2026-001_CAP-4.2_BROWSER_FINGERPRINT_PROFILE.md`
- `docs/team/assignments/2026-05-12_LLM-2026-002_CAP-2.1_JS_AST_STRING_TABLE.md`
- `PROJECT_STATUS.md`
- `autonomous_crawler/tools/browser_fingerprint.py`
- `autonomous_crawler/tests/test_browser_fingerprint.py`
- `autonomous_crawler/tools/js_static_analysis.py`
- `autonomous_crawler/tests/test_js_static_analysis.py`
- `autonomous_crawler/tools/browser_context.py`
- `autonomous_crawler/tools/js_asset_inventory.py`
- `docs/memory/handoffs/2026-05-12_LLM-2026-001_cap_4_2_browser_fingerprint.md`
- `docs/memory/handoffs/2026-05-12_LLM-2026-002_cap_2_1_js_static_analysis.md`

## Verification Run

```text
git pull origin main
Already up to date.

python -m unittest autonomous_crawler.tests.test_browser_fingerprint autonomous_crawler.tests.test_js_static_analysis -v
Ran 106 tests
OK

python -m unittest autonomous_crawler.tests.test_browser_context autonomous_crawler.tests.test_js_asset_inventory -v
Ran 73 tests
OK
```

## Overall Judgment

Recommendation: conditionally accept the worker deliveries.

Both delivered modules are real capability foundations, deterministic, generic,
and tested without external network or browser dependencies. They improve CLM's
ability to reason about crawler developer problems before running heavier tools:

- `browser_fingerprint.py` turns browser context configuration into a structured
  consistency report.
- `js_static_analysis.py` turns JS text into string/function/call evidence that
  can guide future JS capture, hook, and API discovery work.

However, both modules are still offline analysis helpers. They are not yet wired
into Recon, browser interception, artifact manifests, or strategy selection.
That integration is the next point where these capabilities become productized
instead of just available.

## Audit Questions

### 1. Do the delivered modules clearly map to CAP-4.2 and CAP-2.1?

Yes, with one naming caveat.

`browser_fingerprint.py` clearly maps to `CAP-4.2`: it normalizes
`BrowserContextConfig`, reports UA/viewport mismatch, locale/timezone mismatch,
default UA with custom profile, proxy/default locale-timezone mismatch, risk
level, and recommendations.

`js_static_analysis.py` maps to the current MVP interpretation of `CAP-2.1`:
string table, endpoint strings, suspicious function names, suspicious calls,
and ranked scoring. It is not a true AST parser yet, so docs and handoff should
continue calling this a static-analysis or string-table foundation rather than
completed AST reverse engineering.

### 2. Are they generic capabilities, or accidentally site-specific rules?

Mostly generic.

The JS suspicious keyword catalog includes common crawler-analysis clues such as
`sign`, `token`, `encrypt`, `captcha`, `fingerprint`, `wbi`, and `xbogus`.
Those are generic enough for a foundation, though `wbi` and `xbogus` are more
platform-flavored and should stay as examples within a broader keyword taxonomy,
not become site-specific workflow decisions.

The fingerprint checks are generic consistency heuristics and do not encode a
single target site.

### 3. Are secrets/session/proxy artifacts redacted where applicable?

Acceptable for this sprint.

The fingerprint profile stores only `storage_state_present` instead of the raw
storage path. Proxy output uses `redact_proxy_url()`, and tests confirm password
redaction. No session cookies, API keys, or proxy credentials are emitted by the
new reports during reviewed flows.

One future caution: the report includes full `user_agent`, locale, timezone, and
proxy presence. That is appropriate operational metadata, but if reports are
exported publicly they should be treated as runtime environment evidence.

### 4. Do tests prove behavior without external network or browser dependency?

Yes.

The added test files run as pure unit tests. They do not launch Playwright, open
network connections, or require API keys. The focused test run passed:

```text
Ran 106 tests
OK
```

Neighboring context/inventory tests also passed:

```text
Ran 73 tests
OK
```

### 5. What is the next highest-leverage capability?

Recommended next capability task: JS capture integration.

The strongest next step is to connect the already accepted browser interception
and JS asset inventory work to `js_static_analysis.py`, then persist the
analysis into artifact manifests and Recon evidence. This would turn:

```text
observe/intercept JS -> inventory assets -> analyze strings/functions/calls -> rank files/endpoints/hooks
```

into one practical capability path.

After that, the second-highest leverage task is real browser-side fingerprint
probing: launch a controlled context and compare configured values with
`navigator`, `screen`, `Intl`, WebGL/canvas/font, and WebRTC observations.

## Findings

### Finding 1: JS static analysis is not integrated with JS asset capture

Severity: medium

`js_static_analysis.py` is currently only referenced by its tests and handoff.
`rg` found no runtime call from Recon, `browser_interceptor.py`, or
`js_asset_inventory.py`. This means CLM has the new capability available, but
the main workflow cannot yet produce static JS evidence automatically.

Impact: useful but not yet productized. A user running CLM on a dynamic site
will not automatically get ranked string/function/call clues.

Recommendation: add a follow-up task to feed captured inline/external JS text
from browser interception or asset inventory into `analyze_js_static()`, then
store bounded results in `artifact_manifest` and `recon_report`.

### Finding 2: CAP-2.1 "AST" wording can overstate the implementation

Severity: medium

The assignment calls this `JS AST/String Table MVP`, and the capability matrix
labels CAP-2.1 as JS AST reverse engineering. The delivered module explicitly
uses regex/token heuristics and no AST parser. This is a valid MVP choice, but
it should remain documented as pre-AST static analysis.

Impact: future workers may assume AST-level coverage exists and build planning
or acceptance criteria on top of a stronger parser than the code provides.

Recommendation: conditionally accept as `CAP-2.1 static-analysis foundation`.
Create a later `CAP-2.1b` task for parser-backed AST extraction if/when needed.

### Finding 3: Browser fingerprint report is config-side only

Severity: medium

`browser_fingerprint.py` analyzes `BrowserContextConfig` values. It does not
probe a real browser runtime for `navigator.*`, `screen.*`, `Intl`, WebGL,
canvas, fonts, AudioContext, or WebRTC leak behavior. The worker handoff
states this gap clearly.

Impact: this is a good profile consistency checker, but it cannot yet prove
that Playwright's runtime surface matches the configured profile.

Recommendation: accept as the CAP-4.2 offline profile report, then assign a
browser-side probing follow-up after JS capture integration.

### Finding 4: Locale/timezone mapping heuristics are intentionally shallow

Severity: low

The locale-to-timezone mapping is useful, but necessarily incomplete. Some
valid combinations may be flagged, and some inconsistent profiles may pass.
The implementation is conservative enough for an MVP and returns explainable
findings.

Impact: low false-positive/false-negative risk in advisory output.

Recommendation: keep findings advisory, not blocking. Future fingerprint pool
work can move these rules into data-driven profiles.

### Finding 5: Keyword taxonomy mixes generic and platform-flavored clues

Severity: low

The JS keyword catalog includes broad terms plus platform-flavored clues such
as `wbi`, `xbogus`, and `x-bogus`. This is practical for crawler developer
work, but should not hard-code site-specific decisions into strategy logic.

Impact: acceptable in scoring, risky only if later used as deterministic target
site routing.

Recommendation: keep the taxonomy in static-analysis evidence, and require any
site-specific use to live in profiles/training fixtures rather than core logic.

### Finding 6: No CAP-1.2 changes were delivered in this round

Severity: low

The audit assignment lists `CAP-1.2 TLS/transport diagnostics`, but the worker
deliveries inspected here are CAP-4.2 and CAP-2.1. Existing project status
already records CAP-1.2 diagnostics as started separately through
`transport_diagnostics.py`.

Impact: no rejection needed, but this round should not be counted as new
transport-diagnostics progress.

Recommendation: keep CAP-1.2 as a separate next-track candidate only after JS
capture and fingerprint probing work are connected.

## Supervisor Decision Recommendation

Conditionally accept worker work.

Conditions:

1. Record that CAP-2.1 is a static-analysis/string-table foundation, not full
   AST reverse engineering.
2. Assign a follow-up integration task that wires JS capture/inventory into
   `analyze_js_static()` and stores bounded evidence in Recon/artifacts.
3. Keep fingerprint reporting advisory until a browser-side probing module
   validates runtime surfaces.

## Recommended Next Capability Task

Next: JS capture integration.

Suggested task:

```text
CAP-4.4 + CAP-2.1: Browser JS Capture -> Static Analysis Evidence Integration
```

Expected output:

- feed captured inline/external JS text into `analyze_js_static()`
- rank JS files by endpoint/signature/token/challenge clues
- persist bounded JS analysis in artifact manifest
- expose summary in `recon_report`
- add deterministic fixture tests without external network

This is the most direct way to turn the current offline modules into a useful
top-crawler developer workflow.
