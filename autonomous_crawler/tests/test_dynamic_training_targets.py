"""Focused tests for dynamic/ecommerce training target fixtures.

Validates that scenario definitions carry the required evidence fields
and that ``build_state()`` maps them correctly into executor workflow state.

No public network access is required — all tests operate on data structures.
"""
from __future__ import annotations

import unittest

from autonomous_crawler.tests.dynamic_training_targets import (
    CATEGORIES,
    SCENARIO_BY_ID,
    SCENARIO_TYPES,
    build_state,
    get_scenario,
    get_scenarios_by_category,
)


# ---------------------------------------------------------------------------
# Coverage & catalogue
# ---------------------------------------------------------------------------


class ScenarioCatalogueTests(unittest.TestCase):
    """Verify the scenario catalogue covers the required categories."""

    def test_scenario_count_at_least_eight(self) -> None:
        self.assertGreaterEqual(len(SCENARIO_TYPES), 8)

    def test_all_required_categories_present(self) -> None:
        present = {s["category"] for s in SCENARIO_TYPES}
        required = {
            "js_rendered_list",
            "xhr_api_data",
            "lazy_load_scroll",
            "cookie_session",
            "challenge_block",
            "static_fallback",
        }
        self.assertTrue(required.issubset(present), f"Missing: {required - present}")

    def test_scenario_ids_unique(self) -> None:
        ids = [s["id"] for s in SCENARIO_TYPES]
        self.assertEqual(len(ids), len(set(ids)))

    def test_scenario_by_id_lookup(self) -> None:
        for scenario in SCENARIO_TYPES:
            self.assertIs(SCENARIO_BY_ID[scenario["id"]], scenario)

    def test_get_scenario_raises_on_missing(self) -> None:
        with self.assertRaises(KeyError):
            get_scenario("nonexistent_id")

    def test_get_scenarios_by_category(self) -> None:
        js_scenarios = get_scenarios_by_category("js_rendered_list")
        self.assertGreaterEqual(len(js_scenarios), 1)
        for s in js_scenarios:
            self.assertEqual(s["category"], "js_rendered_list")

    def test_categories_list_matches_scenarios(self) -> None:
        scenario_cats = {s["category"] for s in SCENARIO_TYPES}
        self.assertEqual(set(CATEGORIES), scenario_cats)


# ---------------------------------------------------------------------------
# Evidence field presence
# ---------------------------------------------------------------------------


class ScenarioEvidenceFieldTests(unittest.TestCase):
    """Prove every scenario carries the fields needed for comparison evidence."""

    def test_all_scenarios_have_id(self) -> None:
        for s in SCENARIO_TYPES:
            self.assertIn("id", s, f"Scenario missing 'id': {s.get('name')}")

    def test_all_scenarios_have_url(self) -> None:
        for s in SCENARIO_TYPES:
            self.assertIn("url", s, f"Scenario '{s['id']}' missing 'url'")

    def test_all_scenarios_have_mode(self) -> None:
        for s in SCENARIO_TYPES:
            self.assertIn("mode", s, f"Scenario '{s['id']}' missing 'mode'")

    def test_all_scenarios_have_selectors(self) -> None:
        for s in SCENARIO_TYPES:
            self.assertIn("selectors", s, f"Scenario '{s['id']}' missing 'selectors'")
            self.assertIsInstance(s["selectors"], dict)
            self.assertGreater(len(s["selectors"]), 0)

    def test_all_scenarios_have_wait_selector(self) -> None:
        for s in SCENARIO_TYPES:
            self.assertIn("wait_selector", s)

    def test_all_scenarios_have_wait_until(self) -> None:
        for s in SCENARIO_TYPES:
            self.assertIn("wait_until", s)

    def test_all_scenarios_have_capture_xhr(self) -> None:
        for s in SCENARIO_TYPES:
            self.assertIn("capture_xhr", s)

    def test_all_scenarios_have_target_fields(self) -> None:
        for s in SCENARIO_TYPES:
            self.assertIn("target_fields", s)
            self.assertIsInstance(s["target_fields"], list)
            self.assertGreater(len(s["target_fields"]), 0)

    def test_all_scenarios_have_risk(self) -> None:
        for s in SCENARIO_TYPES:
            self.assertIn("risk", s)
            self.assertIn(s["risk"], {"low", "medium", "high"})

    def test_all_scenarios_have_timeout_ms(self) -> None:
        for s in SCENARIO_TYPES:
            self.assertIn("timeout_ms", s)
            self.assertGreater(s["timeout_ms"], 0)


# ---------------------------------------------------------------------------
# Browser-mode scenarios carry browser-specific evidence
# ---------------------------------------------------------------------------


