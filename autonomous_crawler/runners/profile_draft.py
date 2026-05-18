"""Browser/API evidence to SiteProfile draft converter.

Takes structured evidence from browser training, network observation, or
recon reports and produces a SiteProfile draft dict that can be saved as
JSON and loaded by profile_ecommerce runner.

Supports three evidence patterns:
- static DOM list/detail (selector_matches from HTML)
- observed API pagination (captured XHR/fetch with pagination params)
- mixed SSR + hydration API (HTML shell with API-driven content)

No site-specific logic lives here — all inference is generic.
"""
from __future__ import annotations

import re
from collections import Counter
from typing import Any
from urllib.parse import parse_qs, urlparse


# ---------------------------------------------------------------------------
# Required fields for a usable profile draft
# ---------------------------------------------------------------------------

REQUIRED_SELECTOR_FIELDS = frozenset({"title", "price", "image", "description"})
WEAK_SELECTOR_THRESHOLD = 2  # selector_matches count below this is weak


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def draft_profile_from_evidence(
    evidence: dict[str, Any],
    site_name: str = "",
) -> dict[str, Any]:
    """Convert browser/API evidence into a SiteProfile draft dict.

    Args:
        evidence: Structured evidence from browser training or recon.
            Expected keys (all optional):
            - url, final_url
            - selector_matches: dict[name, count]
            - network_candidates: {resource_counts, xhr_count, captured_xhr}
            - html_chars: int
            - rendered_item_count: int
            - scroll_events: list
            - failure_classification: dict
            - api_hints: list[dict] (from scout_page)
            - field_candidates: dict (from scout_page)
            - recon_report: dict (from recon)
        site_name: Override name. Falls back to domain from URL.

    Returns:
        SiteProfile-compatible dict with draft selectors, api_hints,
        pagination_hints, quality_expectations, training_notes, and
        profile_diagnostics.
    """
    url = evidence.get("url") or evidence.get("final_url") or ""
    name = site_name or _domain_as_name(url)

    selectors = _draft_selectors(evidence)
    api_hints = _draft_api_hints(evidence)
    pagination_hints = _draft_pagination_hints(evidence)
    quality_expectations = _draft_quality_expectations(evidence, selectors)
    crawl_preferences = _draft_crawl_preferences(evidence, api_hints)
    target_fields = _draft_target_fields(evidence, selectors)
    training_notes = _draft_training_notes(evidence)
    diagnostics = _draft_profile_diagnostics(
        evidence, selectors, api_hints, pagination_hints, target_fields,
    )

    profile: dict[str, Any] = {
        "name": name,
        "selectors": selectors,
        "target_fields": target_fields,
        "api_hints": api_hints,
        "pagination_hints": pagination_hints,
        "quality_expectations": quality_expectations,
        "training_notes": training_notes,
        "access_config": {},
        "rate_limits": {},
        "constraints": {},
        "crawl_preferences": crawl_preferences,
    }

    # Runnability assessment needs the full profile structure
    runnability = _assess_runnability(profile, evidence)
    diagnostics["runnability"] = runnability

    profile["profile_diagnostics"] = diagnostics
    return profile


# ---------------------------------------------------------------------------
# Evidence merge
# ---------------------------------------------------------------------------


def merge_evidence_sources(
    *sources: dict[str, Any],
    site_name: str = "",
) -> dict[str, Any]:
    """Merge multiple evidence sources into one consolidated evidence dict.

    Sources are merged in order. Later sources override earlier ones for
    scalar fields; dict fields are deep-merged; list fields are concatenated
    (deduplicated where possible). Conflicts are recorded in a
    ``_merge_conflicts`` key.

    Typical sources:
    - recon_report
    - browser scenario evidence
    - network_candidates / api_hints / field_candidates

    Returns:
        Consolidated evidence dict suitable for ``draft_profile_from_evidence``.
    """
    merged: dict[str, Any] = {}
    conflicts: list[str] = []

    for source in sources:
        if not isinstance(source, dict):
            continue
        for key, value in source.items():
            if key.startswith("_"):
                continue
            if key not in merged:
                merged[key] = _deep_copy_value(value)
                continue
            existing = merged[key]
            if isinstance(existing, dict) and isinstance(value, dict):
                _merge_dicts(existing, value, path=key, conflicts=conflicts)
            elif isinstance(existing, list) and isinstance(value, list):
                merged[key] = _merge_lists(existing, value)
            else:
                # Scalar conflict: later wins
                if existing != value:
                    conflicts.append(f"{key}: {existing!r} -> {value!r}")
                merged[key] = value

    if conflicts:
        merged.setdefault("training_notes", [])
        for c in conflicts:
            merged["training_notes"].append(f"Merge conflict: {c}")
        merged["_merge_conflicts"] = conflicts

    if site_name:
        merged["_site_name"] = site_name
    return merged


