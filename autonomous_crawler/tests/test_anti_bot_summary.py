"""Tests for compact AntiBotReport summaries."""
from __future__ import annotations

import unittest

from autonomous_crawler.api.app import create_app
from autonomous_crawler.tools.anti_bot_report import (
    AntiBotFinding,
    AntiBotReport,
    summarize_anti_bot_report,
)


class AntiBotSummaryTests(unittest.TestCase):
    def test_summary_from_report_object(self) -> None:
        report = AntiBotReport(
            detected=True,
            risk_level="high",
            risk_score=88,
            recommended_action="manual_handoff",
            categories=["challenge", "proxy", "fingerprint"],
            findings=[
                AntiBotFinding(
                    code="access_managed_challenge",
                    category="challenge",
                    severity="high",
                    source="access_diagnostics",
                    summary="Managed challenge detected.",
                ),
                AntiBotFinding(
                    code="proxy_health_risk",
                    category="proxy",
                    severity="medium",
                    source="proxy_trace",
                    summary="Proxy cooldown evidence present.",
                ),
            ],
        )

        summary = summarize_anti_bot_report(report)
        self.assertTrue(summary["detected"])
        self.assertEqual(summary["risk_level"], "high")
        self.assertEqual(summary["recommended_action"], "manual_handoff")
        self.assertEqual(summary["top_findings"][0]["code"], "access_managed_challenge")

    def test_summary_from_dict_is_bounded(self) -> None:
        summary = summarize_anti_bot_report({
            "detected": True,
            "risk_level": "medium",
            "risk_score": 44,
            "recommended_action": "browser_render_or_profile_review",
            "categories": ["transport", "fingerprint", "websocket", "proxy", "js"],
            "findings": [
                {"code": "transport_sensitive_access", "category": "transport", "severity": "medium", "summary": "Transport differs."},
                {"code": "browser_fingerprint_risk", "category": "fingerprint", "severity": "medium", "summary": "Fingerprint risk."},
                {"code": "websocket_runtime_dependency", "category": "runtime_protocol", "severity": "medium", "summary": "WS traffic present."},
                {"code": "extra", "category": "extra", "severity": "low", "summary": "ignored"},
            ],
        })

        self.assertEqual(len(summary["categories"]), 5)
        self.assertEqual(len(summary["top_findings"]), 3)
        self.assertEqual(summary["top_findings"][2]["code"], "websocket_runtime_dependency")

    def test_empty_summary_is_safe(self) -> None:
        summary = summarize_anti_bot_report(None)
        self.assertFalse(summary["detected"])
        self.assertEqual(summary["risk_level"], "low")
        self.assertEqual(summary["recommended_action"], "standard_http")

    def test_api_response_includes_summary_field(self) -> None:
        app = create_app()
        openapi = app.openapi()
        self.assertIn("anti_bot_summary", openapi["components"]["schemas"]["CrawlResponse"]["properties"])


if __name__ == "__main__":
    unittest.main()
