"""Signed capability checks for optional CLM private extensions.

This module is intentionally transparent. It does not hide failures, corrupt
outputs, or sabotage callers. Community capabilities always work. Private
capabilities require a signed local token and otherwise report a clear
`unlicensed` status so callers can degrade to Community behavior.

Token format:

```text
clm1.<base64url-json-payload>.<base64url-hmac-sha256-signature>
```

The HMAC secret is read from `CLM_LICENSE_SECRET` by default. A token can be
provided by `CLM_LICENSE_TOKEN` or by `clm_config.json` under
`license.token`.
"""
from __future__ import annotations

import base64
import hmac
import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


COMMUNITY_CAPABILITIES = frozenset({
    "community.demo",
    "community.mock_crawl",
    "community.basic_cli",
    "community.basic_api",
    "community.workbench",
})

PRIVATE_CAPABILITY_PREFIXES = ("private.", "enterprise.", "pro.")


@dataclass(frozen=True)
class LicensePayload:
    subject: str = ""
    issuer: str = ""
    expires_at: int | None = None
    capabilities: tuple[str, ...] = field(default_factory=tuple)
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "LicensePayload":
        capabilities = payload.get("capabilities") or payload.get("features") or []
        if isinstance(capabilities, str):
            capabilities = [capabilities]
        expires_at = payload.get("expires_at") or payload.get("exp")
        try:
            expires_int = int(expires_at) if expires_at not in (None, "") else None
        except (TypeError, ValueError):
            expires_int = None
        metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
        return cls(
            subject=str(payload.get("subject") or payload.get("sub") or ""),
            issuer=str(payload.get("issuer") or payload.get("iss") or ""),
            expires_at=expires_int,
            capabilities=tuple(sorted({str(item).strip() for item in capabilities if str(item).strip()})),
            metadata=dict(metadata),
        )

    def is_expired(self, *, now: float | None = None) -> bool:
        if self.expires_at is None:
            return False
        return int(now if now is not None else time.time()) >= self.expires_at


@dataclass(frozen=True)
class LicenseCheckResult:
    valid: bool
    reason: str
    payload: LicensePayload | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "reason": self.reason,
            "payload": {
                "subject": self.payload.subject,
                "issuer": self.payload.issuer,
                "expires_at": self.payload.expires_at,
                "capabilities": list(self.payload.capabilities),
                "metadata": dict(self.payload.metadata),
            } if self.payload else None,
        }


@dataclass(frozen=True)
class CapabilityStatus:
    name: str
    available: bool
    edition: str
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "available": self.available,
            "edition": self.edition,
            "reason": self.reason,
        }


class CapabilityGate:
    """Resolve Community and Private Core capability availability."""

    def __init__(
        self,
        *,
        token: str = "",
        secret: str = "",
        public_capabilities: set[str] | None = None,
    ) -> None:
        self._token = token.strip()
        self._secret = secret
        self._public_capabilities = set(public_capabilities or COMMUNITY_CAPABILITIES)
        self._license_result: LicenseCheckResult | None = None

    @property
    def license_result(self) -> LicenseCheckResult:
        if self._license_result is None:
            self._license_result = verify_license_token(self._token, self._secret)
        return self._license_result

    def check(self, capability: str) -> CapabilityStatus:
        name = str(capability or "").strip()
        if not name:
            return CapabilityStatus(name="", available=False, edition="unknown", reason="empty capability")
        if name in self._public_capabilities:
            return CapabilityStatus(name=name, available=True, edition="community", reason="community capability")
        if not _is_private_capability(name):
            return CapabilityStatus(
                name=name,
                available=False,
                edition="unknown",
                reason="capability is not registered as community or private",
            )
        result = self.license_result
        if not result.valid or result.payload is None:
            return CapabilityStatus(name=name, available=False, edition="private", reason=result.reason)
        allowed = set(result.payload.capabilities)
        if "*" in allowed or name in allowed:
            return CapabilityStatus(name=name, available=True, edition="private", reason="licensed")
        return CapabilityStatus(name=name, available=False, edition="private", reason="not included in license")

    def summary(self, capabilities: list[str] | tuple[str, ...] | None = None) -> dict[str, Any]:
        names = list(capabilities or sorted(self._public_capabilities))
        return {
            "license": self.license_result.to_dict(),
            "capabilities": [self.check(name).to_dict() for name in names],
        }


def build_capability_gate(
    *,
    config_path: str | Path | None = None,
    token: str | None = None,
    secret: str | None = None,
) -> CapabilityGate:
    config = _load_config(config_path)
    license_config = config.get("license") if isinstance(config.get("license"), dict) else {}
    resolved_token = (
        token
        or os.environ.get("CLM_LICENSE_TOKEN")
        or str(license_config.get("token") or "")
    )
    resolved_secret = (
        secret
        or os.environ.get("CLM_LICENSE_SECRET")
        or str(license_config.get("secret") or "")
    )
    return CapabilityGate(token=resolved_token, secret=resolved_secret)


def verify_license_token(token: str, secret: str, *, now: float | None = None) -> LicenseCheckResult:
    token = (token or "").strip()
    if not token:
        return LicenseCheckResult(valid=False, reason="no license token configured")
    if not secret:
        return LicenseCheckResult(valid=False, reason="no license verification secret configured")
    parts = token.split(".")
    if len(parts) != 3 or parts[0] != "clm1":
        return LicenseCheckResult(valid=False, reason="invalid token format")
    payload_b64, signature_b64 = parts[1], parts[2]
    signing_input = f"clm1.{payload_b64}".encode("utf-8")
    expected = _b64url_encode(hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest())
    if not hmac.compare_digest(expected, signature_b64):
        return LicenseCheckResult(valid=False, reason="invalid token signature")
    try:
        payload_raw = _b64url_decode(payload_b64).decode("utf-8")
        payload_json = json.loads(payload_raw)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        return LicenseCheckResult(valid=False, reason=f"invalid token payload: {exc}")
    if not isinstance(payload_json, dict):
        return LicenseCheckResult(valid=False, reason="token payload must be an object")
    payload = LicensePayload.from_dict(payload_json)
    if payload.is_expired(now=now):
        return LicenseCheckResult(valid=False, reason="license token expired", payload=payload)
    return LicenseCheckResult(valid=True, reason="valid", payload=payload)


def create_license_token(payload: dict[str, Any], secret: str) -> str:
    """Create a local signed token for tests or owner-side tooling."""
    if not secret:
        raise ValueError("secret is required")
    payload_b64 = _b64url_encode(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8"))
    signing_input = f"clm1.{payload_b64}".encode("utf-8")
    signature = _b64url_encode(hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest())
    return f"clm1.{payload_b64}.{signature}"


def _is_private_capability(name: str) -> bool:
    return name.startswith(PRIVATE_CAPABILITY_PREFIXES)


def _load_config(config_path: str | Path | None) -> dict[str, Any]:
    path = Path(config_path) if config_path else Path("clm_config.json")
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)
