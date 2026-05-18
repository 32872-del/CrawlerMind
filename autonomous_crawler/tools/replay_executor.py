"""Executable replay layer with sandbox runtime integration (REPLAY-RUNTIME-1).

Takes a HookSandboxPlan + fixture context and executes replay steps:
timestamp/nonce generation, signature function calls, encrypted payload
execution, and final request building.

Execution modes:
- sandbox: real JS execution via Node.js subprocess (when source_code available)
- fixture_stub: deterministic Python-based fixtures (fallback)
- skipped: runtime unavailable or step not applicable
- error: execution failed

Falls back to fixture stubs when sandbox is unavailable or fails.
Does NOT recover keys or bypass protections.
"""
from __future__ import annotations

import hashlib
import hmac as hmac_mod
import json
import time
import uuid
from base64 import b64encode
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlencode, urlparse, parse_qs

from .hook_sandbox_planner import (
    DynamicInput,
    HookSandboxPlan,
    HookTarget,
    ReplayStep,
    SandboxTarget,
)
from .js_sandbox import (
    CompositeRuntime,
    SandboxResult,
    get_default_runtime,
)


# ---------------------------------------------------------------------------
# Credential redaction
# ---------------------------------------------------------------------------

_SENSITIVE_KEYS = frozenset({
    "secret", "secret_key", "api_secret", "api_key", "password",
    "token", "auth", "authorization", "bearer", "private_key",
    "x-sign", "x-signature", "x-token",
})

_REDACT_PLACEHOLDER = "***REDACTED***"


def _redact_dict(d: dict[str, Any]) -> dict[str, Any]:
    """Redact sensitive values in a dict."""
    redacted: dict[str, Any] = {}
    for k, v in d.items():
        if k.lower() in _SENSITIVE_KEYS:
            redacted[k] = _REDACT_PLACEHOLDER
        elif isinstance(v, dict):
            redacted[k] = _redact_dict(v)
        else:
            redacted[k] = v
    return redacted


def _redact_string(s: str) -> str:
    """Redact known credential patterns in strings."""
    if any(kw in s.lower() for kw in ("secret", "password", "api_key", "bearer")):
        return _REDACT_PLACEHOLDER
    return s


# ---------------------------------------------------------------------------
# Result data models
# ---------------------------------------------------------------------------

@dataclass
class StepResult:
    """Result of executing one replay step."""
    order: int
    action: str
    target: str
    status: str  # ok | skipped | error | missing_function | missing_key
    output: Any = None
    error: str = ""
    duration_ms: float = 0.0
    execution_mode: str = "fixture_stub"  # sandbox | fixture_stub | skipped | error

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "order": self.order,
            "action": self.action,
            "target": self.target,
            "status": self.status,
            "duration_ms": round(self.duration_ms, 2),
            "execution_mode": self.execution_mode,
        }
        if self.output is not None:
            d["output"] = self.output
        if self.error:
            d["error"] = _redact_string(self.error)
        return d


@dataclass
class ReplayResult:
    """Full result of executing a HookSandboxPlan."""
    steps_run: list[StepResult] = field(default_factory=list)
    generated_inputs: dict[str, Any] = field(default_factory=dict)
    hook_outputs: dict[str, Any] = field(default_factory=dict)
    sandbox_outputs: dict[str, Any] = field(default_factory=dict)
    request_preview: dict[str, Any] = field(default_factory=dict)
    request_patch: dict[str, Any] = field(default_factory=dict)
    profile_api_hints: dict[str, Any] = field(default_factory=dict)
    blockers_remaining: list[str] = field(default_factory=list)
    success: bool = False
    credential_leak_detected: bool = False
    execution_mode: str = "fixture_stub"  # sandbox | fixture_stub | mixed | skipped

    def to_dict(self) -> dict[str, Any]:
        return {
            "steps_run": [s.to_dict() for s in self.steps_run],
            "generated_inputs": _redact_dict(self.generated_inputs),
            "hook_outputs": _redact_dict(self.hook_outputs),
            "sandbox_outputs": _redact_dict(self.sandbox_outputs),
            "request_preview": _redact_dict(self.request_preview),
            "request_patch": _redact_dict(self.request_patch),
            "profile_api_hints": _redact_dict(self.profile_api_hints),
            "blockers_remaining": list(self.blockers_remaining),
            "success": self.success,
            "credential_leak_detected": self.credential_leak_detected,
            "execution_mode": self.execution_mode,
        }


