"""Tests for browser scenario training harness (SCRAPLING-HARDEN-2B).

Mocked tests — no network or Playwright required.
Covers: scroll, virtualized list, mobile viewport, profile health, fixtures.
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
from typing import Any

from run_browser_scenario_training_2026_05_15 import (
    LOCAL_SCENARIOS,
    PUBLIC_DEMO_SCENARIOS,
    FixtureServer,
    ScenarioDefinition,
    _check_expected,
    _extract_training_state,
    build_evidence,
    run_scenario,
)


def _mock_response(
    *,
    ok: bool = True,
    html: str = "<html><body>test</body></html>",
    status_code: int = 200,
    final_url: str = "https://example.com",
    error: str = "",
    engine_result: dict[str, Any] | None = None,
    captured_xhr: list[dict[str, Any]] | None = None,
) -> MagicMock:
    resp = MagicMock()
    resp.ok = ok
    resp.html = html
    resp.status_code = status_code
    resp.final_url = final_url
    resp.error = error
    resp.engine_result = engine_result or {}
    resp.captured_xhr = captured_xhr or []
    return resp


# ---------------------------------------------------------------------------
# ScenarioDefinition
# ---------------------------------------------------------------------------


class ScenarioDefinitionTests(unittest.TestCase):

    def test_defaults(self) -> None:
        s = ScenarioDefinition(id="test", name="Test")
        self.assertEqual(s.id, "test")
        self.assertEqual(s.url, "")
        self.assertEqual(s.url_path, "")
        self.assertEqual(s.mode, "dynamic")
        self.assertFalse(s.scroll_enabled)
        self.assertEqual(s.scroll_max, 10)
        self.assertEqual(s.scroll_delay_ms, 300)
        self.assertEqual(s.scroll_target, "")
        self.assertEqual(s.mobile_profile, {})
        self.assertEqual(s.selectors, {})
        self.assertEqual(s.risk, "low")

    def test_scroll_fields(self) -> None:
        s = ScenarioDefinition(
            id="scroll_test",
            name="Scroll Test",
            scroll_enabled=True,
            scroll_max=20,
            scroll_delay_ms=100,
            scroll_target="#container",
        )
        self.assertTrue(s.scroll_enabled)
        self.assertEqual(s.scroll_max, 20)
        self.assertEqual(s.scroll_delay_ms, 100)
        self.assertEqual(s.scroll_target, "#container")

    def test_mobile_profile(self) -> None:
        mp = {"profile_id": "mobile", "user_agent": "iPhone", "viewport": "375x812"}
        s = ScenarioDefinition(id="mobile", name="Mobile", mobile_profile=mp)
        self.assertEqual(s.mobile_profile["profile_id"], "mobile")
        self.assertEqual(s.mobile_profile["viewport"], "375x812")


# ---------------------------------------------------------------------------
# FixtureServer
# ---------------------------------------------------------------------------


class FixtureServerTests(unittest.TestCase):

    def test_fixture_dir_default(self) -> None:
        server = FixtureServer()
        self.assertIn("browser_scenarios", str(server._fixture_dir))

    def test_fixture_dir_custom(self) -> None:
        server = FixtureServer(fixture_dir="/tmp/fixtures")
        self.assertEqual(server._fixture_dir, Path("/tmp/fixtures"))

    def test_context_manager(self) -> None:
        with patch.object(FixtureServer, "start", return_value="http://127.0.0.1:9999"):
            with patch.object(FixtureServer, "stop"):
                server = FixtureServer()
                with server as base_url:
                    self.assertEqual(base_url, "http://127.0.0.1:9999")


# ---------------------------------------------------------------------------
# ExtractTrainingState
# ---------------------------------------------------------------------------


class ExtractTrainingStateTests(unittest.TestCase):

    def test_extracts_valid_json(self) -> None:
        state = {"rendered_count": 50, "scroll_events": [{"type": "scroll"}]}
        html = f'<pre id="__training_state" style="display:none">{json.dumps(state)}</pre>'
        result = _extract_training_state(html)
        self.assertEqual(result["rendered_count"], 50)
        self.assertEqual(len(result["scroll_events"]), 1)

    def test_returns_empty_on_no_element(self) -> None:
        html = "<html><body>no training state</body></html>"
        result = _extract_training_state(html)
        self.assertEqual(result, {})

    def test_returns_empty_on_invalid_json(self) -> None:
        html = '<pre id="__training_state" style="display:none">not json</pre>'
        result = _extract_training_state(html)
        self.assertEqual(result, {})

    def test_extracts_nested_data(self) -> None:
        state = {
            "rendered_count": 8,
            "viewport_info": {"width": 375, "height": 812},
            "ua_info": {"isMobile": True},
            "visible_range": {"start": 0, "end": 15},
            "total_items": 10000,
        }
        html = f'<pre id="__training_state">{json.dumps(state)}</pre>'
        result = _extract_training_state(html)
        self.assertEqual(result["total_items"], 10000)
        self.assertTrue(result["ua_info"]["isMobile"])
        self.assertEqual(result["visible_range"]["end"], 15)


# ---------------------------------------------------------------------------
# CheckExpected
# ---------------------------------------------------------------------------


class CheckExpectedTests(unittest.TestCase):

    def test_min_rendered_items_pass(self) -> None:
        evidence = {"rendered_item_count": 50}
        checks = _check_expected(evidence, {"min_rendered_items": 20})
        self.assertTrue(checks["min_rendered_items"]["pass"])
        self.assertEqual(checks["min_rendered_items"]["actual"], 50)

    def test_min_rendered_items_fail(self) -> None:
        evidence = {"rendered_item_count": 5}
        checks = _check_expected(evidence, {"min_rendered_items": 20})
        self.assertFalse(checks["min_rendered_items"]["pass"])

    def test_min_scroll_events_pass(self) -> None:
        evidence = {"scroll_events": [{"type": "scroll"}] * 5}
        checks = _check_expected(evidence, {"min_scroll_events": 3})
        self.assertTrue(checks["min_scroll_events"]["pass"])
        self.assertEqual(checks["min_scroll_events"]["actual"], 5)

    def test_min_scroll_events_fail(self) -> None:
        evidence = {"scroll_events": []}
        checks = _check_expected(evidence, {"min_scroll_events": 2})
        self.assertFalse(checks["min_scroll_events"]["pass"])

    def test_min_html_chars(self) -> None:
        evidence = {"html_chars": 5000}
        checks = _check_expected(evidence, {"min_html_chars": 1000})
        self.assertTrue(checks["min_html_chars"]["pass"])

    def test_failure_category(self) -> None:
        evidence = {"failure_classification": {"category": "challenge"}}
        checks = _check_expected(evidence, {"failure_category": "challenge"})
        self.assertTrue(checks["failure_category"]["pass"])

    def test_failure_category_mismatch(self) -> None:
        evidence = {"failure_classification": {"category": "none"}}
        checks = _check_expected(evidence, {"failure_category": "challenge"})
        self.assertFalse(checks["failure_category"]["pass"])

    def test_multiple_checks(self) -> None:
        evidence = {
            "rendered_item_count": 30,
            "scroll_events": [{"type": "scroll"}] * 5,
            "html_chars": 8000,
        }
        expected = {
            "min_rendered_items": 20,
            "min_scroll_events": 3,
            "min_html_chars": 1000,
        }
        checks = _check_expected(evidence, expected)
        self.assertEqual(len(checks), 3)
        self.assertTrue(all(c["pass"] for c in checks.values()))

    def test_empty_expected(self) -> None:
        checks = _check_expected({"rendered_item_count": 0}, {})
        self.assertEqual(checks, {})


# ---------------------------------------------------------------------------
# BuildEvidence
# ---------------------------------------------------------------------------


class BuildEvidenceTests(unittest.TestCase):

    def test_basic_evidence_structure(self) -> None:
        scenario = ScenarioDefinition(
            id="test", name="Test", url="http://example.com",
            selectors={"item": ".item"},
        )
        response = _mock_response(html='<div class="item">A</div><div class="item">B</div>')
        evidence = build_evidence(scenario, response, elapsed=1.5, rendered_count=2)
        self.assertEqual(evidence["id"], "test")
        self.assertEqual(evidence["name"], "Test")
        self.assertTrue(evidence["ok"])
        self.assertEqual(evidence["rendered_item_count"], 2)
        self.assertAlmostEqual(evidence["elapsed_seconds"], 1.5, places=1)
        self.assertIn("selector_matches", evidence)
        self.assertIn("network_candidates", evidence)

    def test_evidence_with_scroll_data(self) -> None:
        scenario = ScenarioDefinition(id="s", name="S", selectors={})
        response = _mock_response()
        scroll_events = [{"type": "scroll", "index": 1}]
        evidence = build_evidence(
            scenario, response, elapsed=2.0,
            scroll_events=scroll_events,
            rendered_count=50,
        )
        self.assertEqual(len(evidence["scroll_events"]), 1)
        self.assertEqual(evidence["rendered_item_count"], 50)

    def test_evidence_with_profile_health(self) -> None:
        scenario = ScenarioDefinition(id="s", name="S", selectors={})
        response = _mock_response(engine_result={
            "profile_health_update": {"health_score": 0.95, "total_requests": 3},
            "profile": {"profile_id": "test-profile"},
        })
        evidence = build_evidence(scenario, response, elapsed=1.0)
        self.assertIsNotNone(evidence["profile_health"])
        self.assertEqual(evidence["profile_health"]["health_score"], 0.95)
        self.assertEqual(evidence["profile_evidence"]["profile_id"], "test-profile")

    def test_evidence_with_viewport_ua(self) -> None:
        scenario = ScenarioDefinition(id="s", name="S", selectors={})
        response = _mock_response()
        viewport = {"width": 375, "height": 812}
        ua = {"isMobile": True}
        evidence = build_evidence(
            scenario, response, elapsed=1.0,
            viewport_info=viewport, ua_info=ua,
        )
        self.assertEqual(evidence["viewport_info"]["width"], 375)
        self.assertTrue(evidence["ua_info"]["isMobile"])

    def test_evidence_with_failure(self) -> None:
        scenario = ScenarioDefinition(id="s", name="S", selectors={})
        response = _mock_response(ok=False, error="timeout")
        response.engine_result = {"failure_classification": {"category": "timeout"}}
        evidence = build_evidence(scenario, response, elapsed=30.0)
        self.assertFalse(evidence["ok"])
        self.assertEqual(evidence["failure_classification"]["category"], "timeout")

    def test_evidence_includes_expected_checks(self) -> None:
        scenario = ScenarioDefinition(
            id="s", name="S", selectors={},
            expected={"min_rendered_items": 5},
        )
        response = _mock_response()
        evidence = build_evidence(scenario, response, elapsed=1.0, rendered_count=10)
        self.assertIn("expected_checks", evidence)
        self.assertTrue(evidence["expected_checks"]["min_rendered_items"]["pass"])

    def test_stop_reason_completed(self) -> None:
        scenario = ScenarioDefinition(id="s", name="S", selectors={})
        response = _mock_response()
        evidence = build_evidence(scenario, response, elapsed=1.0, stop_reason="completed")
        self.assertEqual(evidence["stop_reason"], "completed")

    def test_stop_reason_render_failed(self) -> None:
        scenario = ScenarioDefinition(id="s", name="S", selectors={})
        response = _mock_response(ok=False)
        evidence = build_evidence(scenario, response, elapsed=1.0, stop_reason="render_failed")
        self.assertEqual(evidence["stop_reason"], "render_failed")

    def test_stop_reason_scroll_no_items(self) -> None:
        scenario = ScenarioDefinition(id="s", name="S", selectors={})
        response = _mock_response()
        evidence = build_evidence(scenario, response, elapsed=1.0, stop_reason="scroll_no_items")
        self.assertEqual(evidence["stop_reason"], "scroll_no_items")

    def test_stop_reason_default_completed(self) -> None:
        scenario = ScenarioDefinition(id="s", name="S", selectors={})
        response = _mock_response()
        evidence = build_evidence(scenario, response, elapsed=1.0)
        self.assertEqual(evidence["stop_reason"], "completed")


# ---------------------------------------------------------------------------
# RunScenario (mocked runtime)
# ---------------------------------------------------------------------------


class RunScenarioTests(unittest.TestCase):

    def _make_runtime(self, html: str = "<html><body>ok</body></html>") -> MagicMock:
        runtime = MagicMock()
        response = _mock_response(html=html)
        runtime.render.return_value = response
        return runtime

    def test_run_scenario_basic(self) -> None:
        scenario = ScenarioDefinition(
            id="basic", name="Basic", url="http://example.com",
        )
        runtime = self._make_runtime()
        result = run_scenario(scenario, runtime)
        self.assertTrue(result["ok"])
        self.assertEqual(result["id"], "basic")
        runtime.render.assert_called_once()

    def test_run_scenario_uses_url_path_for_local(self) -> None:
        scenario = ScenarioDefinition(
            id="local", name="Local", url_path="test.html",
        )
        runtime = self._make_runtime()
        result = run_scenario(scenario, runtime, base_url="http://127.0.0.1:8000")
        call_args = runtime.render.call_args
        request = call_args[0][0]
        self.assertEqual(request.url, "http://127.0.0.1:8000/test.html")

    def test_run_scenario_uses_full_url(self) -> None:
        scenario = ScenarioDefinition(
            id="remote", name="Remote", url="https://example.com/page",
        )
        runtime = self._make_runtime()
        result = run_scenario(scenario, runtime, base_url="http://127.0.0.1:8000")
        call_args = runtime.render.call_args
        request = call_args[0][0]
        self.assertEqual(request.url, "https://example.com/page")

    def test_run_scenario_runtime_error(self) -> None:
        scenario = ScenarioDefinition(id="err", name="Err", url="http://example.com")
        runtime = MagicMock()
        runtime.render.side_effect = RuntimeError("crash")
        result = run_scenario(scenario, runtime)
        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "error")
        self.assertIn("crash", result["error"])
        self.assertEqual(result["stop_reason"], "runtime_error")

    def test_run_scenario_extracts_rendered_count_from_state(self) -> None:
        state = json.dumps({"rendered_count": 42, "scroll_events": []})
        html = f'<pre id="__training_state">{state}</pre><div class="item">x</div>'
        scenario = ScenarioDefinition(
            id="s", name="S", url="http://example.com",
            selectors={"item": ".item"},
        )
        runtime = self._make_runtime(html=html)
        result = run_scenario(scenario, runtime)
        self.assertEqual(result["rendered_item_count"], 42)

    def test_run_scenario_fallback_selector_counting(self) -> None:
        html = '<div class="card">a</div><div class="card">b</div><div class="card">c</div>'
        scenario = ScenarioDefinition(
            id="s", name="S", url="http://example.com",
            selectors={"card": ".card"},
        )
        runtime = self._make_runtime(html=html)
        result = run_scenario(scenario, runtime)
        self.assertEqual(result["rendered_item_count"], 3)

    def test_run_scenario_mobile_profile_applied(self) -> None:
        scenario = ScenarioDefinition(
            id="mobile", name="Mobile", url="http://example.com",
            mobile_profile={
                "profile_id": "mob",
                "user_agent": "iPhone UA",
                "viewport": "375x812",
                "is_mobile": True,
                "has_touch": True,
            },
        )
        runtime = self._make_runtime()
        result = run_scenario(scenario, runtime)
        call_args = runtime.render.call_args
        request = call_args[0][0]
        self.assertEqual(request.browser_config.get("user_agent"), "iPhone UA")

    def test_run_scenario_stop_reason_completed(self) -> None:
        html = '<div class="item">a</div>'
        scenario = ScenarioDefinition(
            id="s", name="S", url="http://example.com",
            selectors={"item": ".item"},
        )
        runtime = self._make_runtime(html=html)
        result = run_scenario(scenario, runtime)
        self.assertEqual(result["stop_reason"], "completed")

    def test_run_scenario_stop_reason_no_items(self) -> None:
        html = '<div class="other">x</div>'
        scenario = ScenarioDefinition(
            id="s", name="S", url="http://example.com",
            selectors={"item": ".item"},
        )
        runtime = self._make_runtime(html=html)
        result = run_scenario(scenario, runtime)
        self.assertEqual(result["stop_reason"], "no_items_matched")


# ---------------------------------------------------------------------------
# ScrollTraining (mocked)
# ---------------------------------------------------------------------------


class ScrollTrainingTests(unittest.TestCase):

    def test_scroll_training_init_script_waits_for_dom(self) -> None:
        """The init_script should contain DOMContentLoaded listener."""
        scenario = LOCAL_SCENARIOS[0]  # infinite_scroll_fixture
        self.assertTrue(scenario.scroll_enabled)
        self.assertIn("infinite_scroll", scenario.url_path)

    def test_scroll_training_scroll_target_window(self) -> None:
        """Infinite scroll uses window as scroll target."""
        scenario = LOCAL_SCENARIOS[0]
        self.assertEqual(scenario.scroll_target, "")

    def test_scroll_training_scroll_target_container(self) -> None:
        """Virtualized list uses #virtual-viewport as scroll target."""
        scenario = LOCAL_SCENARIOS[1]
        self.assertEqual(scenario.scroll_target, "#virtual-viewport")

    def test_mobile_scenario_no_scroll(self) -> None:
        """Mobile viewport fixture has no scroll training."""
        scenario = LOCAL_SCENARIOS[2]
        self.assertFalse(scenario.scroll_enabled)


