"""Request-level replay diagnostics and dynamic input refresh helpers.

This module is intentionally data-only. It does not reverse a site's private
algorithm, but it gives CLM a concrete runtime contract for API replay:
identify volatile request parts, mark signature/session dependencies, and
refresh generic dynamic inputs such as timestamps and nonces before each run.
"""
from __future__ import annotations

import copy
import json
import secrets
import time
import uuid
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse


TIMESTAMP_NAMES = {
    "t", "ts", "_ts", "timestamp", "time", "mtime", "requesttime",
    "request_time", "clienttime", "client_time",
}
NONCE_NAMES = {
    "nonce", "noncestr", "nonce_str", "rand", "random", "r", "_", "requestid",
    "request_id", "traceid", "trace_id", "uuid",
}
SIGNATURE_NAMES = {
    "sign", "signature", "sig", "_signature", "xsign", "xsignature",
    "xbogus", "wbi", "token", "xtoken", "auth", "authorization",
}
SESSION_HEADER_NAMES = {
    "cookie", "authorization", "xcsrftoken", "xxsrftoken", "csrftoken",
    "xrequestedwith", "xmagentocacheid", "store", "xstore",
}


@dataclass(frozen=True)
class ReplayDynamicInput:
    name: str
    location: str
    path: str
    generation_method: str
    refresh_each_request: bool = True
    required: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "location": self.location,
            "path": self.path,
            "generation_method": self.generation_method,
            "refresh_each_request": self.refresh_each_request,
            "required": self.required,
        }


@dataclass(frozen=True)
class ReplayDiagnostics:
    replay_required: bool = False
    risk_level: str = "none"
    dynamic_inputs: list[ReplayDynamicInput] = field(default_factory=list)
    signed_components: list[dict[str, str]] = field(default_factory=list)
    session_requirements: list[dict[str, str]] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "replay-diagnostics/v1",
            "replay_required": self.replay_required,
            "risk_level": self.risk_level,
            "dynamic_inputs": [item.to_dict() for item in self.dynamic_inputs],
            "signed_components": list(self.signed_components),
            "session_requirements": list(self.session_requirements),
            "recommendations": list(self.recommendations),
        }


def build_replay_diagnostics(
    *,
    url: str,
    method: str = "GET",
    headers: dict[str, Any] | None = None,
    post_json: Any = None,
    post_data: str = "",
) -> ReplayDiagnostics:
    """Inspect a captured API request and describe replay fragility.

    Output is designed to be stored under ``SiteProfile.api_hints`` and consumed
    later by the profile runner before it builds each request.
    """
    dynamic_inputs: list[ReplayDynamicInput] = []
    signed_components: list[dict[str, str]] = []
    session_requirements: list[dict[str, str]] = []

    parsed = urlparse(str(url or ""))
    query = parse_qs(parsed.query, keep_blank_values=True)
    for name, values in query.items():
        normalized = _normalize_name(name)
        value = values[0] if values else ""
        if normalized in TIMESTAMP_NAMES or _looks_like_timestamp(value):
            dynamic_inputs.append(ReplayDynamicInput(
                name=str(name),
                location="query",
                path=str(name),
                generation_method=_timestamp_generation_method(value),
            ))
        elif normalized in NONCE_NAMES:
            dynamic_inputs.append(ReplayDynamicInput(
                name=str(name),
                location="query",
                path=str(name),
                generation_method="random_hex_16" if normalized != "uuid" else "uuid4",
            ))
        if normalized in SIGNATURE_NAMES:
            signed_components.append({"location": "query", "name": str(name), "kind": "signature_or_token"})

    for key, value in dict(headers or {}).items():
        normalized = _normalize_name(key)
        if normalized in SESSION_HEADER_NAMES:
            session_requirements.append({"location": "header", "name": str(key), "kind": "session_header"})
        if normalized in SIGNATURE_NAMES:
            signed_components.append({"location": "header", "name": str(key), "kind": "signature_or_token"})
        if normalized in TIMESTAMP_NAMES or _looks_like_timestamp(str(value)):
            dynamic_inputs.append(ReplayDynamicInput(
                name=str(key),
                location="header",
                path=str(key),
                generation_method=_timestamp_generation_method(str(value)),
            ))
        elif normalized in NONCE_NAMES:
            dynamic_inputs.append(ReplayDynamicInput(
                name=str(key),
                location="header",
                path=str(key),
                generation_method="random_hex_16",
            ))

    body_payload = post_json if isinstance(post_json, (dict, list)) else _parse_json(post_data)
    if isinstance(body_payload, (dict, list)):
        for path, value in _walk_json_leaf_values(body_payload):
            name = path.split(".")[-1] if path else ""
            normalized = _normalize_name(name)
            if normalized in TIMESTAMP_NAMES or _looks_like_timestamp(str(value)):
                dynamic_inputs.append(ReplayDynamicInput(
                    name=name,
                    location="json",
                    path=path,
                    generation_method=_timestamp_generation_method(str(value)),
                ))
            elif normalized in NONCE_NAMES:
                dynamic_inputs.append(ReplayDynamicInput(
                    name=name,
                    location="json",
                    path=path,
                    generation_method="uuid4" if normalized == "uuid" else "random_hex_16",
                ))
            if normalized in SIGNATURE_NAMES:
                signed_components.append({"location": "json", "name": name, "path": path, "kind": "signature_or_token"})

    dynamic_inputs = _dedupe_dynamic_inputs(dynamic_inputs)
    signed_components = _dedupe_dicts(signed_components, ("location", "name", "path"))
    session_requirements = _dedupe_dicts(session_requirements, ("location", "name"))
    recommendations = _recommendations(dynamic_inputs, signed_components, session_requirements)
    risk_level = _risk_level(dynamic_inputs, signed_components, session_requirements)
    return ReplayDiagnostics(
        replay_required=bool(dynamic_inputs or signed_components or session_requirements),
        risk_level=risk_level,
        dynamic_inputs=dynamic_inputs,
        signed_components=signed_components,
        session_requirements=session_requirements,
        recommendations=recommendations,
    )


