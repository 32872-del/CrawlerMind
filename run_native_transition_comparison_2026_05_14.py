#!/usr/bin/env python3
"""Compare CLM-native runtimes against Scrapling transition runtimes.

This is a developer training/acceptance helper for SCRAPLING-ABSORB native
absorption work. It does not decide production defaults. It records evidence
so we can decide when CLM-native backends are stable enough to become the
preferred path.
"""
from __future__ import annotations

import argparse
import json
import threading
import time
from contextlib import contextmanager
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import urlparse

from autonomous_crawler.agents.executor import executor_node
from autonomous_crawler.tests.fixtures.native_runtime_parity import (
    PRODUCT_CATALOG_HTML,
    JSON_LD_SCRIPT_HTML,
    CSS_MISS_XPATH_HIT_HTML,
    RELATIVE_URL_HTML,
    NESTED_CATEGORY_DETAIL_HTML,
)


DEFAULT_OUTPUT = Path("dev_logs") / "training" / "2026-05-14_native_transition_comparison.json"
DEFAULT_PROFILE_OUTPUT = Path("dev_logs") / "training" / "2026-05-14_native_transition_profile_comparison.json"
MAX_PREVIEW_ITEMS = 5
SUPPORTED_SCENARIO_KEYS = {
    "browser_config",
    "capture_xhr",
    "headers",
    "id",
    "max_items",
    "mode",
    "name",
    "risk",
    "selectors",
    "target_fields",
    "task_type",
    "timeout_ms",
    "transport",
    "url",
    "wait_selector",
    "wait_until",
    "expect",
    "protected",
}

# Fixture HTML map for local static scenarios
FIXTURE_HTML_MAP: dict[str, str] = {
    "/fixtures/product-catalog": PRODUCT_CATALOG_HTML,
    "/fixtures/json-ld-script": JSON_LD_SCRIPT_HTML,
    "/fixtures/css-miss-xpath-hit": CSS_MISS_XPATH_HIT_HTML,
    "/fixtures/relative-url": RELATIVE_URL_HTML,
    "/fixtures/nested-category-detail": NESTED_CATEGORY_DETAIL_HTML,
}


STATIC_COMPARISON_SCENARIOS: list[dict[str, Any]] = [
    {
        "id": "example_home_static",
        "name": "Example.com home page",
        "url": "https://example.com/",
        "selectors": {"title": "h1", "link": "a@href"},
        "risk": "low-public-static",
    },
    {
        "id": "quotes_home_static",
        "name": "Quotes to Scrape home",
        "url": "https://quotes.toscrape.com/",
        "selectors": {
            "item_container": ".quote",
            "title": ".quote .text",
            "summary": ".quote .author",
            "link": ".quote a@href",
        },
        "risk": "low-public-training-site",
    },
    {
        "id": "react_learn_ssr",
        "name": "React learn SSR page",
        "url": "https://react.dev/learn",
        "selectors": {"title": "h1", "link": "a@href"},
        "risk": "low-public-ssr",
    },
]


LOCAL_SPA_HTML = """<!doctype html>
<html>
<head><meta charset="utf-8"><title>CLM Local SPA</title></head>
<body>
  <main id="app"><p class="loading">Loading...</p></main>
  <script>
    fetch('/api/products')
      .then((response) => response.json())
      .then((payload) => {
        const app = document.querySelector('#app');
        app.innerHTML = payload.items.map((item) => `
          <article class="product-card">
            <h2 class="product-title">${item.title}</h2>
            <span class="product-price">${item.price}</span>
            <a class="product-link" href="${item.url}">Open</a>
          </article>
        `).join('');
      });
  </script>
</body>
</html>
"""


LOCAL_SPA_PRODUCTS = {
    "items": [
        {"title": "Native Alpha Jacket", "price": "$129.90", "url": "/products/alpha"},
        {"title": "Native Beta Pants", "price": "$89.50", "url": "/products/beta"},
    ]
}


def build_dynamic_scenarios(base_url: str) -> list[dict[str, Any]]:
    """Build local deterministic dynamic comparison scenarios."""
    return [
        {
            "id": "local_spa_products",
            "name": "Local SPA product list",
            "url": f"{base_url}/spa",
            "mode": "browser",
            "selectors": {
                "item_container": ".product-card",
                "title": ".product-title",
                "price": ".product-price",
                "link": ".product-link@href",
            },
            "wait_selector": ".product-card",
            "wait_until": "networkidle",
            "capture_xhr": r"/api/products",
            "browser_config": {
                "headless": True,
                "capture_api": True,
                "max_body_preview_chars": 2000,
            },
            "target_fields": ["title", "price", "link"],
            "risk": "local-deterministic-spa",
        }
    ]


