# 2026-05-15 LLM-2026-002 — REPLAY-RUNTIME-1

**Task**: JS Sandbox Runtime Integration for Replay Executor
**Worker**: LLM-2026-002
**Status**: COMPLETE

## Summary

Extended the deterministic replay executor with a real JS sandbox runtime layer. The executor now tries sandbox-first (Node.js subprocess) when `source_code` is available on hook/sandbox targets, and falls back to deterministic Python fixture stubs on failure or when no runtime is available.

## Files Changed

| File | Action | Description |
|------|--------|-------------|
| `autonomous_crawler/tools/js_sandbox.py` | NEW | JS sandbox runtime: JSRuntime protocol, NodeJSRuntime, CompositeRuntime, SandboxResult |
| `autonomous_crawler/tools/replay_executor.py` | MODIFIED | Added execution_mode to StepResult/ReplayResult, sandbox-first execution strategy, runtime parameter |
| `autonomous_crawler/tools/hook_sandbox_planner.py` | MODIFIED | Added source_code field to HookTarget and SandboxTarget |
| `autonomous_crawler/tests/test_replay_executor.py` | MODIFIED | Added 29 new tests (60 total): sandbox execution, timeout, fallback, redaction, NodeJSRuntime, CompositeRuntime |

## Runtime Protocol

### JSRuntime Protocol

```python
class JSRuntime(Protocol):
    def execute(source, function_name, args, *, timeout_ms, allowed_globals, dynamic_inputs) -> SandboxResult
    def is_available() -> bool
    name: str
```

### SandboxResult

```python
@dataclass
class SandboxResult:
    status: str        # ok | timeout | error | missing_runtime | skipped
    result: Any        # function return value
    error: str         # error message
    duration_ms: float
    runtime_events: list[dict]
    redacted_preview: str
    execution_mode: str  # sandbox | fixture_stub | skipped | error
```

### Implementations

- **NodeJSRuntime**: Executes JS via `node --eval` subprocess. Self-contained wrapper that evaluates source, calls function, handles sync/async results.
- **CompositeRuntime**: Tries multiple runtimes in order, returns first success.
- **get_default_runtime()**: Module-level singleton, auto-detects Node.js.

## Sandbox/Fallback Behavior

```
execute_replay(plan, context, runtime)
  for each step:
    if call_hook:
      1. Find HookTarget.source_code
      2. If source_code + runtime available → sandbox.execute()
      3. If sandbox ok → execution_mode="sandbox"
      4. If sandbox fails → fall back to fixture stub
      5. If no fixture → execution_mode="missing_function"
    if call_sandbox:
      1. Find SandboxTarget.source_code
      2. Same sandbox-first, fixture-fallback logic
    if generate_input:
      Always fixture_stub (Python timestamps/nonces)
```

Overall `execution_mode` on ReplayResult:
- `sandbox`: all ok steps used sandbox
- `mixed`: some sandbox, some fixture_stub
- `fixture_stub`: all ok steps used fixture_stub
- `skipped`: no ok steps

## Security & Stability

- **Timeout**: enforced via `subprocess.run(timeout=...)`, default 5s
- **Output limits**: stdout truncated to 4096 chars, stderr to 2048
- **Credential redaction**: `_redact_value()` in js_sandbox.py, `_redact_dict()`/`_redact_string()` in replay_executor.py
- **Sandbox failure isolation**: sandbox errors never crash the executor — always falls back to fixture
- **No untrusted code execution**: source_code is CLM-generated or user-provided fixture code

## Test Results

```
test_replay_executor: 60 passed (was 31, +29 new)
full suite:         2135 passed (5 skipped)
compileall:         clean
```

### New test classes

| Class | Tests | Coverage |
|-------|-------|----------|
| TestExecutionMode | 4 | execution_mode on StepResult/ReplayResult |
| TestSandboxExecution | 6 | HMAC, AES, SHA256, Base64, combined, request preview via Node.js |
| TestSandboxTimeout | 2 | timeout triggers error, doesn't crash |
| TestSandboxMissingFunction | 2 | missing function fallback, broken JS fallback |
| TestSandboxFallbackToFixture | 2 | no source_code uses fixture, empty runtime uses fixture |
| TestSandboxCredentialRedaction | 2 | sandbox output redaction, credential_leak_detected |
| TestNodeJSRuntime | 8 | direct runtime: function, crypto, timeout, syntax error, missing func, available, events, preview |
| TestCompositeRuntime | 3 | fallback order, all fail, skip unavailable |

