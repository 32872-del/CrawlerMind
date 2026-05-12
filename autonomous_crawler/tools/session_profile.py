"""Authorized session profile model.

Profiles describe user-provided headers/cookies/storage state. They are never
required for normal CLM use and sensitive values are redacted in summaries.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


SENSITIVE_HEADER_NAMES = {"authorization", "cookie", "x-api-key", "x-auth-token"}


@dataclass(frozen=True)
class SessionProfile:
    name: str = "default"
    allowed_domains: list[str] = field(default_factory=list)
    headers: dict[str, str] = field(default_factory=dict)
    cookies: dict[str, str] = field(default_factory=dict)
    storage_state_path: str = ""

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> "SessionProfile":
        payload = payload or {}
        headers = payload.get("headers") or {}
        cookies = payload.get("cookies") or {}
        allowed_domains = payload.get("allowed_domains") or []
        return cls(
            name=str(payload.get("name") or "default"),
            allowed_domains=[str(item).lower() for item in allowed_domains],
            headers={str(k): str(v) for k, v in headers.items()} if isinstance(headers, dict) else {},
            cookies={str(k): str(v) for k, v in cookies.items()} if isinstance(cookies, dict) else {},
            storage_state_path=str(payload.get("storage_state_path") or ""),
        )

    def applies_to(self, url: str) -> bool:
        if not self.allowed_domains:
            return True
        hostname = (urlparse(url).hostname or "").lower()
        return any(hostname == domain or hostname.endswith(f".{domain}") for domain in self.allowed_domains)

    def validate(self) -> list[str]:
        errors: list[str] = []
        if self.has_global_scope():
            errors.append("allowed_domains is empty; session applies to all domains")
        if self.storage_state_path and not Path(self.storage_state_path).exists():
            errors.append("storage_state_path does not exist")
        return errors

    def has_global_scope(self) -> bool:
        return not bool(self.allowed_domains)

    def headers_for(self, url: str) -> dict[str, str]:
        if not self.applies_to(url):
            return {}
        headers = dict(self.headers)
        if self.cookies and "Cookie" not in headers and "cookie" not in {k.lower() for k in headers}:
            headers["Cookie"] = "; ".join(f"{key}={value}" for key, value in self.cookies.items())
        return headers

    def to_safe_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "allowed_domains": list(self.allowed_domains),
            "global_scope": self.has_global_scope(),
            "headers": redact_headers(self.headers),
            "cookies": {key: "[redacted]" for key in self.cookies},
            "storage_state_path": redact_storage_state_path(self.storage_state_path),
            "errors": self.validate(),
        }


def redact_headers(headers: dict[str, Any] | None) -> dict[str, str]:
    safe: dict[str, str] = {}
    for key, value in (headers or {}).items():
        if str(key).lower() in SENSITIVE_HEADER_NAMES:
            safe[str(key)] = "[redacted]"
        else:
            safe[str(key)] = str(value)
    return safe


def redact_storage_state_path(path: str) -> str:
    if not path:
        return ""
    name = Path(path).name
    return f"[redacted-path]/{name}" if name else "[redacted-path]"