class BrowserScenarioEvidenceTests(unittest.TestCase):
    """Browser-mode scenarios must carry wait_selector and wait_until."""

    def _browser_scenarios(self) -> list[dict]:
        return [s for s in SCENARIO_TYPES if s["mode"] == "browser"]

    def test_browser_scenarios_exist(self) -> None:
        self.assertGreater(len(self._browser_scenarios()), 0)

    def test_browser_scenarios_have_nonempty_wait_selector(self) -> None:
        for s in self._browser_scenarios():
            self.assertTrue(
                s["wait_selector"],
                f"Browser scenario '{s['id']}' must have non-empty wait_selector",
            )

    def test_browser_scenarios_have_nonempty_wait_until(self) -> None:
        for s in self._browser_scenarios():
            self.assertTrue(
                s["wait_until"],
                f"Browser scenario '{s['id']}' must have non-empty wait_until",
            )

    def test_browser_scenarios_have_browser_config(self) -> None:
        for s in self._browser_scenarios():
            self.assertIn("browser_config", s)
            self.assertIsInstance(s["browser_config"], dict)


# ---------------------------------------------------------------------------
# XHR capture scenarios
# ---------------------------------------------------------------------------


class XhrCaptureScenarioTests(unittest.TestCase):
    """Scenarios with capture_xhr must be browser-mode with a regex pattern."""

    def test_xhr_scenarios_are_browser_mode(self) -> None:
        for s in SCENARIO_TYPES:
            if s.get("capture_xhr"):
                self.assertEqual(
                    s["mode"],
                    "browser",
                    f"Scenario '{s['id']}' has capture_xhr but mode != browser",
                )

    def test_xhr_scenario_has_valid_regex(self) -> None:
        import re

        for s in SCENARIO_TYPES:
            pattern = s.get("capture_xhr", "")
            if pattern:
                re.compile(pattern)  # must not raise


# ---------------------------------------------------------------------------
# Challenge/block evidence scenarios
# ---------------------------------------------------------------------------


class ChallengeBlockEvidenceTests(unittest.TestCase):
    """Challenge/block scenarios must have expected_evidence with failure fields."""

    def _challenge_scenarios(self) -> list[dict]:
        return [s for s in SCENARIO_TYPES if s["category"] == "challenge_block"]

    def test_challenge_scenarios_exist(self) -> None:
        self.assertGreater(len(self._challenge_scenarios()), 0)

    def test_challenge_scenarios_have_expected_evidence(self) -> None:
        for s in self._challenge_scenarios():
            self.assertIn("expected_evidence", s, f"Scenario '{s['id']}'")
            ev = s["expected_evidence"]
            self.assertIn("failure_classification", ev)
            self.assertIn("blocked_status_codes", ev)
            self.assertIsInstance(ev["blocked_status_codes"], list)

    def test_challenge_scenarios_high_risk(self) -> None:
        for s in self._challenge_scenarios():
            self.assertEqual(s["risk"], "high")


# ---------------------------------------------------------------------------
# Session/cookie scenarios
# ---------------------------------------------------------------------------


class SessionScenarioTests(unittest.TestCase):
    """Session scenarios must carry browser_config with session fields."""

    def _session_scenarios(self) -> list[dict]:
        return [s for s in SCENARIO_TYPES if s["category"] == "cookie_session"]

    def test_session_scenarios_exist(self) -> None:
        self.assertGreater(len(self._session_scenarios()), 0)

    def test_session_scenarios_have_session_keys_in_browser_config(self) -> None:
        for s in self._session_scenarios():
            bc = s["browser_config"]
            self.assertIn("user_data_dir", bc, f"Scenario '{s['id']}'")
            self.assertIn("storage_state", bc, f"Scenario '{s['id']}'")


# ---------------------------------------------------------------------------
# Scroll/lazy-load scenarios
# ---------------------------------------------------------------------------


class ScrollScenarioTests(unittest.TestCase):
    """Scroll scenarios must carry scroll_count and scroll_delay in browser_config."""

    def _scroll_scenarios(self) -> list[dict]:
        return [s for s in SCENARIO_TYPES if s["category"] == "lazy_load_scroll"]

    def test_scroll_scenarios_exist(self) -> None:
        self.assertGreater(len(self._scroll_scenarios()), 0)

    def test_scroll_scenarios_have_scroll_config(self) -> None:
        for s in self._scroll_scenarios():
            bc = s["browser_config"]
            self.assertIn("scroll_count", bc, f"Scenario '{s['id']}'")
            self.assertGreater(bc["scroll_count"], 0)
            self.assertIn("scroll_delay", bc, f"Scenario '{s['id']}'")
            self.assertGreater(bc["scroll_delay"], 0)


# ---------------------------------------------------------------------------
# Protected/init_script scenarios
# ---------------------------------------------------------------------------


class ProtectedInitScriptTests(unittest.TestCase):
    """Protected/init_script scenarios must carry init_script in browser_config."""

    def _protected_scenarios(self) -> list[dict]:
        return [s for s in SCENARIO_TYPES if s["category"] == "protected_init"]

    def test_protected_scenarios_exist(self) -> None:
        self.assertGreater(len(self._protected_scenarios()), 0)

    def test_protected_scenarios_have_init_script(self) -> None:
        for s in self._protected_scenarios():
            bc = s["browser_config"]
            self.assertIn("init_script", bc, f"Scenario '{s['id']}'")
            self.assertTrue(bc["init_script"])

    def test_protected_scenarios_high_risk(self) -> None:
        for s in self._protected_scenarios():
            self.assertEqual(s["risk"], "high")


