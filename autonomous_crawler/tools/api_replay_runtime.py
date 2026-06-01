"""Executable API replay bridge for profile-driven crawls.

This module connects the request diagnostics layer with the existing
hook/sandbox replay executor.  It is intentionally profile/data driven:
site-specific signing code, if needed, lives in profile hints as sandbox source
or bindings, while the core runner only knows how to build, execute, and apply
request patches.
"""
from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from .hook_sandbox_planner import HookSandboxPlan, HookTarget, ReplayStep, SandboxTarget
from .replay_executor import FixtureContext, ReplayResult, execute_replay


@dataclass(frozen=True)
class ReplayOutputBinding:
    """Where to place one replay output in the outgoing request."""

    source: str
    location: str
    path: str
    value_type: str = "hook"

    def to_dict(self) -> dict[str, str]:
        return {
            "source": self.source,
            "location": self.location,
            "path": self.path,
            "value_type": self.value_type,
        }


@dataclass
class ApiReplayRuntimeResult:
    """Result of applying replay runtime to one API request."""

    url: str
    headers: dict[str, str]
    json_body: Any = None
    applied: bool = False
    plan: dict[str, Any] = field(default_factory=dict)
    replay_result: dict[str, Any] = field(default_factory=dict)
    bindings_applied: list[dict[str, str]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "headers": dict(self.headers),
            "json_body": self.json_body,
            "applied": self.applied,
            "plan": dict(self.plan),
            "replay_result": dict(self.replay_result),
            "bindings_applied": list(self.bindings_applied),
            "errors": list(self.errors),
        }


def apply_api_replay_runtime(
    *,
    api_hints: dict[str, Any] | None,
    url: str,
    headers: dict[str, str] | None = None,
    json_body: Any = None,
    method: str = "GET",
) -> ApiReplayRuntimeResult:
    """Execute and apply a profile API replay plan, if one is available.

    Supported profile fields under ``api_hints``:

    - ``replay_diagnostics.signed_components``: default output bindings.
    - ``replay_runtime.hook_name``: hook target name, default
      ``api_request_signature``.
    - ``replay_runtime.hook_sources``: optional JS source code by hook name.
    - ``replay_runtime.output_bindings``: explicit output bindings.
    - ``replay_runtime.secret_key/session_id/encrypt_key``: fixture/sandbox
      context inputs for authorized/custom profiles.
    - ``replay_plan``: optional explicit hook/sandbox plan dictionary.
    """
    api_hints = dict(api_hints or {})
    next_url = str(url or "")
    next_headers = {str(k): str(v) for k, v in dict(headers or {}).items()}
    next_json = copy.deepcopy(json_body)

    plan = replay_plan_from_api_hints(api_hints)
    bindings = replay_output_bindings_from_api_hints(api_hints)
    if not plan or not plan.replay_steps or not bindings:
        return ApiReplayRuntimeResult(url=next_url, headers=next_headers, json_body=next_json)

    runtime_cfg = api_hints.get("replay_runtime") if isinstance(api_hints.get("replay_runtime"), dict) else {}
    base_url, params = split_url_query(next_url)
    context = FixtureContext(
        url=base_url,
        params=params,
        headers=next_headers,
        body=json.dumps(next_json, ensure_ascii=False, sort_keys=True) if next_json is not None else str(api_hints.get("post_data") or ""),
        secret_key=str(runtime_cfg.get("secret_key") or runtime_cfg.get("api_secret") or ""),
        session_id=str(runtime_cfg.get("session_id") or ""),
        encrypt_key=str(runtime_cfg.get("encrypt_key") or runtime_cfg.get("secret_key") or ""),
        timeout_ms=int(runtime_cfg.get("timeout_ms") or 5000),
    )
    result = execute_replay(plan, context=context)
    errors: list[str] = []
    if not result.success:
        errors.extend(result.blockers_remaining)

    applied_bindings: list[dict[str, str]] = []
    for binding in bindings:
        value = replay_output_value(result, binding)
        if value in (None, ""):
            errors.append(f"missing replay output for {binding.value_type}:{binding.source}")
            continue
        next_url, next_headers, next_json = apply_output_binding(
            url=next_url,
            headers=next_headers,
            json_body=next_json,
            binding=binding,
            value=value,
        )
        applied_bindings.append(binding.to_dict())

    return ApiReplayRuntimeResult(
        url=next_url,
        headers=next_headers,
        json_body=next_json,
        applied=bool(applied_bindings),
        plan=plan.to_dict(),
        replay_result=result.to_dict(),
        bindings_applied=applied_bindings,
        errors=errors,
    )