def _deep_copy_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _deep_copy_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_deep_copy_value(v) for v in value]
    return value


def _merge_dicts(
    base: dict[str, Any],
    overlay: dict[str, Any],
    path: str,
    conflicts: list[str],
) -> None:
    for key, value in overlay.items():
        full_key = f"{path}.{key}"
        if key not in base:
            base[key] = _deep_copy_value(value)
        elif isinstance(base[key], dict) and isinstance(value, dict):
            _merge_dicts(base[key], value, full_key, conflicts)
        elif isinstance(base[key], list) and isinstance(value, list):
            base[key] = _merge_lists(base[key], value)
        else:
            if base[key] != value:
                conflicts.append(f"{full_key}: {base[key]!r} -> {value!r}")
            base[key] = value


def _merge_lists(base: list[Any], overlay: list[Any]) -> list[Any]:
    seen: set[str] = set()
    result: list[Any] = []
    for item in base + overlay:
        key = str(item)
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result


# ---------------------------------------------------------------------------
# Selector inference
# ---------------------------------------------------------------------------


def _draft_selectors(evidence: dict[str, Any]) -> dict[str, Any]:
    """Infer CSS selectors from selector_matches and field_candidates."""
    selectors: dict[str, Any] = {}

    # From recon_report inferred_selectors or profile_selectors
    recon = evidence.get("recon_report") or {}
    for recon_key in ("inferred_selectors", "profile_selectors"):
        recon_sels = recon.get(recon_key) or {}
        if isinstance(recon_sels, dict):
            for name, sel in recon_sels.items():
                if isinstance(sel, str) and sel:
                    selectors.setdefault(name, sel)

    # From training harness selector_matches
    selector_matches = evidence.get("selector_matches") or {}
    for name, count in selector_matches.items():
        if count > 0:
            selectors.setdefault(name, _selector_spec(name, count))

    # From scout_page field_candidates (higher quality)
    field_candidates = evidence.get("field_candidates") or {}
    for field_name, candidates in field_candidates.items():
        if not isinstance(candidates, list) or not candidates:
            continue
        best = max(candidates, key=lambda c: c.get("score", 0))
        sel = best.get("selector", "")
        if sel:
            selectors[field_name] = sel

    # From explicit selectors in evidence (e.g., from ScenarioDefinition)
    explicit = evidence.get("selectors") or {}
    for name, sel in explicit.items():
        if isinstance(sel, str) and sel:
            selectors.setdefault(name, sel)

    return selectors


def _selector_spec(name: str, count: int) -> str:
    """Build a selector spec string from a name and match count."""
    if name.startswith(".") or name.startswith("#"):
        return name
    if count > 1:
        return f".{name}"
    return f".{name}"


# ---------------------------------------------------------------------------
# Selector repair suggestions
# ---------------------------------------------------------------------------


