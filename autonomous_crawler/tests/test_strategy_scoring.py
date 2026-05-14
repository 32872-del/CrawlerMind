"""Tests for conservative StrategyScoringPolicy (CAP-5.1 calibration)."""
from __future__ import annotations

import unittest

from autonomous_crawler.agents.strategy import strategy_node
from autonomous_crawler.tools.strategy_evidence import (
    EvidenceSignal,
    StrategyEvidenceReport,
    build_strategy_evidence_report,
)
from autonomous_crawler.tools.strategy_scoring import (
    ALL_CANDIDATES,
    StrategyCandidateScore,
    score_strategy_candidates,
)


def _state(**recon_overrides: object) -> dict:
    recon = {
        "target_url": "https://shop.example/catalog",
        "task_type": "product_list",
        "rendering": "static",
        "anti_bot": {"detected": False},
        "dom_structure": {"item_count": 0, "field_selectors": {}},
        "constraints": {},
    }
    recon.update(recon_overrides)
    return {
        "user_goal": "collect products",
        "target_url": recon["target_url"],
        "recon_report": recon,
        "messages": [],
    }


def _signature_js_evidence() -> dict:
    return {
        "top_crypto_signals": ["hash:sha256", "timestamp:timestamp"],
        "items": [{
            "source": "captured",
            "url": "https://shop.example/app.js",
            "total_score": 95,
            "keyword_categories": ["token"],
            "crypto_analysis": {
                "signals": [{"kind": "hash", "name": "sha256", "confidence": "high"}],
                "categories": ["hash", "sorting", "query_build", "timestamp"],
                "likely_signature_flow": True,
                "likely_encryption_flow": False,
                "likely_timestamp_nonce_flow": True,
                "score": 88,
                "recommendations": ["Trace request parameter canonicalization before replaying API calls"],
            },
        }],
    }


class StrategyScoringPolicyTests(unittest.TestCase):
    def test_good_dom_scores_http_highest(self) -> None:
        report = build_strategy_evidence_report({
            "dom_structure": {
                "item_count": 8,
                "product_selector": ".card",
                "field_selectors": {"title": ".title", "price": ".price"},
            },
        })
        scorecard = score_strategy_candidates(report).to_dict()

        self.assertEqual(scorecard["executable_recommended_mode"], "http")
        self.assertIn("good_dom_preserved", scorecard["guardrails"])
        self.assertEqual(scorecard["candidates"][0]["name"], "http")

    def test_observed_api_scores_api_intercept_highest_without_dom(self) -> None:
        report = build_strategy_evidence_report({
            "api_candidates": [{
                "url": "https://shop.example/api/products",
                "method": "GET",
                "kind": "json",
                "score": 82,
                "reason": "browser_network_observation",
                "status_code": 200,
            }],
        })
        scorecard = score_strategy_candidates(report).to_dict()

        self.assertEqual(scorecard["executable_recommended_mode"], "api_intercept")
        self.assertEqual(scorecard["candidates"][0]["name"], "api_intercept")

    def test_challenge_scores_manual_handoff_and_browser_guardrail(self) -> None:
        report = build_strategy_evidence_report({
            "anti_bot": {"detected": True, "matches": ["cf-challenge"]},
            "access_diagnostics": {
                "signals": {"challenge": "cf-challenge"},
                "findings": ["challenge_detected:cf-challenge"],
            },
        })
        scorecard = score_strategy_candidates(report).to_dict()

        self.assertEqual(scorecard["recommended"], "manual_handoff")
        self.assertEqual(scorecard["executable_recommended_mode"], "browser")
        self.assertIn("challenge_blocks_api_replay", scorecard["guardrails"])

    def test_signature_evidence_penalizes_naive_api_replay(self) -> None:
        report = build_strategy_evidence_report({
            "api_candidates": [{
                "url": "https://shop.example/api/products",
                "method": "GET",
                "kind": "json",
                "score": 70,
                "reason": "browser_network_observation",
                "status_code": 200,
            }],
            "js_evidence": _signature_js_evidence(),
        })
        scorecard = score_strategy_candidates(report).to_dict()

        self.assertEqual(scorecard["recommended"], "deeper_recon")
        self.assertIn("crypto_requires_runtime_inputs", scorecard["guardrails"])
        api_candidate = next(item for item in scorecard["candidates"] if item["name"] == "api_intercept")
        self.assertTrue(any("crypto evidence" in reason for reason in api_candidate["penalties"]))

    def test_websocket_activity_scores_browser_and_deeper_recon(self) -> None:
        report = build_strategy_evidence_report({
            "websocket_summary": {
                "connection_count": 2,
                "total_frames": 12,
                "message_kinds": ["json"],
            },
        })
        scorecard = score_strategy_candidates(report).to_dict()
        names = [item["name"] for item in scorecard["candidates"][:2]]

        self.assertIn("browser", names)
        self.assertIn("deeper_recon", names)

    def test_strategy_node_attaches_scorecard_without_overriding_mode(self) -> None:
        state = strategy_node(_state(
            dom_structure={
                "item_count": 5,
                "product_selector": ".card",
                "field_selectors": {"title": ".title"},
            },
            api_candidates=[{
                "url": "https://shop.example/api/products",
                "method": "GET",
                "kind": "json",
                "score": 90,
                "reason": "browser_network_observation",
                "status_code": 200,
            }],
        ))
        strategy = state["crawl_strategy"]

        self.assertEqual(strategy["mode"], "http")
        self.assertIn("strategy_scorecard", strategy)
        self.assertEqual(strategy["strategy_scorecard"]["executable_recommended_mode"], "http")
        self.assertNotIn("strategy_scorecard_warning", strategy)

    def test_scorecard_warning_when_advisory_differs_from_deterministic_mode(self) -> None:
        state = strategy_node(_state(
            api_candidates=[{
                "url": "https://shop.example/api/products",
                "method": "GET",
                "kind": "json",
                "score": 80,
                "reason": "browser_network_observation",
                "status_code": 200,
            }],
            js_evidence=_signature_js_evidence(),
        ))
        strategy = state["crawl_strategy"]

        self.assertEqual(strategy["mode"], "api_intercept")
        self.assertEqual(strategy["strategy_scorecard"]["recommended"], "deeper_recon")
        self.assertIn("strategy_scorecard_warning", strategy)
        self.assertEqual(strategy["strategy_scorecard_warning"]["current_mode"], "api_intercept")