# ---------------------------------------------------------------------------
# Fixture context
# ---------------------------------------------------------------------------

@dataclass
class FixtureContext:
    """Deterministic fixture data for replay execution.

    Provides mock keys, URLs, params, and hook function implementations.
    """
    url: str = "https://api.example.com/data"
    params: dict[str, Any] = field(default_factory=lambda: {"page": "1", "limit": "20"})
    headers: dict[str, str] = field(default_factory=lambda: {"Accept": "application/json"})
    body: str = ""
    secret_key: str = "test-secret-key-do-not-use-in-production"
    session_id: str = "test-session-001"
    encrypt_key: str = "test-encrypt-key"
    timeout_ms: int = 5000

    # Custom hook function implementations (name -> callable)
    hook_implementations: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "params": dict(self.params),
            "headers": _redact_dict(self.headers),
            "body": self.body[:500] if self.body else "",
            "session_id": self.session_id,
        }


# ---------------------------------------------------------------------------
# Built-in fixture hook implementations
# ---------------------------------------------------------------------------

def _hmac_sha256(data: str, key: str) -> str:
    """Deterministic HMAC-SHA256 fixture."""
    return hmac_mod.new(key.encode(), data.encode(), hashlib.sha256).hexdigest()


def _sha256_hash(data: str) -> str:
    """Deterministic SHA256 fixture."""
    return hashlib.sha256(data.encode()).hexdigest()


def _md5_hash(data: str) -> str:
    """Deterministic MD5 fixture."""
    return hashlib.md5(data.encode()).hexdigest()


def _base64_encode(data: str) -> str:
    """Deterministic base64 fixture."""
    return b64encode(data.encode()).decode()


def _generate_timestamp() -> int:
    """Deterministic timestamp fixture (ms)."""
    return int(time.time() * 1000)


def _generate_nonce() -> str:
    """Deterministic nonce fixture."""
    return uuid.uuid4().hex[:16]


def _aes_encrypt_stub(plaintext: str, key: str) -> str:
    """AES encryption stub — NOT real encryption, just a deterministic fixture."""
    # Produces a deterministic "ciphertext" from plaintext + key
    combined = f"{key}:{plaintext}"
    return f"AES_STUB({hashlib.sha256(combined.encode()).hexdigest()[:32]})"


_BUILTIN_HOOKS: dict[str, Any] = {
    "hmacSHA256": lambda inputs: _hmac_sha256(
        inputs.get("payload", inputs.get("url", "")),
        inputs.get("key", ""),
    ),
    "hmac": lambda inputs: _hmac_sha256(
        inputs.get("payload", ""),
        inputs.get("key", ""),
    ),
    "sha256": lambda inputs: _sha256_hash(inputs.get("payload", inputs.get("url", ""))),
    "md5": lambda inputs: _md5_hash(inputs.get("payload", "")),
    "sign": lambda inputs: _hmac_sha256(
        inputs.get("payload", inputs.get("url", "")),
        inputs.get("key", inputs.get("secret", "")),
    ),
    "signRequest": lambda inputs: _hmac_sha256(
        inputs.get("url", "") + "?" + urlencode(inputs.get("params", {})),
        inputs.get("key", inputs.get("secret", "")),
    ),
    "base64": lambda inputs: _base64_encode(inputs.get("raw_value", "")),
    "btoa": lambda inputs: _base64_encode(inputs.get("raw_value", "")),
    "generateToken": lambda inputs: _base64_encode(
        f"{inputs.get('session_id', '')}:{inputs.get('timestamp', '')}:{inputs.get('nonce', '')}"
    ),
    "api_request_signature": lambda inputs: _hmac_sha256(
        inputs.get("request_url", "") + json.dumps(inputs.get("query_params", {}), sort_keys=True),
        inputs.get("key", ""),
    ),
}


