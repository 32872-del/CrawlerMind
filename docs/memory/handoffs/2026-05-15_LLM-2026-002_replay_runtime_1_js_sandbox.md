---
worker: LLM-2026-002
date: 2026-05-15
task: REPLAY-RUNTIME-1 (2 rounds)
status: COMPLETE
---

# Handoff: JS Sandbox Runtime + Signed Request Preview

## What was delivered

### Round 1: JS Sandbox Runtime

Extended the deterministic replay executor with a real JS sandbox runtime. Sandbox-first execution (Node.js subprocess) when `source_code` is available, deterministic fixture fallback otherwise.

- `autonomous_crawler/tools/js_sandbox.py` (NEW): JSRuntime protocol, NodeJSRuntime, CompositeRuntime, SandboxResult
- `StepResult.execution_mode` / `ReplayResult.execution_mode`: sandbox | fixture_stub | mixed | skipped | error
- `execute_replay(plan, context, runtime)` — optional runtime parameter

### Round 2: Signed Request Preview + Profile API Hints

Extended ReplayResult with machine-readable request patch and profile integration artifact.

- `ReplayResult.request_patch`: method, url (signed), params, headers, body, dynamic_inputs_used, signature_outputs
- `ReplayResult.profile_api_hints`: replay_required, replay_plan_id, risk_level, signed_headers, signed_params, dynamic_inputs, hook_targets, sandbox_targets
- All sensitive values redacted in serialized output

### Tests: 97 passed (was 31 baseline)

Full suite: 2179 passed (5 skipped, 2 pre-existing in test_profile_draft), compile clean.

## Sandbox/fallback behavior

1. Hook/sandbox step has `source_code` + runtime available → try sandbox
2. Sandbox succeeds → `execution_mode="sandbox"`
3. Sandbox fails → fall back to fixture stub
4. No source_code or no runtime → always fixture stub
5. No fixture → `status="missing_function"`

## Request patch protocol

Output of `_build_request_patch()`: machine-readable signed HTTP request for downstream consumers.

## Known limitations

1. Node.js only — no Deno/Bun/browser runtime
2. No ES module / WebCrypto in `--eval`
3. `source_code` field on targets is empty by default
4. `profile_api_hints` is data-only — not directly wired into SiteProfile

## Next steps

1. Planner source_code injection from JS evidence
2. Wire `profile_api_hints` into site_profile.py
3. WebCrypto polyfill
4. Deno/Bun runtimes