# ---------------------------------------------------------------------------
# build_state() mapping
# ---------------------------------------------------------------------------


class BuildStateTests(unittest.TestCase):
    """Verify build_state() maps scenario fields into executor workflow state."""

    def test_build_state_sets_engine(self) -> None:
        scenario = get_scenario("js_rendered_product_list")
        state = build_state(scenario, "native")
        self.assertEqual(state["crawl_strategy"]["engine"], "native")

    def test_build_state_sets_mode(self) -> None:
        scenario = get_scenario("js_rendered_product_list")
        state = build_state(scenario, "native")
        self.assertEqual(state["crawl_strategy"]["mode"], "browser")

    def test_build_state_sets_selectors(self) -> None:
        scenario = get_scenario("js_rendered_product_list")
        state = build_state(scenario, "native")
        self.assertIn("product_card", state["crawl_strategy"]["selectors"])
        self.assertIn("title", state["crawl_strategy"]["selectors"])

    def test_build_state_sets_wait_selector(self) -> None:
        scenario = get_scenario("js_rendered_product_list")
        state = build_state(scenario, "native")
        self.assertEqual(state["crawl_strategy"]["wait_selector"], ".product-card")

    def test_build_state_sets_wait_until(self) -> None:
        scenario = get_scenario("js_rendered_product_list")
        state = build_state(scenario, "native")
        self.assertEqual(state["crawl_strategy"]["wait_until"], "networkidle")

    def test_build_state_sets_capture_xhr(self) -> None:
        scenario = get_scenario("xhr_api_product_data")
        state = build_state(scenario, "native")
        self.assertEqual(
            state["crawl_strategy"]["capture_xhr"], "/api/v[0-9]+/products"
        )

    def test_build_state_sets_timeout_ms(self) -> None:
        scenario = get_scenario("lazy_load_infinite_scroll")
        state = build_state(scenario, "native")
        self.assertEqual(state["crawl_strategy"]["timeout_ms"], 60000)

    def test_build_state_sets_browser_config(self) -> None:
        scenario = get_scenario("lazy_load_infinite_scroll")
        state = build_state(scenario, "native")
        bc = state["crawl_strategy"]["browser_config"]
        self.assertEqual(bc["scroll_count"], 5)
        self.assertEqual(bc["scroll_delay"], 1.5)

    def test_build_state_sets_target_fields(self) -> None:
        scenario = get_scenario("xhr_api_product_data")
        state = build_state(scenario, "native")
        self.assertIn("title", state["recon_report"]["target_fields"])
        self.assertIn("api_response", state["recon_report"]["target_fields"])

    def test_build_state_sets_task_type(self) -> None:
        scenario = get_scenario("challenge_block_evidence")
        state = build_state(scenario, "native")
        self.assertEqual(state["recon_report"]["task_type"], "challenge_block")

    def test_build_state_static_fallback_has_empty_browser_fields(self) -> None:
        scenario = get_scenario("static_fallback_page")
        state = build_state(scenario, "native")
        self.assertEqual(state["crawl_strategy"]["mode"], "http")
        self.assertEqual(state["crawl_strategy"]["wait_selector"], "")
        self.assertEqual(state["crawl_strategy"]["capture_xhr"], "")

    def test_build_state_preserves_init_script(self) -> None:
        scenario = get_scenario("protected_dynamic_init_script")
        state = build_state(scenario, "native")
        bc = state["crawl_strategy"]["browser_config"]
        self.assertIn("init_script", bc)
        self.assertIn("navigator", bc["init_script"])

    def test_build_state_all_scenarios(self) -> None:
        """Smoke: build_state succeeds for every scenario with both engines."""
        for scenario in SCENARIO_TYPES:
            for engine in ("native", "scrapling"):
                state = build_state(scenario, engine)
                self.assertEqual(state["crawl_strategy"]["engine"], engine)
                self.assertEqual(state["target_url"], scenario["url"])


# ---------------------------------------------------------------------------
# Scenario ↔ build_state round-trip (no executor import)
# ---------------------------------------------------------------------------


class ScenarioRoundTripTests(unittest.TestCase):
    """Ensure scenario → build_state → crawl_strategy preserves all evidence."""

    def _evidence_keys(self) -> set[str]:
        return {
            "engine",
            "mode",
            "selectors",
            "wait_selector",
            "wait_until",
            "timeout_ms",
            "capture_xhr",
            "browser_config",
        }

    def test_all_browser_scenarios_round_trip(self) -> None:
        for scenario in SCENARIO_TYPES:
            state = build_state(scenario, "native")
            cs = state["crawl_strategy"]
            for key in self._evidence_keys():
                self.assertIn(key, cs, f"Missing '{key}' in {scenario['id']}")

    def test_selectors_not_empty_after_round_trip(self) -> None:
        for scenario in SCENARIO_TYPES:
            state = build_state(scenario, "native")
            self.assertGreater(
                len(state["crawl_strategy"]["selectors"]),
                0,
                f"Empty selectors for {scenario['id']}",
            )


if __name__ == "__main__":
    unittest.main()
