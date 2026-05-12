"""Browser fingerprint profile report for context consistency checking.

This module normalises a ``BrowserContextConfig`` into a fingerprint profile,
checks for internal inconsistencies (e.g. mobile UA with desktop viewport),
and produces a serializable report with risk level and recommendations.

It does NOT implement stealth, canvas/WebGL spoofing, or real browser probing.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .browser_context import BrowserContextConfig, DEFAULT_USER_AGENT
from .proxy_manager import redact_proxy_url

# ---------------------------------------------------------------------------
# Mobile UA indicators
# ---------------------------------------------------------------------------
_MOBILE_UA_TOKENS = ("mobile", "android", "iphone", "ipad", "ipod", "webos", "blackberry")

# ---------------------------------------------------------------------------
# Locale → expected timezone region prefixes (heuristic)
# ---------------------------------------------------------------------------
_LOCALE_TIMEZONE_MAP: dict[str, list[str]] = {
    "en-US": ["America/"],
    "en-GB": ["Europe/London"],
    "de-": ["Europe/Berlin", "Europe/Vienna", "Europe/Zurich"],
    "fr-": ["Europe/Paris"],
    "es-": ["Europe/Madrid", "America/"],
    "it-": ["Europe/Rome"],
    "nl-": ["Europe/Amsterdam"],
    "pl-": ["Europe/Warsaw"],
    "pt-": ["Europe/Lisbon", "America/Sao_Paulo"],
    "ru-": ["Europe/Moscow"],
    "ja-": ["Asia/Tokyo"],
    "ko-": ["Asia/Seoul"],
    "zh-": ["Asia/Shanghai", "Asia/Hong_Kong", "Asia/Taipei"],
    "ar-": ["Asia/Riyadh", "Africa/"],
    "hi-": ["Asia/Kolkata"],
    "tr-": ["Europe/Istanbul"],
    "sv-": ["Europe/Stockholm"],
    "da-": ["Europe/Copenhagen"],
    "fi-": ["Europe/Helsinki"],
    "nb-": ["Europe/Oslo"],
    "no-": ["Europe/Oslo"],
}


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class FingerprintProfile:
    """Normalized view of a browser context for fingerprint analysis."""

    user_agent: str = ""
    viewport_width: int = 0
    viewport_height: int = 0
    locale: str = ""
    timezone_id: str = ""
    color_scheme: str = ""
    java_script_enabled: bool = True
    proxy_present: bool = False
    proxy_redacted: str = ""
    storage_state_present: bool = False
    headless: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_agent": self.user_agent,
            "viewport": {"width": self.viewport_width, "height": self.viewport_height},
            "locale": self.locale,
            "timezone_id": self.timezone_id,
            "color_scheme": self.color_scheme,
            "java_script_enabled": self.java_script_enabled,
            "proxy_present": self.proxy_present,
            "proxy_redacted": self.proxy_redacted,
            "storage_state_present": self.storage_state_present,
            "headless": self.headless,
        }


@dataclass(frozen=True)
class FingerprintFinding:
    """A single consistency finding."""

    code: str
    severity: str  # "low", "medium", "high"
    message: str

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code, "severity": self.severity, "message": self.message}


@dataclass
class FingerprintReport:
    """Serializable fingerprint report."""

    profile: FingerprintProfile
    findings: list[FingerprintFinding] = field(default_factory=list)
    risk_level: str = "low"
    recommendations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile": self.profile.to_dict(),
            "findings": [f.to_dict() for f in self.findings],
            "risk_level": self.risk_level,
            "recommendations": list(self.recommendations),
        }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def build_fingerprint_report(
    config: BrowserContextConfig | dict[str, Any] | None,
) -> FingerprintReport:
    """Build a fingerprint profile report from a browser context config.

    Accepts a ``BrowserContextConfig`` instance or a plain dict.  Returns a
    serializable ``FingerprintReport`` with profile, findings, risk level,
    and recommendations.
    """
    if not isinstance(config, BrowserContextConfig):
        config = BrowserContextConfig.from_dict(config)

    profile = _extract_profile(config)
    findings = _check_consistency(profile, config)
    risk_level = _compute_risk_level(findings)
    recommendations = _build_recommendations(findings)

    return FingerprintReport(
        profile=profile,
        findings=findings,
        risk_level=risk_level,
        recommendations=recommendations,
    )


# ---------------------------------------------------------------------------
# Profile extraction
# ---------------------------------------------------------------------------
def _extract_profile(config: BrowserContextConfig) -> FingerprintProfile:
    return FingerprintProfile(
        user_agent=config.user_agent,
        viewport_width=config.viewport.width,
        viewport_height=config.viewport.height,
        locale=config.locale,
        timezone_id=config.timezone_id,
        color_scheme=config.color_scheme,
        java_script_enabled=config.java_script_enabled,
        proxy_present=bool(config.proxy_url),
        proxy_redacted=redact_proxy_url(config.proxy_url) if config.proxy_url else "",
        storage_state_present=bool(config.storage_state_path),
        headless=config.headless,
    )


# ---------------------------------------------------------------------------
# Consistency checks
# ---------------------------------------------------------------------------
def _check_consistency(
    profile: FingerprintProfile, config: BrowserContextConfig
) -> list[FingerprintFinding]:
    findings: list[FingerprintFinding] = []
    findings.extend(_check_ua_viewport_mismatch(profile))
    findings.extend(_check_locale_timezone(profile))
    findings.extend(_check_default_ua_with_custom_profile(profile, config))
    findings.extend(_check_proxy_with_defaults(profile))
    return findings


def _is_mobile_ua(user_agent: str) -> bool:
    lowered = user_agent.lower()
    return any(token in lowered for token in _MOBILE_UA_TOKENS)


def _check_ua_viewport_mismatch(profile: FingerprintProfile) -> list[FingerprintFinding]:
    findings: list[FingerprintFinding] = []
    if not profile.user_agent:
        return findings

    is_mobile = _is_mobile_ua(profile.user_agent)

    # Mobile UA + desktop viewport
    if is_mobile and profile.viewport_width > 1024:
        findings.append(FingerprintFinding(
            code="ua_viewport_mismatch",
            severity="high",
            message=(
                f"Mobile user-agent detected but viewport is {profile.viewport_width}x"
                f"{profile.viewport_height} (desktop size).  Real mobile devices "
                "typically have viewport width ≤ 430."
            ),
        ))

    # Desktop UA + tiny viewport
    if not is_mobile and profile.viewport_width < 800:
        findings.append(FingerprintFinding(
            code="ua_viewport_mismatch",
            severity="high",
            message=(
                f"Desktop user-agent detected but viewport is {profile.viewport_width}x"
                f"{profile.viewport_height} (mobile size).  Real desktop browsers "
                "typically have viewport width ≥ 1024."
            ),
        ))

    return findings


def _check_locale_timezone(profile: FingerprintProfile) -> list[FingerprintFinding]:
    findings: list[FingerprintFinding] = []
    if not profile.locale or not profile.timezone_id:
        return findings

    # UTC timezone with non-UTC locale is mildly suspicious
    if profile.timezone_id == "UTC" and not profile.locale.startswith("en"):
        findings.append(FingerprintFinding(
            code="locale_timezone_mismatch",
            severity="low",
            message=(
                f"Locale is '{profile.locale}' but timezone is UTC.  "
                "Most real users have a local timezone."
            ),
        ))
        return findings

    # Check known locale → timezone mappings
    for prefix, expected_zones in _LOCALE_TIMEZONE_MAP.items():
        if profile.locale.startswith(prefix):
            if not any(profile.timezone_id.startswith(z) for z in expected_zones):
                findings.append(FingerprintFinding(
                    code="locale_timezone_mismatch",
                    severity="medium",
                    message=(
                        f"Locale '{profile.locale}' typically maps to timezone "
                        f"starting with {'/'.join(expected_zones)} but timezone is "
                        f"'{profile.timezone_id}'."
                    ),
                ))
            break

    return findings


def _check_default_ua_with_custom_profile(
    profile: FingerprintProfile, config: BrowserContextConfig
) -> list[FingerprintFinding]:
    """Detect when other fields are customized but UA is left at the default."""
    findings: list[FingerprintFinding] = []

    if profile.user_agent != DEFAULT_USER_AGENT:
        return findings

    custom_fields: list[str] = []
    if config.locale != "en-US":
        custom_fields.append("locale")
    if config.timezone_id != "UTC":
        custom_fields.append("timezone")
    if config.viewport.width != 1365 or config.viewport.height != 768:
        custom_fields.append("viewport")
    if config.color_scheme != "light":
        custom_fields.append("color_scheme")
    if config.proxy_url:
        custom_fields.append("proxy")

    if len(custom_fields) >= 2:
        findings.append(FingerprintFinding(
            code="default_ua_custom_profile",
            severity="medium",
            message=(
                f"User-agent is the library default but {', '.join(custom_fields)} "
                "are customized.  A real browser would have a matching UA."
            ),
        ))

    return findings


def _check_proxy_with_defaults(profile: FingerprintProfile) -> list[FingerprintFinding]:
    findings: list[FingerprintFinding] = []

    if not profile.proxy_present:
        return findings

    default_fields: list[str] = []
    if profile.timezone_id == "UTC":
        default_fields.append("timezone")
    if profile.locale == "en-US":
        default_fields.append("locale")

    if default_fields:
        findings.append(FingerprintFinding(
            code="proxy_default_locale_tz",
            severity="low",
            message=(
                f"Proxy is configured but {' and '.join(default_fields)} "
                f"{'is' if len(default_fields) == 1 else 'are'} left at default.  "
                "Consider setting locale/timezone to match the proxy region."
            ),
        ))

    return findings


# ---------------------------------------------------------------------------
# Risk level
# ---------------------------------------------------------------------------
_RISK_ORDER = {"low": 0, "medium": 1, "high": 2}


def _compute_risk_level(findings: list[FingerprintFinding]) -> str:
    if not findings:
        return "low"
    return max(
        (f.severity for f in findings),
        key=lambda s: _RISK_ORDER.get(s, 0),
    )


# ---------------------------------------------------------------------------
# Recommendations
# ---------------------------------------------------------------------------
def _build_recommendations(findings: list[FingerprintFinding]) -> list[str]:
    recs: list[str] = []
    seen_codes: set[str] = set()

    for finding in findings:
        if finding.code in seen_codes:
            continue
        seen_codes.add(finding.code)

        if finding.code == "ua_viewport_mismatch":
            recs.append(
                "Align user-agent with viewport: use a mobile UA for mobile "
                "viewports and a desktop UA for desktop viewports."
            )
        elif finding.code == "locale_timezone_mismatch":
            recs.append(
                "Set timezone_id to match the configured locale's region "
                "for a more consistent fingerprint."
            )
        elif finding.code == "default_ua_custom_profile":
            recs.append(
                "Provide a custom user-agent string that matches the "
                "browser version implied by the other profile settings."
            )
        elif finding.code == "proxy_default_locale_tz":
            recs.append(
                "Set locale and timezone to match the proxy's geographic "
                "region to avoid fingerprint inconsistency."
            )

    return recs
