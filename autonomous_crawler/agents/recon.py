"""Recon Agent - Analyzes target website structure.

Responsibilities (README Section 7):
- Detect frontend framework
- Detect SPA / SSR
- Discover APIs / XHR / GraphQL
- Detect anti-bot
- Analyze DOM / pagination

Tools (README Section 10):
- detect_framework()
- discover_api_endpoints()
- detect_anti_bot()
- analyze_dom_structure()
"""
from __future__ import annotations

from typing import Any

from .base import preserve_state
from ..errors import FETCH_HTTP_ERROR, FETCH_UNSUPPORTED_SCHEME, RECON_FAILED, format_error_entry
from ..tools.html_recon import build_recon_report, fetch_best_html
from ..tools.api_candidates import build_direct_json_candidate, build_graphql_candidate
from ..tools.browser_network_observer import observe_browser_network


@preserve_state
def recon_node(state: dict[str, Any]) -> dict[str, Any]:
    """Recon the target URL and produce a recon_report.

    This MVP implementation uses deterministic local HTML heuristics. It can be
    replaced or enriched with MCP crawler recon tools without changing the
    downstream Strategy contract.
    """
    target_url = state.get("target_url", "")
    existing_report = state.get("recon_report", {})

    configured_report = _configured_api_recon_report(target_url, existing_report)
    if configured_report:
        return {
            "status": "recon_done",
            "recon_report": configured_report,
            "messages": state.get("messages", []) + [
                (
                    f"[Recon] Using configured API target {target_url} - "
                    f"method={configured_report['api_candidates'][0].get('method', 'GET')}, "
                    "fetch_mode=configured_api"
                )
            ],
        }

    fetch_result = fetch_best_html(target_url)
    if fetch_result.error:
        error_msg = fetch_result.error
        if "unsupported scheme" in error_msg.lower():
            error_code = FETCH_UNSUPPORTED_SCHEME
        else:
            error_code = FETCH_HTTP_ERROR
        return {
            "status": "recon_failed",
            "recon_report": {
                **existing_report,
                "target_url": target_url,
                "recon_error": error_msg,
            },
            "error_code": error_code,
            "error_log": state.get("error_log", []) + [
                format_error_entry(error_code, f"Recon fetch failed: {error_msg}")
            ],
            "messages": state.get("messages", []) + [
                f"[Recon] Failed to fetch {target_url}: {error_msg}"
            ],
        }

    inferred_report = build_recon_report(fetch_result.url, fetch_result.html)
    recon_report = {
        **existing_report,
        **inferred_report,
        "fetch": {
            "status_code": fetch_result.status_code,
            "html_chars": len(fetch_result.html),
            "selected_mode": fetch_result.mode,
            "selected_score": fetch_result.score,
        },
        "fetch_trace": fetch_result.to_trace(),
    }
    network_messages: list[str] = []
    if _should_observe_network(existing_report, target_url):
        observation = observe_browser_network(target_url)
        observation_dict = observation.to_dict()
        recon_report["network_observation"] = observation_dict
        if observation.api_candidates:
            recon_report["api_candidates"] = _merge_api_candidates(
                recon_report.get("api_candidates", []),
                observation.api_candidates,
            )
        network_messages.append(
            (
                "[Recon] Network observation "
                f"status={observation.status}, "
                f"entries={len(observation.entries)}, "
                f"api_candidates={len(observation.api_candidates)}"
            )
        )

    return {
        "status": "recon_done",
        "recon_report": recon_report,
        "messages": state.get("messages", []) + [
            (
                f"[Recon] Analyzed {target_url} - "
                f"framework={recon_report['frontend_framework']}, "
                f"items={recon_report['dom_structure'].get('item_count', 0)}, "
                f"anti_bot={recon_report['anti_bot']['detected']}, "
                f"fetch_mode={fetch_result.mode}"
            )
        ] + network_messages,
    }


def _should_observe_network(existing_report: dict[str, Any], target_url: str) -> bool:
    constraints = existing_report.get("constraints") or {}
    if not constraints.get("observe_network"):
        return False
    return target_url.startswith(("http://", "https://"))


def _merge_api_candidates(
    existing: list[dict[str, Any]],
    observed: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for candidate in list(existing or []) + list(observed or []):
        url = str(candidate.get("url", ""))
        method = str(candidate.get("method", "GET")).upper()
        if not url:
            continue
        key = (method, url)
        current = by_key.get(key)
        if current is None or int(candidate.get("score") or 0) > int(current.get("score") or 0):
            by_key[key] = candidate
    return sorted(by_key.values(), key=lambda item: int(item.get("score") or 0), reverse=True)


def _configured_api_recon_report(
    target_url: str,
    existing_report: dict[str, Any],
) -> dict[str, Any]:
    """Build recon output for caller-supplied API/GraphQL settings.

    This avoids wasting time rendering an API playground or docs page when the
    caller already provided the endpoint/query through constraints.
    """
    constraints = existing_report.get("constraints") or {}
    graphql_query = constraints.get("graphql_query")
    explicit_api_endpoint = constraints.get("api_endpoint")

    if not graphql_query and not explicit_api_endpoint:
        return {}

    endpoint = str(explicit_api_endpoint or target_url)
    if graphql_query:
        candidate = build_graphql_candidate(
            endpoint,
            query=str(graphql_query),
            variables=constraints.get("graphql_variables") or {},
        )
        framework = "graphql"
        finding = "explicit_graphql_query"
    else:
        candidate = build_direct_json_candidate(endpoint)
        framework = "api"
        finding = "explicit_api_endpoint"

    return {
        **existing_report,
        "target_url": target_url,
        "frontend_framework": framework,
        "rendering": "api",
        "anti_bot": {"detected": False, "type": "none", "severity": "low", "indicators": []},
        "api_endpoints": [endpoint],
        "api_candidates": [candidate],
        "dom_structure": {
            "is_product_list": False,
            "has_pagination": False,
            "pagination_type": "none",
            "product_selector": "",
            "item_count": 0,
            "field_selectors": {},
            "candidates": [],
        },
        "access_diagnostics": {
            "findings": [finding],
            "signals": {"api_hints": [endpoint], "challenge": ""},
            "recommendation": "api_direct",
        },
        "fetch": {
            "status_code": None,
            "html_chars": 0,
            "selected_mode": "configured_api",
            "selected_score": 100,
        },
        "fetch_trace": {
            "selected_mode": "configured_api",
            "selected_url": endpoint,
            "selected_score": 100,
            "attempts": [],
            "error": "",
        },
    }