# ---------------------------------------------------------------------------
# CAP-5.1 calibration tests
# ---------------------------------------------------------------------------


class ScoreClampingTests(unittest.TestCase):
    """Verify _bounded_score clamps to [0, 100] and negative scores are clamped."""

    def test_negative_score_clamped_to_zero_in_candidate(self) -> None:
        """A candidate with a net-negative score shows 0 in to_dict()."""
        candidate = StrategyCandidateScore(name="http", score=-50)
        self.assertEqual(candidate.to_dict()["score"], 0)

    def test_score_above_100_clamped_in_signal(self) -> None:
        """A signal with score>100 is clamped to 100 during scoring."""
        report = StrategyEvidenceReport(
            signals=[EvidenceSignal(code="dom_repeated_items", source="dom", score=200)],
        )
        scorecard = score_strategy_candidates(report)
        http = next(c for c in scorecard.candidates if c.name == "http")
        # score is clamped to 100, then +20 strong DOM boost = 120, but to_dict clamps display
        self.assertGreaterEqual(http.to_dict()["score"], 100)

    def test_zero_score_signal_does_not_change_candidate(self) -> None:
        """A signal with score=0 adds 0 but still records the reason."""
        report = StrategyEvidenceReport(
            signals=[EvidenceSignal(code="dom_repeated_items", source="dom", score=0)],
        )
        scorecard = score_strategy_candidates(report)
        http = next(c for c in scorecard.candidates if c.name == "http")
        # score 0 clamped to 0, but reason still recorded
        self.assertIn("repeated DOM items with usable selectors", http.reasons)

    def test_scorecard_to_dict_clamps_all_candidates(self) -> None:
        """All candidates in scorecard.to_dict() have score >= 0."""
        report = StrategyEvidenceReport(
            signals=[
                EvidenceSignal(code="blocked_api_candidate", source="api", score=0, details={}),
                EvidenceSignal(code="challenge_detected", source="access", score=90),
            ],
        )
        scorecard = score_strategy_candidates(report).to_dict()
        for candidate in scorecard["candidates"]:
            self.assertGreaterEqual(candidate["score"], 0, f"{candidate['name']} has negative score")