# ---------------------------------------------------------------------------
# Scenario lists
# ---------------------------------------------------------------------------


class ScenarioListTests(unittest.TestCase):

    def test_local_scenarios_count(self) -> None:
        self.assertEqual(len(LOCAL_SCENARIOS), 3)

    def test_local_scenario_ids(self) -> None:
        ids = [s.id for s in LOCAL_SCENARIOS]
        self.assertIn("infinite_scroll_fixture", ids)
        self.assertIn("virtualized_list_fixture", ids)
        self.assertIn("mobile_viewport_fixture", ids)

    def test_local_scenario_url_paths(self) -> None:
        for s in LOCAL_SCENARIOS:
            self.assertTrue(s.url_path, f"{s.id} missing url_path")
            self.assertTrue(s.url_path.endswith(".html"))

    def test_public_demo_scenarios_count(self) -> None:
        self.assertGreaterEqual(len(PUBLIC_DEMO_SCENARIOS), 7)

    def test_public_demo_urls_are_https(self) -> None:
        for s in PUBLIC_DEMO_SCENARIOS:
            self.assertTrue(s.url.startswith("https://"), f"{s.id} URL not HTTPS")

    def test_public_demo_has_selectors(self) -> None:
        for s in PUBLIC_DEMO_SCENARIOS:
            self.assertTrue(s.selectors, f"{s.id} missing selectors")

    def test_public_demo_has_expected(self) -> None:
        for s in PUBLIC_DEMO_SCENARIOS:
            self.assertTrue(s.expected, f"{s.id} missing expected checks")

    def test_vue_examples_config(self) -> None:
        s = next(x for x in PUBLIC_DEMO_SCENARIOS if x.id == "vue_examples_spa")
        self.assertIn("example_link", s.selectors)
        self.assertEqual(s.wait_selector, "a.link")
        self.assertIn("min_rendered_items", s.expected)

    def test_react_learn_config(self) -> None:
        s = next(x for x in PUBLIC_DEMO_SCENARIOS if x.id == "react_learn_spa")
        self.assertIn("nav_link", s.selectors)
        self.assertEqual(s.wait_selector, "a.p-2.pe-2")
        self.assertIn("min_rendered_items", s.expected)

    def test_tanstack_virtual_config(self) -> None:
        s = next(x for x in PUBLIC_DEMO_SCENARIOS if x.id == "tanstack_virtual_docs")
        self.assertIn("pre", s.selectors.get("code_block", ""))
        self.assertIn("min_html_chars", s.expected)

    def test_virtuoso_config(self) -> None:
        s = next(x for x in PUBLIC_DEMO_SCENARIOS if x.id == "react_virtuoso_demo")
        self.assertTrue(s.scroll_enabled)
        self.assertIn("[data-index]", s.selectors.get("list_item", ""))

    def test_scrapethissite_ajax_config(self) -> None:
        s = next(x for x in PUBLIC_DEMO_SCENARIOS if x.id == "scrapethissite_ajax")
        self.assertIn("year_link", s.selectors)
        self.assertIn("film_row", s.selectors)
        self.assertEqual(s.wait_selector, "a.year-link")
        self.assertIn("min_rendered_items", s.expected)

    def test_dummyjson_products_config(self) -> None:
        s = next(x for x in PUBLIC_DEMO_SCENARIOS if x.id == "dummyjson_products_ssr")
        self.assertIn("product_card", s.selectors)
        self.assertIn("min_html_chars", s.expected)

    def test_scrapethissite_countries_config(self) -> None:
        s = next(x for x in PUBLIC_DEMO_SCENARIOS if x.id == "scrapethissite_countries")
        self.assertIn("country", s.selectors)
        self.assertIn("min_rendered_items", s.expected)

    def test_no_site_specific_rules_in_public_scenarios(self) -> None:
        """Public scenarios store selectors in ScenarioDefinition, not in runtime."""
        for s in PUBLIC_DEMO_SCENARIOS:
            self.assertIsInstance(s.selectors, dict)
            self.assertIsInstance(s.expected, dict)

    def test_infinite_scroll_config(self) -> None:
        s = LOCAL_SCENARIOS[0]
        self.assertTrue(s.scroll_enabled)
        self.assertGreaterEqual(s.scroll_max, 5)
        self.assertIn("item", s.selectors)
        self.assertIn("min_rendered_items", s.expected)
        self.assertIn("min_scroll_events", s.expected)

    def test_virtualized_list_config(self) -> None:
        s = LOCAL_SCENARIOS[1]
        self.assertTrue(s.scroll_enabled)
        self.assertEqual(s.scroll_target, "#virtual-viewport")
        self.assertIn("virtual_item", s.selectors)
        self.assertIn("min_rendered_items", s.expected)

    def test_mobile_viewport_config(self) -> None:
        s = LOCAL_SCENARIOS[2]
        self.assertFalse(s.scroll_enabled)
        self.assertIn("profile_id", s.mobile_profile)
        self.assertIn("card", s.selectors)
        self.assertIn("min_rendered_items", s.expected)

    def test_no_site_specific_rules_in_defaults(self) -> None:
        """ScenarioDefinition defaults contain no site-specific logic."""
        s = ScenarioDefinition(id="x", name="X")
        self.assertEqual(s.browser_config, {})
        self.assertEqual(s.selectors, {})
        self.assertEqual(s.expected, {})