def _suggest_selector_repairs(
    evidence: dict[str, Any],
    selectors: dict[str, Any],
    missing_fields: frozenset[str],
) -> dict[str, Any]:
    """Generate repair suggestions for missing fields.

    Returns dict with:
    - missing_fields: list of field names not covered by selectors
    - candidate_selectors: {field: [list of candidate selectors]}
    - candidate_api_paths: {field: [list of candidate JSON paths]}
    """
    repairs: dict[str, Any] = {
        "missing_fields": sorted(missing_fields),
        "candidate_selectors": {},
        "candidate_api_paths": {},
    }

    if not missing_fields:
        return repairs

    # Build selector candidates from field_candidates
    field_candidates = evidence.get("field_candidates") or {}
    for field in missing_fields:
        candidates: list[dict[str, Any]] = []
        # Direct match in field_candidates
        if field in field_candidates:
            for c in field_candidates[field]:
                if isinstance(c, dict) and c.get("selector"):
                    candidates.append({
                        "selector": c["selector"],
                        "score": c.get("score", 0),
                        "count": c.get("count", 0),
                        "source": "field_candidates",
                    })
        # Fuzzy match: check if any field_candidate key contains the field name
        for fc_name, fc_list in field_candidates.items():
            if fc_name == field:
                continue
            if field in fc_name.lower() or fc_name.lower() in field:
                for c in (fc_list if isinstance(fc_list, list) else []):
                    if isinstance(c, dict) and c.get("selector"):
                        candidates.append({
                            "selector": c["selector"],
                            "score": c.get("score", 0) * 0.8,  # penalty for fuzzy
                            "count": c.get("count", 0),
                            "source": f"field_candidates:{fc_name}",
                        })
        if candidates:
            candidates.sort(key=lambda c: c["score"], reverse=True)
            repairs["candidate_selectors"][field] = candidates[:5]

    # API path candidates from captured XHR
    network = evidence.get("network_candidates") or {}
    captured_xhr = network.get("captured_xhr") or []
    for field in missing_fields:
        api_candidates: list[dict[str, Any]] = []
        for entry in captured_xhr:
            if not isinstance(entry, dict):
                continue
            url = entry.get("url", "")
            content_type = entry.get("content_type", "")
            if "json" not in content_type.lower() and not url.endswith(".json"):
                continue
            # Guess JSON path from URL structure
            parsed = urlparse(url)
            path_parts = [p for p in parsed.path.split("/") if p]
            if any(field.lower() in p.lower() for p in path_parts):
                api_candidates.append({
                    "url": url,
                    "method": entry.get("method", "GET"),
                    "reason": f"URL path contains '{field}'",
                })
        if api_candidates:
            repairs["candidate_api_paths"][field] = api_candidates[:5]

    return repairs


# ---------------------------------------------------------------------------
# Profile diagnostics
# ---------------------------------------------------------------------------


def _draft_profile_diagnostics(
    evidence: dict[str, Any],
    selectors: dict[str, Any],
    api_hints: dict[str, Any],
    pagination_hints: dict[str, Any],
    target_fields: list[str],
) -> dict[str, Any]:
    """Generate profile diagnostics for draft quality assessment."""
    diagnostics: dict[str, Any] = {}

    # Missing fields
    selector_repairs = _suggest_selector_repairs(
        evidence, selectors, _find_missing_fields(selectors),
    )
    diagnostics["missing_fields"] = selector_repairs["missing_fields"]
    diagnostics["candidate_selectors"] = selector_repairs["candidate_selectors"]
    diagnostics["candidate_api_paths"] = selector_repairs["candidate_api_paths"]

    # Weak selectors
    weak: list[dict[str, Any]] = []
    selector_matches = evidence.get("selector_matches") or {}
    for name, sel in selectors.items():
        match_count = selector_matches.get(name, -1)
        if 0 < match_count < WEAK_SELECTOR_THRESHOLD:
            weak.append({"field": name, "selector": sel, "match_count": match_count})
    diagnostics["weak_selectors"] = weak

    # API candidate quality
    diagnostics["api_candidate_quality"] = _assess_api_quality(api_hints, evidence)

    # Pagination confidence
    diagnostics["pagination_confidence"] = _assess_pagination_confidence(pagination_hints, evidence)

    # Recommended next actions
    diagnostics["recommended_next_actions"] = _recommend_actions(
        diagnostics, selectors, api_hints, pagination_hints, evidence,
    )

    return diagnostics


def _find_missing_fields(selectors: dict[str, Any]) -> frozenset[str]:
    """Find required fields not covered by any selector."""
    normalized = {k.lower().replace("-", "_").replace(" ", "_") for k in selectors}
    missing: set[str] = set()
    for field in REQUIRED_SELECTOR_FIELDS:
        if not any(field in name for name in normalized):
            missing.add(field)
    return frozenset(missing)


def _assess_api_quality(
    api_hints: dict[str, Any],
    evidence: dict[str, Any],
) -> dict[str, Any]:
    """Assess quality of API candidates."""
    quality: dict[str, Any] = {"confidence": "none"}

    if not api_hints:
        return quality

    endpoint = api_hints.get("endpoint", "")
    fmt = api_hints.get("format", "")
    xhr_count = api_hints.get("xhr_count", 0)

    if endpoint and fmt == "json":
        quality["confidence"] = "high"
        quality["endpoint"] = endpoint
        quality["format"] = fmt
    elif endpoint:
        quality["confidence"] = "medium"
        quality["endpoint"] = endpoint
    elif xhr_count > 0:
        quality["confidence"] = "low"
        quality["xhr_count"] = xhr_count

    # Check if API returns structured data
    network = evidence.get("network_candidates") or {}
    captured_xhr = network.get("captured_xhr") or []
    json_xhr = sum(1 for e in captured_xhr
                   if isinstance(e, dict)
                   and ("json" in e.get("content_type", "").lower()
                        or e.get("url", "").endswith(".json")))
    if json_xhr > 0:
        quality["json_response_count"] = json_xhr

    return quality


