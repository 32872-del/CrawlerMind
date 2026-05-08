"""Strategy Agent - Generates crawl strategy based on recon report.

Priority (README Section 7):
1. API Direct Access
2. Embedded JSON / Hydration Data
3. Static DOM Parsing
4. Browser Automation
"""
from __future__ import annotations

from typing import Any, Callable

from .base import preserve_state
from ..tools.site_spec_adapter import build_site_spec
from ..llm.protocols import StrategyAdvisor
from ..llm.audit import build_decision_record


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
    target_url = recon_report.get("target_url", state.get("target_url", ""))

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

    if (
        preferred_engine == "fnspider"
        and task_type == "product_list"
        and _can_use_fnspider(target_url)
    ):
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


def _can_use_fnspider(target_url: str) -> bool:
    return str(target_url).strip().lower().startswith(("http://", "https://"))


_STRATEGY_ALLOWED_MODES = frozenset({"http", "browser", "api_intercept"})
_STRATEGY_ALLOWED_ENGINES = frozenset({"", "fnspider"})
_STRATEGY_ALLOWED_WAIT_UNTIL = frozenset({"domcontentloaded", "load", "networkidle"})
_STRATEGY_ALLOWED_FIELDS = frozenset({
    "mode", "engine", "selectors", "wait_selector", "wait_until",
    "max_items", "reasoning_summary",
})
_STRATEGY_ALLOWED_SELECTOR_KEYS = frozenset({
    "item_container", "title", "price", "image", "link", "rank",
    "hot_score", "summary", "description", "url", "stock", "size", "color",
})
_FALLBACK_SELECTORS = {
    "item_container": ".product-item",
    "title": ".product-title",
    "price": ".product-price",
    "image": ".product-image img@src",
    "link": ".product-item a@href",
}


def _validate_strategy_advisor_output(
    advisor_output: dict[str, Any],
    task_type: str,
    target_url: str = "",
) -> tuple[dict[str, Any], list[str], list[str]]:
    """Validate and filter strategy advisor output.

    Returns (safe_fields, accepted_keys, rejected_keys).
    """
    safe: dict[str, Any] = {}
    accepted: list[str] = []
    rejected: list[str] = []

    for key, value in advisor_output.items():
        if key not in _STRATEGY_ALLOWED_FIELDS:
            rejected.append(key)
            continue

        if key == "mode":
            if value not in _STRATEGY_ALLOWED_MODES:
                rejected.append(key)
                continue
            safe[key] = value
            accepted.append(key)

        elif key == "engine":
            engine = str(value).strip().lower()
            if engine not in _STRATEGY_ALLOWED_ENGINES:
                rejected.append(key)
                continue
            if engine == "fnspider" and task_type != "product_list":
                rejected.append(key)
                continue
            if engine == "fnspider" and not _can_use_fnspider(target_url):
                rejected.append(key)
                continue
            safe[key] = engine
            accepted.append(key)

        elif key == "wait_until":
            if value not in _STRATEGY_ALLOWED_WAIT_UNTIL:
                rejected.append(key)
                continue
            safe[key] = value
            accepted.append(key)

        elif key == "max_items":
            if not isinstance(value, int) or value <= 0:
                rejected.append(key)
                continue
            safe[key] = value
            accepted.append(key)

        elif key == "selectors":
            if not isinstance(value, dict):
                rejected.append(key)
                continue
            clean_selectors: dict[str, str] = {}
            for sel_key, sel_val in value.items():
                if sel_key not in _STRATEGY_ALLOWED_SELECTOR_KEYS:
                    rejected.append(f"selectors.{sel_key}")
                    continue
                if not isinstance(sel_val, str) or not sel_val.strip():
                    rejected.append(f"selectors.{sel_key}")
                    continue
                if len(sel_val) > 300:
                    rejected.append(f"selectors.{sel_key}")
                    continue
                if any(c < "\x20" for c in sel_val):
                    rejected.append(f"selectors.{sel_key}")
                    continue
                clean_selectors[sel_key] = sel_val
            if clean_selectors:
                safe[key] = clean_selectors

        elif key == "wait_selector":
            if not isinstance(value, str) or not value.strip():
                rejected.append(key)
                continue
            if len(value) > 300:
                rejected.append(key)
                continue
            safe[key] = value
            accepted.append(key)

        else:
            safe[key] = value
            accepted.append(key)

    return safe, accepted, rejected