class ConfidenceThresholdTests(unittest.TestCase):
    """Verify confidence is set correctly based on score thresholds."""

    def test_high_confidence_when_top_gte_80_and_gap_gte_25(self) -> None:
        """High confidence: top score >= 80 and gap >= 25."""
        report = build_strategy_evidence_report({
            "dom_structure": {
                "item_count": 10,
                "product_selector": ".card",
                "field_selectors": {"title": ".title", "price": ".price", "image": ".img"},
            },
        })
        scorecard = score_strategy_candidates(report).to_dict()
        # Strong DOM should give http a high score with a big gap
        self.assertEqual(scorecard["confidence"], "high")

    def test_medium_confidence_when_top_gte_50_but_small_gap(self) -> None:
        """Medium confidence: top >= 50 but gap < 25."""
        report = StrategyEvidenceReport(
            signals=[
                EvidenceSignal(code="js_endpoint_strings", source="js", score=55),
                EvidenceSignal(code="transport_sensitive", source="transport", score=75),
            ],
        )
        scorecard = score_strategy_candidates(report).to_dict()
        # Both give moderate scores to different candidates
        self.assertIn(scorecard["confidence"], ("medium", "high"))

    def test_low_confidence_when_all_scores_low(self) -> None:
        """Low confidence: no candidate reaches 50."""
        report = StrategyEvidenceReport(signals=[])
        scorecard = score_strategy_candidates(report).to_dict()
        self.assertEqual(scorecard["confidence"], "low")

    def test_empty_signals_yields_low_confidence(self) -> None:
        """Empty signal list → low confidence."""
        report = StrategyEvidenceReport(signals=[], warnings=[], action_hints={})
        scorecard = score_strategy_candidates(report)
        self.assertEqual(scorecard.confidence, "low")


class EmptySignalsTests(unittest.TestCase):
    """Verify behavior with no evidence signals."""

    def test_empty_signals_all_candidates_at_zero(self) -> None:
        """With no signals, all candidates score 0."""
        report = StrategyEvidenceReport(signals=[])
        scorecard = score_strategy_candidates(report).to_dict()
        for candidate in scorecard["candidates"]:
            self.assertEqual(candidate["score"], 0, f"{candidate['name']} should be 0")

    def test_empty_signals_default_guardrail_present(self) -> None:
        """Even with no signals, evidence_only_no_bypass guardrail is present."""
        report = StrategyEvidenceReport(signals=[])
        scorecard = score_strategy_candidates(report).to_dict()
        self.assertIn("evidence_only_no_bypass", scorecard["guardrails"])

    def test_empty_signals_fallback_to_http(self) -> None:
        """With no evidence, http is the first executable mode (all scores equal)."""
        report = StrategyEvidenceReport(signals=[])
        scorecard = score_strategy_candidates(report)
        # When all scores are 0, sorted preserves insertion order;
        # http is first in ALL_CANDIDATES and is executable.
        self.assertEqual(scorecard.executable_recommended_mode, "http")


class BlockedApiPenaltyTests(unittest.TestCase):
    """Verify blocked_api_candidate applies correct penalties and bonuses."""

    def test_blocked_api_penalizes_api_intercept(self) -> None:
        """blocked_api_candidate subtracts 35 from api_intercept."""
        report = StrategyEvidenceReport(
            signals=[EvidenceSignal(
                code="blocked_api_candidate",
                source="api",
                score=0,
                details={"url": "https://example.com/api", "status_code": 403},
            )],
        )
        scorecard = score_strategy_candidates(report).to_dict()
        api = next(c for c in scorecard["candidates"] if c["name"] == "api_intercept")
        self.assertTrue(any("blocked" in p for p in api["penalties"]))
        self.assertEqual(api["score"], 0)  # net negative clamped to 0

    def test_blocked_api_boosts_browser_and_deeper_recon(self) -> None:
        """blocked_api_candidate adds +20 browser, +25 deeper_recon."""
        report = StrategyEvidenceReport(
            signals=[EvidenceSignal(
                code="blocked_api_candidate",
                source="api",
                score=0,
                details={"url": "https://example.com/api", "status_code": 403},
            )],
        )
        scorecard = score_strategy_candidates(report).to_dict()
        browser = next(c for c in scorecard["candidates"] if c["name"] == "browser")
        deeper = next(c for c in scorecard["candidates"] if c["name"] == "deeper_recon")
        self.assertGreaterEqual(browser["score"], 20)
        self.assertGreaterEqual(deeper["score"], 25)

    def test_blocked_api_adds_guardrail(self) -> None:
        """blocked_api_candidate adds blocked_api_candidate_penalty guardrail."""
        report = StrategyEvidenceReport(
            signals=[EvidenceSignal(
                code="blocked_api_candidate",
                source="api",
                score=0,
                details={},
            )],
        )
        scorecard = score_strategy_candidates(report).to_dict()
        self.assertIn("blocked_api_candidate_penalty", scorecard["guardrails"])


