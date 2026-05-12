"""Tests for conservative StrategyScoringPolicy."""
from __future__ import annotations

import unittest

from autonomous_crawler.agents.strategy import strategy_node
from autonomous_crawler.tools.strategy_evidence import build_strategy_evidence_report
from autonomous_crawler.tools.strategy_scoring import score_strategy_candidates


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


if __name__ == "__main__":
    unittest.main()
