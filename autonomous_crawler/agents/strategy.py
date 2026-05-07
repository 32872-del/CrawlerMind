"""Strategy Agent - Generates crawl strategy based on recon report.

Priority (README Section 7):
1. API Direct Access
2. Embedded JSON / Hydration Data
3. Static DOM Parsing
4. Browser Automation
"""
from __future__ import annotations

from typing import Any

from .base import preserve_state
from ..tools.site_spec_adapter import build_site_spec


@preserve_state
def strategy_node(state: dict[str, Any]) -> dict[str, Any]:
    """Generate crawl strategy from recon_report.

    This is a STUB implementation. In production, this node will:
    1. Analyze recon_report to determine best strategy
    2. Prioritize: API > Hydration > DOM > Browser
    3. Generate selectors, pagination config, headers
    4. Call LLM if strategy is ambiguous
    """
    recon_report = state.get("recon_report", {})
    retries = state.get("retries", 0)
    task_type = recon_report.get("task_type", "product_list")
    constraints = recon_report.get("constraints", {})
    preferred_engine = _preferred_engine(state)

    # --- STUB: Simple strategy selection ---
    # In production, this should be LLM-driven based on recon_report
    api_endpoints = recon_report.get("api_endpoints", [])
    anti_bot = recon_report.get("anti_bot", {})
    rendering = recon_report.get("rendering", "static")
    dom_structure = recon_report.get("dom_structure", {})
    inferred_selectors = {
        "item_container": dom_structure.get("product_selector", ""),
        **(dom_structure.get("field_selectors") or {}),
    }
    inferred_selectors = {k: v for k, v in inferred_selectors.items() if v}
    fallback_selectors = {
        "item_container": ".product-item",
        "title": ".product-title",
        "price": ".product-price",
        "image": ".product-image img@src",
        "link": ".product-item a@href",
    }

    if preferred_engine == "fnspider" and task_type == "product_list":
        strategy = {
            "mode": "http",
            "engine": "fnspider",
            "extraction_method": "fnspider_site_spec",
            "selectors": inferred_selectors or fallback_selectors,
            "pagination": {
                "type": dom_structure.get("pagination_type", "url_param"),
                "param": "page",
            },
            "headers": {},
            "max_items": constraints.get("max_items", 0),
            "rationale": "User requested bundled fnspider engine",
        }
    elif task_type == "ranking_list" and inferred_selectors:
        strategy = {
            "mode": "http",
            "extraction_method": "dom_parse",
            "selectors": inferred_selectors,
            "pagination": {
                "type": dom_structure.get("pagination_type", "none"),
                "param": "page",
            },
            "headers": {},
            "max_items": constraints.get("max_items", 0),
            "rationale": "Ranking list with inferred DOM selectors",
        }
    elif api_endpoints:
        # Priority 1: API Direct Access
        strategy = {
            "mode": "api_intercept",
            "extraction_method": "api_json",
            "api_endpoint": api_endpoints[0] if api_endpoints else "",
            "selectors": {},
            "pagination": {"type": "api_offset", "param": "offset"},
            "headers": {"Accept": "application/json"},
            "rationale": "API endpoint discovered, using direct API access",
        }
    elif rendering == "static" and not anti_bot.get("detected"):
        # Priority 3: Static DOM Parsing
        strategy = {
            "mode": "http",
            "extraction_method": "dom_parse",
            "selectors": inferred_selectors or fallback_selectors,
            "pagination": {
                "type": dom_structure.get("pagination_type", "url_param"),
                "param": "page",
            },
            "headers": {},
            "max_items": constraints.get("max_items", 0),
            "rationale": (
                "Static page with no anti-bot, using inferred DOM selectors"
                if inferred_selectors
                else "Static page with no anti-bot, using fallback DOM selectors"
            ),
        }
    else:
        # Priority 4: Browser Automation
        strategy = {
            "mode": "browser",
            "extraction_method": "browser_render",
            "selectors": inferred_selectors or fallback_selectors,
            "pagination": {"type": "scroll", "scroll_count": 5},
            "headers": {},
            "max_items": constraints.get("max_items", 0),
            "rationale": "SPA or anti-bot detected, using browser automation",
        }

    # If retrying, add feedback from previous attempt
    if retries > 0:
        validation = state.get("validation_result", {})
        strategy["retry_feedback"] = validation.get("anomalies", [])
        strategy["rationale"] += f" (retry #{retries})"

    if task_type == "product_list":
        strategy["site_spec_draft"] = build_site_spec(
            user_goal=state.get("user_goal", ""),
            target_url=recon_report.get("target_url", state.get("target_url", "")),
            recon_report=recon_report,
            selectors=strategy.get("selectors", {}),
            mode=strategy.get("mode", "http"),
        )

    return {
        "status": "strategized",
        "crawl_strategy": strategy,
        "messages": state.get("messages", []) + [f"[Strategy] Mode={strategy['mode']}, Method={strategy['extraction_method']}, Rationale={strategy['rationale']}"],
    }


def _preferred_engine(state: dict[str, Any]) -> str:
    preferences = state.get("crawl_preferences") or {}
    candidates = [
        state.get("preferred_engine"),
        preferences.get("engine") if isinstance(preferences, dict) else None,
    ]
    for candidate in candidates:
        if candidate:
            return str(candidate).strip().lower()
    return ""
