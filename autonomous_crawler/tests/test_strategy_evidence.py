"""Tests for unified strategy evidence reporting."""
from __future__ import annotations

import unittest

from autonomous_crawler.agents.strategy import strategy_node
from autonomous_crawler.tools.strategy_evidence import (
    build_reverse_engineering_hints,
    build_strategy_evidence_report,
    has_high_crypto_replay_risk,
)


def _base_state(**recon_overrides: object) -> dict:
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


def _crypto_js_evidence() -> dict:
    return {
        "top_endpoints": ["/api/products"],
        "top_crypto_signals": ["hash:sha256", "timestamp:timestamp"],
        "items": [{
            "source": "captured",
            "url": "https://shop.example/app.js",
            "total_score": 92,
            "reasons": ["crypto:hash", "crypto:timestamp"],
            "keyword_categories": ["token"],
            "crypto_analysis": {
                "signals": [
                    {"kind": "hash", "name": "sha256", "confidence": "high"},
                    {"kind": "timestamp", "name": "timestamp", "confidence": "medium"},
                    {"kind": "sorting", "name": "param_sort", "confidence": "medium"},
                ],
                "categories": ["hash", "query_build", "sorting", "timestamp"],
                "likely_signature_flow": True,
                "likely_encryption_flow": False,
                "likely_timestamp_nonce_flow": True,
                "score": 84,
                "recommendations": ["Trace request parameter canonicalization before replaying API calls"],
            },
        }],
    }


class StrategyEvidenceReportTests(unittest.TestCase):
    def test_dom_evidence_signal_is_reported(self) -> None:
        report = build_strategy_evidence_report({
            "dom_structure": {
                "item_count": 6,
                "product_selector": ".product",
                "field_selectors": {"title": ".title", "price": ".price"},
            },
        })
        payload = report.to_dict()

        self.assertEqual(payload["signals"][0]["code"], "dom_repeated_items")
        self.assertIn("dom", payload["dominant_sources"])
        self.assertEqual(payload["signals"][0]["details"]["item_count"], 6)

    def test_observed_api_candidate_signal_is_reported(self) -> None:
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
        signals = report.to_dict()["signals"]

        self.assertEqual(signals[0]["code"], "observed_api_candidate")
        self.assertEqual(signals[0]["source"], "api")
        self.assertEqual(signals[0]["confidence"], "high")

    def test_crypto_evidence_builds_reverse_engineering_hints(self) -> None:
        hints = build_reverse_engineering_hints(_crypto_js_evidence())

        self.assertEqual(hints["api_replay_blocker"], "signature_flow_requires_runtime_inputs")
        self.assertIn("hook_plan", hints)
        self.assertIn("canonical_param_order", hints["signature_inputs"])
        self.assertIn("timestamp", hints["dynamic_inputs"])

    def test_api_intercept_strategy_gets_replay_warning_for_signature_flow(self) -> None:
        state = strategy_node(_base_state(
            api_candidates=[{
                "url": "https://shop.example/api/products",
                "method": "GET",
                "kind": "json",
                "score": 82,
                "reason": "browser_network_observation",
                "status_code": 200,
            }],
            js_evidence=_crypto_js_evidence(),
        ))
        strategy = state["crawl_strategy"]

        self.assertEqual(strategy["mode"], "api_intercept")
        self.assertEqual(strategy["api_replay_warning"], "signature_or_encryption_evidence")
        self.assertIn("reverse_engineering_hints", strategy)
        self.assertIn("strategy_evidence", strategy)
        self.assertTrue(has_high_crypto_replay_risk(
            build_strategy_evidence_report(state["recon_report"])
        ))

    def test_good_dom_still_wins_with_crypto_evidence(self) -> None:
        state = strategy_node(_base_state(
            dom_structure={
                "item_count": 5,
                "product_selector": ".card",
                "field_selectors": {"title": ".title", "price": ".price"},
            },
            js_evidence=_crypto_js_evidence(),
        ))
        strategy = state["crawl_strategy"]

        self.assertEqual(strategy["mode"], "http")
        self.assertEqual(strategy["extraction_method"], "dom_parse")
        self.assertIn("reverse_engineering_hints", strategy)
        self.assertNotIn("api_replay_warning", strategy)

    def test_challenge_and_transport_signals_are_reported(self) -> None:
        report = build_strategy_evidence_report({
            "anti_bot": {"detected": True, "matches": ["cf-challenge"]},
            "access_diagnostics": {
                "signals": {"challenge": "cf-challenge"},
                "findings": ["challenge_detected:cf-challenge"],
            },
            "transport_diagnostics": {
                "transport_sensitive": True,
                "selected_mode": "curl_cffi",
                "findings": ["status_differs_by_transport"],
                "recommendations": ["Prefer selected transport mode: curl_cffi"],
            },
        })
        codes = {signal["code"] for signal in report.to_dict()["signals"]}

        self.assertIn("challenge_detected", codes)
        self.assertIn("transport_sensitive", codes)
        self.assertIn("challenge_detected", report.warnings)

    def test_fingerprint_and_websocket_signals_are_reported(self) -> None:
        report = build_strategy_evidence_report({
            "browser_fingerprint_probe": {
                "status": "ok",
                "risk_level": "high",
                "findings": [{"code": "webdriver_exposed"}],
                "recommendations": ["Hide webdriver"],
            },
            "websocket_summary": {
                "connection_count": 2,
                "total_frames": 9,
                "message_kinds": ["json"],
            },
        })
        codes = {signal["code"] for signal in report.to_dict()["signals"]}

        self.assertIn("fingerprint_runtime_risk", codes)
        self.assertIn("websocket_activity", codes)

    def test_malformed_recon_does_not_crash(self) -> None:
        report = build_strategy_evidence_report({
            "dom_structure": "bad",
            "api_candidates": ["bad"],
            "js_evidence": "bad",
            "access_diagnostics": [],
        })

        self.assertEqual(report.to_dict()["signals"], [])


if __name__ == "__main__":
    unittest.main()