def build_profile_scenarios(base_url: str) -> list[dict[str, Any]]:
    """Build a broader local profile set for reusable training."""
    return [
        {
            "id": "profile_product_catalog",
            "name": "Profile: Product Card Catalog",
            "url": f"{base_url}/fixtures/product-catalog",
            "mode": "http",
            "selectors": {
                "item_container": ".product-card",
                "title": ".product-name",
                "price": ".product-price",
                "link": ".product-link@href",
                "image": ".product-photo@src",
                "brand": ".product-brand",
            },
            "target_fields": ["title", "price", "link", "image", "brand"],
            "risk": "local-profile-static",
            "expect": {
                "required_status": "executed",
                "required_status_code": 200,
                "min_html_chars": 400,
                "min_selector_matches": {
                    "title": 3,
                    "price": 3,
                    "link": 3,
                    "image": 3,
                    "brand": 3,
                },
            },
        },
        {
            "id": "profile_json_ld_script",
            "name": "Profile: JSON-LD and Script Coexistence",
            "url": f"{base_url}/fixtures/json-ld-script",
            "mode": "http",
            "selectors": {
                "item_container": ".product",
                "title": ".product-title",
                "price": ".product-price",
                "link": ".product-url@href",
                "image": ".product-img@src",
            },
            "target_fields": ["title", "price", "link", "image"],
            "risk": "local-profile-static",
            "expect": {
                "required_status": "executed",
                "required_status_code": 200,
                "min_html_chars": 600,
                "min_selector_matches": {
                    "title": 2,
                    "price": 2,
                    "link": 2,
                    "image": 2,
                },
            },
        },
        {
            "id": "profile_local_spa_products",
            "name": "Profile: Local SPA Product List",
            "url": f"{base_url}/spa",
            "mode": "browser",
            "selectors": {
                "item_container": ".product-card",
                "title": ".product-title",
                "price": ".product-price",
                "link": ".product-link@href",
            },
            "wait_selector": ".product-card",
            "wait_until": "networkidle",
            "capture_xhr": r"/api/products",
            "browser_config": {
                "headless": True,
                "capture_api": True,
                "max_body_preview_chars": 2000,
            },
            "target_fields": ["title", "price", "link"],
            "risk": "local-profile-dynamic",
            "expect": {
                "required_status": "executed",
                "required_status_code": 200,
                "min_html_chars": 150,
                "min_captured_xhr": 1,
                "min_selector_matches": {
                    "title": 2,
                    "price": 2,
                    "link": 2,
                },
            },
        },
    ]


def build_static_fixture_scenarios(base_url: str) -> list[dict[str, Any]]:
    """Build local deterministic static comparison scenarios from test fixtures.

    These scenarios exercise breadth: product cards, JSON-LD coexistence,
    CSS-miss/XPath-hit, relative URLs, and nested category hierarchies.
    """
    return [
        {
            "id": "fixture_product_catalog",
            "name": "Fixture: Product Card Catalog",
            "url": f"{base_url}/fixtures/product-catalog",
            "selectors": {
                "item_container": ".product-card",
                "title": ".product-name",
                "price": ".product-price",
                "link": ".product-link@href",
                "image": ".product-photo@src",
                "brand": ".product-brand",
            },
            "target_fields": ["title", "price", "link", "image", "brand"],
            "risk": "local-deterministic-fixture",
        },
        {
            "id": "fixture_json_ld_script",
            "name": "Fixture: JSON-LD + Script Coexistence",
            "url": f"{base_url}/fixtures/json-ld-script",
            "selectors": {
                "item_container": ".product",
                "title": ".product-title",
                "price": ".product-price",
                "link": ".product-url@href",
                "image": ".product-img@src",
            },
            "target_fields": ["title", "price", "link", "image"],
            "risk": "local-deterministic-fixture",
        },
        {
            "id": "fixture_css_miss_xpath_hit",
            "name": "Fixture: CSS Miss / XPath Hit",
            "url": f"{base_url}/fixtures/css-miss-xpath-hit",
            "selectors": {
                "css_item_name": ".item .item-name",
                "css_section_miss": ".item .catalog-section",
            },
            "target_fields": ["css_item_name"],
            "risk": "local-deterministic-fixture",
        },
        {
            "id": "fixture_relative_url",
            "name": "Fixture: Relative URL Extraction",
            "url": f"{base_url}/fixtures/relative-url",
            "selectors": {
                "link": ".thumb-link@href",
                "image": ".thumb-img@src",
                "alt": ".thumb-img@alt",
            },
            "target_fields": ["link", "image", "alt"],
            "risk": "local-deterministic-fixture",
        },
        {
            "id": "fixture_nested_category_detail",
            "name": "Fixture: Nested Category/Detail Hierarchy",
            "url": f"{base_url}/fixtures/nested-category-detail",
            "selectors": {
                "category": ".category-name",
                "subcategory": ".subcategory-name",
                "detail_link": ".detail-link@href",
                "detail_text": ".detail-link",
                "price": ".product-item .price",
                "product_id": ".product-item@data-pid",
            },
            "target_fields": ["category", "subcategory", "detail_link", "detail_text", "price"],
            "risk": "local-deterministic-fixture",
        },
    ]


