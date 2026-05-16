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
        site_name: Override name. Falls back to domain from URL.

    Returns:
        SiteProfile-compatible dict with draft selectors, api_hints,
        pagination_hints, quality_expectations, and training_notes.
    """
    url = evidence.get("url") or evidence.get("final_url") or ""
    name = site_name or _domain_as_name(url)

    selectors = _draft_selectors(evidence)
    api_hints = _draft_api_hints(evidence)
    pagination_hints = _draft_pagination_hints(evidence)
    quality_expectations = _draft_quality_expectations(evidence)
    crawl_preferences = _draft_crawl_preferences(evidence, api_hints)
    target_fields = _draft_target_fields(evidence, selectors)
    training_notes = _draft_training_notes(evidence)

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
    return profile


# ---------------------------------------------------------------------------
# Selector inference
# ---------------------------------------------------------------------------


def _draft_selectors(evidence: dict[str, Any]) -> dict[str, Any]:
    """Infer CSS selectors from selector_matches and field_candidates."""
    selectors: dict[str, Any] = {}

    # From training harness selector_matches
    selector_matches = evidence.get("selector_matches") or {}
    for name, count in selector_matches.items():
        if count > 0:
            selectors[name] = _selector_spec(name, count)

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
# API hints inference
# ---------------------------------------------------------------------------


def _draft_api_hints(evidence: dict[str, Any]) -> dict[str, Any]:
    """Infer API hints from captured XHR and network candidates."""
    api_hints: dict[str, Any] = {}

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

    if not captured_xhr and xhr_count == 0:
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
        api_hints["endpoint"] = json_endpoints[0]
        api_hints["format"] = "json"
        if len(json_endpoints) > 1:
            api_hints["all_endpoints"] = json_endpoints[:10]
    elif get_endpoints:
        api_hints["endpoint"] = get_endpoints[0]

    if xhr_count > 0:
        api_hints["xhr_count"] = xhr_count

    return api_hints


# ---------------------------------------------------------------------------
# Pagination hints inference
# ---------------------------------------------------------------------------


def _draft_pagination_hints(evidence: dict[str, Any]) -> dict[str, Any]:
    """Infer pagination from XHR params, scroll events, or URL patterns."""
    pagination: dict[str, Any] = {}

    # Check scroll events for infinite scroll pattern
    scroll_events = evidence.get("scroll_events") or []
    if scroll_events:
        pagination["type"] = "infinite_scroll"
        pagination["scroll_event_count"] = len(scroll_events)

    # Check captured XHR for pagination params
    network = evidence.get("network_candidates") or {}
    captured_xhr = network.get("captured_xhr") or []
    page_params = _find_pagination_params(captured_xhr)
    if page_params:
        if not pagination.get("type"):
            pagination["type"] = "offset"
        pagination["params"] = page_params

    # Check explicit pagination_hints from evidence
    explicit = evidence.get("pagination_hints") or {}
    if isinstance(explicit, dict) and explicit:
        pagination.update(explicit)

    return pagination


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
# Quality expectations
# ---------------------------------------------------------------------------


def _draft_quality_expectations(evidence: dict[str, Any]) -> dict[str, Any]:
    """Generate quality expectations from evidence."""
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

    # Common product/content field names
    known_fields = {
        "title", "name", "price", "description", "image", "image_src",
        "image_urls", "url", "link", "category", "rating", "review_count",
        "color", "colors", "size", "sizes", "highest_price",
        "body", "content", "date", "author",
    }

    for name in selectors:
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