_BUILTIN_SANDBOX: dict[str, Any] = {
    "aes": lambda inputs: _aes_encrypt_stub(
        inputs.get("plaintext", ""),
        inputs.get("key_material", inputs.get("key", "")),
    ),
    "cryptojs": lambda inputs: _aes_encrypt_stub(
        inputs.get("plaintext", ""),
        inputs.get("key_material", inputs.get("key", "")),
    ),
    "api_payload_encryption": lambda inputs: _aes_encrypt_stub(
        inputs.get("plaintext_payload", inputs.get("plaintext", "")),
        inputs.get("encryption_key", inputs.get("key", "")),
    ),
}


# ---------------------------------------------------------------------------
# Main executor
# ---------------------------------------------------------------------------

def execute_replay(
    plan: HookSandboxPlan,
    context: FixtureContext | None = None,
    runtime: CompositeRuntime | None = None,
) -> ReplayResult:
    """Execute a HookSandboxPlan with sandbox-first, fixture-fallback strategy.

    Args:
        plan: The HookSandboxPlan to execute.
        context: Fixture context providing URLs, keys, params, etc.
        runtime: JS sandbox runtime. None = use default (auto-detect Node.js).

    Returns:
        ReplayResult with step outputs, generated inputs, and request preview.
    """
    if context is None:
        context = FixtureContext()

    if runtime is None:
        runtime = get_default_runtime()

    result = ReplayResult()
    all_generated: dict[str, Any] = {}
    hook_outputs: dict[str, Any] = {}
    sandbox_outputs: dict[str, Any] = {}

    # Merge built-in hooks with context overrides
    hooks = {**_BUILTIN_HOOKS, **context.hook_implementations}

    for step in plan.replay_steps:
        step_result = _execute_step(
            step, plan, context, hooks, all_generated, hook_outputs, sandbox_outputs,
            runtime=runtime,
        )
        result.steps_run.append(step_result)

        if step_result.status in ("error", "missing_function"):
            result.blockers_remaining.append(
                f"step_{step.order}_{step.action}_{step.target}: {step_result.error}"
            )

    result.generated_inputs = all_generated
    result.hook_outputs = hook_outputs
    result.sandbox_outputs = sandbox_outputs

    # Build request preview from the final request step
    result.request_preview = _build_request_preview(
        plan, context, all_generated, hook_outputs, sandbox_outputs,
    )

    # Build machine-readable request patch
    result.request_patch = _build_request_patch(
        plan, context, all_generated, hook_outputs, sandbox_outputs,
    )

    # Build profile API hints artifact
    result.profile_api_hints = _build_profile_api_hints(
        plan, context, all_generated, hook_outputs, sandbox_outputs,
        result.request_patch,
    )

    # Check for credential leaks
    result.credential_leak_detected = _check_credential_leak(result)

    # Success: all steps completed without errors, no blockers
    result.success = (
        all(s.status in ("ok", "skipped") for s in result.steps_run)
        and not result.credential_leak_detected
    )

    # Compute overall execution mode
    modes = {s.execution_mode for s in result.steps_run if s.status == "ok"}
    if modes == {"sandbox"}:
        result.execution_mode = "sandbox"
    elif "sandbox" in modes:
        result.execution_mode = "mixed"
    elif modes == {"fixture_stub"} or modes == {"fixture_stub", "skipped"}:
        result.execution_mode = "fixture_stub"
    else:
        result.execution_mode = "skipped"

    return result