def _merge_strategy_advisor_fields(
    strategy: dict[str, Any],
    safe_fields: dict[str, Any],
) -> tuple[dict[str, Any], list[str], list[str]]:
    """Merge safe advisor fields without clobbering strong deterministic data."""
    merged = dict(strategy)
    accepted: list[str] = []
    rejected: list[str] = []

    for key, value in safe_fields.items():
        if key == "selectors":
            existing = dict(merged.get("selectors") or {})
            selector_updates: dict[str, str] = value
            for selector_key, selector_value in selector_updates.items():
                current = existing.get(selector_key, "")
                if _can_replace_selector(selector_key, current):
                    existing[selector_key] = selector_value
                    accepted.append(f"selectors.{selector_key}")
                else:
                    rejected.append(f"selectors.{selector_key} (kept deterministic)")
            merged["selectors"] = existing

        elif key == "mode":
            current_mode = merged.get("mode")
            if current_mode == value or _mode_can_be_replaced(current_mode, value):
                merged[key] = value
                accepted.append(key)
            else:
                rejected.append(f"{key} (kept deterministic)")

        elif key == "engine":
            if not merged.get("engine"):
                merged[key] = value
                accepted.append(key)
            elif merged.get("engine") == value:
                accepted.append(key)
            else:
                rejected.append(f"{key} (kept deterministic)")

        elif key == "max_items":
            current_max = int(merged.get("max_items", 0) or 0)
            if current_max <= 0 or current_max == value:
                merged[key] = value
                accepted.append(key)
            else:
                rejected.append(f"{key} (kept deterministic)")

        elif key in {"wait_selector", "wait_until"}:
            if not merged.get(key) or merged.get(key) == value:
                merged[key] = value
                accepted.append(key)
            else:
                rejected.append(f"{key} (kept deterministic)")

        elif key == "reasoning_summary":
            merged["advisor_reasoning_summary"] = value
            accepted.append(key)

    return merged, accepted, rejected


def _can_replace_selector(selector_key: str, current: str) -> bool:
    """Return whether an advisor selector can fill/replace a selector."""
    if not current:
        return True
    if _FALLBACK_SELECTORS.get(selector_key) == current:
        return True
    return False


def _mode_can_be_replaced(current: Any, suggested: Any) -> bool:
    """Allow advisor mode upgrades only from deterministic fallback HTTP."""
    if not current:
        return True
    if current == suggested:
        return True
    return current == "http" and suggested == "browser"


def make_strategy_node(
    advisor: StrategyAdvisor | None = None,
) -> Callable[[dict[str, Any]], dict[str, Any]]:
    """Return a strategy node, optionally wrapping a strategy advisor.

    When no advisor is provided, the returned node is equivalent to
    ``strategy_node`` but always emits the LLM audit state fields.
    """

    def _node(state: dict[str, Any]) -> dict[str, Any]:
        result = strategy_node(state)

        existing_decisions: list[dict[str, Any]] = list(
            state.get("llm_decisions") or []
        )
        existing_errors: list[str] = list(state.get("llm_errors") or [])

        if advisor is None:
            result["llm_enabled"] = state.get("llm_enabled", False)
            result["llm_decisions"] = existing_decisions
            result["llm_errors"] = existing_errors
            return result

        result["llm_enabled"] = True
        decisions = existing_decisions
        errors = existing_errors

        recon_report = state.get("recon_report", {})
        planner_output = {
            "task_id": state.get("task_id"),
            "recon_report": recon_report,
            "user_goal": state.get("user_goal", ""),
        }

        try:
            advisor_output = advisor.choose_strategy(planner_output, recon_report)
            task_type = recon_report.get("task_type", "product_list")
            safe_fields, _validation_accepted, validation_rejected = _validate_strategy_advisor_output(
                advisor_output,
                task_type,
                recon_report.get("target_url", state.get("target_url", "")),
            )

            strategy = result.get("crawl_strategy", {})
            strategy, merge_accepted, merge_rejected = _merge_strategy_advisor_fields(
                strategy,
                safe_fields,
            )
            result["crawl_strategy"] = strategy
            accepted = merge_accepted
            rejected = validation_rejected + merge_rejected

            decisions.append(build_decision_record(
                node="strategy",
                advisor=advisor,
                input_summary=f"task_type={task_type}",
                raw_response=advisor_output,
                parsed_decision=safe_fields,
                accepted_fields=accepted,
                rejected_fields=rejected,
                fallback_used=False,
            ))

        except Exception as exc:
            errors.append(f"strategy advisor: {exc}")
            decisions.append(build_decision_record(
                node="strategy",
                advisor=advisor,
                input_summary=f"task_type={recon_report.get('task_type', 'unknown')}",
                raw_response=str(exc),
                parsed_decision={},
                accepted_fields=[],
                rejected_fields=list(_STRATEGY_ALLOWED_FIELDS),
                fallback_used=True,
            ))

        result["llm_decisions"] = decisions
        result["llm_errors"] = errors
        return result

    return _node