class _LocalSpaHandler(BaseHTTPRequestHandler):
    server_version = "CLMTrainingHTTP/1.0"

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        path = urlparse(self.path).path
        if path in {"/", "/spa"}:
            self._send_text(LOCAL_SPA_HTML, "text/html; charset=utf-8")
            return
        if path == "/api/products":
            self._send_text(
                json.dumps(LOCAL_SPA_PRODUCTS, ensure_ascii=False),
                "application/json; charset=utf-8",
            )
            return
        if path in FIXTURE_HTML_MAP:
            self._send_text(FIXTURE_HTML_MAP[path], "text/html; charset=utf-8")
            return
        self.send_response(404)
        self.end_headers()

    def log_message(self, _format: str, *_args: Any) -> None:
        return

    def _send_text(self, text: str, content_type: str) -> None:
        body = text.encode("utf-8")
        self.send_response(200)
        self.send_header("content-type", content_type)
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


@contextmanager
def local_spa_server() -> Iterator[str]:
    """Start a local deterministic SPA training server."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), _LocalSpaHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address
        yield f"http://{host}:{port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def scenarios_for_suite(suite: str) -> list[dict[str, Any]]:
    if suite == "static":
        return list(STATIC_COMPARISON_SCENARIOS)
    if suite == "static-fixtures":
        raise ValueError("static-fixtures scenarios require local_spa_server()")
    if suite == "dynamic":
        raise ValueError("dynamic scenarios require local_spa_server()")
    if suite == "all":
        raise ValueError("all scenarios require local_spa_server()")
    if suite == "profile":
        raise ValueError("profile scenarios require local_spa_server() or a profile file")
    raise ValueError(f"unknown suite: {suite}")


def load_profile_scenarios(profile_path: str | Path) -> list[dict[str, Any]]:
    """Load reusable comparison scenarios from a JSON profile file."""
    path = Path(profile_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    raw_scenarios = payload.get("scenarios") if isinstance(payload, dict) else payload
    if not isinstance(raw_scenarios, list):
        raise ValueError("profile must be a list or an object with scenarios")
    scenarios: list[dict[str, Any]] = []
    for index, raw in enumerate(raw_scenarios, start=1):
        if not isinstance(raw, dict):
            raise ValueError(f"profile scenario #{index} must be an object")
        scenarios.append(normalize_profile_scenario(raw, index=index))
    return scenarios


def apply_base_url(scenarios: list[dict[str, Any]], base_url: str) -> list[dict[str, Any]]:
    """Replace `{base_url}` placeholders in profile scenario URLs."""
    updated: list[dict[str, Any]] = []
    for scenario in scenarios:
        copy = dict(scenario)
        copy["url"] = str(copy.get("url", "")).replace("{base_url}", base_url.rstrip("/"))
        updated.append(copy)
    return updated


def normalize_profile_scenario(raw: dict[str, Any], *, index: int = 0) -> dict[str, Any]:
    unknown = sorted(set(raw) - SUPPORTED_SCENARIO_KEYS)
    if unknown:
        raise ValueError(
            f"scenario {raw.get('id') or index} has unsupported keys: {', '.join(unknown)}"
        )
    scenario_id = str(raw.get("id") or f"profile_scenario_{index}").strip()
    if not scenario_id:
        raise ValueError(f"scenario #{index} id is required")
    name = str(raw.get("name") or scenario_id).strip()
    url = str(raw.get("url") or "").strip()
    if not url:
        raise ValueError(f"scenario {scenario_id} url is required")
    selectors = raw.get("selectors") or {}
    if not isinstance(selectors, dict):
        raise ValueError(f"scenario {scenario_id} selectors must be an object")
    browser_config = raw.get("browser_config") or {}
    if not isinstance(browser_config, dict):
        raise ValueError(f"scenario {scenario_id} browser_config must be an object")
    expect = raw.get("expect") or {}
    if not isinstance(expect, dict):
        raise ValueError(f"scenario {scenario_id} expect must be an object")

    mode = str(raw.get("mode") or "http").strip().lower()
    if mode in {"static"}:
        mode = "http"
    if mode in {"dynamic", "protected"}:
        mode = "browser"
        browser_config = {**browser_config, "mode": str(raw.get("mode")).strip().lower()}
    if mode not in {"http", "browser"}:
        raise ValueError(
            f"scenario {scenario_id} mode must be http, static, browser, dynamic, or protected"
        )

    return {
        "id": scenario_id,
        "name": name,
        "url": url,
        "mode": mode,
        "selectors": {str(key): str(value) for key, value in selectors.items()},
        "wait_selector": str(raw.get("wait_selector") or ""),
        "wait_until": str(raw.get("wait_until") or "domcontentloaded"),
        "timeout_ms": int(raw.get("timeout_ms", 30000) or 30000),
        "capture_xhr": str(raw.get("capture_xhr") or ""),
        "browser_config": browser_config,
        "target_fields": [str(item) for item in (raw.get("target_fields") or ["title", "link"])],
        "headers": {str(key): str(value) for key, value in (raw.get("headers") or {}).items()},
        "max_items": int(raw.get("max_items", 0) or 0),
        "transport": str(raw.get("transport") or ""),
        "task_type": str(raw.get("task_type") or "product_list"),
        "risk": str(raw.get("risk") or "profile"),
        "expect": normalize_expectations(expect, scenario_id=scenario_id),
    }


def normalize_expectations(expect: dict[str, Any], *, scenario_id: str) -> dict[str, Any]:
    allowed = {
        "min_html_chars",
        "min_captured_xhr",
        "min_artifacts",
        "required_status",
        "required_status_code",
        "min_selector_matches",
        "allow_review",
    }
    unknown = sorted(set(expect) - allowed)
    if unknown:
        raise ValueError(
            f"scenario {scenario_id} expect has unsupported keys: {', '.join(unknown)}"
        )
    selector_expect = expect.get("min_selector_matches") or {}
    if not isinstance(selector_expect, dict):
        raise ValueError(f"scenario {scenario_id} expect.min_selector_matches must be an object")
    return {
        "min_html_chars": int(expect.get("min_html_chars", 0) or 0),
        "min_captured_xhr": int(expect.get("min_captured_xhr", 0) or 0),
        "min_artifacts": int(expect.get("min_artifacts", 0) or 0),
        "required_status": str(expect.get("required_status") or ""),
        "required_status_code": int(expect.get("required_status_code", 0) or 0),
        "min_selector_matches": {str(key): int(value or 0) for key, value in selector_expect.items()},
        "allow_review": bool(expect.get("allow_review", False)),
    }


def build_state(scenario: dict[str, Any], engine: str) -> dict[str, Any]:
    """Build an executor-only state for a runtime backend."""
    mode = str(scenario.get("mode") or "http")
    browser_config = dict(scenario.get("browser_config") or {})
    browser_mode = str(browser_config.pop("mode", "") or "").strip().lower()
    if mode == "browser" and browser_mode in {"dynamic", "protected"}:
        browser_config["mode"] = browser_mode
    return {
        "user_goal": f"compare {mode} runtime for {scenario['name']}",
        "target_url": scenario["url"],
        "crawl_strategy": {
            "mode": mode,
            "engine": engine,
            "extraction_method": f"{engine}_runtime",
            "selectors": dict(scenario.get("selectors") or {}),
            "headers": dict(scenario.get("headers") or {}),
            "max_items": int(scenario.get("max_items", 0) or 0),
            "transport": scenario.get("transport", ""),
            "wait_selector": scenario.get("wait_selector", ""),
            "wait_until": scenario.get("wait_until", "domcontentloaded"),
            "timeout_ms": int(scenario.get("timeout_ms", 30000) or 30000),
            "capture_xhr": scenario.get("capture_xhr", ""),
            "browser_config": browser_config,
        },
        "recon_report": {
            "task_type": scenario.get("task_type", "product_list"),
            "target_fields": list(scenario.get("target_fields") or ["title", "link"]),
            "constraints": {},
        },
        "visited_urls": [],
        "raw_html": {},
        "api_responses": [],
        "extracted_data": {},
        "validation_result": {},
        "retries": 0,
        "max_retries": 0,
        "status": "pending",
        "error_log": [],
        "messages": [],
    }


def run_backend(scenario: dict[str, Any], engine: str) -> dict[str, Any]:
    """Run one engine and return a compact comparison summary."""
    started = time.time()
    state = executor_node(build_state(scenario, engine))
    elapsed = time.time() - started
    engine_result = state.get("engine_result") or {}
    raw_html = state.get("raw_html") or {}
    html_text = next(iter(raw_html.values()), "") if raw_html else ""
    selector_results = engine_result.get("selector_results") or []
    captured_xhr = engine_result.get("captured_xhr") or state.get("api_responses") or []
    runtime_events = engine_result.get("runtime_events") or state.get("runtime_events") or []
    artifacts = engine_result.get("artifacts") or state.get("runtime_artifacts") or []
    details = engine_result.get("details") if isinstance(engine_result.get("details"), dict) else {}
    failure_classification = details.get("failure_classification") or engine_result.get("failure_classification") or {}
    fingerprint_report = details.get("fingerprint_report") or engine_result.get("fingerprint_report") or {}
    return {
        "engine": engine,
        "status": state.get("status", ""),
        "elapsed_seconds": round(elapsed, 3),
        "final_url": engine_result.get("final_url") or (state.get("visited_urls") or [""])[0],
        "status_code": engine_result.get("status_code", 0),
        "backend": engine_result.get("backend", ""),
        "transport": engine_result.get("transport", ""),
        "mode": engine_result.get("mode", ""),
        "html_chars": len(html_text),
        "captured_xhr_count": len(captured_xhr),
        "captured_xhr_preview": _preview_xhr(captured_xhr),
        "runtime_event_types": _runtime_event_types(runtime_events),
        "artifact_count": len(artifacts),
        "artifact_kinds": _artifact_kinds(artifacts),
        "failure_classification": failure_classification,
        "fingerprint_risk": _fingerprint_risk(fingerprint_report),
        "selector_matches": {
            str(item.get("name", "")): int(item.get("matched", 0) or 0)
            for item in selector_results
            if isinstance(item, dict)
        },
        "selector_errors": [
            {
                "name": item.get("name", ""),
                "error": item.get("error", ""),
            }
            for item in selector_results
            if isinstance(item, dict) and item.get("error")
        ],
        "error_code": state.get("error_code", ""),
        "error_log": list(state.get("error_log") or [])[:3],
        "messages": list(state.get("messages") or [])[-3:],
    }


def compare_pair(native: dict[str, Any], transition: dict[str, Any]) -> dict[str, Any]:
    """Build a small parity summary from two backend summaries."""
    native_html = int(native.get("html_chars", 0) or 0)
    transition_html = int(transition.get("html_chars", 0) or 0)
    ratio = 0.0
    if transition_html:
        ratio = round(native_html / transition_html, 4)
    native_matches = native.get("selector_matches") or {}
    transition_matches = transition.get("selector_matches") or {}
    keys = sorted(set(native_matches) | set(transition_matches))
    return {
        "same_status": native.get("status") == transition.get("status"),
        "same_status_code": native.get("status_code") == transition.get("status_code"),
        "html_char_ratio_native_over_transition": ratio,
        "captured_xhr_delta": int(native.get("captured_xhr_count", 0) or 0) - int(transition.get("captured_xhr_count", 0) or 0),
        "artifact_delta": int(native.get("artifact_count", 0) or 0) - int(transition.get("artifact_count", 0) or 0),
        "selector_match_delta": {
            key: int(native_matches.get(key, 0) or 0) - int(transition_matches.get(key, 0) or 0)
            for key in keys
        },
        "requires_review": _requires_review(native, transition, ratio),
    }


def _requires_review(native: dict[str, Any], transition: dict[str, Any], ratio: float) -> bool:
    if native.get("status") != transition.get("status"):
        return True
    if native.get("status_code") != transition.get("status_code"):
        return True
    if ratio and (ratio < 0.8 or ratio > 1.25):
        return True
    if native.get("selector_errors") or transition.get("selector_errors"):
        return True
    return False


def evaluate_expectations(scenario: dict[str, Any], backend: dict[str, Any]) -> dict[str, Any]:
    expect = scenario.get("expect") or {}
    if not expect:
        return {"checked": False, "passed": True, "failures": []}

    failures: list[str] = []
    required_status = str(expect.get("required_status") or "")
    if required_status and backend.get("status") != required_status:
        failures.append(f"status expected {required_status}, got {backend.get('status')}")
    required_status_code = int(expect.get("required_status_code", 0) or 0)
    if required_status_code and int(backend.get("status_code", 0) or 0) != required_status_code:
        failures.append(f"status_code expected {required_status_code}, got {backend.get('status_code')}")
    min_html_chars = int(expect.get("min_html_chars", 0) or 0)
    if min_html_chars and int(backend.get("html_chars", 0) or 0) < min_html_chars:
        failures.append(f"html_chars expected >= {min_html_chars}, got {backend.get('html_chars')}")
    min_xhr = int(expect.get("min_captured_xhr", 0) or 0)
    if min_xhr and int(backend.get("captured_xhr_count", 0) or 0) < min_xhr:
        failures.append(f"captured_xhr_count expected >= {min_xhr}, got {backend.get('captured_xhr_count')}")
    min_artifacts = int(expect.get("min_artifacts", 0) or 0)
    if min_artifacts and int(backend.get("artifact_count", 0) or 0) < min_artifacts:
        failures.append(f"artifact_count expected >= {min_artifacts}, got {backend.get('artifact_count')}")

    selector_matches = backend.get("selector_matches") or {}
    for name, minimum in (expect.get("min_selector_matches") or {}).items():
        actual = int(selector_matches.get(name, 0) or 0)
        if actual < int(minimum or 0):
            failures.append(f"selector {name} expected >= {minimum}, got {actual}")

    return {"checked": True, "passed": not failures, "failures": failures}


def scenario_review_required(
    scenario: dict[str, Any],
    pair: dict[str, Any],
    native_expectation: dict[str, Any],
    transition_expectation: dict[str, Any],
) -> bool:
    expect = scenario.get("expect") or {}
    if expect.get("allow_review"):
        pair_review = False
    else:
        pair_review = bool(pair.get("requires_review"))
    return (
        pair_review
        or not native_expectation.get("passed", True)
        or not transition_expectation.get("passed", True)
    )


def _preview_xhr(captured_xhr: list[Any]) -> list[dict[str, Any]]:
    preview: list[dict[str, Any]] = []
    for item in captured_xhr[:MAX_PREVIEW_ITEMS]:
        if not isinstance(item, dict):
            continue
        preview.append({
            "url": str(item.get("url") or "")[:500],
            "method": str(item.get("method") or ""),
            "status_code": int(item.get("status_code", item.get("status", 0)) or 0),
            "content_type": str(item.get("content_type") or item.get("type") or "")[:120],
            "body_preview_chars": len(str(item.get("body_preview") or item.get("preview") or "")),
        })
    return preview


def _runtime_event_types(events: list[Any]) -> list[str]:
    event_types: list[str] = []
    for event in events:
        if not isinstance(event, dict):
            continue
        event_type = str(event.get("type") or "")
        if event_type and event_type not in event_types:
            event_types.append(event_type)
        if len(event_types) >= 20:
            break
    return event_types


def _artifact_kinds(artifacts: list[Any]) -> list[str]:
    kinds: list[str] = []
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            continue
        kind = str(artifact.get("kind") or "")
        if kind and kind not in kinds:
            kinds.append(kind)
    return kinds


def _fingerprint_risk(fingerprint_report: dict[str, Any]) -> str:
    if not isinstance(fingerprint_report, dict):
        return ""
    return str(
        fingerprint_report.get("risk_level")
        or fingerprint_report.get("risk")
        or fingerprint_report.get("level")
        or ""
    )


def run_comparison(
    *,
    scenarios: list[dict[str, Any]] | None = None,
    output_path: Path = DEFAULT_OUTPUT,
    suite: str = "static",
) -> dict[str, Any]:
    """Run the comparison suite and persist JSON evidence."""
    selected = scenarios or STATIC_COMPARISON_SCENARIOS
    results = []
    print("=" * 72)
    print("Crawler-Mind Native vs Transition Runtime Comparison")
    print("=" * 72)
    print(f"Suite: {suite}")
    for scenario in selected:
        print(f"\n[{scenario['id']}] {scenario['name']}")
        print(f"URL: {scenario['url']}")
        native = run_backend(scenario, "native")
        transition = run_backend(scenario, "scrapling")
        pair = compare_pair(native, transition)
        native_expectation = evaluate_expectations(scenario, native)
        transition_expectation = evaluate_expectations(scenario, transition)
        pair["requires_review"] = scenario_review_required(
            scenario,
            pair,
            native_expectation,
            transition_expectation,
        )
        results.append({
            "id": scenario["id"],
            "name": scenario["name"],
            "url": scenario["url"],
            "risk": scenario.get("risk", ""),
            "mode": scenario.get("mode", "http"),
            "expect": scenario.get("expect", {}),
            "native": native,
            "transition": transition,
            "expectation_results": {
                "native": native_expectation,
                "transition": transition_expectation,
            },
            "comparison": pair,
        })
        print(
            "Result: "
            f"native={native['status']}({native['status_code']}) "
            f"transition={transition['status']}({transition['status_code']}) "
            f"html_ratio={pair['html_char_ratio_native_over_transition']} "
            f"review={pair['requires_review']}"
        )

    output = {
        "run_at": datetime.now().isoformat(),
        "purpose": f"SCRAPLING-ABSORB native-vs-transition {suite} runtime comparison",
        "suite": suite,
        "results": results,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nSaved comparison: {output_path}")
    return output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--suite",
        choices=("static", "static-fixtures", "dynamic", "all", "profile"),
        default="static",
        help="comparison suite to run",
    )
    parser.add_argument(
        "--profile",
        type=Path,
        help="JSON profile file with reusable comparison scenarios",
    )
    parser.add_argument(
        "--scenario",
        action="append",
        help="run only matching scenario id; may be passed multiple times",
    )
    args = parser.parse_args(argv)
    if args.suite == "profile":
        with local_spa_server() as base_url:
            try:
                scenarios = (
                    apply_base_url(load_profile_scenarios(args.profile), base_url)
                    if args.profile
                    else build_profile_scenarios(base_url)
                )
            except (OSError, json.JSONDecodeError, ValueError) as exc:
                print(str(exc))
                return 2
            scenarios = _filter_scenarios(scenarios, args.scenario)
            if scenarios is None:
                return 2
            output_path = args.output if args.output != DEFAULT_OUTPUT else DEFAULT_PROFILE_OUTPUT
            output = run_comparison(scenarios=scenarios, output_path=output_path, suite=args.suite)
    elif args.suite in {"static-fixtures", "dynamic", "all"}:
        with local_spa_server() as base_url:
            scenarios = []
            if args.suite in {"static", "all"}:
                scenarios.extend(STATIC_COMPARISON_SCENARIOS)
            if args.suite in {"static-fixtures", "all"}:
                scenarios.extend(build_static_fixture_scenarios(base_url))
            if args.suite in {"dynamic", "all"}:
                scenarios.extend(build_dynamic_scenarios(base_url))
            scenarios = _filter_scenarios(scenarios, args.scenario)
            if scenarios is None:
                return 2
            output = run_comparison(scenarios=scenarios, output_path=args.output, suite=args.suite)
    else:
        scenarios = _filter_scenarios(STATIC_COMPARISON_SCENARIOS, args.scenario)
        if scenarios is None:
            return 2
        output = run_comparison(scenarios=scenarios, output_path=args.output, suite=args.suite)
    needs_review = [
        item["id"]
        for item in output["results"]
        if item["comparison"]["requires_review"]
    ]
    if needs_review:
        print(f"Review needed: {', '.join(needs_review)}")
        return 1
    return 0


def _filter_scenarios(
    scenarios: list[dict[str, Any]],
    scenario_ids: list[str] | None,
) -> list[dict[str, Any]] | None:
    if not scenario_ids:
        return scenarios
    wanted = set(scenario_ids)
    selected = [item for item in scenarios if item["id"] in wanted]
    missing = wanted - {item["id"] for item in selected}
    if missing:
        print(f"Unknown scenario id(s): {', '.join(sorted(missing))}")
        return None
    return selected


if __name__ == "__main__":
    raise SystemExit(main())