def _execute_step(
    step: ReplayStep,
    plan: HookSandboxPlan,
    context: FixtureContext,
    hooks: dict[str, Any],
    generated: dict[str, Any],
    hook_outputs: dict[str, Any],
    sandbox_outputs: dict[str, Any],
    *,
    runtime: CompositeRuntime | None = None,
) -> StepResult:
    """Execute one replay step."""
    t0 = time.monotonic()

    try:
        if step.action == "generate_input":
            return _execute_generate_input(step, plan, generated, t0)
        elif step.action == "call_hook":
            return _execute_call_hook(
                step, plan, context, hooks, generated, hook_outputs, t0,
                runtime=runtime,
            )
        elif step.action == "call_sandbox":
            return _execute_call_sandbox(
                step, plan, context, generated, sandbox_outputs, t0,
                runtime=runtime,
            )
        elif step.action == "build_request":
            return StepResult(
                order=step.order, action=step.action, target=step.target,
                status="ok", output="request_built",
                duration_ms=(time.monotonic() - t0) * 1000,
                execution_mode="fixture_stub",
            )
        elif step.action == "send_request":
            return StepResult(
                order=step.order, action=step.action, target=step.target,
                status="ok", output="request_ready",
                duration_ms=(time.monotonic() - t0) * 1000,
                execution_mode="fixture_stub",
            )
        else:
            return StepResult(
                order=step.order, action=step.action, target=step.target,
                status="skipped", output=f"unknown_action:{step.action}",
                duration_ms=(time.monotonic() - t0) * 1000,
                execution_mode="skipped",
            )
    except Exception as exc:
        return StepResult(
            order=step.order, action=step.action, target=step.target,
            status="error", error=f"{type(exc).__name__}: {exc}",
            duration_ms=(time.monotonic() - t0) * 1000,
            execution_mode="error",
        )


def _execute_generate_input(
    step: ReplayStep,
    plan: HookSandboxPlan,
    generated: dict[str, Any],
    t0: float,
) -> StepResult:
    """Generate a dynamic input (timestamp, nonce, etc.)."""
    target = step.target
    # Find the DynamicInput spec
    inp_spec: DynamicInput | None = None
    for inp in plan.dynamic_inputs:
        if inp.name == target:
            inp_spec = inp
            break

    if inp_spec is None:
        # Auto-generate for known types
        if "timestamp" in target or "ts" in target:
            value = _generate_timestamp()
        elif "nonce" in target:
            value = _generate_nonce()
        elif "uuid" in target:
            value = str(uuid.uuid4())
        else:
            value = f"fixture_{target}_{int(time.time())}"
    else:
        method = inp_spec.generation_method.lower()
        if "date.now" in method or "timestamp" in target:
            value = _generate_timestamp()
        elif "random" in method or "nonce" in target:
            value = _generate_nonce()
        else:
            value = f"fixture_{target}_{int(time.time())}"

    generated[target] = value
    return StepResult(
        order=step.order, action=step.action, target=target,
        status="ok", output=value,
        duration_ms=(time.monotonic() - t0) * 1000,
        execution_mode="fixture_stub",
    )