def _assess_pagination_confidence(
    pagination_hints: dict[str, Any],
    evidence: dict[str, Any],
) -> dict[str, Any]:
    """Assess confidence in pagination detection."""
    assessment: dict[str, Any] = {"confidence": "none", "type": ""}

    if not pagination_hints:
        return assessment

    ptype = pagination_hints.get("type", "")
    assessment["type"] = ptype

    if ptype == "infinite_scroll":
        scroll_events = evidence.get("scroll_events") or []
        if len(scroll_events) >= 3:
            assessment["confidence"] = "high"
        elif scroll_events:
            assessment["confidence"] = "medium"
        else:
            assessment["confidence"] = "low"
    elif ptype in ("offset", "page", "cursor"):
        params = pagination_hints.get("params") or {}
        if params:
            assessment["confidence"] = "high"
            assessment["params"] = params
        else:
            assessment["confidence"] = "medium"
    else:
        assessment["confidence"] = "low"

    return assessment


def _recommend_actions(
    diagnostics: dict[str, Any],
    selectors: dict[str, Any],
    api_hints: dict[str, Any],
    pagination_hints: dict[str, Any],
    evidence: dict[str, Any],
) -> list[str]:
    """Generate recommended next actions based on diagnostics."""
    actions: list[str] = []

    missing = diagnostics.get("missing_fields") or []
    if missing:
        actions.append(f"Resolve missing fields: {', '.join(missing)}")

    weak = diagnostics.get("weak_selectors") or []
    if weak:
        fields = [w["field"] for w in weak]
        actions.append(f"Verify weak selectors (low match count): {', '.join(fields)}")

    api_quality = diagnostics.get("api_candidate_quality") or {}
    if api_quality.get("confidence") == "high":
        actions.append("Consider API-first crawl strategy for better data quality")
    elif api_quality.get("confidence") == "medium":
        actions.append("Review API endpoint candidates for structured data access")

    pag_conf = diagnostics.get("pagination_confidence") or {}
    if pag_conf.get("confidence") == "none":
        rendered = evidence.get("rendered_item_count", 0)
        if rendered > 0:
            actions.append("No pagination detected — verify if list is complete or needs scroll/page")

    candidate_selectors = diagnostics.get("candidate_selectors") or {}
    if candidate_selectors:
        fields = list(candidate_selectors.keys())[:3]
        actions.append(f"Review candidate selectors for: {', '.join(fields)}")

    if not selectors:
        actions.append("No selectors inferred — manual selector definition required")

    return actions


# ---------------------------------------------------------------------------
# API hints inference
# ---------------------------------------------------------------------------


def _draft_api_hints(evidence: dict[str, Any]) -> dict[str, Any]:
    """Infer API hints from captured XHR and network candidates."""
    api_hints: dict[str, Any] = {}

    # From recon_report constraints
    recon = evidence.get("recon_report") or {}
    recon_constraints = recon.get("constraints") or {}
    recon_api = recon_constraints.get("api_hints") or {}
    if isinstance(recon_api, dict) and recon_api.get("endpoint"):
        api_hints.setdefault("endpoint", recon_api["endpoint"])
        if recon_api.get("format"):
            api_hints.setdefault("format", recon_api["format"])

    network = evidence.get("network_candidates") or {}
    captured_xhr = network.get("captured_xhr") or []
    xhr_count = network.get("xhr_count", 0)

    # Also check api_hints from scout_page
    scout_api = evidence.get("api_hints") or []
    if isinstance(scout_api, list):
        for hint in scout_api:
            if isinstance(hint, dict) and hint.get("json_like"):
                api_hints.setdefault("endpoint", hint.get("url", ""))
                break

    if not captured_xhr and xhr_count == 0 and not api_hints:
        return api_hints

    # Analyze captured XHR for API patterns
    json_endpoints: list[str] = []
    get_endpoints: list[str] = []
    for entry in captured_xhr:
        if not isinstance(entry, dict):
            continue
        url = entry.get("url", "")
        method = entry.get("method", "GET").upper()
        content_type = entry.get("content_type", "")
        if not url:
            continue

        is_json = "json" in content_type.lower() or url.endswith(".json")
        if is_json:
            json_endpoints.append(url)
        if method == "GET":
            get_endpoints.append(url)

    if json_endpoints:
        api_hints.setdefault("endpoint", json_endpoints[0])
        api_hints.setdefault("format", "json")
        if len(json_endpoints) > 1:
            api_hints.setdefault("all_endpoints", json_endpoints[:10])
    elif get_endpoints:
        api_hints.setdefault("endpoint", get_endpoints[0])

    if xhr_count > 0:
        api_hints.setdefault("xhr_count", xhr_count)

    # Auto-detect items_path and field_mapping from captured response structure
    items_path = _infer_api_items_path(evidence)
    if items_path:
        api_hints.setdefault("items_path", items_path)
    field_mapping = _infer_api_field_mapping(evidence)
    if field_mapping:
        api_hints.setdefault("field_mapping", field_mapping)

    return api_hints


