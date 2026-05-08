from __future__ import annotations

import json
import unittest

from autonomous_crawler.agents.recon import recon_node
from autonomous_crawler.agents.strategy import strategy_node
from autonomous_crawler.agents.validator import validator_node
from autonomous_crawler.errors import ANTI_BOT_BLOCKED
from autonomous_crawler.tools.access_diagnostics import diagnose_access
from autonomous_crawler.tools.html_recon import (
    MOCK_CHALLENGE_HTML,
    MOCK_JS_SHELL_HTML,
    MOCK_STRUCTURED_HTML,
)
from autonomous_crawler.tools.recon_tools import diagnose_access as diagnose_access_tool


class AccessDiagnosticsTests(unittest.TestCase):
    def test_js_shell_is_detected(self) -> None:
        result = diagnose_access(MOCK_JS_SHELL_HTML, url="https://app.example")

        self.assertIn("js_rendering_likely_required", result["findings"])
        self.assertEqual(
            result["recommendations"][0]["action"]["mode"],
            "browser",
        )
        self.assertIn("/api/products", result["signals"]["api_hints"])

    def test_challenge_is_detected_without_bypass(self) -> None:
        result = diagnose_access(MOCK_CHALLENGE_HTML, url="https://blocked.example")

        self.assertFalse(result["ok"])
        self.assertEqual(result["signals"]["challenge"], "cf-challenge")
        self.assertIn("challenge_detected:cf-challenge", result["findings"])
        self.assertEqual(result["recommendations"][0]["type"], "manual_review")

    def test_structured_data_is_detected(self) -> None:
        result = diagnose_access(MOCK_STRUCTURED_HTML, url="https://shop.example")

        structured = result["signals"]["structured_data"]
        self.assertEqual(structured["json_ld_count"], 1)
        self.assertTrue(structured["next_data"])
        self.assertIn("Product", structured["sample_types"])
        self.assertIn("embedded_structured_data_available", result["findings"])

    def test_recon_report_contains_access_diagnostics(self) -> None:
        state = recon_node({
            "target_url": "mock://js-shell",
            "recon_report": {},
            "messages": [],
            "error_log": [],
        })

        diagnostics = state["recon_report"]["access_diagnostics"]
        self.assertIn("js_rendering_likely_required", diagnostics["findings"])
        self.assertEqual(state["recon_report"]["rendering"], "spa")

    def test_strategy_routes_js_shell_to_browser_before_api_intercept(self) -> None:
        state = strategy_node({
            "user_goal": "collect products",
            "target_url": "mock://js-shell",
            "recon_report": {
                "target_url": "mock://js-shell",
                "task_type": "product_list",
                "constraints": {},
                "rendering": "spa",
                "anti_bot": {"detected": False},
                "api_endpoints": ["/api/products"],
                "access_diagnostics": diagnose_access(MOCK_JS_SHELL_HTML),
                "dom_structure": {
                    "pagination_type": "none",
                    "product_selector": "",
                    "field_selectors": {},
                },
            },
            "retries": 0,
            "messages": [],
        })

        strategy = state["crawl_strategy"]
        self.assertEqual(strategy["mode"], "browser")
        self.assertEqual(strategy["extraction_method"], "browser_render")
        self.assertNotEqual(strategy["mode"], "api_intercept")

    def test_strategy_marks_challenge_warning(self) -> None:
        state = strategy_node({
            "user_goal": "collect products",
            "target_url": "mock://challenge",
            "recon_report": {
                "target_url": "mock://challenge",
                "task_type": "product_list",
                "constraints": {},
                "rendering": "static",
                "anti_bot": {"detected": True, "type": "cf-challenge"},
                "api_endpoints": [],
                "access_diagnostics": diagnose_access(MOCK_CHALLENGE_HTML),
                "dom_structure": {
                    "pagination_type": "none",
                    "product_selector": "",
                    "field_selectors": {},
                },
            },
            "retries": 0,
            "messages": [],
        })

        strategy = state["crawl_strategy"]
        self.assertEqual(strategy["mode"], "browser")
        self.assertEqual(strategy["access_warning"], "challenge_detected")

    def test_validator_maps_challenge_empty_result_to_anti_bot_code(self) -> None:
        state = validator_node({
            "extracted_data": {"items": [], "confidence": 0.0},
            "recon_report": {
                "target_fields": ["title"],
                "access_diagnostics": diagnose_access(MOCK_CHALLENGE_HTML),
            },
            "retries": 0,
            "max_retries": 0,
            "messages": [],
        })

        self.assertEqual(state["status"], "failed")
        self.assertEqual(state["error_code"], ANTI_BOT_BLOCKED)

    def test_langchain_tool_wrapper_exposes_diagnostics(self) -> None:
        payload = json.loads(diagnose_access_tool.invoke({"url": "mock://structured"}))

        self.assertTrue(payload["signals"]["structured_data"]["next_data"])
        self.assertIn("embedded_structured_data_available", payload["findings"])


if __name__ == "__main__":
    unittest.main()