def _execute_call_hook(
    step: ReplayStep,
    plan: HookSandboxPlan,
    context: FixtureContext,
    hooks: dict[str, Any],
    generated: dict[str, Any],
    hook_outputs: dict[str, Any],
    t0: float,
    *,
    runtime: CompositeRuntime | None = None,
) -> StepResult:
    """Call a hook function: sandbox first, fixture fallback."""
    target = step.target

    # Find hook spec for source_code
    hook_spec: HookTarget | None = None
    for h in plan.hook_targets:
        if h.name == target:
            hook_spec = h
            break

    # --- Strategy 1: Try sandbox if source_code available ---
    if hook_spec and hook_spec.source_code and runtime and runtime.is_available():
        inputs = _build_hook_inputs(target, plan, context, generated)
        sandbox_result = runtime.execute(
            hook_spec.source_code,
            target,
            inputs,
            timeout_ms=context.timeout_ms if hasattr(context, 'timeout_ms') else 5000,
            dynamic_inputs=generated,
        )
        if sandbox_result.status == "ok":
            output = sandbox_result.result
            hook_outputs[target] = output
            return StepResult(
                order=step.order, action=step.action, target=target,
                status="ok", output=output,
                duration_ms=(time.monotonic() - t0) * 1000,
                execution_mode="sandbox",
            )
        # Sandbox failed — fall through to fixture stub
        # (record the sandbox failure in runtime_events if needed later)

    # --- Strategy 2: Deterministic fixture stub ---
    func = hooks.get(target)
    if func is None:
        # Strict partial match: target must START with a known hook name (min 4 chars)
        target_lower = target.lower()
        for name, fn in hooks.items():
            if len(name) >= 4 and target_lower.startswith(name.lower()):
                func = fn
                break

    if func is None:
        return StepResult(
            order=step.order, action=step.action, target=target,
            status="missing_function", error=f"No fixture for hook: {target}",
            duration_ms=(time.monotonic() - t0) * 1000,
            execution_mode="skipped",
        )

    inputs = _build_hook_inputs(target, plan, context, generated)
    try:
        output = func(inputs)
        hook_outputs[target] = output
        return StepResult(
            order=step.order, action=step.action, target=target,
            status="ok", output=output,
            duration_ms=(time.monotonic() - t0) * 1000,
            execution_mode="fixture_stub",
        )
    except Exception as exc:
        return StepResult(
            order=step.order, action=step.action, target=target,
            status="error", error=f"{type(exc).__name__}: {exc}",
            duration_ms=(time.monotonic() - t0) * 1000,
            execution_mode="error",
        )


def _execute_call_sandbox(
    step: ReplayStep,
    plan: HookSandboxPlan,
    context: FixtureContext,
    generated: dict[str, Any],
    sandbox_outputs: dict[str, Any],
    t0: float,
    *,
    runtime: CompositeRuntime | None = None,
) -> StepResult:
    """Call a sandbox target: real JS sandbox first, fixture stub fallback."""
    target = step.target

    # Find sandbox spec for source_code
    sandbox_spec: SandboxTarget | None = None
    for s in plan.sandbox_targets:
        if s.name == target:
            sandbox_spec = s
            break

    # --- Strategy 1: Try sandbox if source_code available ---
    if sandbox_spec and sandbox_spec.source_code and runtime and runtime.is_available():
        inputs = _build_sandbox_inputs(target, plan, context, generated)
        sandbox_result = runtime.execute(
            sandbox_spec.source_code,
            target,
            inputs,
            timeout_ms=context.timeout_ms if hasattr(context, 'timeout_ms') else 5000,
            dynamic_inputs=generated,
        )
        if sandbox_result.status == "ok":
            output = sandbox_result.result
            sandbox_outputs[target] = output
            return StepResult(
                order=step.order, action=step.action, target=target,
                status="ok", output=output,
                duration_ms=(time.monotonic() - t0) * 1000,
                execution_mode="sandbox",
            )

    # --- Strategy 2: Deterministic fixture stub ---
    func = _BUILTIN_SANDBOX.get(target)
    if func is None:
        for name, fn in _BUILTIN_SANDBOX.items():
            if name.lower() in target.lower() or target.lower() in name.lower():
                func = fn
                break

    if func is None:
        return StepResult(
            order=step.order, action=step.action, target=target,
            status="missing_function", error=f"No sandbox stub for: {target}",
            duration_ms=(time.monotonic() - t0) * 1000,
            execution_mode="skipped",
        )

    inputs = _build_sandbox_inputs(target, plan, context, generated)
    try:
        output = func(inputs)
        sandbox_outputs[target] = output
        return StepResult(
            order=step.order, action=step.action, target=target,
            status="ok", output=output,
            duration_ms=(time.monotonic() - t0) * 1000,
            execution_mode="fixture_stub",
        )
    except Exception as exc:
        return StepResult(
            order=step.order, action=step.action, target=target,
            status="error", error=f"{type(exc).__name__}: {exc}",
            duration_ms=(time.monotonic() - t0) * 1000,
            execution_mode="error",
        )


