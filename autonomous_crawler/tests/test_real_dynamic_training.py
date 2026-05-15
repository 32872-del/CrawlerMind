"""Tests for real dynamic training runner (SCRAPLING-ABSORB-2I).

Mocked tests — no network or Playwright required.
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
from typing import Any

from run_real_dynamic_training_2026_05_14 import (
    TRAINING_SCENARIOS,
    _build_result,
    _check_expected,
    run_scenario,
    run_scenario_with_runtime,
    run_training,
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


class CheckExpectedTests(unittest.TestCase):
    """Tests for _check_expected()."""

    def test_min_html_chars_pass(self) -> None:
        result = {"html_chars": 5000}
        checks = _check_expected(result, {"min_html_chars": 1000})
        self.assertTrue(checks["min_html_chars"]["pass"])

    def test_min_html_chars_fail(self) -> None:
        result = {"html_chars": 50}
        checks = _check_expected(result, {"min_html_chars": 1000})
        self.assertFalse(checks["min_html_chars"]["pass"])

    def test_min_selector_hits_pass(self) -> None:
        result = {"selector_matches": {"quote": 10, "text": 10}}
        checks = _check_expected(result, {"min_selector_hits": {"quote": 1, "text": 1}})
        self.assertTrue(checks["min_selector_hits.quote"]["pass"])
        self.assertTrue(checks["min_selector_hits.text"]["pass"])

    def test_min_selector_hits_fail(self) -> None:
        result = {"selector_matches": {"quote": 0}}
        checks = _check_expected(result, {"min_selector_hits": {"quote": 1}})
        self.assertFalse(checks["min_selector_hits.quote"]["pass"])

    def test_min_selector_hits_missing(self) -> None:
        result: dict[str, Any] = {"selector_matches": {}}
        checks = _check_expected(result, {"min_selector_hits": {"quote": 1}})
        self.assertFalse(checks["min_selector_hits.quote"]["pass"])

    def test_failure_category_pass(self) -> None:
        result = {"failure_classification": {"category": "http_blocked"}}
        checks = _check_expected(result, {"failure_category": "http_blocked"})
        self.assertTrue(checks["failure_category"]["pass"])

    def test_failure_category_fail(self) -> None:
        result = {"failure_classification": {"category": "timeout"}}
        checks = _check_expected(result, {"failure_category": "http_blocked"})
        self.assertFalse(checks["failure_category"]["pass"])

    def test_failure_category_none(self) -> None:
        result: dict[str, Any] = {"failure_classification": {}}
        checks = _check_expected(result, {"failure_category": "http_blocked"})
        self.assertFalse(checks["failure_category"]["pass"])

    def test_status_code_pass(self) -> None:
        result = {"status_code": 403}
        checks = _check_expected(result, {"status_code": 403})
        self.assertTrue(checks["status_code"]["pass"])

    def test_status_code_fail(self) -> None:
        result = {"status_code": 200}
        checks = _check_expected(result, {"status_code": 403})
        self.assertFalse(checks["status_code"]["pass"])

    def test_empty_expected(self) -> None:
        result: dict[str, Any] = {"html_chars": 100}
        checks = _check_expected(result, {})
        self.assertEqual(checks, {})

    def test_combined_checks(self) -> None:
        result = {
            "html_chars": 5000,
            "status_code": 200,
            "selector_matches": {"title": 5},
            "failure_classification": {"category": "none"},
        }
        expected = {
            "min_html_chars": 1000,
            "status_code": 200,
            "min_selector_hits": {"title": 1},
        }
        checks = _check_expected(result, expected)
        self.assertTrue(checks["min_html_chars"]["pass"])
        self.assertTrue(checks["status_code"]["pass"])
        self.assertTrue(checks["min_selector_hits.title"]["pass"])


class BuildResultTests(unittest.TestCase):
    """Tests for _build_result()."""

    def test_basic_result(self) -> None:
        scenario: dict[str, Any] = {
            "id": "test_s1",
            "name": "Test Scenario",
            "url": "https://example.com",
            "risk": "low",
            "selectors": {},
            "expected": {},
        }
        response = _mock_response()
        result = _build_result(scenario, response, 1.5)
        self.assertEqual(result["id"], "test_s1")
        self.assertEqual(result["name"], "Test Scenario")
        self.assertEqual(result["url"], "https://example.com")
        self.assertEqual(result["risk"], "low")
        self.assertEqual(result["status"], "ok")
        self.assertTrue(result["ok"])
        self.assertEqual(result["status_code"], 200)
        self.assertEqual(result["html_chars"], len("<html><body>test</body></html>"))
        self.assertAlmostEqual(result["elapsed_seconds"], 1.5)

    def test_failed_response(self) -> None:
        scenario: dict[str, Any] = {
            "id": "test_fail",
            "name": "Fail",
            "url": "https://example.com/403",
            "risk": "medium",
            "selectors": {},
            "expected": {},
        }
        response = _mock_response(ok=False, status_code=403, html="")
        result = _build_result(scenario, response, 0.5)
        self.assertEqual(result["status"], "failed")
        self.assertFalse(result["ok"])
        self.assertEqual(result["html_chars"], 0)

    def test_engine_result_fields(self) -> None:
        scenario: dict[str, Any] = {
            "id": "test_e",
            "name": "Engine",
            "url": "https://example.com",
            "risk": "low",
            "selectors": {},
            "expected": {},
        }
        response = _mock_response(engine_result={
            "engine": "native_browser",
            "mode": "dynamic",
            "session_mode": "ephemeral",
            "failure_classification": {"category": "http_blocked"},
            "resource_counts": {"script": 5, "xhr": 2},
            "pool": {"active_count": 3},
            "profile": {"profile_id": "desktop"},
            "rotator": {"profile_count": 2},
        })
        result = _build_result(scenario, response, 1.0)
        self.assertEqual(result["engine"], "native_browser")
        self.assertEqual(result["mode"], "dynamic")
        self.assertEqual(result["failure_classification"]["category"], "http_blocked")
        self.assertEqual(result["resource_counts"]["script"], 5)
        self.assertEqual(result["profile_evidence"]["profile_id"], "desktop")
        self.assertEqual(result["profile_evidence"]["pool_active"], 3)

    def test_xhr_count(self) -> None:
        scenario: dict[str, Any] = {
            "id": "xhr",
            "name": "XHR",
            "url": "https://example.com",
            "risk": "low",
            "selectors": {},
            "expected": {},
        }
        response = _mock_response(captured_xhr=[
            {"url": "https://api.example.com/data"},
            {"url": "https://api.example.com/items"},
        ])
        result = _build_result(scenario, response, 1.0)
        self.assertEqual(result["xhr_count"], 2)

    def test_selector_matches_with_html(self) -> None:
        scenario: dict[str, Any] = {
            "id": "sel",
            "name": "Selectors",
            "url": "https://example.com",
            "risk": "low",
            "selectors": {
                "title": "h1",
                "item": ".item",
            },
            "expected": {},
        }
        html = "<html><body><h1>Hello</h1><div class='item'>A</div><div class='item'>B</div></body></html>"
        response = _mock_response(html=html)
        result = _build_result(scenario, response, 1.0)
        self.assertEqual(result["selector_matches"]["title"], 1)
        self.assertEqual(result["selector_matches"]["item"], 2)

    def test_expected_checks_in_result(self) -> None:
        scenario: dict[str, Any] = {
            "id": "exp",
            "name": "Expected",
            "url": "https://example.com",
            "risk": "low",
            "selectors": {},
            "expected": {"min_html_chars": 10, "status_code": 200},
        }
        response = _mock_response()
        result = _build_result(scenario, response, 1.0)
        self.assertIn("expected_checks", result)
        self.assertTrue(result["expected_checks"]["min_html_chars"]["pass"])
        self.assertTrue(result["expected_checks"]["status_code"]["pass"])


class ScenarioListTests(unittest.TestCase):
    """Tests for TRAINING_SCENARIOS structure."""

    def test_at_least_three_scenarios(self) -> None:
        self.assertGreaterEqual(len(TRAINING_SCENARIOS), 3)

    def test_each_scenario_has_required_keys(self) -> None:
        required = {"id", "name", "url", "mode", "selectors"}
        for s in TRAINING_SCENARIOS:
            for key in required:
                self.assertIn(key, s, f"Scenario {s.get('id')} missing {key}")

    def test_scenario_ids_unique(self) -> None:
        ids = [s["id"] for s in TRAINING_SCENARIOS]
        self.assertEqual(len(ids), len(set(ids)))

    def test_urls_are_https(self) -> None:
        for s in TRAINING_SCENARIOS:
            self.assertTrue(
                s["url"].startswith("https://"),
                f"Scenario {s['id']} URL not HTTPS: {s['url']}",
            )


class RunScenarioWithRuntimeTests(unittest.TestCase):
    """Tests for run_scenario_with_runtime() with mocked runtime."""

    def test_success_scenario(self) -> None:
        scenario: dict[str, Any] = {
            "id": "mock_ok",
            "name": "Mock OK",
            "url": "https://example.com",
            "mode": "dynamic",
            "selectors": {"body": "body"},
            "expected": {"min_html_chars": 5},
        }
        runtime = MagicMock()
        runtime.render.return_value = _mock_response(
            html="<html><body>Hello World</body></html>"
        )
        pool = MagicMock()

        result = run_scenario_with_runtime(scenario, runtime, pool)
        self.assertEqual(result["status"], "ok")
        self.assertTrue(result["ok"])
        self.assertEqual(result["status_code"], 200)
        self.assertGreater(result["html_chars"], 5)
        runtime.render.assert_called_once()

    def test_error_scenario(self) -> None:
        scenario: dict[str, Any] = {
            "id": "mock_err",
            "name": "Mock Error",
            "url": "https://example.com",
            "mode": "dynamic",
            "selectors": {},
            "expected": {},
        }
        runtime = MagicMock()
        runtime.render.side_effect = RuntimeError("playwright crash")
        pool = MagicMock()

        result = run_scenario_with_runtime(scenario, runtime, pool)
        self.assertEqual(result["status"], "error")
        self.assertIn("RuntimeError", result["error"])

    def test_runtime_called_with_request(self) -> None:
        scenario: dict[str, Any] = {
            "id": "mock_req",
            "name": "Mock Request",
            "url": "https://example.com/page",
            "mode": "protected",
            "selectors": {"title": "h1"},
            "wait_selector": "h1",
            "wait_until": "networkidle",
            "timeout_ms": 15000,
            "headers": {"X-Test": "value"},
            "browser_config": {"render_time_ms": 2000},
        }
        runtime = MagicMock()
        runtime.render.return_value = _mock_response()
        pool = MagicMock()

        run_scenario_with_runtime(scenario, runtime, pool)
        call_args = runtime.render.call_args
        request = call_args[0][0]
        self.assertEqual(request.url, "https://example.com/page")
        self.assertEqual(request.mode, "protected")


if __name__ == "__main__":
    unittest.main()
