"""Conservative strategy scoring policy.

The scoring policy consumes ``StrategyEvidenceReport`` and produces an
explainable scorecard.  It is deliberately conservative: the scorecard explains
recommended actions and guardrails, while the existing Strategy node remains
responsible for the final executable mode.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .strategy_evidence import EvidenceSignal, StrategyEvidenceReport, has_high_crypto_replay_risk


EXECUTABLE_MODES = ("http", "api_intercept", "browser")
ADVISORY_ACTIONS = ("deeper_recon", "manual_handoff")
ALL_CANDIDATES = (*EXECUTABLE_MODES, *ADVISORY_ACTIONS)


@dataclass
class StrategyCandidateScore:
    """Score and reasons for one candidate strategy/action."""

    name: str
    score: int = 0
    reasons: list[str] = field(default_factory=list)
    penalties: list[str] = field(default_factory=list)

    def add(self, amount: int, reason: str) -> None:
        self.score += amount
        if reason:
            self.reasons.append(reason)

    def subtract(self, amount: int, reason: str) -> None:
        self.score -= amount
        if reason:
            self.penalties.append(reason)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "score": max(0, self.score),
            "reasons": list(dict.fromkeys(self.reasons)),
            "penalties": list(dict.fromkeys(self.penalties)),
        }


@dataclass
class StrategyScorecard:
    """Explainable scorecard for Strategy."""

    candidates: list[StrategyCandidateScore]
    recommended: str
    executable_recommended_mode: str
    guardrails: list[str] = field(default_factory=list)
    confidence: str = "low"

    def to_dict(self) -> dict[str, Any]:
        return {
            "recommended": self.recommended,
            "executable_recommended_mode": self.executable_recommended_mode,
            "confidence": self.confidence,
            "guardrails": list(dict.fromkeys(self.guardrails)),
            "candidates": [candidate.to_dict() for candidate in self.candidates],
        }


def score_strategy_candidates(report: StrategyEvidenceReport) -> StrategyScorecard:
    """Score candidate modes/actions from normalized evidence."""
    scores = {name: StrategyCandidateScore(name=name) for name in ALL_CANDIDATES}
    guardrails: list[str] = ["evidence_only_no_bypass"]

    for signal in report.signals:
        _apply_signal(scores, guardrails, signal)

    if has_high_crypto_replay_risk(report):
        scores["api_intercept"].subtract(35, "crypto evidence makes direct replay risky")
        scores["deeper_recon"].add(45, "signature/encryption evidence needs hook or sandbox planning")
        guardrails.append("crypto_requires_runtime_inputs")
        if report.action_hints.get("needs_browser_runtime"):
            scores["browser"].add(20, "WebCrypto evidence may need browser runtime")

    if "challenge_detected" in report.warnings:
        scores["api_intercept"].subtract(60, "challenge evidence blocks unsafe API replay")
        scores["manual_handoff"].add(70, "challenge evidence may require authorized/manual review")
        guardrails.append("challenge_blocks_api_replay")

    if _has_strong_dom(report.signals):
        scores["http"].add(20, "strong DOM evidence is preserved")
        scores["api_intercept"].subtract(15, "strong DOM evidence should not be overridden by weaker API hints")
        guardrails.append("good_dom_preserved")

    ordered = sorted(scores.values(), key=lambda item: item.to_dict()["score"], reverse=True)
    recommended = ordered[0].name
    executable_mode = _best_executable_mode(ordered)
    return StrategyScorecard(
        candidates=ordered,
        recommended=recommended,
        executable_recommended_mode=executable_mode,
        guardrails=guardrails,
        confidence=_confidence(ordered),
    )


def _apply_signal(
    scores: dict[str, StrategyCandidateScore],
    guardrails: list[str],
    signal: EvidenceSignal,
) -> None:
    amount = _bounded_score(signal.score)
    code = signal.code

    if code == "dom_repeated_items":
        scores["http"].add(amount, "repeated DOM items with usable selectors")
        scores["deeper_recon"].subtract(15, "DOM evidence is already actionable")
    elif code == "dom_partial_selectors":
        scores["http"].add(20, "partial DOM selectors exist")
        scores["deeper_recon"].add(25, "partial DOM evidence needs selector refinement")
    elif code == "observed_api_candidate":
        scores["api_intercept"].add(amount, "browser-observed public API candidate")
        scores["deeper_recon"].subtract(10, "observed API candidate is actionable")
    elif code == "api_candidate":
        scores["api_intercept"].add(max(20, amount - 10), "API candidate available")
    elif code == "blocked_api_candidate":
        scores["api_intercept"].subtract(35, "candidate API appears blocked")
        scores["browser"].add(20, "blocked API may need browser context")
        scores["deeper_recon"].add(25, "blocked API needs more diagnostics")
        guardrails.append("blocked_api_candidate_penalty")
    elif code == "js_endpoint_strings":
        scores["api_intercept"].add(25, "JS endpoint strings found")
        scores["deeper_recon"].add(30, "JS endpoints need validation before replay")
    elif code == "js_keyword_categories":
        categories = set(signal.details.get("categories") or [])
        if categories.intersection({"challenge", "fingerprint", "anti_bot"}):
            scores["browser"].add(30, "JS challenge/fingerprint categories found")
            scores["manual_handoff"].add(25, "anti-bot JS clues require review")
        if categories.intersection({"token", "crypto", "encryption"}):
            scores["deeper_recon"].add(25, "JS token/crypto clues need analysis")
    elif code in {"crypto_signature_flow", "crypto_encryption_flow", "crypto_timestamp_nonce_flow"}:
        scores["deeper_recon"].add(amount, "crypto/signature evidence needs reverse-engineering plan")
        scores["api_intercept"].subtract(20, "crypto evidence makes naive API replay fragile")
    elif code == "transport_sensitive":
        selected = str(signal.details.get("selected_mode") or "")
        scores["browser" if selected == "browser" else "http"].add(20, "transport diagnostics found a preferred transport")
        scores["deeper_recon"].add(25, "transport-sensitive access needs diagnostics")
    elif code == "fingerprint_runtime_risk":
        scores["browser"].add(35, "runtime fingerprint evidence affects browser strategy")
        scores["deeper_recon"].add(25, "fingerprint risk needs profile tuning")
        guardrails.append("fingerprint_risk_requires_profile_review")
    elif code == "challenge_detected":
        scores["browser"].add(35, "challenge evidence favors browser inspection")
        scores["manual_handoff"].add(55, "challenge evidence may need manual authorization")
    elif code == "js_rendering_required":
        scores["browser"].add(45, "JS rendering likely required")
    elif code == "websocket_activity":
        scores["browser"].add(30, "WebSocket activity needs browser runtime")
        scores["deeper_recon"].add(30, "WebSocket traffic needs protocol/frame analysis")


def _best_executable_mode(ordered: list[StrategyCandidateScore]) -> str:
    for candidate in ordered:
        if candidate.name in EXECUTABLE_MODES:
            return candidate.name
    return "browser"


def _confidence(ordered: list[StrategyCandidateScore]) -> str:
    top = ordered[0].to_dict()["score"] if ordered else 0
    second = ordered[1].to_dict()["score"] if len(ordered) > 1 else 0
    if top >= 80 and top - second >= 25:
        return "high"
    if top >= 50:
        return "medium"
    return "low"


def _has_strong_dom(signals: list[EvidenceSignal]) -> bool:
    return any(signal.code == "dom_repeated_items" and signal.score >= 55 for signal in signals)


def _bounded_score(score: int) -> int:
    return max(0, min(100, int(score or 0)))