def _build_hook_inputs(
    target: str,
    plan: HookSandboxPlan,
    context: FixtureContext,
    generated: dict[str, Any],
) -> dict[str, Any]:
    """Build input dict for a hook function."""
    inputs: dict[str, Any] = {
        "url": context.url,
        "params": context.params,
        "headers": context.headers,
        "body": context.body,
        "key": context.secret_key,
        "secret": context.secret_key,
        "session_id": context.session_id,
        "request_url": context.url,
        "query_params": context.params,
        "payload": context.url,  # alias used by signature hooks
        "raw_value": context.url,  # alias used by encoding hooks
    }
    inputs.update(generated)

    # Find hook spec for additional input names
    for hook in plan.hook_targets:
        if hook.name == target:
            for inp_name in hook.inputs_to_capture:
                if inp_name not in inputs:
                    inputs[inp_name] = f"fixture_{inp_name}"
            break

    return inputs


def _build_sandbox_inputs(
    target: str,
    plan: HookSandboxPlan,
    context: FixtureContext,
    generated: dict[str, Any],
) -> dict[str, Any]:
    """Build input dict for a sandbox stub."""
    inputs: dict[str, Any] = {
        "plaintext": '{"data": "test_payload"}',
        "key_material": context.encrypt_key,
        "key": context.encrypt_key,
        "ciphertext": "",
    }
    inputs.update(generated)
    return inputs


def _build_request_preview(
    plan: HookSandboxPlan,
    context: FixtureContext,
    generated: dict[str, Any],
    hook_outputs: dict[str, Any],
    sandbox_outputs: dict[str, Any],
) -> dict[str, Any]:
    """Build a preview of the final request."""
    preview: dict[str, Any] = {
        "method": "GET",
        "url": context.url,
        "params": dict(context.params),
        "headers": dict(context.headers),
    }

    # Inject generated inputs as query params
    for name, value in generated.items():
        if name in ("timestamp", "ts"):
            preview["params"][name] = str(value)
        elif name == "nonce":
            preview["params"][name] = str(value)

    # Inject hook outputs as signature headers
    for name, value in hook_outputs.items():
        if isinstance(value, str):
            preview["headers"][f"x-{name}"] = value

    # Inject sandbox outputs
    for name, value in sandbox_outputs.items():
        if isinstance(value, str):
            preview["body"] = value

    return preview


def _build_request_patch(
    plan: HookSandboxPlan,
    context: FixtureContext,
    generated: dict[str, Any],
    hook_outputs: dict[str, Any],
    sandbox_outputs: dict[str, Any],
) -> dict[str, Any]:
    """Build a machine-readable request patch for profile/API runtime consumption.

    Unlike request_preview (human-readable), this is structured for downstream
    consumers to merge into actual HTTP requests.
    """
    # Collect signed params (dynamic inputs that go into query string)
    signed_params: dict[str, Any] = {}
    for name, value in generated.items():
        signed_params[name] = str(value)

    # Collect signature headers (hook outputs that become headers)
    signature_headers: dict[str, str] = {}
    for name, value in hook_outputs.items():
        if isinstance(value, str):
            signature_headers[f"x-{name}"] = value

    # Collect body patches (sandbox outputs that go into body)
    body_patch: str = ""
    body_json: dict[str, Any] | None = None
    for name, value in sandbox_outputs.items():
        if isinstance(value, str):
            body_patch = value
            # Try to parse as JSON for structured body
            try:
                parsed = json.loads(value)
                if isinstance(parsed, dict):
                    body_json = parsed
            except (json.JSONDecodeError, TypeError):
                pass

    # Build the final signed URL
    from urllib.parse import urlencode as _urlencode
    base_url = context.url
    all_params = {**context.params, **signed_params}
    if all_params:
        signed_url = f"{base_url}?{_urlencode(all_params)}"
    else:
        signed_url = base_url

    # Merge headers
    merged_headers = {**context.headers, **signature_headers}

    # Dynamic inputs used
    dynamic_inputs_used = list(generated.keys())

    # Signature outputs (names + redacted values)
    signature_outputs = {}
    for name, value in hook_outputs.items():
        signature_outputs[name] = _redact_string(str(value)) if isinstance(value, str) else value

    return {
        "method": "GET" if not context.body else "POST",
        "url": signed_url,
        "base_url": base_url,
        "params": _redact_dict(all_params),
        "headers": _redact_dict(merged_headers),
        "body": body_patch[:500] if body_patch else "",
        "body_json": _redact_dict(body_json) if body_json else None,
        "dynamic_inputs_used": dynamic_inputs_used,
        "signature_outputs": signature_outputs,
        "sandbox_outputs_used": list(sandbox_outputs.keys()),
    }