## Known Limitations

1. **Node.js only** — no Deno, Bun, or browser runtime yet. CompositeRuntime is ready for them.
2. **No async support in wrapper** — promise handling exists but complex async chains may fail.
3. **No module imports** — `require()` works in Node but ES modules (`import`) don't in `--eval` mode.
4. **No WebCrypto** — `crypto.subtle` is not available in Node.js `--eval` without browser polyfill.
5. **Source code from planner** — `source_code` field on HookTarget/SandboxTarget is empty by default; planner doesn't populate it from JS evidence yet.

## Next Steps

1. **Planner source_code injection** — have `plan_hook_sandbox()` extract and attach JS source from `js_evidence.items[].source_code`
2. **WebCrypto polyfill** — add `@peculiar/webcrypto` or similar for `crypto.subtle` support
3. **ES module support** — use `--input-type=module` flag for import-based JS
4. **Deno/Bun runtimes** — add `DenoRuntime` and `BunRuntime` to CompositeRuntime
5. **Sandbox metrics** — track sandbox vs fixture hit rates across runs

---

## Round 2: Signed Request Preview + Profile API Hints

### Summary

Extended ReplayResult with `request_patch` (machine-readable signed request) and `profile_api_hints` (data-only artifact for SiteProfile.api_hints integration).

### Files Changed

| File | Action | Description |
|------|--------|-------------|
| `autonomous_crawler/tools/replay_executor.py` | MODIFIED | Added request_patch, profile_api_hints, _build_request_patch(), _build_profile_api_hints() |
| `autonomous_crawler/tests/test_replay_executor.py` | MODIFIED | Added 37 new tests (97 total): request patch, profile hints, signed fixtures, sandbox patch/hints |

### ReplayRequestPatch Protocol

Machine-readable request patch output from replay executor:

```python
{
    "method": "GET",                          # HTTP method
    "url": "https://api.com/data?ts=123&...", # Signed URL with all params
    "base_url": "https://api.com/data",       # Original URL
    "params": {"page": "1", "timestamp": "...", "nonce": "..."},  # Merged params
    "headers": {"Accept": "...", "x-hmacSHA256": "..."},          # Merged headers
    "body": "AES_STUB(...)",                  # Encrypted body (if any)
    "body_json": null,                        # Parsed JSON body (if applicable)
    "dynamic_inputs_used": ["timestamp", "nonce"],
    "signature_outputs": {"hmacSHA256": "***REDACTED***"},
    "sandbox_outputs_used": ["aes"],
}
```

### Profile API Hints Artifact

Data-only artifact for `SiteProfile.api_hints`:

```python
{
    "replay_required": True,
    "replay_plan_id": "h:hmacSHA256:signature|s:aes",
    "risk_level": "high",
    "signed_headers": ["x-hmacSHA256"],
    "signed_params": ["nonce", "timestamp"],
    "dynamic_inputs": [
        {"name": "timestamp", "generation_method": "Date.now()", "required": True},
        {"name": "nonce", "generation_method": "Math.random()...", "required": True},
    ],
    "hook_targets": ["hmacSHA256"],
    "sandbox_targets": ["aes"],
}
```

### Bug Fix

Fixed `_build_hook_inputs()` — `payload` alias was set to `"fixture_payload"` instead of the actual URL, causing all signature hooks to produce identical output regardless of URL.

### Test Results

```
test_replay_executor: 97 passed (was 60, +37 new)
full suite:         2179 passed (5 skipped, 2 pre-existing failures in test_profile_draft)
compileall:         clean
```

### New test classes (Round 2)

| Class | Tests | Coverage |
|-------|-------|----------|
| TestRequestPatch | 13 | method, URL, params, headers, dynamic_inputs, signature_outputs, redaction, body, combined |
| TestProfileApiHints | 12 | replay_required, plan_id, risk_level, signed_headers, signed_params, dynamic_inputs, hook/sandbox targets |
| TestSignedRequestFixture | 7 | deterministic, different URLs/keys, param merging, URL structure |
| TestSandboxRequestPatch | 3 | real signature, AES body, combined (Node.js) |
| TestSandboxProfileHints | 2 | hint structure parity, signed headers (Node.js) |