def replay_plan_from_api_hints(api_hints: dict[str, Any] | None) -> HookSandboxPlan | None:
    api_hints = dict(api_hints or {})
    explicit = api_hints.get("replay_plan") if isinstance(api_hints.get("replay_plan"), dict) else None
    if explicit:
        return hook_sandbox_plan_from_dict(explicit)

    diagnostics = api_hints.get("replay_diagnostics") if isinstance(api_hints.get("replay_diagnostics"), dict) else {}
    runtime_cfg = api_hints.get("replay_runtime") if isinstance(api_hints.get("replay_runtime"), dict) else {}
    signed_components = diagnostics.get("signed_components") if isinstance(diagnostics.get("signed_components"), list) else []
    sandbox_targets_cfg = runtime_cfg.get("sandbox_targets") if isinstance(runtime_cfg.get("sandbox_targets"), list) else []
    if not signed_components and not runtime_cfg.get("enabled") and not sandbox_targets_cfg:
        return None

    hook_name = str(runtime_cfg.get("hook_name") or "api_request_signature").strip() or "api_request_signature"
    hook_sources = runtime_cfg.get("hook_sources") if isinstance(runtime_cfg.get("hook_sources"), dict) else {}
    hook_targets: list[HookTarget] = []
    if signed_components or runtime_cfg.get("hook_name") or hook_sources:
        source_code = str(hook_sources.get(hook_name) or runtime_cfg.get("source_code") or "")
        hook_targets.append(HookTarget(
            name=hook_name,
            kind=str(runtime_cfg.get("hook_kind") or "signature"),
            source="api_replay_runtime",
            confidence="high" if signed_components else "medium",
            inputs_to_capture=["request_url", "query_params", "headers", "body", "key"],
            outputs_to_capture=["signature", "token"],
            source_code=source_code,
        ))

    sandbox_targets: list[SandboxTarget] = []
    sandbox_sources = runtime_cfg.get("sandbox_sources") if isinstance(runtime_cfg.get("sandbox_sources"), dict) else {}
    for item in sandbox_targets_cfg:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        sandbox_targets.append(SandboxTarget(
            name=name,
            runtime=str(item.get("runtime") or "browser_or_node"),
            reason=str(item.get("reason") or "profile_replay_runtime"),
            capture=[str(value) for value in (item.get("capture") or [])],
            source_code=str(item.get("source_code") or sandbox_sources.get(name) or ""),
        ))

    replay_steps = build_replay_steps(hook_targets, sandbox_targets)
    return HookSandboxPlan(
        hook_targets=hook_targets,
        sandbox_targets=sandbox_targets,
        replay_steps=replay_steps,
        risk_level=str(diagnostics.get("risk_level") or ("medium" if hook_targets else "none")),
        blockers=[],
    )


def hook_sandbox_plan_from_dict(payload: dict[str, Any]) -> HookSandboxPlan:
    hook_targets = [
        HookTarget(
            name=str(item.get("name") or ""),
            kind=str(item.get("kind") or "signature"),
            source=str(item.get("source") or "profile_replay_plan"),
            confidence=str(item.get("confidence") or "medium"),
            context=str(item.get("context") or ""),
            inputs_to_capture=[str(value) for value in (item.get("inputs_to_capture") or [])],
            outputs_to_capture=[str(value) for value in (item.get("outputs_to_capture") or [])],
            source_code=str(item.get("source_code") or ""),
        )
        for item in payload.get("hook_targets", [])
        if isinstance(item, dict) and str(item.get("name") or "").strip()
    ]
    sandbox_targets = [
        SandboxTarget(
            name=str(item.get("name") or ""),
            runtime=str(item.get("runtime") or "browser_or_node"),
            reason=str(item.get("reason") or ""),
            capture=[str(value) for value in (item.get("capture") or [])],
            source_code=str(item.get("source_code") or ""),
        )
        for item in payload.get("sandbox_targets", [])
        if isinstance(item, dict) and str(item.get("name") or "").strip()
    ]
    replay_steps = [
        ReplayStep(
            order=int(item.get("order") or index),
            action=str(item.get("action") or ""),
            target=str(item.get("target") or ""),
            depends_on=[int(value) for value in (item.get("depends_on") or [])],
        )
        for index, item in enumerate(payload.get("replay_steps", []))
        if isinstance(item, dict) and str(item.get("action") or "").strip()
    ]
    if not replay_steps:
        replay_steps = build_replay_steps(hook_targets, sandbox_targets)
    return HookSandboxPlan(
        hook_targets=hook_targets,
        sandbox_targets=sandbox_targets,
        replay_steps=replay_steps,
        risk_level=str(payload.get("risk_level") or "medium"),
        blockers=[str(value) for value in (payload.get("blockers") or [])],
    )