# ---------------------------------------------------------------------------
# Pagination hints inference
# ---------------------------------------------------------------------------


def _draft_pagination_hints(evidence: dict[str, Any]) -> dict[str, Any]:
    """Infer pagination from XHR params, scroll events, or URL patterns.

    Auto-detects page/limit, offset/limit, or cursor pagination from captured
    XHR URLs and generates the pagination_hints needed by initial_requests_from_profile().
    """
    pagination: dict[str, Any] = {}

    # From recon_report constraints
    recon = evidence.get("recon_report") or {}
    recon_constraints = recon.get("constraints") or {}
    recon_pagination = recon_constraints.get("pagination") or {}
    if isinstance(recon_pagination, dict) and recon_pagination:
        pagination.update(recon_pagination)

    # Check scroll events for infinite scroll pattern
    scroll_events = evidence.get("scroll_events") or []
    if scroll_events and not pagination.get("type"):
        pagination["type"] = "infinite_scroll"
        pagination["scroll_event_count"] = len(scroll_events)

    # Check explicit pagination_hints from evidence (overrides auto-detected)
    explicit = evidence.get("pagination_hints") or {}
    if isinstance(explicit, dict) and explicit:
        pagination.update(explicit)

    # Check captured XHR for pagination params — auto-detect type (fills gaps only)
    network = evidence.get("network_candidates") or {}
    captured_xhr = network.get("captured_xhr") or []
    inferred = _infer_pagination_from_xhr(captured_xhr)
    if inferred and not pagination.get("type"):
        pagination.update(inferred)

    return pagination


def _infer_pagination_from_xhr(captured_xhr: list[dict[str, Any]]) -> dict[str, Any]:
    """Auto-detect pagination type and params from captured XHR URLs.

    Returns pagination_hints compatible with initial_requests_from_profile():
    - page/limit: type="page", page_param, page_size, start_page
    - offset/limit: type="offset", offset_param, page_size, start_offset
    - cursor: type="cursor", cursor_param
    """
    if not captured_xhr:
        return {}

    param_counter: Counter[str] = Counter()
    sample_values: dict[str, str] = {}

    page_keys = {"page", "pagenum", "pagenumber", "page_number", "page_num", "p"}
    offset_keys = {"offset", "skip", "start"}
    limit_keys = {"limit", "per_page", "perpage", "page_size", "pagesize", "count", "size", "take"}
    cursor_keys = {"cursor", "after", "before", "next_token", "continuation", "pagination_token"}

    for entry in captured_xhr:
        if not isinstance(entry, dict):
            continue
        url = entry.get("url", "")
        if not url:
            continue
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        for key in params:
            lower = key.lower()
            if lower in page_keys | offset_keys | limit_keys | cursor_keys:
                param_counter[key] += 1
                sample_values.setdefault(key, params[key][0])

    if not param_counter:
        return {}

    # Determine pagination type
    detected_page = next((k for k in param_counter if k.lower() in page_keys), None)
    detected_offset = next((k for k in param_counter if k.lower() in offset_keys), None)
    detected_limit = next((k for k in param_counter if k.lower() in limit_keys), None)
    detected_cursor = next((k for k in param_counter if k.lower() in cursor_keys), None)

    if detected_page:
        hints: dict[str, Any] = {"type": "page", "page_param": detected_page}
        try:
            hints["start_page"] = int(sample_values.get(detected_page, "1"))
        except (ValueError, TypeError):
            hints["start_page"] = 1
        if detected_limit:
            hints["page_size_param"] = detected_limit
            try:
                hints["page_size"] = int(sample_values[detected_limit])
            except (ValueError, TypeError):
                pass
        return hints

    if detected_offset:
        hints = {"type": "offset", "offset_param": detected_offset}
        try:
            hints["start_offset"] = int(sample_values.get(detected_offset, "0"))
        except (ValueError, TypeError):
            hints["start_offset"] = 0
        if detected_limit:
            hints["page_size_param"] = detected_limit
            try:
                hints["page_size"] = int(sample_values[detected_limit])
            except (ValueError, TypeError):
                pass
        return hints

    if detected_cursor:
        hints = {"type": "cursor", "cursor_param": detected_cursor}
        if detected_limit:
            hints["limit_param"] = detected_limit
        return hints

    return {}