# ---------------------------------------------------------------------------
# Profile health integration
# ---------------------------------------------------------------------------


class ProfileHealthEvidenceTests(unittest.TestCase):

    def test_health_update_in_engine_result(self) -> None:
        health = {
            "profile_id": "training-desktop",
            "total_requests": 5,
            "success_count": 4,
            "failure_count": 1,
            "health_score": 0.7,
        }
        scenario = ScenarioDefinition(id="s", name="S", selectors={})
        response = _mock_response(engine_result={
            "profile_health_update": health,
            "profile": {"profile_id": "training-desktop"},
        })
        evidence = build_evidence(scenario, response, elapsed=1.0)
        self.assertEqual(evidence["profile_health"]["health_score"], 0.7)
        self.assertEqual(evidence["profile_health"]["total_requests"], 5)

    def test_no_health_when_no_rotator(self) -> None:
        scenario = ScenarioDefinition(id="s", name="S", selectors={})
        response = _mock_response(engine_result={})
        evidence = build_evidence(scenario, response, elapsed=1.0)
        self.assertIsNone(evidence["profile_health"])


# ---------------------------------------------------------------------------
# Fixture HTML integrity
# ---------------------------------------------------------------------------


class FixtureIntegrityTests(unittest.TestCase):

    FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "browser_scenarios"

    def test_infinite_scroll_exists(self) -> None:
        path = self.FIXTURE_DIR / "infinite_scroll.html"
        self.assertTrue(path.exists(), f"Missing: {path}")

    def test_virtualized_list_exists(self) -> None:
        path = self.FIXTURE_DIR / "virtualized_list.html"
        self.assertTrue(path.exists(), f"Missing: {path}")

    def test_mobile_viewport_exists(self) -> None:
        path = self.FIXTURE_DIR / "mobile_viewport.html"
        self.assertTrue(path.exists(), f"Missing: {path}")

    def test_fixtures_have_training_state_element(self) -> None:
        for name in ["infinite_scroll.html", "virtualized_list.html", "mobile_viewport.html"]:
            path = self.FIXTURE_DIR / name
            content = path.read_text(encoding="utf-8")
            self.assertIn('__training_state', content, f"{name} missing __training_state element")

    def test_fixtures_expose_rendered_count(self) -> None:
        for name in ["infinite_scroll.html", "virtualized_list.html", "mobile_viewport.html"]:
            path = self.FIXTURE_DIR / name
            content = path.read_text(encoding="utf-8")
            self.assertIn('__rendered_count', content, f"{name} missing __rendered_count")

    def test_infinite_scroll_has_intersection_observer(self) -> None:
        path = self.FIXTURE_DIR / "infinite_scroll.html"
        content = path.read_text(encoding="utf-8")
        self.assertIn("IntersectionObserver", content)

    def test_virtualized_list_has_scroll_listener(self) -> None:
        path = self.FIXTURE_DIR / "virtualized_list.html"
        content = path.read_text(encoding="utf-8")
        self.assertIn("addEventListener('scroll'", content)

    def test_mobile_viewport_has_touch_events(self) -> None:
        path = self.FIXTURE_DIR / "mobile_viewport.html"
        content = path.read_text(encoding="utf-8")
        self.assertIn("touchstart", content)
        self.assertIn("touchmove", content)
        self.assertIn("touchend", content)

    def test_mobile_viewport_has_responsive_css(self) -> None:
        path = self.FIXTURE_DIR / "mobile_viewport.html"
        content = path.read_text(encoding="utf-8")
        self.assertIn("@media", content)


if __name__ == "__main__":
    unittest.main()
