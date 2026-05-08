from __future__ import annotations

import unittest

from autonomous_crawler.agents.recon import recon_node
from autonomous_crawler.tools.site_zoo import SITE_ZOO, fixture_by_url, get_fixture


class SiteZooTests(unittest.TestCase):
    def test_fixture_inventory_has_p1_categories(self) -> None:
        categories = {fixture.category for fixture in SITE_ZOO.values()}

        self.assertIn("static", categories)
        self.assertIn("detail", categories)
        self.assertIn("variant", categories)
        self.assertIn("spa", categories)
        self.assertIn("structured", categories)
        self.assertIn("api", categories)
        self.assertIn("challenge", categories)

    def test_fixture_by_url_returns_fixture(self) -> None:
        fixture = get_fixture("static_list")

        self.assertIs(fixture_by_url(fixture.url), fixture)

    def test_static_list_fixture_runs_through_recon(self) -> None:
        fixture = get_fixture("static_list")
        state = recon_node({
            "target_url": fixture.url,
            "recon_report": {},
            "messages": [],
            "error_log": [],
        })

        dom = state["recon_report"]["dom_structure"]
        self.assertEqual(dom["product_selector"], ".catalog-card")
        self.assertEqual(dom["item_count"], 2)

    def test_challenge_fixture_runs_through_access_diagnostics(self) -> None:
        fixture = get_fixture("challenge")
        state = recon_node({
            "target_url": fixture.url,
            "recon_report": {},
            "messages": [],
            "error_log": [],
        })

        diagnostics = state["recon_report"]["access_diagnostics"]
        self.assertFalse(diagnostics["ok"])
        self.assertEqual(diagnostics["signals"]["challenge"], "cf-challenge")


if __name__ == "__main__":
    unittest.main()