def _find_pagination_params(captured_xhr: list[dict[str, Any]]) -> dict[str, str]:
    """Scan XHR URLs for common pagination query parameters."""
    param_counter: Counter[str] = Counter()
    sample_values: dict[str, str] = {}

    pagination_param_names = {"page", "offset", "limit", "cursor", "skip", "start", "per_page", "pageSize", "pageNumber"}

    for entry in captured_xhr:
        if not isinstance(entry, dict):
            continue
        url = entry.get("url", "")
        if not url:
            continue
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        for key in params:
            if key.lower() in pagination_param_names:
                param_counter[key] += 1
                sample_values[key] = params[key][0]

    if not param_counter:
        return {}

    return {k: sample_values[k] for k, _ in param_counter.most_common(3)}


# ---------------------------------------------------------------------------
# API items_path and field_mapping inference
# ---------------------------------------------------------------------------


def _infer_api_items_path(evidence: dict[str, Any]) -> str:
    """Auto-detect the JSON path to the items array in an API response.

    Checks captured XHR responses for sample JSON bodies and finds the
    first array, returning a dot-separated path like "data.products".
    """
    network = evidence.get("network_candidates") or {}
    captured_xhr = network.get("captured_xhr") or []

    for entry in captured_xhr:
        if not isinstance(entry, dict):
            continue
        body = entry.get("body") or entry.get("response_body") or ""
        if not body or not isinstance(body, str):
            continue
        try:
            data = __import__("json").loads(body)
        except (ValueError, TypeError):
            continue
        if isinstance(data, list):
            return ""
        if isinstance(data, dict):
            path = _find_first_array_path(data)
            if path:
                return path
    return ""


def _find_first_array_path(data: dict[str, Any]) -> str:
    """Traverse nested dict to find the first list value, returning its dot path."""
    visited: set[int] = set()

    def _traverse(obj: Any, parts: list[str]) -> str:
        if isinstance(obj, list):
            return ".".join(parts)
        if not isinstance(obj, dict):
            return ""
        obj_id = id(obj)
        if obj_id in visited:
            return ""
        visited.add(obj_id)
        for key, value in obj.items():
            result = _traverse(value, parts + [key])
            if result:
                return result
        return ""

    return _traverse(data, [])


def _infer_api_field_mapping(evidence: dict[str, Any]) -> dict[str, str]:
    """Auto-detect field mapping from ProductRecord fields to API response keys.

    The mapping direction is ProductRecord field -> API key, matching how
    mapped_value() in profile_ecommerce uses it: mapping["title"] returns
    the API key to look up in the item dict.

    Example: {"title": "name", "price": "price", "image": "image_url"}
    """
    # API key -> ProductRecord field
    api_to_product = {
        "name": "title", "title": "title", "product_name": "title",
        "price": "price", "amount": "price", "cost": "price",
        "description": "description", "desc": "description", "body": "description",
        "image": "image", "image_url": "image", "image_src": "image",
        "images": "image_urls", "image_urls": "image_urls",
        "url": "canonical_url", "link": "canonical_url", "href": "canonical_url",
        "category": "category", "sku": "sku", "rating": "rating",
        "color": "colors", "colors": "colors", "colour": "colors",
        "size": "sizes", "sizes": "sizes",
    }

    network = evidence.get("network_candidates") or {}
    captured_xhr = network.get("captured_xhr") or []

    for entry in captured_xhr:
        if not isinstance(entry, dict):
            continue
        body = entry.get("body") or entry.get("response_body") or ""
        if not body or not isinstance(body, str):
            continue
        try:
            data = __import__("json").loads(body)
        except (ValueError, TypeError):
            continue

        items = _extract_array_from_response(data)
        if not items or not isinstance(items[0], dict):
            continue

        item_keys = set(items[0].keys())
        # Build reverse mapping: ProductRecord field -> API key
        mapping: dict[str, str] = {}
        for key in item_keys:
            normalized = key.lower().strip().replace("-", "_").replace(" ", "_")
            if normalized in api_to_product:
                product_field = api_to_product[normalized]
                mapping[product_field] = key
        if mapping:
            return mapping

    return {}


