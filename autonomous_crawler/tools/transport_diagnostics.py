"""CAP-1.2 HTTP/TLS transport diagnostics.

This module compares permitted transport modes for the same URL and explains
whether access behavior appears transport-sensitive. It does not implement JA3
spoofing itself; it exposes the evidence needed before deeper TLS/HTTP2 work.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .access_diagnostics import diagnose_access
from .fetch_policy import FetchAttempt, FetchFn, fetch_best_page
from .rate_limiter import DomainRateLimiter
from .rate_limit_policy import RateLimitPolicy


SENSITIVE_HEADERS = {"set-cookie", "cookie", "authorization", "x-api-key", "x-auth-token"}


@dataclass(frozen=True)
class TransportModeReport:
    mode: str
    url: str
    status_code: int | None = None
    http_version: str = ""
    transport_profile: str = ""
    html_chars: int = 0
    text_chars: int = 0
    challenge: str = ""
    challenge_kind: str = ""
    score: int = 0
    error: str = ""
    headers: dict[str, str] = field(default_factory=dict)
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "url": self.url,
            "status_code": self.status_code,
            "http_version": self.http_version,
            "transport_profile": self.transport_profile,
            "html_chars": self.html_chars,
            "text_chars": self.text_chars,
            "challenge": self.challenge,
            "challenge_kind": self.challenge_kind,
            "score": self.score,
            "error": self.error,
            "headers": dict(self.headers),
            "reasons": list(self.reasons),
        }


@dataclass(frozen=True)
class TransportDiagnosticsReport:
    url: str
    selected_mode: str
    transport_sensitive: bool
    findings: list[str]
    recommendations: list[str]
    modes: list[TransportModeReport]

    def to_dict(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "selected_mode": self.selected_mode,
            "transport_sensitive": self.transport_sensitive,
            "findings": list(self.findings),
            "recommendations": list(self.recommendations),
            "modes": [mode.to_dict() for mode in self.modes],
        }


def diagnose_transport_modes(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    modes: list[str] | None = None,
    fetchers: dict[str, FetchFn] | None = None,
    rate_limiter: DomainRateLimiter | None = None,
) -> TransportDiagnosticsReport:
    """Fetch with all requested modes and compare transport behavior."""
    selected_modes = modes or ["requests", "curl_cffi", "browser"]
    limiter = rate_limiter or DomainRateLimiter(
        RateLimitPolicy.from_dict({"default": {"delay_seconds": 0}}),
        enabled=False,
    )
    result = fetch_best_page(
        url,
        headers=headers,
        modes=selected_modes,
        fetchers=fetchers,
        rate_limiter=limiter,
        stop_on_good_enough=False,
        skip_browser_after_transport_errors=False,
    )
    mode_reports = [_build_mode_report(attempt) for attempt in result.attempts]
    findings = _find_transport_differences(mode_reports)
    recommendations = _build_recommendations(mode_reports, findings, result.mode)
    return TransportDiagnosticsReport(
        url=url,
        selected_mode=result.mode,
        transport_sensitive=bool(findings),
        findings=findings,
        recommendations=recommendations,
        modes=mode_reports,
    )


def _build_mode_report(attempt: FetchAttempt) -> TransportModeReport:
    diagnostics = attempt.diagnostics or diagnose_access(
        attempt.html,
        url=attempt.url,
        status_code=attempt.status_code,
        response_headers=attempt.response_headers,
    )
    signals = diagnostics.get("signals") or {}
    challenge_details = signals.get("challenge_details") or {}
    return TransportModeReport(
        mode=attempt.mode,
        url=attempt.url,
        status_code=attempt.status_code,
        http_version=attempt.http_version,
        transport_profile=_infer_transport_profile(attempt),
        html_chars=len(attempt.html or ""),
        text_chars=int(signals.get("text_chars") or 0),
        challenge=str(signals.get("challenge") or ""),
        challenge_kind=str(challenge_details.get("kind") or ""),
        score=attempt.score,
        error=attempt.error,
        headers=_safe_header_summary(attempt.response_headers),
        reasons=list(attempt.reasons or []),
    )


def _find_transport_differences(modes: list[TransportModeReport]) -> list[str]:
    findings: list[str] = []
    if not modes:
        return ["no_transport_attempts"]

    statuses = {mode.status_code for mode in modes if mode.status_code is not None}
    if len(statuses) > 1:
        findings.append("status_differs_by_transport")

    challenges = {mode.mode: mode.challenge for mode in modes if mode.challenge}
    if challenges:
        if len(challenges) != len(modes) or len(set(challenges.values())) > 1:
            findings.append("challenge_differs_by_transport")
        else:
            findings.append("challenge_consistent_across_transports")

    successful = [mode for mode in modes if mode.status_code and 200 <= mode.status_code < 300]
    blocked = [mode for mode in modes if mode.status_code in {403, 429, 503} or mode.challenge]
    if successful and blocked:
        findings.append("some_transports_succeed_while_others_blocked")

    scores = [mode.score for mode in modes]
    if scores and max(scores) - min(scores) >= 40:
        findings.append("quality_score_differs_by_transport")

    versions = {mode.http_version for mode in modes if mode.http_version}
    if len(versions) > 1:
        findings.append("http_version_differs")

    profiles = {mode.transport_profile for mode in modes if mode.transport_profile}
    if len(profiles) > 1:
        findings.append("transport_profile_differs")

    servers = {
        _normalized_header_value(mode.headers, "server")
        for mode in modes
        if _normalized_header_value(mode.headers, "server")
    }
    if len(servers) > 1:
        findings.append("server_header_differs")

    edge_headers = [
        mode for mode in modes
        if _normalized_header_value(mode.headers, "cf-ray")
        or _normalized_header_value(mode.headers, "x-cache")
        or _normalized_header_value(mode.headers, "via")
    ]
    if edge_headers and len(edge_headers) != len(modes):
        findings.append("edge_header_presence_differs")

    errors = [mode for mode in modes if mode.error]
    if errors and len(errors) != len(modes):
        findings.append("transport_errors_are_mode_specific")

    return findings


def _build_recommendations(
    modes: list[TransportModeReport],
    findings: list[str],
    selected_mode: str,
) -> list[str]:
    recommendations: list[str] = []
    if "some_transports_succeed_while_others_blocked" in findings:
        recommendations.append(f"Prefer selected transport mode: {selected_mode}")
    if "challenge_differs_by_transport" in findings:
        recommendations.append("Record transport-specific challenge evidence before changing strategy")
    if "http_version_differs" in findings:
        recommendations.append("Inspect HTTP/2/TLS fingerprint settings for blocked modes")
    if "transport_profile_differs" in findings:
        recommendations.append("Compare client profile assumptions before adding more fetch modes")
    if "server_header_differs" in findings or "edge_header_presence_differs" in findings:
        recommendations.append("Compare CDN/cache headers; transport may be reaching different edge behavior")
    if "transport_errors_are_mode_specific" in findings:
        recommendations.append("Treat failing transport as optional fallback, not primary")
    if not recommendations:
        recommendations.append("No strong transport-specific signal found")
    return recommendations


def _infer_transport_profile(attempt: FetchAttempt) -> str:
    if attempt.mode == "requests":
        return "httpx-default"
    if attempt.mode == "curl_cffi":
        return "curl_cffi:chrome124"
    if attempt.mode == "browser":
        return "playwright-browser-context"
    return attempt.mode


def _normalized_header_value(headers: dict[str, str], name: str) -> str:
    target = name.lower()
    for key, value in headers.items():
        if str(key).lower() == target:
            return str(value).strip().lower()
    return ""


def _safe_header_summary(headers: dict[str, Any] | None) -> dict[str, str]:
    safe: dict[str, str] = {}
    for key, value in (headers or {}).items():
        lower = str(key).lower()
        if lower in SENSITIVE_HEADERS:
            safe[str(key)] = "[redacted]"
        elif lower in {"server", "content-type", "cf-ray", "x-cache", "via", "alt-svc"}:
            safe[str(key)] = str(value)[:200]
    return safe
