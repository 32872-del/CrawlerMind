"""Structured challenge and access-block detection.

The detector is diagnostic only. It identifies likely Cloudflare/CAPTCHA/login/
rate-limit pages so the rest of CLM can choose a safe next step, such as lower
rate limits, authorized session handoff, or manual review.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any


@dataclass(frozen=True)
class ChallengeSignal:
    detected: bool
    kind: str = "none"
    vendor: str = "none"
    severity: str = "low"
    primary_marker: str = ""
    markers: list[str] = field(default_factory=list)
    status_code: int | None = None
    requires_manual_handoff: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "detected": self.detected,
            "kind": self.kind,
            "vendor": self.vendor,
            "severity": self.severity,
            "primary_marker": self.primary_marker,
            "markers": list(self.markers),
            "status_code": self.status_code,
            "requires_manual_handoff": self.requires_manual_handoff,
        }


CHALLENGE_MARKERS: tuple[tuple[str, str, str], ...] = (
    ("cf-challenge", "managed_challenge", "cloudflare"),
    ("cf-browser-verification", "managed_challenge", "cloudflare"),
    ("cf-mitigated", "managed_challenge", "cloudflare"),
    ("checking your browser", "managed_challenge", "cloudflare"),
    ("just a moment", "managed_challenge", "cloudflare"),
    ("attention required", "managed_challenge", "cloudflare"),
    ("hcaptcha", "captcha", "hcaptcha"),
    ("recaptcha", "captcha", "recaptcha"),
    ("g-recaptcha", "captcha", "recaptcha"),
    ("captcha", "captcha", "unknown"),
    ("geetest", "captcha", "geetest"),
    ("_incapsula_resource", "managed_challenge", "incapsula"),
    ("datadome", "managed_challenge", "datadome"),
    ("perimeterx", "managed_challenge", "perimeterx"),
    ("access denied", "access_denied", "unknown"),
)

LOGIN_MARKERS: tuple[str, ...] = (
    "sign in",
    "log in",
    "login",
    "account required",
    "authentication required",
)


def detect_challenge_signal(
    html: str,
    *,
    status_code: int | None = None,
    response_headers: dict[str, Any] | None = None,
) -> ChallengeSignal:
    """Return structured challenge/access-block information."""
    if _looks_like_json_payload(html):
        return ChallengeSignal(detected=False, status_code=status_code)

    sample = (html or "")[:200_000].lower()
    header_text = " ".join(
        f"{key}:{value}" for key, value in (response_headers or {}).items()
    ).lower()
    combined = f"{sample} {header_text}"

    matches: list[tuple[str, str, str]] = []
    for marker, kind, vendor in CHALLENGE_MARKERS:
        if marker.lower() in combined:
            matches.append((marker, kind, vendor))

    if not matches and status_code == 429:
        return ChallengeSignal(
            detected=True,
            kind="rate_limited",
            vendor="unknown",
            severity="medium",
            primary_marker="status:429",
            markers=["status:429"],
            status_code=status_code,
            requires_manual_handoff=False,
        )

    if not matches and status_code in {401, 403} and _looks_like_login_gate(sample):
        return ChallengeSignal(
            detected=True,
            kind="login_required",
            vendor="unknown",
            severity="medium",
            primary_marker=f"status:{status_code}",
            markers=[f"status:{status_code}", "login_marker"],
            status_code=status_code,
            requires_manual_handoff=True,
        )

    if not matches:
        return ChallengeSignal(detected=False, status_code=status_code)

    primary_marker, kind, vendor = matches[0]
    markers = [marker for marker, _kind, _vendor in matches]
    severity = "high" if kind in {"managed_challenge", "captcha", "access_denied"} else "medium"
    return ChallengeSignal(
        detected=True,
        kind=kind,
        vendor=vendor,
        severity=severity,
        primary_marker=primary_marker,
        markers=markers,
        status_code=status_code,
        requires_manual_handoff=kind in {"managed_challenge", "captcha", "login_required"},
    )


def detect_challenge_marker(html: str) -> str:
    """Backward-compatible helper returning the first marker string."""
    return detect_challenge_signal(html).primary_marker


def _looks_like_json_payload(text: str) -> bool:
    stripped = (text or "").lstrip()
    return stripped.startswith("{") or stripped.startswith("[")


def _looks_like_login_gate(text: str) -> bool:
    if not text:
        return False
    if any(marker in text for marker in LOGIN_MARKERS):
        return True
    return bool(re.search(r"<form[^>]+(?:login|signin|sign-in)", text))