def _extract_array_from_response(data: Any) -> list[Any]:
    """Extract the first array from a nested API response."""
    if isinstance(data, list):
        return data
    if not isinstance(data, dict):
        return []
    visited: set[int] = set()

    def _find(obj: Any) -> list[Any]:
        if isinstance(obj, list):
            return obj
        if not isinstance(obj, dict):
            return []
        obj_id = id(obj)
        if obj_id in visited:
            return []
        visited.add(obj_id)
        for value in obj.values():
            result = _find(value)
            if result:
                return result
        return []

    return _find(data)


# ---------------------------------------------------------------------------
# Runnable diagnostics
# ---------------------------------------------------------------------------


def _assess_runnability(
    profile: dict[str, Any],
    evidence: dict[str, Any],
) -> dict[str, Any]:
    """Assess whether a draft profile is runnable as a long-run crawl.

    Returns dict with:
    - loadable: whether SiteProfile.from_dict() would succeed
    - has_seed_requests: whether initial_requests_from_profile() would produce requests
    - longrun_candidate: whether the profile is suitable for ProfileLongRunExecutor
    - blocking_reasons: list of reasons preventing execution
    """
    loadable = True
    blocking: list[str] = []

    # Check loadability — try constructing a SiteProfile
    try:
        from autonomous_crawler.runners.site_profile import SiteProfile
        SiteProfile.from_dict(profile)
    except Exception:
        loadable = False
        blocking.append("profile_not_loadable")

    has_seed = False
    if loadable:
        # Check for API seed
        api_hints = profile.get("api_hints") or {}
        endpoint = str(api_hints.get("endpoint") or "").strip()
        pagination = profile.get("pagination_hints") or {}
        ptype = str(pagination.get("type") or pagination.get("mode") or "").strip().lower()
        has_api_seed = bool(endpoint and ptype in {"page", "offset", "cursor"})

        # Check for DOM seed
        crawl_prefs = profile.get("crawl_preferences") or {}
        seed_urls = crawl_prefs.get("seed_urls") or []
        has_dom_seed = bool(seed_urls and any(str(u).strip().startswith(("http://", "https://")) for u in seed_urls))

        has_seed = has_api_seed or has_dom_seed
        if not has_seed:
            blocking.append("no_seed_requests")
            if not endpoint and not seed_urls:
                blocking.append("no_endpoint_or_seed_urls")
            elif endpoint and ptype not in {"page", "offset", "cursor"}:
                blocking.append(f"unsupported_pagination_type:{ptype or 'none'}")

    return {
        "loadable": loadable,
        "has_seed_requests": has_seed,
        "longrun_candidate": loadable and has_seed and not blocking,
        "blocking_reasons": blocking,
    }


# ---------------------------------------------------------------------------
# Quality expectations
# ---------------------------------------------------------------------------


