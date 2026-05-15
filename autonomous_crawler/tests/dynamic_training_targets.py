"""Dynamic/ecommerce training scenario fixtures for native-vs-transition comparison.

Each scenario dict is a self-contained target definition that maps through
``build_state()`` into an executor workflow state.  Scenarios are data
structures — they do not require public network access to validate shape.
"""
from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Scenario type catalogue
# ---------------------------------------------------------------------------
# Coverage required by SCRAPLING-ABSORB-2E-A:
#   1. JS rendered product lists
#   2. XHR/API product data
#   3. Lazy load / infinite scroll
#   4. Cookie/session visible changes
#   5. Challenge-like / block evidence
#   6. Static fallback pages
#   (+) Multi-page pagination
#   (+) Protected/dynamic with init_script

SCENARIO_TYPES: list[dict[str, Any]] = [
    # 1. JS rendered product list (SPA)
    {
        "id": "js_rendered_product_list",
        "name": "JS Rendered Product List",
        "category": "js_rendered_list",
        "url": "https://example-shop.example/products",
        "mode": "browser",
        "selectors": {
            "product_card": ".product-card",
            "title": ".product-title",
            "price": ".product-price",
            "image": "img.product-image@src",
        },
        "wait_selector": ".product-card",
        "wait_until": "networkidle",
        "capture_xhr": "",
        "browser_config": {"capture_api": True},
        "target_fields": ["title", "price", "image_src"],
        "risk": "low",
        "timeout_ms": 30000,
    },
    # 2. XHR/API product data
    {
        "id": "xhr_api_product_data",
        "name": "XHR API Product Data",
        "category": "xhr_api_data",
        "url": "https://api-shop.example/products",
        "mode": "browser",
        "selectors": {
            "product_card": ".product-item",
            "title": ".product-name",
            "price": ".product-price",
        },
        "wait_selector": ".product-item",
        "wait_until": "networkidle",
        "capture_xhr": "/api/v[0-9]+/products",
        "browser_config": {"capture_api": True},
        "target_fields": ["title", "price", "api_response"],
        "risk": "low",
        "timeout_ms": 30000,
    },
    # 3. Lazy load / infinite scroll
    {
        "id": "lazy_load_infinite_scroll",
        "name": "Lazy Load Infinite Scroll",
        "category": "lazy_load_scroll",
        "url": "https://scroll-shop.example/products",
        "mode": "browser",
        "selectors": {
            "product_card": ".product-card",
            "title": ".product-title",
            "price": ".product-price",
        },
        "wait_selector": ".product-card",
        "wait_until": "networkidle",
        "capture_xhr": "",
        "browser_config": {
            "capture_api": True,
            "scroll_count": 5,
            "scroll_delay": 1.5,
        },
        "target_fields": ["title", "price"],
        "risk": "medium",
        "timeout_ms": 60000,
    },
    # 4. Cookie/session visible changes
    {
        "id": "cookie_session_changes",
        "name": "Cookie Session Visible Changes",
        "category": "cookie_session",
        "url": "https://session-shop.example/account",
        "mode": "browser",
        "selectors": {
            "greeting": ".welcome-message",
            "member_price": ".member-price",
        },
        "wait_selector": ".welcome-message",
        "wait_until": "networkidle",
        "capture_xhr": "",
        "browser_config": {
            "capture_api": True,
            "user_data_dir": "",
            "storage_state": "",
        },
        "target_fields": ["greeting", "member_price"],
        "risk": "medium",
        "timeout_ms": 30000,
    },
    # 5. Challenge-like / block evidence
    {
        "id": "challenge_block_evidence",
        "name": "Challenge Block Evidence",
        "category": "challenge_block",
        "url": "https://protected-shop.example/products",
        "mode": "browser",
        "selectors": {
            "product_card": ".product-card",
            "title": ".product-title",
        },
        "wait_selector": ".product-card",
        "wait_until": "networkidle",
        "capture_xhr": "",
        "browser_config": {"capture_api": True},
        "target_fields": ["title"],
        "risk": "high",
        "timeout_ms": 45000,
        "expected_evidence": {
            "failure_classification": "challenge_like",
            "blocked_status_codes": [403, 429],
            "requires_review": True,
        },
    },
    # 6. Static fallback page
    {
        "id": "static_fallback_page",
        "name": "Static Fallback Page",
        "category": "static_fallback",
        "url": "https://static-shop.example/products",
        "mode": "http",
        "selectors": {
            "title": "h1",
            "product_card": ".product",
            "price": ".price",
        },
        "wait_selector": "",
        "wait_until": "",
        "capture_xhr": "",
        "browser_config": {},
        "target_fields": ["title", "price"],
        "risk": "low",
        "timeout_ms": 15000,
    },
    # 7. Multi-page pagination
    {
        "id": "multi_page_pagination",
        "name": "Multi Page Pagination",
        "category": "pagination",
        "url": "https://paged-shop.example/products?page=1",
        "mode": "browser",
        "selectors": {
            "product_card": ".product-card",
            "title": ".product-title",
            "price": ".product-price",
            "next_page": "a.next-page@href",
        },
        "wait_selector": ".product-card",
        "wait_until": "networkidle",
        "capture_xhr": "",
        "browser_config": {"capture_api": True},
        "target_fields": ["title", "price", "next_page_url"],
        "risk": "low",
        "timeout_ms": 30000,
        "max_items": 60,
    },
    # 8. Protected/dynamic with init_script
    {
        "id": "protected_dynamic_init_script",
        "name": "Protected Dynamic Init Script",
        "category": "protected_init",
        "url": "https://stealth-shop.example/products",
        "mode": "browser",
        "selectors": {
            "product_card": ".product-card",
            "title": ".product-title",
            "price": ".product-price",
        },
        "wait_selector": ".product-card",
        "wait_until": "networkidle",
        "capture_xhr": "",
        "browser_config": {
            "capture_api": True,
            "init_script": "Object.defineProperty(navigator, 'webdriver', {get: () => false})",
            "fingerprint_report": True,
        },
        "target_fields": ["title", "price"],
        "risk": "high",
        "timeout_ms": 45000,
    },
]