def build_replay_steps(hooks: list[HookTarget], sandbox_targets: list[SandboxTarget]) -> list[ReplayStep]:
    steps: list[ReplayStep] = []
    order = 0
    for hook in hooks:
        steps.append(ReplayStep(order=order, action="call_hook", target=hook.name))
        order += 1
    hook_indices = list(range(order))
    for target in sandbox_targets:
        steps.append(ReplayStep(order=order, action="call_sandbox", target=target.name, depends_on=hook_indices))
        order += 1
    prior = list(range(order))
    steps.append(ReplayStep(order=order, action="build_request", target="final_request", depends_on=prior))
    order += 1
    steps.append(ReplayStep(order=order, action="send_request", target="transport", depends_on=[order - 1]))
    return steps


def replay_output_bindings_from_api_hints(api_hints: dict[str, Any] | None) -> list[ReplayOutputBinding]:
    api_hints = dict(api_hints or {})
    runtime_cfg = api_hints.get("replay_runtime") if isinstance(api_hints.get("replay_runtime"), dict) else {}
    explicit = runtime_cfg.get("output_bindings") if isinstance(runtime_cfg.get("output_bindings"), list) else []
    bindings: list[ReplayOutputBinding] = []
    for item in explicit:
        if not isinstance(item, dict):
            continue
        binding = _binding_from_dict(item)
        if binding:
            bindings.append(binding)
    if bindings:
        return bindings

    diagnostics = api_hints.get("replay_diagnostics") if isinstance(api_hints.get("replay_diagnostics"), dict) else {}
    signed_components = diagnostics.get("signed_components") if isinstance(diagnostics.get("signed_components"), list) else []
    hook_name = str(runtime_cfg.get("hook_name") or "api_request_signature").strip() or "api_request_signature"
    for item in signed_components:
        if not isinstance(item, dict):
            continue
        location = str(item.get("location") or "").strip().lower()
        path = str(item.get("path") or item.get("name") or "").strip()
        if location in {"query", "header", "json"} and path:
            bindings.append(ReplayOutputBinding(source=hook_name, value_type="hook", location=location, path=path))
    return bindings


def replay_output_value(result: ReplayResult, binding: ReplayOutputBinding) -> Any:
    if binding.value_type == "sandbox":
        return result.sandbox_outputs.get(binding.source)
    if binding.value_type == "generated":
        return result.generated_inputs.get(binding.source)
    return result.hook_outputs.get(binding.source)


def apply_output_binding(
    *,
    url: str,
    headers: dict[str, str],
    json_body: Any,
    binding: ReplayOutputBinding,
    value: Any,
) -> tuple[str, dict[str, str], Any]:
    next_url = url
    next_headers = dict(headers)
    next_json = copy.deepcopy(json_body)
    if binding.location == "query":
        next_url = with_query_params(next_url, {binding.path: value})
    elif binding.location == "header":
        next_headers[binding.path] = str(value)
    elif binding.location == "json":
        if not isinstance(next_json, (dict, list)):
            next_json = {}
        set_value_at_path(next_json, binding.path, value)
    return next_url, next_headers, next_json


def split_url_query(url: str) -> tuple[str, dict[str, Any]]:
    parsed = urlparse(str(url or ""))
    params = {key: values[-1] if values else "" for key, values in parse_qs(parsed.query, keep_blank_values=True).items()}
    base = urlunparse((parsed.scheme, parsed.netloc, parsed.path or "/", parsed.params, "", parsed.fragment))
    return base, params


def with_query_params(url: str, params: dict[str, Any]) -> str:
    parsed = urlparse(str(url or ""))
    query = parse_qs(parsed.query, keep_blank_values=True)
    for key, value in params.items():
        if value is None:
            continue
        query[str(key)] = [str(value)]
    encoded = urlencode(query, doseq=True)
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path or "/", parsed.params, encoded, parsed.fragment))


def set_value_at_path(payload: Any, path: str, value: Any) -> bool:
    parts = [part for part in str(path or "").split(".") if part]
    if not parts:
        return False
    current = payload
    for part in parts[:-1]:
        if isinstance(current, dict):
            if part not in current or not isinstance(current[part], (dict, list)):
                current[part] = {}
            current = current[part]
        elif isinstance(current, list) and part.isdigit():
            index = int(part)
            if not (0 <= index < len(current)):
                return False
            current = current[index]
        else:
            return False
    last = parts[-1]
    if isinstance(current, dict):
        current[last] = value
        return True
    if isinstance(current, list) and last.isdigit():
        index = int(last)
        if 0 <= index < len(current):
            current[index] = value
            return True
    return False


def _binding_from_dict(item: dict[str, Any]) -> ReplayOutputBinding | None:
    source = str(item.get("source") or item.get("name") or "").strip()
    location = str(item.get("location") or "").strip().lower()
    path = str(item.get("path") or item.get("name") or "").strip()
    value_type = str(item.get("value_type") or item.get("type") or "hook").strip().lower()
    if not source or location not in {"query", "header", "json"} or not path:
        return None
    if value_type not in {"hook", "sandbox", "generated"}:
        value_type = "hook"
    return ReplayOutputBinding(source=source, location=location, path=path, value_type=value_type)