def _draft_quality_expectations(
    evidence: dict[str, Any],
    selectors: dict[str, Any],
) -> dict[str, Any]:
    """Generate quality expectations from evidence.

    Conservative approach: only declare expectations when evidence supports them.
    """
    quality: dict[str, Any] = {}

    rendered = evidence.get("rendered_item_count", 0)
    if rendered > 0:
        quality["min_items_expected"] = rendered
        quality["item_count_observed"] = rendered

    html_chars = evidence.get("html_chars", 0)
    if html_chars > 0:
        quality["html_size_observed"] = html_chars

    # Infer category from URL or selectors
    url = evidence.get("url") or evidence.get("final_url") or ""
    category = _infer_category(url, evidence)
    if category:
        quality["category"] = category

    # Required fields from selectors
    if selectors:
        normalized_selectors = {
            k.lower().replace("-", "_").replace(" ", "_"): v
            for k, v in selectors.items()
        }
        present_fields = set()
        for field in REQUIRED_SELECTOR_FIELDS:
            if any(field in name for name in normalized_selectors):
                present_fields.add(field)
        if present_fields:
            quality["required_fields"] = sorted(present_fields)

    # Field thresholds: only declare for fields with selector_matches evidence
    selector_matches = evidence.get("selector_matches") or {}
    field_thresholds: dict[str, int] = {}
    for name, count in selector_matches.items():
        if count > 0:
            normalized = name.lower().replace("-", "_").replace(" ", "_")
            for known in REQUIRED_SELECTOR_FIELDS:
                if known in normalized:
                    field_thresholds[name] = max(1, count // 2)
                    break
    if field_thresholds:
        quality["field_thresholds"] = field_thresholds

    return quality


def _draft_crawl_preferences(
    evidence: dict[str, Any],
    api_hints: dict[str, Any],
) -> dict[str, Any]:
    """Generate executable crawl preferences from evidence.

    A draft profile should not merely be loadable; it should preserve the
    observed URL as an initial list seed whenever there is a browser/HTML source.
    API-first profiles still rely on `api_hints.endpoint` plus pagination hints.
    """
    preferences: dict[str, Any] = {}
    source_url = str(evidence.get("url") or evidence.get("final_url") or "").strip()
    if source_url.startswith(("http://", "https://")):
        preferences["seed_urls"] = [source_url]
        preferences["seed_kind"] = "list"
        if api_hints.get("endpoint"):
            preferences["include_seed_urls_with_api"] = False
    return preferences


def _infer_category(url: str, evidence: dict[str, Any]) -> str:
    """Infer a product/content category from URL patterns."""
    url_lower = url.lower()
    category_hints = {
        "product": ["product", "shop", "store", "item", "buy"],
        "article": ["article", "post", "blog", "news", "read"],
        "listing": ["list", "search", "catalog", "category"],
        "documentation": ["docs", "doc", "api", "reference", "guide"],
    }
    for cat, keywords in category_hints.items():
        if any(kw in url_lower for kw in keywords):
            return cat
    return ""


# ---------------------------------------------------------------------------
# Target fields
# ---------------------------------------------------------------------------


def _draft_target_fields(
    evidence: dict[str, Any],
    selectors: dict[str, Any],
) -> list[str]:
    """Infer target fields from selectors and evidence."""
    fields: list[str] = []

    # From recon_report target_fields
    recon = evidence.get("recon_report") or {}
    recon_fields = recon.get("target_fields") or []
    if isinstance(recon_fields, list):
        for f in recon_fields:
            if isinstance(f, str) and f and f not in fields:
                fields.append(f)

    # Common product/content field names
    known_fields = {
        "title", "name", "price", "description", "image", "image_src",
        "image_urls", "url", "link", "category", "rating", "review_count",
        "color", "colors", "size", "sizes", "highest_price",
        "body", "content", "date", "author",
    }

    for name in selectors:
        if name in fields:
            continue
        normalized = name.lower().replace("-", "_").replace(" ", "_")
        for known in known_fields:
            if known in normalized:
                fields.append(name)
                break

    # From field_candidates
    field_candidates = evidence.get("field_candidates") or {}
    for name in field_candidates:
        if name not in fields:
            fields.append(name)

    return fields


# ---------------------------------------------------------------------------
# Training notes
# ---------------------------------------------------------------------------


def _draft_training_notes(evidence: dict[str, Any]) -> list[str]:
    """Generate training notes summarizing evidence quality."""
    notes: list[str] = []

    # Preserve merge-conflict notes from merge_evidence_sources
    existing_notes = evidence.get("training_notes") or []
    for note in existing_notes:
        if isinstance(note, str) and note.startswith("Merge conflict:"):
            notes.append(note)

    stop_reason = evidence.get("stop_reason", "completed")
    if stop_reason != "completed":
        notes.append(f"Training stopped: {stop_reason}")

    failure = evidence.get("failure_classification") or {}
    fail_cat = failure.get("category", "none")
    if fail_cat != "none":
        notes.append(f"Failure category: {fail_cat}")

    rendered = evidence.get("rendered_item_count", 0)
    if rendered == 0:
        notes.append("No items rendered — selectors may need manual review")
    elif rendered < 5:
        notes.append(f"Only {rendered} items rendered — check pagination or scroll")

    network = evidence.get("network_candidates") or {}
    xhr_count = network.get("xhr_count", 0)
    if xhr_count > 0:
        notes.append(f"Observed {xhr_count} XHR/fetch requests — API hints may be available")

    scroll_events = evidence.get("scroll_events") or []
    if scroll_events:
        notes.append(f"Scroll training produced {len(scroll_events)} events")

    return notes


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------


def _domain_as_name(url: str) -> str:
    """Convert URL to a profile name."""
    if not url:
        return "draft-profile"
    parsed = urlparse(url)
    domain = parsed.netloc or parsed.path.split("/")[0]
    domain = domain.replace("www.", "")
    return domain.replace(".", "-") or "draft-profile"