def apply_replay_dynamic_inputs(
    *,
    url: str,
    headers: dict[str, str] | None = None,
    json_body: Any = None,
    diagnostics: dict[str, Any] | None = None,
) -> tuple[str, dict[str, str], Any]:
    """Refresh generic dynamic inputs declared by replay diagnostics."""
    diagnostics = diagnostics if isinstance(diagnostics, dict) else {}
    inputs = diagnostics.get("dynamic_inputs") if isinstance(diagnostics.get("dynamic_inputs"), list) else []
    next_url = str(url or "")
    next_headers = dict(headers or {})
    next_json = copy.deepcopy(json_body)

    query_updates: dict[str, Any] = {}
    for item in inputs:
        if not isinstance(item, dict) or not item.get("refresh_each_request", True):
            continue
        location = str(item.get("location") or "")
        path = str(item.get("path") or item.get("name") or "")
        if not path:
            continue
        value = generate_dynamic_value(str(item.get("generation_method") or "preserve"))
        if location == "query":
            query_updates[path] = value
        elif location == "header":
            next_headers[path] = str(value)
        elif location == "json" and isinstance(next_json, (dict, list)):
            set_value_at_path(next_json, path, value)
    if query_updates:
        next_url = with_query_params(next_url, query_updates)
    return next_url, next_headers, next_json


def generate_dynamic_value(method: str) -> Any:
    normalized = str(method or "").strip().lower()
    if normalized in {"date.now()", "unix_ms", "timestamp_ms"}:
        return int(time.time() * 1000)
    if normalized in {"unix_s", "timestamp_s", "time.time()"}:
        return int(time.time())
    if normalized == "uuid4":
        return str(uuid.uuid4())
    if normalized.startswith("random_hex"):
        size = 16
        parts = normalized.split("_")
        if parts and parts[-1].isdigit():
            size = max(4, min(int(parts[-1]), 64))
        return secrets.token_hex(max(1, size // 2))[:size]
    if normalized in {"math.random()", "random_float"}:
        return f"{secrets.randbelow(10**12) / 10**12:.12f}"
    return ""


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


def with_query_params(url: str, params: dict[str, Any]) -> str:
    parsed = urlparse(str(url or ""))
    query = parse_qs(parsed.query, keep_blank_values=True)
    for key, value in params.items():
        if value is None:
            continue
        query[str(key)] = [str(value)]
    encoded = urlencode(query, doseq=True)
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path or "/", parsed.params, encoded, parsed.fragment))


def _normalize_name(value: Any) -> str:
    return str(value or "").strip().lower().replace("_", "").replace("-", "")


def _looks_like_timestamp(value: str) -> bool:
    text = str(value or "").strip()
    return bool(text.isdigit() and len(text) in {10, 13})


def _timestamp_generation_method(value: str) -> str:
    text = str(value or "").strip()
    return "unix_ms" if len(text) >= 13 else "unix_s"


def _parse_json(text: str) -> Any:
    try:
        return json.loads(str(text or ""))
    except (TypeError, ValueError):
        return None


def _walk_json_leaf_values(payload: Any, prefix: str = "") -> list[tuple[str, Any]]:
    values: list[tuple[str, Any]] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            values.extend(_walk_json_leaf_values(value, path))
    elif isinstance(payload, list):
        for index, value in enumerate(payload[:100]):
            path = f"{prefix}.{index}" if prefix else str(index)
            values.extend(_walk_json_leaf_values(value, path))
    else:
        values.append((prefix, payload))
    return values


def _dedupe_dynamic_inputs(values: list[ReplayDynamicInput]) -> list[ReplayDynamicInput]:
    output: list[ReplayDynamicInput] = []
    seen: set[tuple[str, str]] = set()
    for item in values:
        key = (item.location, item.path)
        if key not in seen:
            seen.add(key)
            output.append(item)
    return output


def _dedupe_dicts(values: list[dict[str, str]], keys: tuple[str, ...]) -> list[dict[str, str]]:
    output: list[dict[str, str]] = []
    seen: set[tuple[str, ...]] = set()
    for item in values:
        key = tuple(str(item.get(part) or "") for part in keys)
        if key not in seen:
            seen.add(key)
            output.append(item)
    return output


def _risk_level(
    dynamic_inputs: list[ReplayDynamicInput],
    signed_components: list[dict[str, str]],
    session_requirements: list[dict[str, str]],
) -> str:
    if signed_components:
        return "high" if session_requirements else "medium"
    if session_requirements:
        return "medium"
    if dynamic_inputs:
        return "low"
    return "none"


def _recommendations(
    dynamic_inputs: list[ReplayDynamicInput],
    signed_components: list[dict[str, str]],
    session_requirements: list[dict[str, str]],
) -> list[str]:
    output: list[str] = []
    if dynamic_inputs:
        output.append("refresh_dynamic_inputs_before_each_api_request")
    if signed_components:
        output.append("signature_or_token_component_detected_prepare_hook_or_browser_replay")
    if session_requirements:
        output.append("reuse_browser_session_or_profile_headers_for_api_replay")
    if not output:
        output.append("direct_api_replay_likely_stable")
    return output
