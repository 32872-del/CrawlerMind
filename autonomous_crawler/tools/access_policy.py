"""Access policy decisions for crawler execution.

This module turns recon/fetch signals into an explicit, auditable decision.
It does not bypass challenges. It records when CLM should continue normally,
slow down, render with a browser, or stop for authorized manual handoff.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class AccessDecision:
    action: str
    risk_level: str
    allowed: bool
    reasons: list[str] = field(default_factory=list)
    safeguards: list[str] = field(default_factory=list)
    requires_authorized_session: bool = False
    requires_manual_review: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "risk_level": self.risk_level,
            "allowed": self.allowed,
            "reasons": list(self.reasons),
            "safeguards": list(self.safeguards),
            "requires_authorized_session": self.requires_authorized_session,
            "requires_manual_review": self.requires_manual_review,
        }


def decide_access(
    diagnostics: dict[str, Any] | None,
    *,
    status_code: int | None = None,
    has_authorized_session: bool = False,
    proxy_enabled: bool = False,
) -> AccessDecision:
    """Build a conservative access decision from diagnostics."""
    diagnostics = diagnostics or {}
    findings = set(diagnostics.get("findings") or [])
    signals = diagnostics.get("signals") or {}
    challenge = signals.get("challenge") or ""
    challenge_details = signals.get("challenge_details") or {}
    reasons: list[str] = []
    safeguards: list[str] = ["respect configured rate limits", "record access decision"]

    if challenge or challenge_details.get("detected"):
        kind = str(challenge_details.get("kind") or "challenge")
        marker = str(challenge_details.get("primary_marker") or challenge)
        reasons.append(f"{kind}:{marker}")
        safeguards.extend([
            "do not solve CAPTCHA by default",
            "use only user-provided authorized sessions",
        ])
        return AccessDecision(
            action="manual_handoff" if not has_authorized_session else "authorized_browser_review",
            risk_level="high",
            allowed=bool(has_authorized_session),
            reasons=reasons,
            safeguards=safeguards,
            requires_authorized_session=True,
            requires_manual_review=True,
        )

    if status_code == 429:
        return AccessDecision(
            action="backoff",
            risk_level="medium",
            allowed=True,
            reasons=["rate_limited:status:429"],
            safeguards=safeguards + ["increase backoff before retry"],
        )

    if status_code in {401, 403}:
        return AccessDecision(
            action="authorized_session_required",
            risk_level="high",
            allowed=bool(has_authorized_session),
            reasons=[f"restricted_status:{status_code}"],
            safeguards=safeguards + ["manual review restricted access"],
            requires_authorized_session=True,
            requires_manual_review=True,
        )

    if "js_rendering_likely_required" in findings:
        return AccessDecision(
            action="browser_render",
            risk_level="low",
            allowed=True,
            reasons=["js_rendering_likely_required"],
            safeguards=safeguards,
        )

    if proxy_enabled:
        safeguards.append("proxy use must remain explicit and configured")

    return AccessDecision(
        action="standard_http",
        risk_level="low",
        allowed=True,
        reasons=["no_access_block_detected"],
        safeguards=safeguards,
    )
