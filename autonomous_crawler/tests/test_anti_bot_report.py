"""Tests for unified AntiBotReport (CAP-6.2)."""
from __future__ import annotations

import unittest

from autonomous_crawler.agents.strategy import strategy_node
from autonomous_crawler.tools.anti_bot_report import build_anti_bot_report
from autonomous_crawler.tools.access_diagnostics import diagnose_access
from autonomous_crawler.tools.html_recon import MOCK_CHALLENGE_HTML
from autonomous_crawler.tools.strategy_evidence import build_strategy_evidence_report


def _signature_js_evidence() -> dict:
    return {
        "top_crypto_signals": ["hash:sha256", "timestamp:timestamp"],
        "items": [{
            "source": "captured",
            "url": "https://shop.example/app.js",
            "total_score": 94,
            "keyword_categories": ["token", "fingerprint"],
            "crypto_analysis": {
                "signals": [
                    {"kind": "hash", "name": "sha256", "confidence": "high"},
                    {"kind": "timestamp", "name": "timestamp", "confidence": "medium"},
                ],
                "categories": ["hash", "query_build", "timestamp"],
                "likely_signature_flow": True,
                "likely_encryption_flow": False,
                "likely_timestamp_nonce_flow": True,
                "score": 86,
            },
        }],
    }


class AntiBotReportTests(unittest.TestCase):
    def test_challenge_report_recommends_manual_handoff(self) -> None:
        report = build_anti_bot_report({
            "access_diagnostics": diagnose_access(MOCK_CHALLENGE_HTML, status_code=403),
            "anti_bot": {"detected": True, "type": "cf-challenge"},
            "fetch": {"status_code": 403, "selected_mode": "requests"},
        }).to_dict()

        self.assertTrue(report["detected"])
        self.assertEqual(report["risk_level"], "high")
        self.assertEqual(report["recommended_action"], "manual_handoff")
        self.assertIn("challenge", report["categories"])
        self.assertIn("challenge_requires_authorized_or_manual_review", report["guardrails"])

    def test_signature_and_fingerprint_evidence_recommends_deeper_recon(self) -> None:
        recon = {"js_evidence": _signature_js_evidence()}
        evidence = build_strategy_evidence_report(recon)
        report = build_anti_bot_report(recon, strategy_evidence=evidence).to_dict()

        self.assertTrue(report["detected"])
        self.assertEqual(report["recommended_action"], "deeper_recon")
        self.assertIn("crypto_signature", report["categories"])
        self.assertIn("js_challenge", report["categories"])
        self.assertIn("do_not_replay_signed_api_without_runtime_inputs", report["guardrails"])

    def test_transport_fingerprint_websocket_and_api_blocks_are_unified(self) -> None:
        report = build_anti_bot_report({
            "api_candidates": [{
                "url": "https://shop.example/api/products",
                "method": "GET",
                "kind": "json",
                "status_code": 403,
            }],
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
            "websocket_summary": {
                "connection_count": 1,
                "total_frames": 3,
                "message_kinds": ["json"],
            },
        }).to_dict()

        self.assertTrue(report["detected"])
        self.assertIn("api_block", report["categories"])
        self.assertIn("transport", report["categories"])
        self.assertIn("fingerprint", report["categories"])
        self.assertIn("runtime_protocol", report["categories"])
        self.assertEqual(report["recommended_action"], "browser_render_or_profile_review")

    def test_proxy_trace_is_redacted(self) -> None:
        report = build_anti_bot_report({
            "fetch_trace": {
                "attempts": [{
                    "proxy_trace": {
                        "selected": True,
                        "proxy": "http://user:secret@proxy.example:8080",
                        "source": "pool_round_robin",
                        "provider": "static",
                        "strategy": "round_robin",
                        "health": {
                            "failure_count": 2,
                            "in_cooldown": True,
                            "last_error": "failed http://user:secret@proxy.example:8080 token=abc",
                        },
                    },
                }],
            },
        }).to_dict()
        payload = str(report)

        self.assertIn("proxy", report["categories"])
        self.assertNotIn("secret", payload)
        self.assertNotIn("token=abc", payload)
        self.assertIn("***", payload)

    def test_strategy_node_attaches_report_without_overriding_mode(self) -> None:
        state = strategy_node({
            "user_goal": "collect products",
            "target_url": "https://shop.example/catalog",
            "recon_report": {
                "target_url": "https://shop.example/catalog",
                "task_type": "product_list",
                "rendering": "static",
                "anti_bot": {"detected": False},
                "constraints": {},
                "api_candidates": [{
                    "url": "https://shop.example/api/products",
                    "method": "GET",
                    "kind": "json",
                    "score": 82,
                    "reason": "browser_network_observation",
                    "status_code": 200,
                }],
                "js_evidence": _signature_js_evidence(),
                "dom_structure": {"item_count": 0, "field_selectors": {}},
            },
            "messages": [],
        })

        strategy = state["crawl_strategy"]
        self.assertEqual(strategy["mode"], "api_intercept")
        self.assertIn("anti_bot_report", strategy)
        self.assertEqual(strategy["anti_bot_report"]["recommended_action"], "deeper_recon")
        self.assertIn("crypto_signature", strategy["anti_bot_report"]["categories"])

    def test_empty_report_is_safe_low_risk(self) -> None:
        report = build_anti_bot_report({}).to_dict()

        self.assertFalse(report["detected"])
        self.assertEqual(report["risk_level"], "low")
        self.assertEqual(report["risk_score"], 0)
        self.assertEqual(report["recommended_action"], "standard_http")
        self.assertIn("diagnostic_only_no_bypass", report["guardrails"])


if __name__ == "__main__":
    unittest.main()
