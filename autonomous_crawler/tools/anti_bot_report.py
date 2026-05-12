"""Unified anti-bot evidence report (CAP-6.2).

The report is diagnostic and advisory. It consolidates access, transport,
fingerprint, JavaScript/crypto, proxy, API-block, and WebSocket signals into a
single safe payload for Strategy and future run dashboards. It does not solve
CAPTCHAs, bypass login, replay signatures, or enable proxies by itself.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .proxy_pool import redact_proxy_url
from .proxy_trace import redact_error_message
from .strategy_evidence import StrategyEvidenceReport, build_reverse_engineering_hints


SEVERITY_WEIGHT = {
    "low": 8,
    "medium": 24,
    "high": 42,
    "critical": 65,
}


@dataclass(frozen=True)
class AntiBotFinding:
    """One normalized finding in an anti-bot report."""

    code: str
    category: str
    severity: str
    source: str
    summary: str
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "category": self.category,
            "severity": self.severity,
            "source": self.source,
            "summary": self.summary,
            "evidence": _safe_payload(self.evidence),
        }


@dataclass(frozen=True)
class AntiBotReport:
    """Unified anti-bot/challenge posture for a crawl target."""

    detected: bool
    risk_level: str
    risk_score: int
    recommended_action: str
    categories: list[str] = field(default_factory=list)
    findings: list[AntiBotFinding] = field(default_factory=list)
    next_steps: list[str] = field(default_factory=list)
    guardrails: list[str] = field(default_factory=list)
    evidence_sources: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "detected": self.detected,
            "risk_level": self.risk_level,
            "risk_score": self.risk_score,
            "recommended_action": self.recommended_action,
            "categories": list(self.categories),
            "findings": [finding.to_dict() for finding in self.findings],
            "next_steps": list(self.next_steps),
            "guardrails": list(self.guardrails),
            "evidence_sources": list(self.evidence_sources),
        }


def build_anti_bot_report(
    recon_report: dict[str, Any],
    *,
    strategy_evidence: StrategyEvidenceReport | None = None,
    strategy_scorecard: dict[str, Any] | None = None,
) -> AntiBotReport:
    """Build a safe unified anti-bot report from recon/strategy evidence."""
    recon = recon_report if isinstance(recon_report, dict) else {}
    findings: list[AntiBotFinding] = []

    _extend_access_findings(findings, recon)
    _extend_api_findings(findings, recon)
    _extend_transport_findings(findings, recon)
    _extend_fingerprint_findings(findings, recon)
    _extend_js_crypto_findings(findings, recon)
    _extend_websocket_findings(findings, recon)
    _extend_proxy_findings(findings, recon)
    _extend_strategy_findings(findings, strategy_evidence)

    findings = _dedupe_findings(findings)
    categories = _dedupe([finding.category for finding in findings])
    evidence_sources = _dedupe([finding.source for finding in findings])
    risk_score = _risk_score(findings)
    risk_level = _risk_level(findings, risk_score)
    recommended_action = _recommended_action(
        findings,
        risk_level=risk_level,
        strategy_scorecard=strategy_scorecard,
    )
    next_steps = _next_steps(findings, recommended_action)
    guardrails = _guardrails(findings)

    return AntiBotReport(
        detected=bool(findings),
        risk_level=risk_level,
        risk_score=risk_score,
        recommended_action=recommended_action,
        categories=categories,
        findings=findings,
        next_steps=next_steps,
        guardrails=guardrails,
        evidence_sources=evidence_sources,
    )


def _extend_access_findings(findings: list[AntiBotFinding], recon: dict[str, Any]) -> None:
    access = recon.get("access_diagnostics") if isinstance(recon.get("access_diagnostics"), dict) else {}
    signals = access.get("signals") if isinstance(access.get("signals"), dict) else {}
    details = signals.get("challenge_details") if isinstance(signals.get("challenge_details"), dict) else {}
    anti_bot = recon.get("anti_bot") if isinstance(recon.get("anti_bot"), dict) else {}
    challenge = (
        signals.get("challenge")
        or details.get("primary_marker")
        or anti_bot.get("type")
        or anti_bot.get("matches")
        or ""
    )
    if isinstance(challenge, list):
        challenge = challenge[0] if challenge else ""

    if challenge or anti_bot.get("detected"):
        kind = str(details.get("kind") or anti_bot.get("type") or "managed_challenge")
        vendor = str(details.get("vendor") or "unknown")
        severity = str(details.get("severity") or "high")
        findings.append(AntiBotFinding(
            code=f"access_{kind}",
            category="challenge",
            severity=_valid_severity(severity, fallback="high"),
            source="access_diagnostics",
            summary="Challenge, CAPTCHA, login gate, or access block signal detected.",
            evidence={
                "marker": str(challenge),
                "kind": kind,
                "vendor": vendor,
                "requires_manual_handoff": bool(details.get("requires_manual_handoff")),
                "findings": list(access.get("findings") or [])[:10],
            },
        ))

    access_decision = access.get("access_decision") if isinstance(access.get("access_decision"), dict) else {}
    action = str(access_decision.get("action") or "")
    if action in {"backoff", "manual_handoff", "authorized_browser_review"}:
        findings.append(AntiBotFinding(
            code=f"access_decision_{action}",
            category="access_policy",
            severity="high" if action != "backoff" else "medium",
            source="access_policy",
            summary="Access policy selected a guarded action.",
            evidence={
                "action": action,
                "reason": access_decision.get("reason", ""),
                "requires_authorization": bool(access_decision.get("requires_authorization")),
            },
        ))

    fetch = recon.get("fetch") if isinstance(recon.get("fetch"), dict) else {}
    status = _safe_int(fetch.get("status_code"))
    if status == 429:
        findings.append(AntiBotFinding(
            code="http_429_rate_limited",
            category="rate_limit",
            severity="medium",
            source="fetch",
            summary="Target returned HTTP 429 rate-limit evidence.",
            evidence={"status_code": status, "selected_mode": fetch.get("selected_mode", "")},
        ))


def _extend_api_findings(findings: list[AntiBotFinding], recon: dict[str, Any]) -> None:
    blocked: list[dict[str, Any]] = []
    for candidate in recon.get("api_candidates") or []:
        if not isinstance(candidate, dict):
            continue
        status = _safe_int(candidate.get("status_code"))
        if status in {401, 403, 429, 503}:
            blocked.append({
                "url": candidate.get("url", ""),
                "method": candidate.get("method", "GET"),
                "kind": candidate.get("kind", ""),
                "status_code": status,
                "reason": candidate.get("reason", ""),
            })
    if blocked:
        findings.append(AntiBotFinding(
            code="blocked_api_candidates",
            category="api_block",
            severity="medium",
            source="api_candidates",
            summary="One or more API candidates appear blocked or rate-limited.",
            evidence={"candidates": blocked[:5]},
        ))


def _extend_transport_findings(findings: list[AntiBotFinding], recon: dict[str, Any]) -> None:
    report = recon.get("transport_diagnostics") if isinstance(recon.get("transport_diagnostics"), dict) else {}
    transport_findings = [str(value) for value in report.get("findings") or [] if value]
    if not report or (not report.get("transport_sensitive") and not transport_findings):
        return
    findings.append(AntiBotFinding(
        code="transport_sensitive_access",
        category="transport",
        severity="medium" if report.get("transport_sensitive") else "low",
        source="transport_diagnostics",
        summary="Access behavior differs across transport/client modes.",
        evidence={
            "selected_mode": report.get("selected_mode", ""),
            "findings": transport_findings[:10],
            "recommendations": list(report.get("recommendations") or [])[:5],
        },
    ))


def _extend_fingerprint_findings(findings: list[AntiBotFinding], recon: dict[str, Any]) -> None:
    report = recon.get("browser_fingerprint_probe") if isinstance(recon.get("browser_fingerprint_probe"), dict) else {}
    if not report:
        return
    risk = str(report.get("risk_level") or "low")
    probe_findings = list(report.get("findings") or [])
    if risk == "low" and not probe_findings:
        return
    findings.append(AntiBotFinding(
        code="browser_fingerprint_risk",
        category="fingerprint",
        severity="high" if risk == "high" else "medium" if risk == "medium" else "low",
        source="browser_fingerprint_probe",
        summary="Runtime browser fingerprint evidence may affect access reliability.",
        evidence={
            "status": report.get("status", ""),
            "risk_level": risk,
            "findings": probe_findings[:10],
            "recommendations": list(report.get("recommendations") or [])[:5],
        },
    ))


def _extend_js_crypto_findings(findings: list[AntiBotFinding], recon: dict[str, Any]) -> None:
    js_evidence = recon.get("js_evidence") if isinstance(recon.get("js_evidence"), dict) else {}
    if not js_evidence:
        return

    categories = set()
    high_score_sources = 0
    for item in js_evidence.get("items") or []:
        if not isinstance(item, dict):
            continue
        categories.update(str(value) for value in item.get("keyword_categories") or [] if value)
        if _safe_int(item.get("total_score")) >= 50:
            high_score_sources += 1

    if categories.intersection({"challenge", "fingerprint", "anti_bot"}):
        findings.append(AntiBotFinding(
            code="js_anti_bot_clues",
            category="js_challenge",
            severity="medium",
            source="js_evidence",
            summary="JavaScript assets contain challenge, fingerprint, or anti-bot clues.",
            evidence={
                "categories": sorted(categories),
                "high_score_sources": high_score_sources,
                "top_suspicious_calls": list(js_evidence.get("top_suspicious_calls") or [])[:10],
            },
        ))

    hints = build_reverse_engineering_hints(js_evidence)
    if hints.get("api_replay_blocker"):
        findings.append(AntiBotFinding(
            code="js_signature_or_encryption_flow",
            category="crypto_signature",
            severity="high",
            source="js_crypto_evidence",
            summary="JS crypto/signature evidence makes naive API replay fragile.",
            evidence={
                "api_replay_blocker": hints.get("api_replay_blocker"),
                "crypto_categories": list(hints.get("crypto_categories") or [])[:12],
                "crypto_signals": list(hints.get("crypto_signals") or [])[:12],
                "needs_browser_runtime": bool(hints.get("needs_browser_runtime")),
            },
        ))


def _extend_websocket_findings(findings: list[AntiBotFinding], recon: dict[str, Any]) -> None:
    summary = recon.get("websocket_summary") if isinstance(recon.get("websocket_summary"), dict) else {}
    connections = _safe_int(summary.get("connection_count"))
    frames = _safe_int(summary.get("total_frames"))
    if connections <= 0 and frames <= 0:
        return
    findings.append(AntiBotFinding(
        code="websocket_runtime_dependency",
        category="runtime_protocol",
        severity="medium",
        source="websocket_summary",
        summary="Page uses WebSocket traffic that may require browser/runtime protocol analysis.",
        evidence={
            "connection_count": connections,
            "total_frames": frames,
            "message_kinds": list(summary.get("message_kinds") or [])[:10],
        },
    ))


def _extend_proxy_findings(findings: list[AntiBotFinding], recon: dict[str, Any]) -> None:
    traces: list[dict[str, Any]] = []
    direct = recon.get("proxy_trace")
    if isinstance(direct, dict):
        traces.append(direct)

    fetch_trace = recon.get("fetch_trace") if isinstance(recon.get("fetch_trace"), dict) else {}
    for attempt in fetch_trace.get("attempts") or []:
        if not isinstance(attempt, dict):
            continue
        trace = attempt.get("proxy_trace")
        if isinstance(trace, dict):
            traces.append(trace)
        context = attempt.get("access_context") if isinstance(attempt.get("access_context"), dict) else {}
        proxy = context.get("proxy") if isinstance(context.get("proxy"), dict) else {}
        if proxy.get("enabled") or proxy.get("selected"):
            traces.append({
                "selected": bool(proxy.get("selected") or proxy.get("enabled")),
                "proxy": proxy.get("proxy") or proxy.get("default_proxy") or "",
                "source": proxy.get("source") or "access_config",
            })

    for trace in traces[:3]:
        health = trace.get("health") if isinstance(trace.get("health"), dict) else {}
        errors = [redact_error_message(str(value)) for value in trace.get("errors") or [] if value]
        if health.get("in_cooldown") or _safe_int(health.get("failure_count")) > 0 or errors:
            findings.append(AntiBotFinding(
                code="proxy_health_risk",
                category="proxy",
                severity="medium",
                source="proxy_trace",
                summary="Proxy selection or health evidence indicates reliability risk.",
                evidence={
                    "selected": bool(trace.get("selected")),
                    "proxy": redact_proxy_url(str(trace.get("proxy") or "")),
                    "source": trace.get("source", ""),
                    "provider": trace.get("provider", ""),
                    "strategy": trace.get("strategy", ""),
                    "health": _safe_payload(health),
                    "errors": errors[:5],
                },
            ))


def _extend_strategy_findings(
    findings: list[AntiBotFinding],
    strategy_evidence: StrategyEvidenceReport | None,
) -> None:
    if strategy_evidence is None:
        return
    for warning in strategy_evidence.warnings or []:
        if warning in {"challenge_detected", "fingerprint_runtime_risk", "transport_sensitive"}:
            continue
        findings.append(AntiBotFinding(
            code=f"strategy_warning_{warning}",
            category="strategy_warning",
            severity="medium",
            source="strategy_evidence",
            summary="Strategy evidence emitted an anti-bot relevant warning.",
            evidence={"warning": warning},
        ))


def _recommended_action(
    findings: list[AntiBotFinding],
    *,
    risk_level: str,
    strategy_scorecard: dict[str, Any] | None,
) -> str:
    codes = {finding.code for finding in findings}
    categories = {finding.category for finding in findings}
    if any("captcha" in finding.code for finding in findings) or "access_managed_challenge" in codes:
        return "manual_handoff"
    if "access_login_required" in codes:
        return "authorized_session_review"
    if "rate_limit" in categories or "http_429_rate_limited" in codes:
        return "backoff"
    if "crypto_signature" in categories:
        return "deeper_recon"
    if "fingerprint" in categories or "transport" in categories or "runtime_protocol" in categories:
        return "browser_render_or_profile_review"
    if risk_level in {"high", "critical"}:
        return "manual_handoff"
    if isinstance(strategy_scorecard, dict):
        recommended = str(strategy_scorecard.get("recommended") or "")
        if recommended in {"deeper_recon", "manual_handoff"}:
            return recommended
        executable = str(strategy_scorecard.get("executable_recommended_mode") or "")
        if executable:
            return executable
    return "standard_http"


def _next_steps(findings: list[AntiBotFinding], recommended_action: str) -> list[str]:
    steps: list[str] = []
    categories = {finding.category for finding in findings}
    if "challenge" in categories:
        steps.append("Preserve challenge evidence and use authorized/manual review before retrying.")
    if "rate_limit" in categories:
        steps.append("Lower request rate, honor retry-after signals when available, and retry later.")
    if "transport" in categories:
        steps.append("Compare transport profiles before adding or removing fetch modes.")
    if "fingerprint" in categories:
        steps.append("Review browser context consistency before long browser runs.")
    if "crypto_signature" in categories:
        steps.append("Trace signature inputs with browser/runtime evidence before direct API replay.")
    if "runtime_protocol" in categories:
        steps.append("Capture WebSocket protocol samples before designing extraction logic.")
    if "proxy" in categories:
        steps.append("Rotate away from unhealthy proxies and keep credential-safe health evidence.")
    if not steps and recommended_action == "standard_http":
        steps.append("Continue with standard HTTP/DOM strategy.")
    return _dedupe(steps)


def _guardrails(findings: list[AntiBotFinding]) -> list[str]:
    guardrails = [
        "diagnostic_only_no_bypass",
        "no_captcha_solving",
        "no_login_bypass",
        "redact_credentials",
    ]
    categories = {finding.category for finding in findings}
    if "crypto_signature" in categories:
        guardrails.append("do_not_replay_signed_api_without_runtime_inputs")
    if "proxy" in categories:
        guardrails.append("proxy_usage_must_be_opt_in")
    if "challenge" in categories:
        guardrails.append("challenge_requires_authorized_or_manual_review")
    return guardrails


def _risk_score(findings: list[AntiBotFinding]) -> int:
    score = 0
    for finding in findings:
        score += SEVERITY_WEIGHT.get(finding.severity, 8)
    return min(100, score)


def _risk_level(findings: list[AntiBotFinding], score: int) -> str:
    severities = {finding.severity for finding in findings}
    if "critical" in severities or score >= 90:
        return "critical"
    if "high" in severities or score >= 55:
        return "high"
    if "medium" in severities or score >= 25:
        return "medium"
    return "low"


def _dedupe_findings(findings: list[AntiBotFinding]) -> list[AntiBotFinding]:
    result: list[AntiBotFinding] = []
    seen: set[tuple[str, str]] = set()
    for finding in findings:
        key = (finding.code, finding.source)
        if key in seen:
            continue
        seen.add(key)
        result.append(finding)
    return result


def _safe_payload(value: Any) -> Any:
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, item in value.items():
            lower = str(key).lower()
            if lower in {"password", "token", "secret", "authorization", "cookie", "api_key", "apikey"}:
                result[str(key)] = "[redacted]"
            elif lower in {"proxy", "proxy_url", "default_proxy"} and isinstance(item, str):
                result[str(key)] = redact_proxy_url(item)
            elif lower in {"error", "last_error"} and isinstance(item, str):
                result[str(key)] = redact_error_message(item)
            else:
                result[str(key)] = _safe_payload(item)
        return result
    if isinstance(value, list):
        return [_safe_payload(item) for item in value[:20]]
    if isinstance(value, tuple):
        return tuple(_safe_payload(item) for item in value[:20])
    if isinstance(value, str):
        return redact_error_message(value)[:500]
    return value


def _valid_severity(value: str, *, fallback: str) -> str:
    return value if value in SEVERITY_WEIGHT else fallback


def _dedupe(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0