SCENARIO_BY_ID: dict[str, dict[str, Any]] = {
    s["id"]: s for s in SCENARIO_TYPES
}

CATEGORIES: list[str] = [
    "js_rendered_list",
    "xhr_api_data",
    "lazy_load_scroll",
    "cookie_session",
    "challenge_block",
    "static_fallback",
    "pagination",
    "protected_init",
]


def get_scenario(scenario_id: str) -> dict[str, Any]:
    """Return a scenario by id, or raise KeyError."""
    return SCENARIO_BY_ID[scenario_id]


def get_scenarios_by_category(category: str) -> list[dict[str, Any]]:
    """Return all scenarios in a category."""
    return [s for s in SCENARIO_TYPES if s.get("category") == category]


def build_state(scenario: dict[str, Any], engine: str) -> dict[str, Any]:
    """Map a scenario dict to an executor workflow state.

    Mirrors ``run_native_transition_comparison_2026_05_14.build_state()``
    without importing the comparison runner (no executor dependency).
    """
    browser_config = dict(scenario.get("browser_config", {}))
    return {
        "target_url": scenario["url"],
        "crawl_strategy": {
            "engine": engine,
            "mode": scenario.get("mode", "browser"),
            "extraction_method": "css",
            "selectors": dict(scenario.get("selectors", {})),
            "wait_selector": scenario.get("wait_selector", ""),
            "wait_until": scenario.get("wait_until", ""),
            "timeout_ms": scenario.get("timeout_ms", 30000),
            "capture_xhr": scenario.get("capture_xhr", ""),
            "browser_config": browser_config,
        },
        "recon_report": {
            "task_type": scenario.get("category", ""),
            "target_fields": list(scenario.get("target_fields", [])),
        },
    }
