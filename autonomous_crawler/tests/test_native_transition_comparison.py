"""Tests for native-vs-transition comparison runner."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlparse

from run_native_transition_comparison_2026_05_14 import (
    build_state,
    build_dynamic_scenarios,
    build_profile_scenarios,
    apply_base_url,
    compare_pair,
    evaluate_expectations,
    load_profile_scenarios,
    local_spa_server,
    normalize_profile_scenario,
    run_comparison,
)


class NativeTransitionComparisonTests(unittest.TestCase):
    def test_build_state_sets_explicit_native_engine(self) -> None:
        state = build_state(
            {
                "id": "fixture",
                "name": "Fixture",
                "url": "https://example.com",
                "selectors": {"title": "h1"},
            },
            "native",
        )

        self.assertEqual(state["crawl_strategy"]["engine"], "native")
        self.assertEqual(state["crawl_strategy"]["mode"], "http")
        self.assertEqual(state["crawl_strategy"]["selectors"], {"title": "h1"})

    def test_build_state_sets_browser_mode_for_dynamic_scenario(self) -> None:
        state = build_state(
            {
                "id": "fixture_spa",
                "name": "Fixture SPA",
                "url": "http://127.0.0.1:9999/spa",
                "mode": "browser",
                "selectors": {"title": ".product-title"},
                "wait_selector": ".product-card",
                "wait_until": "networkidle",
                "capture_xhr": "/api/products",
                "browser_config": {"capture_api": True},
            },
            "native",
        )

        strategy = state["crawl_strategy"]
        self.assertEqual(strategy["engine"], "native")
        self.assertEqual(strategy["mode"], "browser")
        self.assertEqual(strategy["wait_selector"], ".product-card")
        self.assertEqual(strategy["wait_until"], "networkidle")
        self.assertEqual(strategy["capture_xhr"], "/api/products")
        self.assertTrue(strategy["browser_config"]["capture_api"])

    def test_build_dynamic_scenarios_uses_local_base_url(self) -> None:
        scenarios = build_dynamic_scenarios("http://127.0.0.1:12345")

        self.assertEqual(scenarios[0]["id"], "local_spa_products")
        self.assertEqual(scenarios[0]["url"], "http://127.0.0.1:12345/spa")
        self.assertEqual(scenarios[0]["mode"], "browser")

    def test_build_profile_scenarios_includes_static_and_dynamic_cases(self) -> None:
        scenarios = build_profile_scenarios("http://127.0.0.1:12345")

        self.assertEqual(len(scenarios), 3)
        self.assertEqual(scenarios[0]["id"], "profile_product_catalog")
        self.assertEqual(scenarios[2]["mode"], "browser")
        self.assertIn("expect", scenarios[2])

    def test_normalize_profile_scenario_rejects_unknown_keys(self) -> None:
        with self.assertRaises(ValueError):
            normalize_profile_scenario({
                "id": "bad",
                "name": "Bad",
                "url": "https://example.com",
                "unknown": True,
            })

    def test_load_profile_scenarios_from_json_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "profile.json"
            path.write_text(
                json.dumps({
                    "scenarios": [
                        {
                            "id": "profile_1",
                            "name": "Profile 1",
                            "url": "https://example.com",
                            "selectors": {"title": "h1"},
                        }
                    ]
                }),
                encoding="utf-8",
            )

            scenarios = load_profile_scenarios(path)

        self.assertEqual(scenarios[0]["id"], "profile_1")
        self.assertEqual(scenarios[0]["selectors"], {"title": "h1"})

    def test_apply_base_url_replaces_profile_placeholders(self) -> None:
        scenarios = apply_base_url(
            [{"id": "x", "url": "{base_url}/products"}],
            "http://127.0.0.1:12345",
        )

        self.assertEqual(scenarios[0]["url"], "http://127.0.0.1:12345/products")

    def test_local_spa_server_serves_html_and_json(self) -> None:
        import urllib.request

        with local_spa_server() as base_url:
            html = urllib.request.urlopen(f"{base_url}/spa", timeout=5).read().decode("utf-8")
            data = urllib.request.urlopen(f"{base_url}/api/products", timeout=5).read().decode("utf-8")

        self.assertIn("CLM Local SPA", html)
        self.assertIn("Native Alpha Jacket", data)

    def test_compare_pair_flags_status_mismatch(self) -> None:
        result = compare_pair(
            {"status": "executed", "status_code": 200, "html_chars": 100},
            {"status": "failed", "status_code": 403, "html_chars": 100},
        )

        self.assertTrue(result["requires_review"])
        self.assertFalse(result["same_status"])
        self.assertFalse(result["same_status_code"])

    def test_compare_pair_reports_selector_delta(self) -> None:
        result = compare_pair(
            {"status": "executed", "status_code": 200, "html_chars": 100, "selector_matches": {"title": 2}},
            {"status": "executed", "status_code": 200, "html_chars": 100, "selector_matches": {"title": 1}},
        )

        self.assertEqual(result["selector_match_delta"], {"title": 1})
        self.assertFalse(result["requires_review"])

    def test_evaluate_expectations_reports_selector_and_xhr_thresholds(self) -> None:
        scenario = {
            "expect": {
                "required_status": "executed",
                "required_status_code": 200,
                "min_html_chars": 10,
                "min_captured_xhr": 1,
                "min_artifacts": 1,
                "min_selector_matches": {"title": 2},
            }
        }
        backend = {
            "status": "executed",
            "status_code": 200,
            "html_chars": 12,
            "captured_xhr_count": 1,
            "artifact_count": 1,
            "selector_matches": {"title": 2},
        }

        result = evaluate_expectations(scenario, backend)

        self.assertTrue(result["passed"])
        self.assertTrue(result["checked"])

    @patch("run_native_transition_comparison_2026_05_14.executor_node")
    def test_run_comparison_writes_compact_json(self, executor_mock) -> None:
        def fake_executor(state):
            engine = state["crawl_strategy"]["engine"]
            return {
                "status": "executed",
                "visited_urls": [state["target_url"]],
                "raw_html": {state["target_url"]: "<html><h1>Hello</h1></html>"},
                "engine_result": {
                    "engine": engine,
                    "backend": f"{engine}_static",
                    "transport": "httpx" if engine == "native" else "",
                    "status_code": 200,
                    "final_url": state["target_url"],
                    "selector_results": [
                        {
                            "name": "title",
                            "selector": "h1",
                            "selector_type": "css",
                            "values": ["Hello"],
                            "matched": 1,
                        }
                    ],
                },
                "messages": [f"{engine} ok"],
            }

        executor_mock.side_effect = fake_executor

        with tempfile.TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "comparison.json"
            output = run_comparison(
                scenarios=[
                    {
                        "id": "fixture",
                        "name": "Fixture",
                        "url": "https://example.com",
                        "selectors": {"title": "h1"},
                    }
                ],
                output_path=output_path,
                suite="static",
            )
            saved = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(output["results"][0]["id"], "fixture")
        self.assertEqual(saved["suite"], "static")
        self.assertEqual(saved["results"][0]["comparison"]["requires_review"], False)
        self.assertEqual(executor_mock.call_count, 2)

    @patch("run_native_transition_comparison_2026_05_14.executor_node")
    def test_run_comparison_records_dynamic_xhr_counts(self, executor_mock) -> None:
        def fake_executor(state):
            engine = state["crawl_strategy"]["engine"]
            return {
                "status": "executed",
                "visited_urls": [state["target_url"]],
                "raw_html": {state["target_url"]: "<article class='product-card'><h2 class='product-title'>A</h2></article>"},
                "api_responses": [{"url": f"{state['target_url']}/api/products"}],
                "engine_result": {
                    "engine": engine,
                    "backend": f"{engine}_browser",
                    "mode": "dynamic",
                    "status_code": 200,
                    "final_url": state["target_url"],
                    "captured_xhr": [{"url": f"{state['target_url']}/api/products"}],
                    "selector_results": [
                        {
                            "name": "title",
                            "selector": ".product-title",
                            "selector_type": "css",
                            "values": ["A"],
                            "matched": 1,
                        }
                    ],
                },
                "messages": [f"{engine} ok"],
            }

        executor_mock.side_effect = fake_executor

        with tempfile.TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "dynamic.json"
            output = run_comparison(
                scenarios=build_dynamic_scenarios("http://127.0.0.1:12345"),
                output_path=output_path,
                suite="dynamic",
            )

        self.assertEqual(output["suite"], "dynamic")
        self.assertEqual(output["results"][0]["native"]["captured_xhr_count"], 1)
        self.assertEqual(output["results"][0]["transition"]["captured_xhr_count"], 1)

    @patch("run_native_transition_comparison_2026_05_14.executor_node")
    def test_run_comparison_records_profile_expectations_and_evidence(self, executor_mock) -> None:
        def fake_executor(state):
            engine = state["crawl_strategy"]["engine"]
            mode = state["crawl_strategy"]["mode"]
            target_path = urlparse(state["target_url"]).path
            if "product-catalog" in target_path:
                html = (
                    "<main>"
                    + "".join(
                        "<article class='product-card'>"
                        f"<h2 class='product-name'>A{i}</h2>"
                        f"<span class='product-price'>{i}</span>"
                        f"<a class='product-link' href='/a{i}'>Open</a>"
                        f"<img class='product-photo' src='/a{i}.jpg'/>"
                        "<span class='product-brand'>Brand</span>"
                        "</article>"
                        for i in range(1, 4)
                    )
                    + "</main>"
                )
                selector_results = [
                    {"name": "title", "selector": ".product-name", "selector_type": "css", "values": ["A", "B", "C"], "matched": 3},
                    {"name": "price", "selector": ".product-price", "selector_type": "css", "values": ["1", "2", "3"], "matched": 3},
                    {"name": "link", "selector": ".product-link@href", "selector_type": "css", "values": ["/a", "/b", "/c"], "matched": 3},
                    {"name": "image", "selector": ".product-photo@src", "selector_type": "css", "values": ["/a.jpg", "/b.jpg", "/c.jpg"], "matched": 3},
                    {"name": "brand", "selector": ".product-brand", "selector_type": "css", "values": ["Brand", "Brand", "Brand"], "matched": 3},
                ]
                captured_xhr = []
                artifacts = []
            elif "json-ld-script" in target_path:
                html = (
                    "<main>"
                    + "".join(
                        "<article class='product'>"
                        f"<h3 class='product-title'>B{i}</h3>"
                        f"<span class='product-price'>{i}</span>"
                        f"<a class='product-url' href='/b{i}'>Open</a>"
                        f"<img class='product-img' src='/b{i}.jpg'/>"
                        "</article>"
                        for i in range(1, 3)
                    )
                    + ("<script type='application/ld+json'>" + ("{" + "\"@type\":\"ItemList\",\"itemListElement\":[{\"name\":\"A\"}]" * 4) + "</script>")
                    + "</main>"
                )
                selector_results = [
                    {"name": "title", "selector": ".product-title", "selector_type": "css", "values": ["A", "B"], "matched": 2},
                    {"name": "price", "selector": ".product-price", "selector_type": "css", "values": ["1", "2"], "matched": 2},
                    {"name": "link", "selector": ".product-url@href", "selector_type": "css", "values": ["/a", "/b"], "matched": 2},
                    {"name": "image", "selector": ".product-img@src", "selector_type": "css", "values": ["/a.jpg", "/b.jpg"], "matched": 2},
                ]
                captured_xhr = []
                artifacts = []
            else:
                html = "<article class='product-card'><h2 class='product-title'>A</h2><span class='product-price'>1</span><a class='product-link' href='/a'>Open</a></article><article class='product-card'><h2 class='product-title'>B</h2><span class='product-price'>2</span><a class='product-link' href='/b'>Open</a></article>"
                selector_results = [
                    {"name": "title", "selector": ".product-title", "selector_type": "css", "values": ["A", "B"], "matched": 2},
                    {"name": "price", "selector": ".product-price", "selector_type": "css", "values": ["1", "2"], "matched": 2},
                    {"name": "link", "selector": ".product-link@href", "selector_type": "css", "values": ["/a", "/b"], "matched": 2},
                ]
                captured_xhr = [{"url": f"{state['target_url']}/api/products", "status_code": 200}]
                artifacts = [{"kind": "screenshot"}]
            engine_result = {
                "engine": engine,
                "backend": f"{engine}_{mode}",
                "status_code": 200,
                "final_url": state["target_url"],
                "selector_results": selector_results,
                "captured_xhr": captured_xhr,
                "runtime_events": [{"type": "browser_render_complete"}] if mode == "browser" else [{"type": "fetch_complete"}],
                "artifacts": artifacts if mode == "browser" else [],
                "details": {
                    "failure_classification": {"category": "none"},
                    "fingerprint_report": {"risk_level": "low"},
                },
            }
            return {
                "status": "executed",
                "visited_urls": [state["target_url"]],
                "raw_html": {state["target_url"]: html},
                "api_responses": engine_result["captured_xhr"],
                "engine_result": engine_result,
                "messages": [f"{engine} ok"],
            }

        executor_mock.side_effect = fake_executor

        with tempfile.TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "profile.json"
            output = run_comparison(
                scenarios=build_profile_scenarios("http://127.0.0.1:12345"),
                output_path=output_path,
                suite="profile",
            )
            saved = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(output["suite"], "profile")
        self.assertEqual(saved["suite"], "profile")
        self.assertIn("expectation_results", saved["results"][0])
        self.assertEqual(saved["results"][0]["native"]["captured_xhr_count"], 0)
        self.assertEqual(saved["results"][0]["native"]["artifact_count"], 0)
        self.assertEqual(saved["results"][2]["native"]["artifact_count"], 1)
        self.assertEqual(saved["results"][2]["native"]["runtime_event_types"][0], "browser_render_complete")
        self.assertFalse(saved["results"][0]["comparison"]["requires_review"])


if __name__ == "__main__":
    unittest.main()
