from __future__ import annotations

import json
import unittest

from autonomous_crawler.tools.recon_tools import (
    analyze_dom_structure,
    diagnose_access,
    detect_anti_bot,
    detect_framework,
    discover_api_endpoints,
)


class ReconToolsTests(unittest.TestCase):
    def test_detect_framework_tool_uses_real_fetch_helper(self) -> None:
        payload = json.loads(detect_framework.invoke({"url": "mock://catalog"}))

        self.assertEqual(payload["framework"], "unknown")
        self.assertEqual(payload["status_code"], 200)

    def test_analyze_dom_structure_tool_returns_inferred_selectors(self) -> None:
        payload = json.loads(analyze_dom_structure.invoke({"url": "mock://ranking"}))

        self.assertEqual(payload["product_selector"], ".category-wrap_iQLoo")
        self.assertEqual(payload["field_selectors"]["title"], ".title_dIF3B .c-single-text-ellipsis")
        self.assertEqual(payload["field_selectors"]["link"], ".title_dIF3B@href")

    def test_discover_api_endpoints_tool_reports_empty_mock_list(self) -> None:
        payload = json.loads(discover_api_endpoints.invoke({"url": "mock://catalog"}))

        self.assertEqual(payload["endpoints"], [])
        self.assertEqual(payload["total"], 0)

    def test_detect_anti_bot_tool_reports_mock_page_as_clean(self) -> None:
        payload = json.loads(detect_anti_bot.invoke({"url": "mock://catalog"}))

        self.assertFalse(payload["detected"])
        self.assertEqual(payload["type"], "none")

    def test_diagnose_access_tool_reports_js_shell(self) -> None:
        payload = json.loads(diagnose_access.invoke({"url": "mock://js-shell"}))

        self.assertIn("js_rendering_likely_required", payload["findings"])
        self.assertIn("/api/products", payload["signals"]["api_hints"])


if __name__ == "__main__":
    unittest.main()