class StrongDomVsChallengeInteractionTests(unittest.TestCase):
    """Verify DOM boost does NOT cancel challenge penalty."""

    def test_challenge_overrides_dom_boost(self) -> None:
        """Even with strong DOM, challenge still recommends manual_handoff."""
        report = build_strategy_evidence_report({
            "dom_structure": {
                "item_count": 10,
                "product_selector": ".card",
                "field_selectors": {"title": ".title", "price": ".price"},
            },
            "anti_bot": {"detected": True, "matches": ["cf-challenge"]},
            "access_diagnostics": {
                "signals": {"challenge": "cf-challenge"},
                "findings": ["challenge_detected:cf-challenge"],
            },
        })
        scorecard = score_strategy_candidates(report).to_dict()
        self.assertEqual(scorecard["recommended"], "manual_handoff")
        self.assertIn("challenge_blocks_api_replay", scorecard["guardrails"])
        self.assertIn("good_dom_preserved", scorecard["guardrails"])

    def test_challenge_and_crypto_combined(self) -> None:
        """Challenge + crypto both apply; both guardrails added."""
        report = build_strategy_evidence_report({
            "anti_bot": {"detected": True, "matches": ["cf-challenge"]},
            "access_diagnostics": {
                "signals": {"challenge": "cf-challenge"},
                "findings": ["challenge_detected:cf-challenge"],
            },
            "js_evidence": _signature_js_evidence(),
        })
        scorecard = score_strategy_candidates(report).to_dict()
        # Both guardrails must be present
        self.assertIn("challenge_blocks_api_replay", scorecard["guardrails"])
        self.assertIn("crypto_requires_runtime_inputs", scorecard["guardrails"])
        # manual_handoff must be among top candidates
        names = [c["name"] for c in scorecard["candidates"]]
        self.assertIn("manual_handoff", names[:2])

    def test_strong_dom_plus_blocked_api(self) -> None:
        """Strong DOM + blocked API: http still wins from DOM boost."""
        report = build_strategy_evidence_report({
            "dom_structure": {
                "item_count": 8,
                "product_selector": ".card",
                "field_selectors": {"title": ".title", "price": ".price"},
            },
            "api_candidates": [{
                "url": "https://shop.example/api/products",
                "method": "GET",
                "kind": "json",
                "score": 80,
                "status_code": 403,
            }],
        })
        scorecard = score_strategy_candidates(report).to_dict()
        # Strong DOM boost + blocked API penalty on api_intercept → http wins
        self.assertEqual(scorecard["executable_recommended_mode"], "http")


class GuardrailDedupTests(unittest.TestCase):
    """Verify guardrails list is deduplicated in scorecard output."""

    def test_duplicate_guardrails_deduped(self) -> None:
        """Same guardrail added twice appears only once in output."""
        report = StrategyEvidenceReport(
            signals=[
                EvidenceSignal(code="blocked_api_candidate", source="api1", score=0, details={}),
                EvidenceSignal(code="blocked_api_candidate", source="api2", score=0, details={}),
            ],
        )
        scorecard = score_strategy_candidates(report).to_dict()
        guardrail_count = scorecard["guardrails"].count("blocked_api_candidate_penalty")
        self.assertEqual(guardrail_count, 1)


class CandidateReasonDedupTests(unittest.TestCase):
    """Verify candidate reasons and penalties are deduplicated."""

    def test_duplicate_reasons_deduped_in_to_dict(self) -> None:
        """Adding the same reason twice results in one entry in to_dict()."""
        candidate = StrategyCandidateScore(name="http")
        candidate.add(10, "same reason")
        candidate.add(10, "same reason")
        d = candidate.to_dict()
        self.assertEqual(d["reasons"].count("same reason"), 1)

    def test_duplicate_penalties_deduped_in_to_dict(self) -> None:
        """Adding the same penalty twice results in one entry in to_dict()."""
        candidate = StrategyCandidateScore(name="api_intercept")
        candidate.subtract(10, "same penalty")
        candidate.subtract(10, "same penalty")
        d = candidate.to_dict()
        self.assertEqual(d["penalties"].count("same penalty"), 1)


