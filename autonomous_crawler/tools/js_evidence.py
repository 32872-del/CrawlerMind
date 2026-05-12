"""Combined JS evidence report for dynamic-site reconnaissance.

This module bridges CAP-4.4 browser JS capture, CAP-2.1 JS inventory, and
CAP-2.1 static string/function/call analysis. It is deterministic and does not
fetch external scripts by itself.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .js_asset_inventory import (
    JsAssetReport,
    ScriptAsset,
    analyze_js_text,
    build_inventory_summary,
    build_js_inventory,
    score_asset,
)
from .js_static_analysis import StaticAnalysisReport, analyze_js_static
from .js_crypto_analysis import CryptoAnalysisReport, analyze_js_crypto


@dataclass
class JsEvidenceItem:
    """One script-level evidence record."""

    source: str
    url: str = ""
    inline_id: str = ""
    inventory_score: int = 0
    static_score: int = 0
    total_score: int = 0
    reasons: list[str] = field(default_factory=list)
    endpoint_candidates: list[str] = field(default_factory=list)
    static_endpoint_strings: list[str] = field(default_factory=list)
    static_url_strings: list[str] = field(default_factory=list)
    keyword_categories: list[str] = field(default_factory=list)
    suspicious_functions: list[dict[str, Any]] = field(default_factory=list)
    suspicious_calls: list[dict[str, Any]] = field(default_factory=list)
    crypto_analysis: dict[str, Any] = field(default_factory=dict)
    sha256: str = ""
    size_bytes: int = 0
    text_truncated: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "url": self.url,
            "inline_id": self.inline_id,
            "inventory_score": self.inventory_score,
            "static_score": self.static_score,
            "total_score": self.total_score,
            "reasons": list(self.reasons),
            "endpoint_candidates": list(self.endpoint_candidates),
            "static_endpoint_strings": list(self.static_endpoint_strings),
            "static_url_strings": list(self.static_url_strings),
            "keyword_categories": list(self.keyword_categories),
            "suspicious_functions": list(self.suspicious_functions),
            "suspicious_calls": list(self.suspicious_calls),
            "crypto_analysis": dict(self.crypto_analysis),
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
            "text_truncated": self.text_truncated,
        }


@dataclass
class JsEvidenceReport:
    """Combined JS evidence across inline and captured scripts."""

    items: list[JsEvidenceItem] = field(default_factory=list)
    inventory_summary: dict[str, Any] = field(default_factory=dict)
    top_endpoints: list[str] = field(default_factory=list)
    top_suspicious_calls: list[str] = field(default_factory=list)
    top_crypto_signals: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "items": [item.to_dict() for item in self.items],
            "inventory_summary": dict(self.inventory_summary),
            "top_endpoints": list(self.top_endpoints),
            "top_suspicious_calls": list(self.top_suspicious_calls),
            "top_crypto_signals": list(self.top_crypto_signals),
            "recommendations": list(self.recommendations),
        }


def build_js_evidence_report(
    html: str = "",
    *,
    base_url: str = "",
    captured_js_assets: list[dict[str, Any]] | None = None,
    max_items: int = 20,
) -> JsEvidenceReport:
    """Build ranked JS evidence from HTML inline scripts and captured JS assets."""
    inventory_reports = build_js_inventory(html or "", base_url=base_url)
    items: list[JsEvidenceItem] = []

    for report in inventory_reports:
        if report.asset.is_inline:
            items.append(_inline_inventory_to_evidence(report))

    for asset in captured_js_assets or []:
        item = _captured_asset_to_evidence(asset)
        if item:
            items.append(item)

    items.sort(key=lambda item: item.total_score, reverse=True)
    if max_items > 0:
        items = items[:max_items]

    return JsEvidenceReport(
        items=items,
        inventory_summary=build_inventory_summary(inventory_reports),
        top_endpoints=_collect_top_endpoints(items),
        top_suspicious_calls=_collect_top_calls(items),
        top_crypto_signals=_collect_top_crypto_signals(items),
        recommendations=_build_recommendations(items),
    )


def _inline_inventory_to_evidence(report: JsAssetReport) -> JsEvidenceItem:
    static = analyze_js_static(_join_inventory_text(report))
    crypto = analyze_js_crypto(_join_inventory_text(report))
    return _build_item(
        source="inline",
        url=report.asset.url,
        inline_id=report.asset.inline_id,
        inventory_score=report.score,
        inventory_reasons=report.reasons,
        endpoint_candidates=report.endpoint_candidates,
        keyword_categories=sorted({hit.category for hit in report.keyword_hits}),
        static=static,
        crypto=crypto,
    )


def _captured_asset_to_evidence(asset: dict[str, Any]) -> JsEvidenceItem | None:
    js_text = str(
        asset.get("text_preview")
        or asset.get("body_preview")
        or asset.get("content_preview")
        or ""
    )
    if not js_text:
        return JsEvidenceItem(
            source="captured",
            url=str(asset.get("url") or ""),
            sha256=str(asset.get("sha256") or ""),
            size_bytes=_safe_int(asset.get("size_bytes")),
            text_truncated=bool(asset.get("text_truncated")),
            reasons=["captured_js_metadata_only"],
        )

    inventory = analyze_js_text(js_text)
    script_asset = ScriptAsset(
        url=str(asset.get("url") or ""),
        is_inline=False,
        size_estimate=_safe_int(asset.get("size_bytes")),
    )
    inventory_score, inventory_reasons = score_asset(script_asset, inventory)
    static = analyze_js_static(js_text)
    crypto = analyze_js_crypto(js_text)
    return _build_item(
        source="captured",
        url=str(asset.get("url") or ""),
        inventory_score=inventory_score,
        inventory_reasons=inventory_reasons,
        endpoint_candidates=list(inventory.get("endpoint_candidates") or []),
        keyword_categories=sorted({hit.category for hit in inventory.get("keyword_hits", [])}),
        static=static,
        crypto=crypto,
        sha256=str(asset.get("sha256") or ""),
        size_bytes=_safe_int(asset.get("size_bytes")),
        text_truncated=bool(asset.get("text_truncated")),
    )


def _build_item(
    *,
    source: str,
    url: str = "",
    inline_id: str = "",
    inventory_score: int,
    inventory_reasons: list[str],
    endpoint_candidates: list[str],
    keyword_categories: list[str],
    static: StaticAnalysisReport,
    crypto: CryptoAnalysisReport,
    sha256: str = "",
    size_bytes: int = 0,
    text_truncated: bool = False,
) -> JsEvidenceItem:
    static_payload = static.to_dict()
    total_score = inventory_score + static.score
    total_score += crypto.score
    reasons = list(dict.fromkeys([*inventory_reasons, *static.reasons, *[f"crypto:{c}" for c in crypto.categories]]))
    return JsEvidenceItem(
        source=source,
        url=url,
        inline_id=inline_id,
        inventory_score=inventory_score,
        static_score=static.score,
        total_score=total_score,
        reasons=reasons,
        endpoint_candidates=endpoint_candidates,
        static_endpoint_strings=list(static.endpoint_strings),
        static_url_strings=list(static.url_strings),
        keyword_categories=keyword_categories,
        suspicious_functions=list(static_payload["suspicious_functions"]),
        suspicious_calls=list(static_payload["suspicious_calls"]),
        crypto_analysis=crypto.to_dict(),
        sha256=sha256,
        size_bytes=size_bytes,
        text_truncated=text_truncated,
    )


def _join_inventory_text(report: JsAssetReport) -> str:
    """Reconstruct bounded evidence text from inventory-only fields."""
    chunks: list[str] = []
    chunks.extend(report.endpoint_candidates)
    chunks.extend(report.graphql_strings)
    chunks.extend(report.websocket_urls)
    chunks.extend(hit.context_preview for hit in report.keyword_hits if hit.context_preview)
    return "\n".join(chunks)


def _collect_top_endpoints(items: list[JsEvidenceItem], limit: int = 20) -> list[str]:
    seen: set[str] = set()
    endpoints: list[str] = []
    for item in items:
        for endpoint in [*item.endpoint_candidates, *item.static_endpoint_strings, *item.static_url_strings]:
            if endpoint and endpoint not in seen:
                seen.add(endpoint)
                endpoints.append(endpoint)
                if len(endpoints) >= limit:
                    return endpoints
    return endpoints


def _collect_top_calls(items: list[JsEvidenceItem], limit: int = 20) -> list[str]:
    seen: set[str] = set()
    calls: list[str] = []
    for item in items:
        for call in item.suspicious_calls:
            expression = str(call.get("call") or "")
            if expression and expression not in seen:
                seen.add(expression)
                calls.append(expression)
                if len(calls) >= limit:
                    return calls
    return calls


def _collect_top_crypto_signals(items: list[JsEvidenceItem], limit: int = 20) -> list[str]:
    seen: set[str] = set()
    signals: list[str] = []
    for item in items:
        crypto = item.crypto_analysis or {}
        for signal in crypto.get("signals") or []:
            name = str(signal.get("name") or "")
            kind = str(signal.get("kind") or "")
            label = f"{kind}:{name}" if kind and name else name or kind
            if label and label not in seen:
                seen.add(label)
                signals.append(label)
                if len(signals) >= limit:
                    return signals
    return signals


def _build_recommendations(items: list[JsEvidenceItem]) -> list[str]:
    recommendations: list[str] = []
    if any(item.static_endpoint_strings or item.endpoint_candidates for item in items):
        recommendations.append("Review extracted API strings before choosing api_intercept")
    if any(item.suspicious_functions or item.suspicious_calls for item in items):
        recommendations.append("Prioritize high-score JS files for signature/token hook analysis")
    if any("challenge" in item.keyword_categories or "fingerprint" in item.keyword_categories for item in items):
        recommendations.append("Inspect challenge/fingerprint clues before browser automation scaling")
    if any((item.crypto_analysis or {}).get("likely_signature_flow") for item in items):
        recommendations.append("Analyze signature/hash parameter flow before API replay")
    if any((item.crypto_analysis or {}).get("likely_encryption_flow") for item in items):
        recommendations.append("Isolate encryption/WebCrypto routines before replaying protected APIs")
    if not recommendations:
        recommendations.append("No strong JS reverse-engineering clue found")
    return recommendations


def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0
