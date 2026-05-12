"""JS crypto/signature evidence analysis (CAP-2.1/CAP-2.2).

This module detects client-side signing and encryption clues in JavaScript.
It does not execute JS, recover keys, bypass protections, or solve challenges.
Its job is to give the agent structured evidence about where reverse-engineering
work should focus.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


MAX_TEXT_CHARS = 300_000
MAX_CONTEXT_CHARS = 180


@dataclass(frozen=True)
class CryptoSignal:
    """One crypto/signature signal found in JS text."""

    kind: str
    name: str
    confidence: str
    context: str = ""

    def to_dict(self) -> dict[str, str]:
        return {
            "kind": self.kind,
            "name": self.name,
            "confidence": self.confidence,
            "context": self.context,
        }


@dataclass
class CryptoAnalysisReport:
    """Structured crypto/signature analysis report."""

    signals: list[CryptoSignal] = field(default_factory=list)
    categories: list[str] = field(default_factory=list)
    likely_signature_flow: bool = False
    likely_encryption_flow: bool = False
    likely_timestamp_nonce_flow: bool = False
    score: int = 0
    recommendations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "signals": [signal.to_dict() for signal in self.signals],
            "categories": list(self.categories),
            "likely_signature_flow": self.likely_signature_flow,
            "likely_encryption_flow": self.likely_encryption_flow,
            "likely_timestamp_nonce_flow": self.likely_timestamp_nonce_flow,
            "score": self.score,
            "recommendations": list(self.recommendations),
        }


_PATTERNS: tuple[tuple[str, str, str, re.Pattern[str]], ...] = (
    ("hash", "md5", "high", re.compile(r"\b(?:md5|MD5)\s*\(", re.I)),
    ("hash", "sha1", "high", re.compile(r"\bsha1\s*\(", re.I)),
    ("hash", "sha256", "high", re.compile(r"\bsha256\s*\(|SHA-256|sha-?256", re.I)),
    ("hash", "sha512", "high", re.compile(r"\bsha512\s*\(|SHA-512|sha-?512", re.I)),
    ("hmac", "hmac", "high", re.compile(r"\bhmac(?:SHA\d+)?\s*\(|HMAC|createHmac", re.I)),
    ("signature", "sign", "medium", re.compile(r"\b(?:sign|signature|signRequest|signPayload|x-signature)\b", re.I)),
    ("webcrypto", "subtle.digest", "high", re.compile(r"crypto\.subtle\.digest|subtle\.digest", re.I)),
    ("webcrypto", "subtle.sign", "high", re.compile(r"crypto\.subtle\.sign|subtle\.sign", re.I)),
    ("webcrypto", "getRandomValues", "medium", re.compile(r"crypto\.getRandomValues|getRandomValues", re.I)),
    ("encoding", "base64", "medium", re.compile(r"\b(?:btoa|atob|Base64|base64)\b", re.I)),
    ("encoding", "urlencode", "low", re.compile(r"\b(?:encodeURIComponent|URLSearchParams)\b", re.I)),
    ("encryption", "aes", "high", re.compile(r"\bAES\b|aes(?:Encrypt|Decrypt)?|CryptoJS\.AES", re.I)),
    ("encryption", "rsa", "high", re.compile(r"\bRSA\b|JSEncrypt|publicKey|privateKey", re.I)),
    ("encryption", "cryptojs", "high", re.compile(r"\bCryptoJS\b", re.I)),
    ("timestamp", "timestamp", "medium", re.compile(r"\b(?:timestamp|timeStamp|ts)\b|Date\.now\(\)|new Date\(\)\.getTime", re.I)),
    ("nonce", "nonce", "medium", re.compile(r"\b(?:nonce|randomString|uuid|guid)\b", re.I)),
    ("sorting", "param_sort", "medium", re.compile(r"Object\.keys\([^)]*\)\.sort\(\)|\.sort\(\)\.map\(", re.I)),
    ("query_build", "query_join", "medium", re.compile(r"\.join\([\"']&[\"']\)|URLSearchParams", re.I)),
    ("custom_token", "xbogus", "high", re.compile(r"x-?bogus|XBogus|_signature|wbi|mixinKey", re.I)),
)


def analyze_js_crypto(js_text: str) -> CryptoAnalysisReport:
    """Analyze JS text for signing/encryption evidence."""
    text = (js_text or "")[:MAX_TEXT_CHARS]
    signals = _collect_signals(text)
    categories = sorted({signal.kind for signal in signals})
    category_set = set(categories)

    likely_signature_flow = _has_any(category_set, {"signature", "hash", "hmac", "sorting", "query_build", "custom_token"})
    likely_encryption_flow = _has_any(category_set, {"encryption", "webcrypto"}) and (
        "encryption" in category_set or any(s.name in {"subtle.sign", "getRandomValues"} for s in signals)
    )
    likely_timestamp_nonce_flow = _has_any(category_set, {"timestamp", "nonce"})

    score = _score_crypto_report(signals, category_set)
    return CryptoAnalysisReport(
        signals=signals,
        categories=categories,
        likely_signature_flow=likely_signature_flow,
        likely_encryption_flow=likely_encryption_flow,
        likely_timestamp_nonce_flow=likely_timestamp_nonce_flow,
        score=score,
        recommendations=_build_recommendations(category_set, likely_signature_flow, likely_encryption_flow),
    )


def _collect_signals(text: str) -> list[CryptoSignal]:
    signals: list[CryptoSignal] = []
    seen: set[tuple[str, str]] = set()
    for kind, name, confidence, pattern in _PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        key = (kind, name)
        if key in seen:
            continue
        seen.add(key)
        signals.append(CryptoSignal(
            kind=kind,
            name=name,
            confidence=confidence,
            context=_context(text, match.start(), match.end()),
        ))
    return signals


def _score_crypto_report(signals: list[CryptoSignal], categories: set[str]) -> int:
    score = 0
    for signal in signals:
        if signal.confidence == "high":
            score += 18
        elif signal.confidence == "medium":
            score += 10
        else:
            score += 4

    if {"sorting", "query_build", "hash"} <= categories:
        score += 25
    if {"timestamp", "nonce"} <= categories:
        score += 12
    if "custom_token" in categories:
        score += 22
    if "webcrypto" in categories and ("signature" in categories or "hash" in categories):
        score += 18
    if "encryption" in categories:
        score += 16
    return min(score, 100)


def _build_recommendations(
    categories: set[str],
    likely_signature_flow: bool,
    likely_encryption_flow: bool,
) -> list[str]:
    recommendations: list[str] = []
    if likely_signature_flow:
        recommendations.append("Trace request parameter canonicalization before replaying API calls")
    if "custom_token" in categories:
        recommendations.append("Prioritize custom token/signature functions for hook or sandbox execution")
    if likely_encryption_flow:
        recommendations.append("Isolate encryption routines before attempting API replay")
    if "webcrypto" in categories:
        recommendations.append("Browser runtime hooks may be needed because WebCrypto calls are environment-dependent")
    if "timestamp" in categories or "nonce" in categories:
        recommendations.append("Record timestamp/nonce generation inputs when building repeatable requests")
    if not recommendations:
        recommendations.append("No strong crypto/signature evidence found")
    return recommendations


def _context(text: str, start: int, end: int) -> str:
    left = max(0, start - 70)
    right = min(len(text), end + 70)
    snippet = text[left:right].replace("\n", " ").strip()
    if left > 0:
        snippet = "..." + snippet
    if right < len(text):
        snippet = snippet + "..."
    return snippet[:MAX_CONTEXT_CHARS]


def _has_any(values: set[str], candidates: set[str]) -> bool:
    return bool(values.intersection(candidates))