class AllCandidatesPresentTests(unittest.TestCase):
    """Verify all 5 candidates always appear in scorecard."""

    def test_all_five_candidates_present(self) -> None:
        """Empty report still produces all 5 candidates."""
        report = StrategyEvidenceReport(signals=[])
        scorecard = score_strategy_candidates(report).to_dict()
        names = [c["name"] for c in scorecard["candidates"]]
        for name in ALL_CANDIDATES:
            self.assertIn(name, names, f"Missing candidate: {name}")

    def test_candidate_count_is_five(self) -> None:
        """Scorecard always has exactly 5 candidates."""
        report = build_strategy_evidence_report({
            "dom_structure": {"item_count": 5, "product_selector": ".card", "field_selectors": {"title": ".t"}},
            "anti_bot": {"detected": True, "matches": ["cf-challenge"]},
        })
        scorecard = score_strategy_candidates(report).to_dict()
        self.assertEqual(len(scorecard["candidates"]), 5)


class MultipleSignalInteractionTests(unittest.TestCase):
    """Verify combined effect of multiple signal types."""

    def test_challenge_plus_websocket(self) -> None:
        """Challenge + WS activity: challenge wins, WS boosts browser."""
        report = build_strategy_evidence_report({
            "anti_bot": {"detected": True, "matches": ["cf-challenge"]},
            "access_diagnostics": {
                "signals": {"challenge": "cf-challenge"},
                "findings": ["challenge_detected:cf-challenge"],
            },
            "websocket_summary": {"connection_count": 2, "total_frames": 10, "message_kinds": ["json"]},
        })
        scorecard = score_strategy_candidates(report).to_dict()
        self.assertEqual(scorecard["recommended"], "manual_handoff")
        browser = next(c for c in scorecard["candidates"] if c["name"] == "browser")
        self.assertTrue(any("WebSocket" in r for r in browser["reasons"]))

    def test_transport_plus_fingerprint(self) -> None:
        """Transport + fingerprint: both boost browser and deeper_recon."""
        report = build_strategy_evidence_report({
            "transport_diagnostics": {
                "transport_sensitive": True,
                "selected_mode": "curl_cffi",
                "findings": ["status_differs_by_transport"],
            },
            "browser_fingerprint_probe": {
                "status": "ok",
                "risk_level": "medium",
                "findings": [{"code": "webdriver_exposed"}],
            },
        })
        scorecard = score_strategy_candidates(report).to_dict()
        browser = next(c for c in scorecard["candidates"] if c["name"] == "browser")
        deeper = next(c for c in scorecard["candidates"] if c["name"] == "deeper_recon")
        self.assertGreater(browser["score"], 0)
        self.assertGreater(deeper["score"], 0)

    def test_js_rendering_plus_observed_api(self) -> None:
        """JS rendering required + observed API: browser and api both score."""
        report = build_strategy_evidence_report({
            "access_diagnostics": {"findings": ["js_rendering_likely_required"]},
            "api_candidates": [{
                "url": "https://shop.example/api/products",
                "method": "GET",
                "kind": "json",
                "score": 85,
                "reason": "browser_network_observation",
                "status_code": 200,
            }],
        })
        scorecard = score_strategy_candidates(report).to_dict()
        browser = next(c for c in scorecard["candidates"] if c["name"] == "browser")
        api = next(c for c in scorecard["candidates"] if c["name"] == "api_intercept")
        self.assertGreater(browser["score"], 0)
        self.assertGreater(api["score"], 0)


class ExecutableModeSelectionTests(unittest.TestCase):
    """Verify _best_executable_mode picks correctly from ordered candidates."""

    def test_advisory_action_cannot_be_executable_mode(self) -> None:
        """deeper_recon and manual_handoff are advisory, not executable."""
        report = StrategyEvidenceReport(
            signals=[
                EvidenceSignal(code="crypto_signature_flow", source="crypto", score=80),
                EvidenceSignal(code="challenge_detected", source="access", score=90),
            ],
        )
        scorecard = score_strategy_candidates(report)
        self.assertIn(scorecard.executable_recommended_mode, ("http", "api_intercept", "browser"))

    def test_http_is_first_when_all_executables_zero(self) -> None:
        """When all executable modes score 0, http wins (first in ALL_CANDIDATES)."""
        report = StrategyEvidenceReport(signals=[])
        scorecard = score_strategy_candidates(report)
        self.assertEqual(scorecard.executable_recommended_mode, "http")


if __name__ == "__main__":
    unittest.main()