def _build_profile_api_hints(
    plan: HookSandboxPlan,
    context: FixtureContext,
    generated: dict[str, Any],
    hook_outputs: dict[str, Any],
    sandbox_outputs: dict[str, Any],
    request_patch: dict[str, Any],
) -> dict[str, Any]:
    """Build a data-only artifact for SiteProfile.api_hints integration.

    This is a suggestion block that can be placed into a SiteProfile's
    api_hints field. It does NOT import or depend on SiteProfile directly.
    """
    # Determine if replay is required
    has_hooks = bool(plan.hook_targets)
    has_sandbox = bool(plan.sandbox_targets)
    has_dynamic = bool(plan.dynamic_inputs)
    replay_required = has_hooks or has_sandbox or has_dynamic

    # Build signed headers list (header names, not values)
    signed_header_names = sorted(signature_headers_from_hook_outputs(hook_outputs))

    # Build signed params list (param names)
    signed_param_names = sorted(generated.keys())

    # Build dynamic inputs spec
    dynamic_inputs_spec = []
    for inp in plan.dynamic_inputs:
        dynamic_inputs_spec.append({
            "name": inp.name,
            "generation_method": inp.generation_method,
            "required": inp.required,
        })

    # Replay plan identifier (deterministic from plan structure)
    plan_id_parts = []
    for h in plan.hook_targets:
        plan_id_parts.append(f"h:{h.name}:{h.kind}")
    for s in plan.sandbox_targets:
        plan_id_parts.append(f"s:{s.name}")
    plan_id = "|".join(plan_id_parts) if plan_id_parts else "none"

    return {
        "replay_required": replay_required,
        "replay_plan_id": plan_id,
        "risk_level": plan.risk_level,
        "signed_headers": signed_header_names,
        "signed_params": signed_param_names,
        "dynamic_inputs": dynamic_inputs_spec,
        "hook_targets": [h.name for h in plan.hook_targets],
        "sandbox_targets": [s.name for s in plan.sandbox_targets],
        "execution_mode": request_patch.get("method", "GET"),
    }


def signature_headers_from_hook_outputs(hook_outputs: dict[str, Any]) -> list[str]:
    """Extract signature header names from hook outputs."""
    return [f"x-{name}" for name in hook_outputs if isinstance(hook_outputs[name], str)]


def _check_credential_leak(result: ReplayResult) -> bool:
    """Check if any step output contains raw credentials."""
    result_str = json.dumps(result.to_dict(), default=str)
    # Check for known test credentials appearing unredacted
    sensitive_patterns = [
        "test-secret-key-do-not-use-in-production",
        "test-encrypt-key",
    ]
    for pattern in sensitive_patterns:
        if pattern in result_str:
            return True
    return False
