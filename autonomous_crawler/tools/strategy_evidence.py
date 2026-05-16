"""Unified strategy evidence report.

This module turns recon output into compact, ranked signals for Strategy.
It is intentionally advisory: it explains why a strategy was chosen and what
the next reverse-engineering work should inspect, without changing routing by
itself.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class EvidenceSignal:
    """One normalized signal consumed by the strategy agent."""

    code: str
    source: str
    confidence: str = "medium"
    score: int = 0
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "source": self.source,
            "confidence": self.confidence,
            "score": self.score,
            "details": dict(self.details),
        }


@dataclass
class StrategyEvidenceReport:
    """Normalized evidence bundle attached to crawl_strategy."""

    signals: list[EvidenceSignal] = field(default_factory=list)
    dominant_sources: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    action_hints: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "signals": [signal.to_dict() for signal in self.signals],
            "dominant_sources": list(self.dominant_sources),
            "warnings": list(self.warnings),
            "action_hints": dict(self.action_hints),
        }


def build_strategy_evidence_report(recon_report: dict[str, Any]) -> StrategyEvidenceReport:
    """Build a compact evidence report from recon data."""
    recon = recon_report if isinstance(recon_report, dict) else {}
    signals: list[EvidenceSignal] = []
    warnings: list[str] = []

    dom_structure = recon.get("dom_structure")
    api_candidates = recon.get("api_candidates") or []
    js_evidence = recon.get("js_evidence") or {}
    signals.extend(_dom_signals(dom_structure if isinstance(dom_structure, dict) else {}))
    signals.extend(_api_candidate_signals(api_candidates))
    signals.extend(_js_signals(js_evidence))
    signals.extend(_api_reverse_signals(api_candidates))
    signals.extend(_graphql_signals(api_candidates, js_evidence))
    transport = recon.get("transport_diagnostics")
    fingerprint = recon.get("browser_fingerprint_probe")
    access = recon.get("access_diagnostics")
    anti_bot = recon.get("anti_bot")
    websocket = recon.get("websocket_summary")
    signals.extend(_transport_signals(transport if isinstance(transport, dict) else {}))
    signals.extend(_fingerprint_signals(fingerprint if isinstance(fingerprint, dict) else {}))
    signals.extend(_access_signals(access if isinstance(access, dict) else {}, anti_bot if isinstance(anti_bot, dict) else {}))
    signals.extend(_websocket_signals(websocket if isinstance(websocket, dict) else {}))
    signals.extend(_visual_signals(_visual_recon_reports(recon)))

    for signal in signals:
        if signal.code in {
            "challenge_detected",
            "fingerprint_runtime_risk",
            "transport_sensitive",
            "crypto_signature_flow",
            "crypto_encryption_flow",
            "visual_challenge_evidence",
            "graphql_signature_hint",
            "api_auth_token_hint",
            "graphql_rate_limit",
            "api_rate_limit",
        }:
            warnings.append(signal.code)

    signals.sort(key=lambda signal: signal.score, reverse=True)
    return StrategyEvidenceReport(
        signals=signals,
        dominant_sources=_dominant_sources(signals),
        warnings=_dedupe(warnings),
        action_hints=build_reverse_engineering_hints(js_evidence, api_candidates),
    )


def build_reverse_engineering_hints(
    js_evidence: dict[str, Any],
    api_candidates: list[Any] | None = None,
) -> dict[str, Any]:
    """Build action hints from JS crypto/signature evidence and API/GraphQL clues."""
    from autonomous_crawler.tools.hook_sandbox_planner import plan_hook_sandbox

    if not isinstance(js_evidence, dict):
        js_evidence = {}
    if api_candidates is None:
        api_candidates = []

    crypto_items = _crypto_items(js_evidence)
    has_js_crypto = bool(crypto_items or js_evidence.get("top_crypto_signals"))
    has_api_candidates = bool(api_candidates)

    if not has_js_crypto and not has_api_candidates:
        return {}

    hints: dict[str, Any] = {}

    if has_js_crypto:
        categories: set[str] = set()
        signal_names: list[str] = []
        likely_signature = False
        likely_encryption = False
        likely_timestamp_nonce = False
        max_score = 0
        sources: list[dict[str, Any]] = []
        recommendations: list[str] = []

        for item in crypto_items:
            crypto = item.get("crypto_analysis") or {}
            if not isinstance(crypto, dict):
                continue
            categories.update(str(value) for value in crypto.get("categories") or [] if value)
            likely_signature = likely_signature or bool(crypto.get("likely_signature_flow"))
            likely_encryption = likely_encryption or bool(crypto.get("likely_encryption_flow"))
            likely_timestamp_nonce = likely_timestamp_nonce or bool(crypto.get("likely_timestamp_nonce_flow"))
            max_score = max(max_score, _safe_int(crypto.get("score")))
            recommendations.extend(str(value) for value in crypto.get("recommendations") or [] if value)
            for signal in crypto.get("signals") or []:
                if not isinstance(signal, dict):
                    continue
                kind = str(signal.get("kind") or "")
                name = str(signal.get("name") or "")
                label = f"{kind}:{name}" if kind and name else kind or name
                if label:
                    signal_names.append(label)
            sources.append({
                "source": item.get("source", ""),
                "url": item.get("url", ""),
                "inline_id": item.get("inline_id", ""),
                "score": _safe_int(item.get("total_score")),
                "reasons": list(item.get("reasons") or [])[:5],
            })

        signal_names.extend(str(value) for value in js_evidence.get("top_crypto_signals") or [] if value)
        signal_names = _dedupe(signal_names)[:20]
        categories_list = sorted(categories)

        hints = {
            "crypto_score": max_score,
            "crypto_signals": signal_names,
            "crypto_categories": categories_list,
            "high_score_sources": sources[:5],
            "recommendations": _dedupe(recommendations)[:8],
        }
        if likely_signature:
            hints["hook_plan"] = {
                "target": "signature_or_token_generation",
                "signals": signal_names[:10],
                "capture": ["request_url", "query_params", "headers", "body", "timestamp", "nonce"],
            }
            hints["signature_inputs"] = _signature_inputs(categories)
            hints["api_replay_blocker"] = "signature_flow_requires_runtime_inputs"
        if likely_encryption:
            hints["sandbox_plan"] = {
                "target": "encryption_or_webcrypto_routine",
                "runtime": "browser" if "webcrypto" in categories else "node_or_browser",
                "capture": ["plaintext_inputs", "key_material_references", "iv_or_nonce", "ciphertext_output"],
            }
            hints["needs_browser_runtime"] = "webcrypto" in categories
            hints.setdefault("api_replay_blocker", "encrypted_payload_requires_runtime_execution")
        if likely_timestamp_nonce:
            hints["dynamic_inputs"] = ["timestamp", "nonce"]

    # Incorporate API/GraphQL reverse evidence clues
    if has_api_candidates:
        api_replay_hints = _api_replay_blocker_hints(api_candidates)
        for key, value in api_replay_hints.items():
            if key not in hints:
                hints[key] = value
            elif key == "api_replay_blocker" and value:
                hints[key] = value  # API blocker takes precedence

    # Structured hook/sandbox plan (REVERSE-HARDEN-1)
    hook_sandbox = plan_hook_sandbox(js_evidence, api_candidates)
    if hook_sandbox.risk_level != "none":
        hints["hook_sandbox_plan"] = hook_sandbox.to_dict()

    return {key: value for key, value in hints.items() if value not in ([], {}, "", None)}


def has_high_crypto_replay_risk(report: StrategyEvidenceReport) -> bool:
    """Return whether direct API replay needs extra care."""
    hints = report.action_hints or {}
    if hints.get("api_replay_blocker"):
        return True
    replay_risk_codes = {
        "crypto_signature_flow", "crypto_encryption_flow",
        "graphql_signature_hint", "api_auth_token_hint",
    }
    for signal in report.signals:
        if signal.code in replay_risk_codes and signal.score >= 50:
            return True
    return False


def _dom_signals(dom: dict[str, Any]) -> list[EvidenceSignal]:
    item_count = _safe_int(dom.get("item_count"))
    field_selectors = dom.get("field_selectors") if isinstance(dom.get("field_selectors"), dict) else {}
    product_selector = str(dom.get("product_selector") or "")
    signals: list[EvidenceSignal] = []
    if item_count >= 2:
        signals.append(EvidenceSignal(
            code="dom_repeated_items",
            source="dom",
            confidence="high" if field_selectors.get("title") else "medium",
            score=min(85, 30 + item_count * 5 + len(field_selectors) * 8),
            details={
                "item_count": item_count,
                "product_selector": product_selector,
                "field_selectors": dict(field_selectors),
            },
        ))
    elif product_selector or field_selectors:
        signals.append(EvidenceSignal(
            code="dom_partial_selectors",
            source="dom",
            confidence="low",
            score=25,
            details={"product_selector": product_selector, "field_selectors": dict(field_selectors)},
        ))
    return signals


def _api_candidate_signals(candidates: list[Any]) -> list[EvidenceSignal]:
    signals: list[EvidenceSignal] = []
    for candidate in candidates[:10]:
        if not isinstance(candidate, dict):
            continue
        score = _safe_int(candidate.get("score"))
        kind = str(candidate.get("kind") or "")
        status_code = _safe_int(candidate.get("status_code"))
        confidence = "high" if score >= 70 else "medium" if score >= 40 else "low"
        code = "observed_api_candidate" if candidate.get("reason") == "browser_network_observation" else "api_candidate"
        if status_code in {401, 403, 429, 503}:
            code = "blocked_api_candidate"
            confidence = "low"
        signals.append(EvidenceSignal(
            code=code,
            source="api",
            confidence=confidence,
            score=max(score, 35 if kind in {"json", "graphql"} else 20),
            details={
                "url": candidate.get("url", ""),
                "method": candidate.get("method", "GET"),
                "kind": kind,
                "status_code": status_code or "",
                "reason": candidate.get("reason", ""),
            },
        ))
    return signals


def _js_signals(js_evidence: dict[str, Any]) -> list[EvidenceSignal]:
    if not isinstance(js_evidence, dict):
        return []
    signals: list[EvidenceSignal] = []
    endpoints = [str(value) for value in js_evidence.get("top_endpoints") or [] if value]
    if endpoints:
        signals.append(EvidenceSignal(
            code="js_endpoint_strings",
            source="js",
            confidence="medium",
            score=min(75, 30 + len(endpoints) * 4),
            details={"endpoints": endpoints[:10]},
        ))

    categories: set[str] = set()
    high_score_count = 0
    for item in js_evidence.get("items") or []:
        if not isinstance(item, dict):
            continue
        categories.update(str(value) for value in item.get("keyword_categories") or [] if value)
        if _safe_int(item.get("total_score")) >= 50:
            high_score_count += 1
        crypto = item.get("crypto_analysis") or {}
        if isinstance(crypto, dict) and crypto.get("likely_signature_flow"):
            signals.append(_crypto_signal("crypto_signature_flow", item, crypto))
        if isinstance(crypto, dict) and crypto.get("likely_encryption_flow"):
            signals.append(_crypto_signal("crypto_encryption_flow", item, crypto))
        if isinstance(crypto, dict) and crypto.get("likely_timestamp_nonce_flow"):
            signals.append(_crypto_signal("crypto_timestamp_nonce_flow", item, crypto))

    if categories:
        signals.append(EvidenceSignal(
            code="js_keyword_categories",
            source="js",
            confidence="medium",
            score=min(70, 20 + len(categories) * 8 + high_score_count * 10),
            details={"categories": sorted(categories), "high_score_sources": high_score_count},
        ))
    return signals


def _crypto_signal(code: str, item: dict[str, Any], crypto: dict[str, Any]) -> EvidenceSignal:
    score = _safe_int(crypto.get("score"))
    return EvidenceSignal(
        code=code,
        source="crypto",
        confidence="high" if score >= 60 else "medium",
        score=max(score, 45),
        details={
            "source": item.get("source", ""),
            "url": item.get("url", ""),
            "inline_id": item.get("inline_id", ""),
            "categories": list(crypto.get("categories") or []),
            "signals": list(crypto.get("signals") or [])[:10],
        },
    )


# ---------------------------------------------------------------------------
# API / GraphQL reverse evidence signals
# ---------------------------------------------------------------------------

_SIGNATURE_KEYWORDS = (
    "signature", "sign", "hmac", "hash", "digest", "mac",
    "x-sign", "x-signature", "x-token", "x-api-sign",
    "authorization", "bearer", "api-key",
)

_TIMESTAMP_KEYWORDS = ("timestamp", "ts", "time", "nonce", "nonce_str", "random")

_ENCRYPTED_KEYWORDS = ("encrypt", "cipher", "aes", "rsa", "rsa_oaep", "jwe", "jws")


def _api_reverse_signals(candidates: list[Any]) -> list[EvidenceSignal]:
    """Detect signature/timestamp/nonce/token clues in API candidate URLs and metadata."""
    signals: list[EvidenceSignal] = []
    for candidate in candidates[:10]:
        if not isinstance(candidate, dict):
            continue
        url = str(candidate.get("url") or "").lower()
        method = str(candidate.get("method") or "GET").upper()
        kind = str(candidate.get("kind") or "")
        headers = candidate.get("headers") or {}
        body = candidate.get("body") or candidate.get("post_data") or ""
        # Split URL into path+query params for precise matching
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(url)
        query_params = parse_qs(parsed.query, keep_blank_values=True)
        param_keys = set(query_params.keys())

        sig_hits = [kw for kw in _SIGNATURE_KEYWORDS if kw in url or kw in str(headers).lower()]
        ts_hits = [kw for kw in _TIMESTAMP_KEYWORDS if kw in param_keys]
        enc_hits = [kw for kw in _ENCRYPTED_KEYWORDS if kw in url or kw in str(body).lower()]

        if sig_hits:
            signals.append(EvidenceSignal(
                code="api_auth_token_hint",
                source="api",
                confidence="high" if len(sig_hits) >= 2 else "medium",
                score=min(80, 40 + len(sig_hits) * 12),
                details={
                    "url": candidate.get("url", ""),
                    "method": method,
                    "kind": kind,
                    "matched_keywords": sig_hits[:5],
                    "hint": "API request contains signature/token parameters that may require runtime input generation",
                },
            ))
        if ts_hits:
            signals.append(EvidenceSignal(
                code="api_dynamic_input_hint",
                source="api",
                confidence="medium",
                score=min(65, 30 + len(ts_hits) * 10),
                details={
                    "url": candidate.get("url", ""),
                    "matched_keywords": ts_hits[:5],
                    "hint": "API request uses timestamp/nonce parameters — must be generated at request time",
                },
            ))
        if enc_hits:
            signals.append(EvidenceSignal(
                code="api_encrypted_payload_hint",
                source="api",
                confidence="high",
                score=70,
                details={
                    "url": candidate.get("url", ""),
                    "matched_keywords": enc_hits[:5],
                    "hint": "API request appears to contain encrypted payload — replay requires runtime encryption",
                },
            ))
    return signals


def _graphql_signals(
    candidates: list[Any],
    js_evidence: dict[str, Any],
) -> list[EvidenceSignal]:
    """Detect GraphQL-specific reverse evidence: rate limits, auth, signatures."""
    signals: list[EvidenceSignal] = []
    for candidate in candidates[:10]:
        if not isinstance(candidate, dict):
            continue
        kind = str(candidate.get("kind") or "").lower()
        if "graphql" not in kind:
            continue
        url = str(candidate.get("url") or "")
        status_code = _safe_int(candidate.get("status_code"))
        query = str(candidate.get("query") or "")
        headers = candidate.get("headers") or {}

        # Rate-limited GraphQL
        if status_code == 429:
            retry_after = ""
            if isinstance(headers, dict):
                retry_after = str(headers.get("Retry-After") or headers.get("retry-after") or "")
            signals.append(EvidenceSignal(
                code="graphql_rate_limit",
                source="graphql",
                confidence="high",
                score=75,
                details={
                    "url": url,
                    "status_code": 429,
                    "retry_after": retry_after,
                    "hint": "GraphQL endpoint rate-limited — use domain rate limiter with backoff",
                },
            ))

        # Auth/signature in GraphQL headers
        auth_keys = [k for k in (headers.keys() if isinstance(headers, dict) else []) if "auth" in k.lower() or "sign" in k.lower() or "token" in k.lower()]
        if auth_keys or "authorization" in str(headers).lower():
            signals.append(EvidenceSignal(
                code="graphql_signature_hint",
                source="graphql",
                confidence="high",
                score=70,
                details={
                    "url": url,
                    "auth_headers": auth_keys[:5],
                    "hint": "GraphQL endpoint requires auth/signature headers — replay needs valid session or token generation",
                },
            ))

        # Nested field complexity hints
        depth = query.count("{")
        if depth >= 4:
            signals.append(EvidenceSignal(
                code="graphql_nested_complexity",
                source="graphql",
                confidence="low",
                score=30,
                details={
                    "url": url,
                    "nesting_depth": depth,
                    "hint": "Deeply nested GraphQL query — may hit complexity limits",
                },
            ))
    return signals


def _api_replay_blocker_hints(candidates: list[Any]) -> dict[str, Any]:
    """Build replay blocker hints from API/GraphQL candidate evidence."""
    hints: dict[str, Any] = {}
    for candidate in candidates[:10]:
        if not isinstance(candidate, dict):
            continue
        url = str(candidate.get("url") or "").lower()
        kind = str(candidate.get("kind") or "").lower()
        headers = candidate.get("headers") or {}
        body = str(candidate.get("body") or candidate.get("post_data") or "")

        # Signature/token in URL or headers
        has_sig = any(kw in url for kw in _SIGNATURE_KEYWORDS)
        has_header_sig = False
        if isinstance(headers, dict):
            has_header_sig = any(
                "sign" in k.lower() or "token" in k.lower() or "auth" in k.lower()
                for k in headers
            )
        if has_sig or has_header_sig:
            hints.setdefault("api_replay_blocker", "signature_or_token_in_request")
            hints.setdefault("hook_plan", {
                "target": "api_signature_or_token_generation",
                "capture": ["request_url", "headers", "query_params", "timestamp", "nonce"],
            })

        # Encrypted payload
        if any(kw in body for kw in _ENCRYPTED_KEYWORDS):
            hints["api_replay_blocker"] = "encrypted_payload_requires_runtime_execution"
            hints.setdefault("sandbox_plan", {
                "target": "api_payload_encryption",
                "runtime": "node_or_browser",
                "capture": ["plaintext_inputs", "encryption_routine", "key_material"],
            })

        # Rate-limited GraphQL
        if "graphql" in kind and _safe_int(candidate.get("status_code")) == 429:
            hints["rate_limit_hint"] = "graphql_endpoint_rate_limited"
            hints.setdefault("dynamic_inputs", ["timestamp"])
    return hints


def _transport_signals(report: dict[str, Any]) -> list[EvidenceSignal]:
    if not isinstance(report, dict) or not report:
        return []
    findings = [str(value) for value in report.get("findings") or [] if value]
    if not findings and not report.get("transport_sensitive"):
        return []
    return [EvidenceSignal(
        code="transport_sensitive" if report.get("transport_sensitive") else "transport_diagnostics",
        source="transport",
        confidence="high" if report.get("transport_sensitive") else "low",
        score=75 if report.get("transport_sensitive") else 25,
        details={
            "selected_mode": report.get("selected_mode", ""),
            "findings": findings[:10],
            "recommendations": list(report.get("recommendations") or [])[:5],
        },
    )]


def _fingerprint_signals(report: dict[str, Any]) -> list[EvidenceSignal]:
    if not isinstance(report, dict) or not report:
        return []
    findings = report.get("findings") or []
    risk = str(report.get("risk_level") or "")
    if not findings and risk in {"", "low"}:
        return []
    score = 80 if risk == "high" else 55 if risk == "medium" else 25
    return [EvidenceSignal(
        code="fingerprint_runtime_risk",
        source="fingerprint",
        confidence="high" if risk == "high" else "medium",
        score=score,
        details={
            "status": report.get("status", ""),
            "risk_level": risk,
            "findings": findings[:10],
            "recommendations": list(report.get("recommendations") or [])[:5],
        },
    )]


def _access_signals(access: dict[str, Any], anti_bot: dict[str, Any]) -> list[EvidenceSignal]:
    signals: list[EvidenceSignal] = []
    access = access if isinstance(access, dict) else {}
    anti_bot = anti_bot if isinstance(anti_bot, dict) else {}
    access_signals = access.get("signals") if isinstance(access.get("signals"), dict) else {}
    challenge = access_signals.get("challenge") or anti_bot.get("matches") or ""
    if challenge or anti_bot.get("detected"):
        signals.append(EvidenceSignal(
            code="challenge_detected",
            source="access",
            confidence="high",
            score=90,
            details={
                "challenge": challenge,
                "findings": list(access.get("findings") or [])[:10],
                "anti_bot": dict(anti_bot),
            },
        ))
    findings = [str(value) for value in access.get("findings") or [] if value]
    if "js_rendering_likely_required" in findings:
        signals.append(EvidenceSignal(
            code="js_rendering_required",
            source="access",
            confidence="medium",
            score=55,
            details={"findings": findings[:10]},
        ))
    return signals


def _websocket_signals(summary: dict[str, Any]) -> list[EvidenceSignal]:
    if not isinstance(summary, dict) or not summary:
        return []
    connections = _safe_int(summary.get("connection_count"))
    frames = _safe_int(summary.get("total_frames"))
    if connections <= 0 and frames <= 0:
        return []
    return [EvidenceSignal(
        code="websocket_activity",
        source="websocket",
        confidence="medium",
        score=min(75, 35 + connections * 10 + frames),
        details={
            "connection_count": connections,
            "total_frames": frames,
            "message_kinds": list(summary.get("message_kinds") or [])[:10],
        },
    )]


def _visual_signals(reports: list[dict[str, Any]]) -> list[EvidenceSignal]:
    signals: list[EvidenceSignal] = []
    for report in reports[:5]:
        findings = [item for item in report.get("findings") or [] if isinstance(item, dict)]
        finding_codes = [str(item.get("code") or "") for item in findings if item.get("code")]
        ocr = report.get("ocr") if isinstance(report.get("ocr"), dict) else {}
        text_preview = str(ocr.get("text_preview") or "")
        challenge_text = _looks_like_visual_challenge(text_preview, finding_codes)
        if challenge_text:
            signals.append(EvidenceSignal(
                code="visual_challenge_evidence",
                source="visual",
                confidence="medium",
                score=58,
                details={
                    "status": report.get("status", ""),
                    "image_kind": report.get("image_kind", ""),
                    "finding_codes": finding_codes[:10],
                    "ocr_provider": ocr.get("provider", ""),
                    "text_chars": _safe_int(ocr.get("text_chars")),
                },
            ))
        if report.get("status") in {"failed", "degraded"} or finding_codes:
            high_findings = [
                item for item in findings
                if str(item.get("severity") or "") in {"high", "critical"}
            ]
            signals.append(EvidenceSignal(
                code="visual_screenshot_degraded" if report.get("status") != "ok" else "visual_findings",
                source="visual",
                confidence="medium" if high_findings else "low",
                score=48 if high_findings else 28,
                details={
                    "status": report.get("status", ""),
                    "image_kind": report.get("image_kind", ""),
                    "width": _safe_int(report.get("width")),
                    "height": _safe_int(report.get("height")),
                    "finding_codes": finding_codes[:10],
                },
            ))
        if _safe_int(ocr.get("text_chars")) > 0:
            signals.append(EvidenceSignal(
                code="visual_ocr_text",
                source="visual",
                confidence="low",
                score=32,
                details={
                    "provider": ocr.get("provider", ""),
                    "text_chars": _safe_int(ocr.get("text_chars")),
                    "text_truncated": bool(ocr.get("text_truncated")),
                },
            ))
    return signals


def _visual_recon_reports(recon: dict[str, Any]) -> list[dict[str, Any]]:
    candidates: list[Any] = []
    direct = recon.get("visual_recon")
    if direct:
        candidates.append(direct)
    engine_result = recon.get("engine_result") if isinstance(recon.get("engine_result"), dict) else {}
    details = engine_result.get("details") if isinstance(engine_result.get("details"), dict) else {}
    for container in (engine_result, details):
        value = container.get("visual_recon") if isinstance(container, dict) else None
        if value:
            candidates.append(value)

    reports: list[dict[str, Any]] = []
    for candidate in candidates:
        if isinstance(candidate, dict):
            reports.append(candidate)
        elif isinstance(candidate, list):
            reports.extend(item for item in candidate if isinstance(item, dict))
    return reports


def _looks_like_visual_challenge(text_preview: str, finding_codes: list[str]) -> bool:
    lowered = text_preview.lower()
    challenge_markers = (
        "captcha",
        "verify you are human",
        "just a moment",
        "cloudflare",
        "security check",
        "challenge",
    )
    if any(marker in lowered for marker in challenge_markers):
        return True
    return any("captcha" in code or "challenge" in code for code in finding_codes)


def _crypto_items(js_evidence: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for item in js_evidence.get("items") or []:
        if not isinstance(item, dict):
            continue
        crypto = item.get("crypto_analysis") or {}
        if isinstance(crypto, dict) and (
            crypto.get("signals")
            or crypto.get("likely_signature_flow")
            or crypto.get("likely_encryption_flow")
            or crypto.get("likely_timestamp_nonce_flow")
        ):
            items.append(item)
    return items


def _signature_inputs(categories: set[str]) -> list[str]:
    inputs = ["request_path", "query_params", "headers_or_body"]
    if "sorting" in categories or "query_build" in categories:
        inputs.append("canonical_param_order")
    if "timestamp" in categories:
        inputs.append("timestamp")
    if "nonce" in categories:
        inputs.append("nonce")
    if "custom_token" in categories:
        inputs.append("custom_token_seed")
    return _dedupe(inputs)


def _dominant_sources(signals: list[EvidenceSignal]) -> list[str]:
    ranked: dict[str, int] = {}
    for signal in signals:
        ranked[signal.source] = max(ranked.get(signal.source, 0), signal.score)
    return [source for source, _score in sorted(ranked.items(), key=lambda item: item[1], reverse=True)]


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
