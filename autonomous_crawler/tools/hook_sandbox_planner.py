"""Hook / Sandbox planning from JS and API evidence (REVERSE-HARDEN-1).

Turns crypto/signature evidence into structured, actionable plans:
hook targets, sandbox targets, dynamic inputs, and replay steps.
Purely advisory — does not execute JS, recover keys, or bypass protections.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class HookTarget:
    """One function/routine to intercept via browser hooks or proxy."""
    name: str
    kind: str  # signature | encryption | token | timestamp | nonce | encoding
    source: str  # js_static | js_crypto | api_evidence
    confidence: str = "medium"
    context: str = ""
    inputs_to_capture: list[str] = field(default_factory=list)
    outputs_to_capture: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "kind": self.kind,
            "source": self.source,
            "confidence": self.confidence,
            "context": self.context[:200],
            "inputs_to_capture": list(self.inputs_to_capture),
            "outputs_to_capture": list(self.outputs_to_capture),
        }


@dataclass(frozen=True)
class DynamicInput:
    """A per-request value that must be generated at request time."""
    name: str  # timestamp | nonce | uuid | session_token | custom
    generation_method: str  # Date.now() | crypto.getRandomValues() | Math.random() | custom
    required: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "generation_method": self.generation_method,
            "required": self.required,
        }


@dataclass(frozen=True)
class SandboxTarget:
    """A routine that needs runtime execution (browser or Node)."""
    name: str
    runtime: str  # browser | node | browser_or_node
    reason: str = ""
    capture: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "runtime": self.runtime,
            "reason": self.reason,
            "capture": list(self.capture),
        }


@dataclass(frozen=True)
class ReplayStep:
    """One step in the replay sequence."""
    order: int
    action: str  # generate_input | call_hook | call_sandbox | build_request | send_request
    target: str  # function or input name
    depends_on: list[int] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "order": self.order,
            "action": self.action,
            "target": self.target,
            "depends_on": list(self.depends_on),
        }


@dataclass
class HookSandboxPlan:
    """Complete hook/sandbox plan from JS and API evidence."""
    hook_targets: list[HookTarget] = field(default_factory=list)
    sandbox_targets: list[SandboxTarget] = field(default_factory=list)
    dynamic_inputs: list[DynamicInput] = field(default_factory=list)
    replay_steps: list[ReplayStep] = field(default_factory=list)
    risk_level: str = "none"  # none | low | medium | high
    blockers: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "hook_targets": [t.to_dict() for t in self.hook_targets],
            "sandbox_targets": [t.to_dict() for t in self.sandbox_targets],
            "dynamic_inputs": [i.to_dict() for i in self.dynamic_inputs],
            "replay_steps": [s.to_dict() for s in self.replay_steps],
            "risk_level": self.risk_level,
            "blockers": list(self.blockers),
        }


# ---------------------------------------------------------------------------
# Signal-to-plan mapping constants
# ---------------------------------------------------------------------------

_HASH_SIGNALS = {"md5", "sha1", "sha256", "sha512"}
_HMAC_SIGNALS = {"hmac"}
_SIGNATURE_SIGNALS = {"sign"}
_ENCODING_SIGNALS = {"base64", "urlencode"}
_ENCRYPTION_SIGNALS = {"aes", "rsa", "cryptojs"}
_WEBCRYPTO_SIGNALS = {"subtle.digest", "subtle.sign", "getRandomValues"}
_TIMESTAMP_SIGNALS = {"timestamp"}
_NONCE_SIGNALS = {"nonce"}
_TOKEN_SIGNALS = {"xbogus", "wbi"}

_HOOK_KIND_MAP: dict[str, str] = {}
for _s in _HASH_SIGNALS:
    _HOOK_KIND_MAP[_s] = "signature"
for _s in _HMAC_SIGNALS:
    _HOOK_KIND_MAP[_s] = "signature"
for _s in _SIGNATURE_SIGNALS:
    _HOOK_KIND_MAP[_s] = "signature"
for _s in _ENCODING_SIGNALS:
    _HOOK_KIND_MAP[_s] = "encoding"
for _s in _TOKEN_SIGNALS:
    _HOOK_KIND_MAP[_s] = "token"

_SANDBOX_NAMES = set(_ENCRYPTION_SIGNALS) | set(_WEBCRYPTO_SIGNALS)

_DYNAMIC_INPUT_MAP: dict[str, DynamicInput] = {
    "timestamp": DynamicInput(name="timestamp", generation_method="Date.now()", required=True),
    "nonce": DynamicInput(name="nonce", generation_method="Math.random().toString(36).substring(2)", required=True),
}


# ---------------------------------------------------------------------------
# Main planner
# ---------------------------------------------------------------------------

def plan_hook_sandbox(
    js_evidence: dict[str, Any] | None,
    api_candidates: list[Any] | None = None,
) -> HookSandboxPlan:
    """Build a hook/sandbox plan from JS evidence and API candidates.

    Args:
        js_evidence: JsEvidenceReport.to_dict() output (items, crypto_analysis, etc.)
        api_candidates: list of API candidate dicts (url, method, kind, headers, body)

    Returns:
        HookSandboxPlan with hook targets, sandbox targets, dynamic inputs, and replay steps.
    """
    if not isinstance(js_evidence, dict):
        js_evidence = {}
    if api_candidates is None:
        api_candidates = []

    hook_targets: list[HookTarget] = []
    sandbox_targets: list[SandboxTarget] = []
    dynamic_inputs: list[DynamicInput] = []
    seen_hooks: set[str] = set()
    seen_sandbox: set[str] = set()
    seen_inputs: set[str] = set()

    # 1. Extract from JS crypto signals and suspicious functions/calls
    for item in js_evidence.get("items") or []:
        if not isinstance(item, dict):
            continue
        source_url = item.get("url", "")
        inline_id = item.get("inline_id", "")
        source_label = f"{source_url}#{inline_id}" if inline_id else source_url

        # Crypto analysis signals
        crypto = item.get("crypto_analysis") or {}
        if isinstance(crypto, dict):
            for signal in crypto.get("signals") or []:
                if not isinstance(signal, dict):
                    continue
                _process_crypto_signal(
                    signal, source_label,
                    hook_targets, sandbox_targets, dynamic_inputs,
                    seen_hooks, seen_sandbox, seen_inputs,
                )

            # Categories → dynamic inputs
            for cat in crypto.get("categories") or []:
                if cat in _DYNAMIC_INPUT_MAP and cat not in seen_inputs:
                    seen_inputs.add(cat)
                    dynamic_inputs.append(_DYNAMIC_INPUT_MAP[cat])

        # Suspicious functions
        for func in item.get("suspicious_functions") or []:
            if not isinstance(func, dict):
                continue
            name = func.get("name", "")
            if not name or name in seen_hooks:
                continue
            reason = func.get("reason", "")
            if reason == "signature":
                seen_hooks.add(name)
                hook_targets.append(HookTarget(
                    name=name, kind="signature", source="js_static",
                    confidence="medium",
                    inputs_to_capture=["url", "params", "headers"],
                    outputs_to_capture=["signature_value"],
                ))
            elif reason == "encryption":
                if name not in seen_sandbox:
                    seen_sandbox.add(name)
                    sandbox_targets.append(SandboxTarget(
                        name=name, runtime="browser_or_node",
                        reason="encryption_routine_detected",
                        capture=["plaintext", "key_material", "ciphertext"],
                    ))
            elif reason == "token":
                seen_hooks.add(name)
                hook_targets.append(HookTarget(
                    name=name, kind="token", source="js_static",
                    confidence="medium",
                    inputs_to_capture=["session_data", "timestamp"],
                    outputs_to_capture=["token_value"],
                ))

        # Suspicious calls
        for call in item.get("suspicious_calls") or []:
            if not isinstance(call, dict):
                continue
            call_expr = call.get("call", "")
            category = call.get("category", "")
            if not call_expr:
                continue
            # Extract function name from call expression
            func_name = call_expr.split(".")[-1].strip() if "." in call_expr else call_expr.strip()
            if func_name in seen_hooks:
                continue
            if category == "signature":
                seen_hooks.add(func_name)
                hook_targets.append(HookTarget(
                    name=func_name, kind="signature", source="js_crypto",
                    confidence="high",
                    context=call.get("context", "")[:200],
                    inputs_to_capture=["payload", "key"],
                    outputs_to_capture=["signature"],
                ))
            elif category == "encryption":
                if func_name not in seen_sandbox:
                    seen_sandbox.add(func_name)
                    sandbox_targets.append(SandboxTarget(
                        name=func_name, runtime="browser_or_node",
                        reason="encryption_call_detected",
                        capture=["plaintext", "key", "iv", "ciphertext"],
                    ))
            elif category == "token":
                seen_hooks.add(func_name)
                hook_targets.append(HookTarget(
                    name=func_name, kind="token", source="js_crypto",
                    confidence="high",
                    context=call.get("context", "")[:200],
                    inputs_to_capture=["seed_data"],
                    outputs_to_capture=["token"],
                ))

    # 2. Extract from API candidates
    _process_api_candidates(
        api_candidates,
        hook_targets, sandbox_targets, dynamic_inputs,
        seen_hooks, seen_sandbox, seen_inputs,
    )

    # 3. Build replay steps
    replay_steps = _build_replay_steps(hook_targets, sandbox_targets, dynamic_inputs)

    # 4. Compute risk and blockers
    risk_level, blockers = _compute_risk_and_blockers(
        hook_targets, sandbox_targets, dynamic_inputs,
    )

    return HookSandboxPlan(
        hook_targets=hook_targets,
        sandbox_targets=sandbox_targets,
        dynamic_inputs=dynamic_inputs,
        replay_steps=replay_steps,
        risk_level=risk_level,
        blockers=blockers,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _process_crypto_signal(
    signal: dict[str, Any],
    source_label: str,
    hook_targets: list[HookTarget],
    sandbox_targets: list[SandboxTarget],
    dynamic_inputs: list[DynamicInput],
    seen_hooks: set[str],
    seen_sandbox: set[str],
    seen_inputs: set[str],
) -> None:
    kind = str(signal.get("kind") or "")
    name = str(signal.get("name") or "")
    confidence = str(signal.get("confidence") or "medium")
    context = str(signal.get("context") or "")[:200]

    if kind in _HOOK_KIND_MAP:
        hook_kind = _HOOK_KIND_MAP[kind]
        hook_name = name or kind
        if hook_name not in seen_hooks:
            seen_hooks.add(hook_name)
            hook_targets.append(HookTarget(
                name=hook_name, kind=hook_kind, source="js_crypto",
                confidence=confidence, context=context,
                inputs_to_capture=_inputs_for_kind(hook_kind),
                outputs_to_capture=_outputs_for_kind(hook_kind),
            ))

    if kind in _SANDBOX_NAMES or name in _SANDBOX_NAMES:
        sandbox_name = name or kind
        if sandbox_name not in seen_sandbox:
            seen_sandbox.add(sandbox_name)
            runtime = "browser" if "subtle" in name else "browser_or_node"
            sandbox_targets.append(SandboxTarget(
                name=sandbox_name, runtime=runtime,
                reason=f"crypto_{kind}_requires_runtime",
                capture=_capture_for_sandbox(kind, name),
            ))

    if kind == "timestamp" and "timestamp" not in seen_inputs:
        seen_inputs.add("timestamp")
        dynamic_inputs.append(_DYNAMIC_INPUT_MAP["timestamp"])
    if kind == "nonce" and "nonce" not in seen_inputs:
        seen_inputs.add("nonce")
        dynamic_inputs.append(_DYNAMIC_INPUT_MAP["nonce"])


def _process_api_candidates(
    candidates: list[Any],
    hook_targets: list[HookTarget],
    sandbox_targets: list[SandboxTarget],
    dynamic_inputs: list[DynamicInput],
    seen_hooks: set[str],
    seen_sandbox: set[str],
    seen_inputs: set[str],
) -> None:
    from urllib.parse import urlparse, parse_qs

    _API_SIG_KEYWORDS = (
        "signature", "sign", "hmac", "x-sign", "x-signature",
        "x-token", "authorization", "bearer", "api-key",
    )
    _API_ENC_KEYWORDS = ("encrypt", "cipher", "aes", "rsa", "jwe", "jws")
    _API_TS_KEYWORDS = ("timestamp", "ts", "nonce", "nonce_str")

    for candidate in candidates[:10]:
        if not isinstance(candidate, dict):
            continue
        url = str(candidate.get("url") or "").lower()
        body = str(candidate.get("body") or candidate.get("post_data") or "").lower()
        headers = candidate.get("headers") or {}
        headers_str = str(headers).lower() if isinstance(headers, dict) else ""

        parsed = urlparse(url)
        param_keys = set(parse_qs(parsed.query, keep_blank_values=True).keys())

        # Signature/token in URL or headers
        sig_hits = [kw for kw in _API_SIG_KEYWORDS if kw in url or kw in headers_str]
        if sig_hits and "api_signature" not in seen_hooks:
            seen_hooks.add("api_signature")
            hook_targets.append(HookTarget(
                name="api_request_signature", kind="signature", source="api_evidence",
                confidence="high" if len(sig_hits) >= 2 else "medium",
                inputs_to_capture=["request_url", "query_params", "headers", "body"],
                outputs_to_capture=["signature_header", "auth_token"],
            ))

        # Timestamp/nonce in query params
        ts_hits = [kw for kw in _API_TS_KEYWORDS if kw in param_keys]
        for kw in ts_hits:
            if kw not in seen_inputs:
                seen_inputs.add(kw)
                method = "Date.now()" if "ts" in kw or "timestamp" in kw else "Math.random()"
                dynamic_inputs.append(DynamicInput(name=kw, generation_method=method, required=True))

        # Encrypted body
        enc_hits = [kw for kw in _API_ENC_KEYWORDS if kw in body]
        if enc_hits and "api_encryption" not in seen_sandbox:
            seen_sandbox.add("api_encryption")
            sandbox_targets.append(SandboxTarget(
                name="api_payload_encryption", runtime="browser_or_node",
                reason="encrypted_payload_in_api_request",
                capture=["plaintext_payload", "encryption_key", "encrypted_payload"],
            ))


def _inputs_for_kind(kind: str) -> list[str]:
    if kind == "signature":
        return ["url", "params", "headers", "body", "key"]
    if kind == "token":
        return ["session_data", "timestamp", "seed"]
    if kind == "encoding":
        return ["raw_value"]
    return []


def _outputs_for_kind(kind: str) -> list[str]:
    if kind == "signature":
        return ["signature_value"]
    if kind == "token":
        return ["token_value"]
    if kind == "encoding":
        return ["encoded_value"]
    return []


def _capture_for_sandbox(kind: str, name: str) -> list[str]:
    if "subtle" in name:
        return ["algorithm", "key_data", "plaintext_or_ciphertext"]
    if kind == "encryption" or name in ("aes", "rsa", "cryptojs"):
        return ["plaintext", "key_material", "iv_or_nonce", "ciphertext"]
    if kind == "webcrypto":
        return ["algorithm", "key_data", "input", "output"]
    return ["input", "output"]


def _build_replay_steps(
    hooks: list[HookTarget],
    sandbox: list[SandboxTarget],
    inputs: list[DynamicInput],
) -> list[ReplayStep]:
    steps: list[ReplayStep] = []
    order = 0

    # Step 1: Generate dynamic inputs (no dependencies)
    for inp in inputs:
        steps.append(ReplayStep(order=order, action="generate_input", target=inp.name))
        order += 1

    # Step 2: Call hooks (depend on inputs)
    input_indices = list(range(len(inputs)))
    for hook in hooks:
        steps.append(ReplayStep(
            order=order, action="call_hook", target=hook.name,
            depends_on=input_indices,
        ))
        order += 1

    # Step 3: Call sandbox (depend on hooks)
    hook_indices = list(range(len(inputs), len(inputs) + len(hooks)))
    for tgt in sandbox:
        steps.append(ReplayStep(
            order=order, action="call_sandbox", target=tgt.name,
            depends_on=hook_indices or input_indices,
        ))
        order += 1

    # Step 4: Build request (depends on all prior)
    all_prior = list(range(order))
    steps.append(ReplayStep(order=order, action="build_request", target="final_request", depends_on=all_prior))
    order += 1

    # Step 5: Send request
    steps.append(ReplayStep(order=order, action="send_request", target="transport", depends_on=[order - 1]))

    return steps


def _compute_risk_and_blockers(
    hooks: list[HookTarget],
    sandbox: list[SandboxTarget],
    inputs: list[DynamicInput],
) -> tuple[str, list[str]]:
    blockers: list[str] = []

    has_signature = any(h.kind == "signature" for h in hooks)
    has_encryption = bool(sandbox)
    has_dynamic = bool(inputs)
    has_webcrypto = any(s.runtime == "browser" for s in sandbox)

    if has_signature:
        blockers.append("signature_flow_requires_runtime_key_or_hook")
    if has_encryption:
        blockers.append("encryption_requires_runtime_execution")
    if has_webcrypto:
        blockers.append("webcrypto_requires_browser_environment")
    if has_dynamic:
        dynamic_names = [i.name for i in inputs]
        blockers.append(f"dynamic_inputs_required: {', '.join(dynamic_names)}")

    if has_encryption and has_signature:
        risk_level = "high"
    elif has_signature or has_encryption:
        risk_level = "medium"
    elif has_dynamic:
        risk_level = "low"
    else:
        risk_level = "none"

    return risk_level, blockers
