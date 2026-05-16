# 2026-05-15 LLM-2026-002 — REVERSE-HARDEN-1: JS Hook / Sandbox MVP

**Task**: REVERSE-HARDEN-1 — build structured hook/sandbox planning from JS/API evidence
**Worker**: LLM-2026-002
**Status**: COMPLETE

## Summary

Created `hook_sandbox_planner.py` — a lightweight planning module that takes JS crypto/signature evidence and API candidates, and outputs structured hook targets, sandbox targets, dynamic inputs, and replay steps. Integrated into `strategy_evidence.py` as additive `hook_sandbox_plan` in action_hints (backward compatible). 36 deterministic tests with 5 JS fixtures.

## Files Changed

| File | Action | Description |
|------|--------|-------------|
| `autonomous_crawler/tools/hook_sandbox_planner.py` | NEW | Core planner: HookTarget, SandboxTarget, DynamicInput, ReplayStep, HookSandboxPlan, plan_hook_sandbox() |
| `autonomous_crawler/tools/strategy_evidence.py` | MODIFIED | +import plan_hook_sandbox, +hook_sandbox_plan in action_hints |
| `autonomous_crawler/tests/test_hook_sandbox_planner.py` | NEW | 36 tests across 9 test classes |
| `dev_logs/development/2026-05-15_LLM-2026-002_reverse_harden_1_js_hook_sandbox_mvp.md` | NEW | This dev log |
| `docs/memory/handoffs/2026-05-15_LLM-2026-002_reverse_harden_1_js_hook_sandbox_mvp.md` | NEW | Handoff |

## Core Data Models

### HookTarget
One function/routine to intercept. Fields: `name`, `kind` (signature|encryption|token|timestamp|nonce|encoding), `source` (js_static|js_crypto|api_evidence), `confidence`, `context`, `inputs_to_capture`, `outputs_to_capture`.

### DynamicInput
A per-request value that must be generated. Fields: `name` (timestamp|nonce|uuid|session_token|custom), `generation_method` (Date.now()|crypto.getRandomValues()|Math.random()|custom), `required`.

### SandboxTarget
A routine needing runtime execution. Fields: `name`, `runtime` (browser|node|browser_or_node), `reason`, `capture`.

### ReplayStep
One step in the replay sequence. Fields: `order`, `action` (generate_input|call_hook|call_sandbox|build_request|send_request), `target`, `depends_on`.

### HookSandboxPlan
Full plan: `hook_targets`, `sandbox_targets`, `dynamic_inputs`, `replay_steps`, `risk_level` (none|low|medium|high), `blockers`.

## Planner Algorithm

1. **From JS crypto signals**: hash/hmac/signature → HookTarget, encryption/webcrypto → SandboxTarget, timestamp/nonce → DynamicInput
2. **From JS suspicious functions**: signature reason → HookTarget, encryption → SandboxTarget, token → HookTarget
3. **From JS suspicious calls**: signature category → HookTarget (high confidence), encryption → SandboxTarget, token → HookTarget
4. **From API candidates**: signature/token in URL/headers → HookTarget, timestamp/nonce in query params → DynamicInput, encrypted body → SandboxTarget
5. **Build replay steps**: generate inputs → call hooks → call sandbox → build request → send request
6. **Compute risk**: signature+encryption → high, signature or encryption → medium, dynamic only → low, none → none

## Deterministic JS Fixtures

| Fixture | Description | Expected Risk |
|---------|-------------|---------------|
| `_JS_SIGN_HMAC` | signRequest() with HMAC-SHA256, sorted params, Date.now(), Math.random() | medium |
| `_JS_ENCRYPT_AES` | encryptPayload() with CryptoJS.AES, key from DOM | high (sandbox) |
| `_JS_WEBHOOK_TOKEN` | generateToken() with btoa, Date.now, Math.random | low/medium |
| `_JS_WEBHOOK_ALL` | buildSecureRequest() — sign + encrypt + timestamp + nonce + token | high |
| `_JS_CLEAN` | renderList() — no crypto/signature patterns | none |

## StrategyEvidence Integration

- `build_reverse_engineering_hints()` now calls `plan_hook_sandbox(js_evidence, api_candidates)` after building existing hints
- If `plan.risk_level != "none"`, adds `hook_sandbox_plan` key to hints dict
- Existing `hook_plan`, `sandbox_plan`, `dynamic_inputs` keys remain untouched (backward compatible)
- `hook_sandbox_plan` is additive — consumers can use either the old or new format

## Test Results

```
test_hook_sandbox_planner:     36 passed
test_graphql_training:         42 passed
full suite:                  1951 passed (5 skipped)
compileall:                  clean
```

## JS Hook/Sandbox Capabilities

| Capability | Status | Details |
|-----------|--------|---------|
| Hook target extraction | DONE | From crypto signals, suspicious functions, suspicious calls, API evidence |
| Sandbox target extraction | DONE | From encryption/webcrypto signals, API encrypted body |
| Dynamic input extraction | DONE | From timestamp/nonce categories, API query params |
| Replay step sequencing | DONE | Ordered steps with dependency tracking |
| Risk level computation | DONE | none/low/medium/high based on signal combination |
| Blocker identification | DONE | Lists what prevents simple replay |
| StrategyEvidence integration | DONE | Additive hook_sandbox_plan in action_hints |
| Deterministic fixtures | DONE | 5 JS fixtures, each produces stable reproducible plan |

## Remaining Risks

1. **No real-site validation** — all tests use mock fixtures; real-world JS may have obfuscated function names
2. **No AST parsing** — regex-based function/call extraction may miss patterns in minified/obfuscated code
3. **No key recovery** — planner identifies what to hook but does not recover secret keys
4. **No runtime execution** — sandbox targets are identified but not executed
5. **Replay step dependencies are simplified** — linear ordering assumes sequential execution
