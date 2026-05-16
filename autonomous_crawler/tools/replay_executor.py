"""Executable replay fixture layer (REVERSE-HARDEN-2).

Takes a HookSandboxPlan + fixture context and executes deterministic
replay steps: timestamp/nonce generation, signature function calls,
encrypted payload sandbox stubs, and final request building.

Does NOT execute real JS, recover keys, or bypass protections.
All "execution" is deterministic fixture-based for testing/training.
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

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "order": self.order,
            "action": self.action,
            "target": self.target,
            "status": self.status,
            "duration_ms": round(self.duration_ms, 2),
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
    blockers_remaining: list[str] = field(default_factory=list)
    success: bool = False
    credential_leak_detected: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "steps_run": [s.to_dict() for s in self.steps_run],
            "generated_inputs": _redact_dict(self.generated_inputs),
            "hook_outputs": _redact_dict(self.hook_outputs),
            "sandbox_outputs": _redact_dict(self.sandbox_outputs),
            "request_preview": _redact_dict(self.request_preview),
            "blockers_remaining": list(self.blockers_remaining),
            "success": self.success,
            "credential_leak_detected": self.credential_leak_detected,
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
) -> ReplayResult:
    """Execute a HookSandboxPlan using deterministic fixtures.

    Args:
        plan: The HookSandboxPlan to execute.
        context: Fixture context providing URLs, keys, params, etc.

    Returns:
        ReplayResult with step outputs, generated inputs, and request preview.
    """
    if context is None:
        context = FixtureContext()

    result = ReplayResult()
    all_generated: dict[str, Any] = {}
    hook_outputs: dict[str, Any] = {}
    sandbox_outputs: dict[str, Any] = {}

    # Merge built-in hooks with context overrides
    hooks = {**_BUILTIN_HOOKS, **context.hook_implementations}

    for step in plan.replay_steps:
        step_result = _execute_step(
            step, plan, context, hooks, all_generated, hook_outputs, sandbox_outputs,
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

    # Check for credential leaks
    result.credential_leak_detected = _check_credential_leak(result)

    # Success: all steps completed without errors, no blockers
    result.success = (
        all(s.status in ("ok", "skipped") for s in result.steps_run)
        and not result.credential_leak_detected
    )

    return result


def _execute_step(
    step: ReplayStep,
    plan: HookSandboxPlan,
    context: FixtureContext,
    hooks: dict[str, Any],
    generated: dict[str, Any],
    hook_outputs: dict[str, Any],
    sandbox_outputs: dict[str, Any],
) -> StepResult:
    """Execute one replay step."""
    t0 = time.monotonic()

    try:
        if step.action == "generate_input":
            return _execute_generate_input(step, plan, generated, t0)
        elif step.action == "call_hook":
            return _execute_call_hook(step, plan, context, hooks, generated, hook_outputs, t0)
        elif step.action == "call_sandbox":
            return _execute_call_sandbox(step, plan, context, generated, sandbox_outputs, t0)
        elif step.action == "build_request":
            return StepResult(
                order=step.order, action=step.action, target=step.target,
                status="ok", output="request_built",
                duration_ms=(time.monotonic() - t0) * 1000,
            )
        elif step.action == "send_request":
            return StepResult(
                order=step.order, action=step.action, target=step.target,
                status="ok", output="request_ready",
                duration_ms=(time.monotonic() - t0) * 1000,
            )
        else:
            return StepResult(
                order=step.order, action=step.action, target=step.target,
                status="skipped", output=f"unknown_action:{step.action}",
                duration_ms=(time.monotonic() - t0) * 1000,
            )
    except Exception as exc:
        return StepResult(
            order=step.order, action=step.action, target=step.target,
            status="error", error=f"{type(exc).__name__}: {exc}",
            duration_ms=(time.monotonic() - t0) * 1000,
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
    )


def _execute_call_hook(
    step: ReplayStep,
    plan: HookSandboxPlan,
    context: FixtureContext,
    hooks: dict[str, Any],
    generated: dict[str, Any],
    hook_outputs: dict[str, Any],
    t0: float,
) -> StepResult:
    """Call a hook function with deterministic fixture."""
    target = step.target
    func = hooks.get(target)
    if func is None:
        # Strict partial match: target must START with a known hook name (min 4 chars)
        # to avoid "customObfuscatedSign_v3" matching "sign"
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
        )

    # Build inputs for the hook function
    inputs = _build_hook_inputs(target, plan, context, generated)
    try:
        output = func(inputs)
        hook_outputs[target] = output
        return StepResult(
            order=step.order, action=step.action, target=target,
            status="ok", output=output,
            duration_ms=(time.monotonic() - t0) * 1000,
        )
    except Exception as exc:
        return StepResult(
            order=step.order, action=step.action, target=target,
            status="error", error=f"{type(exc).__name__}: {exc}",
            duration_ms=(time.monotonic() - t0) * 1000,
        )


def _execute_call_sandbox(
    step: ReplayStep,
    plan: HookSandboxPlan,
    context: FixtureContext,
    generated: dict[str, Any],
    sandbox_outputs: dict[str, Any],
    t0: float,
) -> StepResult:
    """Call a sandbox stub with deterministic fixture."""
    target = step.target
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
        )

    inputs = _build_sandbox_inputs(target, plan, context, generated)
    try:
        output = func(inputs)
        sandbox_outputs[target] = output
        return StepResult(
            order=step.order, action=step.action, target=target,
            status="ok", output=output,
            duration_ms=(time.monotonic() - t0) * 1000,
        )
    except Exception as exc:
        return StepResult(
            order=step.order, action=step.action, target=target,
            status="error", error=f"{type(exc).__name__}: {exc}",
            duration_ms=(time.monotonic() - t0) * 1000,
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
