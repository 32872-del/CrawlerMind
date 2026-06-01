"""Promote observed XHR/API evidence into executable SiteProfile patches."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import parse_qs, urlparse, urlunparse

from autonomous_crawler.tools.replay_diagnostics import build_replay_diagnostics

from .profile_draft import draft_profile_from_evidence


PRODUCT_URL_TOKENS = (
    "product", "products", "catalog", "category", "categories", "collection",
    "collections", "search", "items", "listing", "graphql",
)


@dataclass(frozen=True)
class APIReplayPromotion:
    promoted: bool
    confidence: float = 0.0
    reason: str = ""
    candidate: dict[str, Any] = field(default_factory=dict)
    profile_patch: dict[str, Any] = field(default_factory=dict)
    rejected_reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "api-replay-promotion/v1",
            "promoted": self.promoted,
            "confidence": round(float(self.confidence), 4),
            "reason": self.reason,
            "candidate": dict(self.candidate),
            "profile_patch": dict(self.profile_patch),
            "rejected_reasons": list(self.rejected_reasons),
        }


def promote_api_replay_from_access_evidence(
    evidence: dict[str, Any] | None,
    *,
    target_url: str = "",
    selected_fields: list[str] | None = None,
    min_confidence: float = 0.62,
) -> APIReplayPromotion:
    """Turn access-probe XHR samples into a runnable API profile patch.

    The access probe stores compact XHR samples for frontend visibility. This
    helper normalizes those samples back into the evidence shape understood by
    profile_draft, ranks product-like API candidates, and emits a bounded
    SiteProfile patch that can be applied to a managed child rerun.
    """
    evidence = evidence if isinstance(evidence, dict) else {}
    samples = _collect_xhr_samples(evidence)
    if not samples:
        return APIReplayPromotion(False, reason="no_xhr_samples", rejected_reasons=["no_xhr_samples"])

    candidates = [_score_xhr_sample(sample) for sample in samples]
    candidates = [item for item in candidates if item.get("url")]
    candidates.sort(key=lambda item: item["score"], reverse=True)
    if not candidates:
        return APIReplayPromotion(False, reason="no_usable_xhr_samples", rejected_reasons=["no_usable_xhr_samples"])

    best = candidates[0]
    confidence = min(0.99, max(0.0, float(best["score"]) / 100.0))
    if confidence < min_confidence:
        return APIReplayPromotion(
            False,
            confidence=confidence,
            reason="candidate_confidence_below_threshold",
            candidate=_safe_candidate(best),
            rejected_reasons=["candidate_confidence_below_threshold"],
        )

    draft_evidence = _draft_evidence_from_candidate(best, target_url=target_url)
    draft = draft_profile_from_evidence(draft_evidence, site_name=_site_name(target_url or best["url"]))
    api_hints = dict(draft.get("api_hints") or {})
    pagination_hints = dict(draft.get("pagination_hints") or {})
    if not api_hints.get("endpoint"):
        api_hints["endpoint"] = _url_without_pagination(best["url"], pagination_hints)
    else:
        api_hints["endpoint"] = _url_without_pagination(str(api_hints["endpoint"]), pagination_hints)
    method = str(best.get("method") or "GET").upper()
    post_json = best.get("post_json") if isinstance(best.get("post_json"), dict) else None
    is_graphql = _looks_like_graphql(best["url"], post_json)
    api_hints["method"] = method
    api_hints["format"] = "graphql" if is_graphql else str(api_hints.get("format") or "json")
    if is_graphql:
        api_hints["kind"] = "graphql"
    elif method == "POST":
        api_hints.setdefault("kind", "api")
    if post_json is not None:
        api_hints["post_json"] = post_json
    elif str(best.get("post_data") or "").strip():
        api_hints.setdefault("post_data", str(best.get("post_data"))[:4000])
    if isinstance(best.get("request_headers"), dict):
        headers = _safe_replay_headers(best["request_headers"])
        if headers:
            api_hints["headers"] = headers
    replay_diagnostics = build_replay_diagnostics(
        url=str(best.get("url") or ""),
        method=method,
        headers=best.get("request_headers") if isinstance(best.get("request_headers"), dict) else {},
        post_json=post_json,
        post_data=str(best.get("post_data") or ""),
    ).to_dict()
    if replay_diagnostics.get("replay_required"):
        api_hints["replay_diagnostics"] = replay_diagnostics
    if not pagination_hints.get("type"):
        pagination_hints["type"] = "none"
    if post_json is not None:
        pagination_hints.update({
            key: value
            for key, value in _infer_json_body_pagination_hints(post_json).items()
        if key not in pagination_hints or not pagination_hints.get(key) or (key == "type" and pagination_hints.get(key) == "none")
        })
        if pagination_hints.get("json_page_path") and not pagination_hints.get("type"):
            pagination_hints["type"] = "page"
        elif pagination_hints.get("json_cursor_path") and pagination_hints.get("type") in {"", "none"}:
            pagination_hints["type"] = "cursor"

    target_fields = [str(item).strip() for item in (selected_fields or []) if str(item).strip()]
    if not target_fields:
        target_fields = list(draft.get("target_fields") or [])

    patch: dict[str, Any] = {
        "api_hints": _clean_api_hints(api_hints),
        "pagination_hints": _clean_pagination_hints(pagination_hints),
        "crawl_preferences": {
            "seed_kind": "api",
            "seed_urls": [api_hints["endpoint"]],
            "include_seed_urls_with_api": False,
        },
        "access_config": {
            "mode": "static",
            "browser_config": {
                "capture_api": True,
            },
        },
    }
    if target_fields:
        patch["target_fields"] = target_fields[:50]
        patch["quality_expectations"] = {
            "required_fields": ["title"] if "title" in target_fields else target_fields[:3],
            "min_field_coverage": 0.65,
        }

    return APIReplayPromotion(
        True,
        confidence=confidence,
        reason="product_like_json_xhr_promoted_to_api_profile",
        candidate=_safe_candidate(best),
        profile_patch=patch,
    )


def _collect_xhr_samples(evidence: dict[str, Any]) -> list[dict[str, Any]]:
    samples: list[dict[str, Any]] = []

    def add_many(values: Any) -> None:
        if isinstance(values, list):
            for item in values:
                if isinstance(item, dict):
                    samples.append(_normalize_xhr_sample(item))

    add_many(evidence.get("xhr_samples"))
    add_many(evidence.get("captured_xhr"))
    snapshot = evidence.get("snapshot") if isinstance(evidence.get("snapshot"), dict) else {}
    add_many(snapshot.get("xhr_samples"))
    add_many(snapshot.get("captured_xhr"))
    probe_snapshot = evidence.get("probe_snapshot") if isinstance(evidence.get("probe_snapshot"), dict) else {}
    add_many(probe_snapshot.get("xhr_samples"))
    base_snapshot = evidence.get("base_snapshot") if isinstance(evidence.get("base_snapshot"), dict) else {}
    add_many(base_snapshot.get("xhr_samples"))
    network = evidence.get("network_candidates") if isinstance(evidence.get("network_candidates"), dict) else {}
    add_many(network.get("captured_xhr"))

    seen: set[str] = set()
    output: list[dict[str, Any]] = []
    for sample in samples:
        key = f"{sample.get('method')} {sample.get('url')} {sample.get('preview')[:80]}"
        if sample.get("url") and key not in seen:
            seen.add(key)
            output.append(sample)
    return output[:30]


def _normalize_xhr_sample(value: dict[str, Any]) -> dict[str, Any]:
    body = value.get("body") or value.get("response_body") or value.get("body_preview") or value.get("json_preview") or value.get("preview") or ""
    if isinstance(body, (dict, list)):
        body_text = json.dumps(body, ensure_ascii=False)
    else:
        body_text = str(body or "")
    post_data = value.get("post_data") or value.get("post_data_preview") or value.get("request_body") or ""
    post_json = _parse_json_like(post_data) if isinstance(post_data, str) else post_data if isinstance(post_data, dict) else None
    request_headers = value.get("request_headers") if isinstance(value.get("request_headers"), dict) else {}
    return {
        "url": str(value.get("url") or "")[:1000],
        "method": str(value.get("method") or "GET").upper()[:12],
        "status": value.get("status_code") or value.get("status"),
        "content_type": str(value.get("content_type") or value.get("mime_type") or "")[:200],
        "body": body_text,
        "preview": body_text[:2000],
        "post_data": post_data,
        "post_json": post_json,
        "request_headers": _safe_replay_headers(request_headers),
    }


def _score_xhr_sample(sample: dict[str, Any]) -> dict[str, Any]:
    score = 0
    reasons: list[str] = []
    url = str(sample.get("url") or "")
    lowered_url = url.lower()
    content_type = str(sample.get("content_type") or "").lower()
    body = str(sample.get("body") or sample.get("preview") or "")
    parsed_body = _parse_json_like(body)
    items = _extract_first_array(parsed_body)

    if "json" in content_type:
        score += 25
        reasons.append("json_content_type")
    if parsed_body is not None:
        score += 22
        reasons.append("json_body")
    if items:
        score += 25
        reasons.append("array_payload")
    if items and isinstance(items[0], dict) and _item_has_product_fields(items[0]):
        score += 18
        reasons.append("product_fields")
    if any(token in lowered_url for token in PRODUCT_URL_TOKENS):
        score += 12
        reasons.append("product_url_tokens")
    if _pagination_params(url):
        score += 8
        reasons.append("pagination_params")
    if sample.get("method") == "POST" and sample.get("post_json") is not None:
        score += 8
        reasons.append("post_json")
    if _looks_like_graphql(url, sample.get("post_json") if isinstance(sample.get("post_json"), dict) else None):
        score += 10
        reasons.append("graphql")
    if _infer_json_body_pagination_hints(sample.get("post_json") if isinstance(sample.get("post_json"), dict) else {}):
        score += 6
        reasons.append("json_body_pagination")
    if _is_noise_url(lowered_url):
        score -= 35
        reasons.append("noise_url")
    status = sample.get("status")
    try:
        status_int = int(status)
    except (TypeError, ValueError):
        status_int = 0
    if status_int and not (200 <= status_int < 300):
        score -= 20
        reasons.append("non_2xx_status")

    result = dict(sample)
    result.update({
        "score": max(0, min(score, 100)),
        "reasons": reasons,
        "parsed_body": parsed_body,
        "item_count": len(items),
    })
    return result


def _draft_evidence_from_candidate(candidate: dict[str, Any], *, target_url: str) -> dict[str, Any]:
    body = candidate.get("body") or candidate.get("preview") or ""
    return {
        "url": target_url or candidate.get("url") or "",
        "final_url": target_url or candidate.get("url") or "",
        "network_candidates": {
            "resource_counts": {"xhr": 1},
            "xhr_count": 1,
            "captured_xhr": [{
                "url": candidate.get("url"),
                "method": candidate.get("method") or "GET",
                "content_type": candidate.get("content_type") or "application/json",
                "body": body,
                "request_headers": candidate.get("request_headers") if isinstance(candidate.get("request_headers"), dict) else {},
                "post_data": json.dumps(candidate.get("post_json"), ensure_ascii=False) if isinstance(candidate.get("post_json"), dict) else candidate.get("post_data") or "",
            }],
        },
    }


def _parse_json_like(text: str) -> Any:
    text = str(text or "").strip()
    if not text:
        return None
    candidates = [text]
    first_obj = min([idx for idx in (text.find("{"), text.find("[")) if idx >= 0] or [-1])
    if first_obj > 0:
        candidates.append(text[first_obj:])
    for candidate in candidates:
        try:
            return json.loads(candidate)
        except (TypeError, ValueError):
            continue
    return None


def _extract_first_array(payload: Any) -> list[Any]:
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        return []
    stack = list(payload.values())
    seen: set[int] = set()
    while stack:
        value = stack.pop(0)
        if isinstance(value, list):
            return value
        if isinstance(value, dict):
            ident = id(value)
            if ident in seen:
                continue
            seen.add(ident)
            stack.extend(value.values())
    return []


def _item_has_product_fields(item: dict[str, Any]) -> bool:
    keys = {str(key).lower().replace("-", "_") for key in item.keys()}
    title = {"title", "name", "product_name", "label"} & keys
    commerce = {"price", "amount", "final_price", "regular_price", "image", "images", "url", "sku"} & keys
    return bool(title and commerce)


def _pagination_params(url: str) -> dict[str, str]:
    params = parse_qs(urlparse(url).query)
    wanted = {"page", "p", "currentpage", "offset", "skip", "start", "cursor", "after", "limit", "page_size", "pagesize", "size"}
    return {key: values[0] for key, values in params.items() if key.lower() in wanted and values}


def _url_without_pagination(url: str, pagination_hints: dict[str, Any]) -> str:
    parsed = urlparse(str(url or ""))
    params = parse_qs(parsed.query, keep_blank_values=True)
    remove = {
        str(pagination_hints.get("page_param") or ""),
        str(pagination_hints.get("offset_param") or ""),
        str(pagination_hints.get("cursor_param") or ""),
        str(pagination_hints.get("page_size_param") or pagination_hints.get("limit_param") or ""),
    }
    remove = {item for item in remove if item}
    if remove:
        params = {key: value for key, value in params.items() if key not in remove}
    query = "&".join(
        f"{key}={item}"
        for key, values in params.items()
        for item in values
    )
    return urlunparse(parsed._replace(query=query))


def _clean_api_hints(api_hints: dict[str, Any]) -> dict[str, Any]:
    allowed = {
        "endpoint", "method", "format", "items_path", "records_path", "data_path",
        "field_mapping", "fields", "params", "post_json", "post_data", "kind",
        "priority", "category", "total_path", "page_size", "headers",
        "replay_diagnostics",
    }
    return {key: value for key, value in api_hints.items() if key in allowed and value not in (None, "", {})}


def _clean_pagination_hints(pagination: dict[str, Any]) -> dict[str, Any]:
    allowed = {
        "type", "page_param", "offset_param", "limit_param", "page_size_param",
        "cursor_param", "next_cursor_path", "start_page", "start_offset",
        "initial_cursor", "page_size", "max_pages", "max_offset",
        "json_page_path", "json_page_size_path", "json_cursor_path",
    }
    return {key: value for key, value in pagination.items() if key in allowed and value not in (None, "", {})}


def _safe_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    return {
        "url": candidate.get("url", ""),
        "method": candidate.get("method", "GET"),
        "status": candidate.get("status"),
        "content_type": candidate.get("content_type", ""),
        "score": candidate.get("score", 0),
        "reasons": list(candidate.get("reasons") or []),
        "item_count": candidate.get("item_count", 0),
        "format": "graphql" if _looks_like_graphql(str(candidate.get("url") or ""), candidate.get("post_json") if isinstance(candidate.get("post_json"), dict) else None) else "json",
        "has_post_json": isinstance(candidate.get("post_json"), dict),
    }


def _is_noise_url(lowered_url: str) -> bool:
    return any(token in lowered_url for token in (
        "analytics", "collect", "pixel", "beacon", "tracking", "sentry",
        "datadog", "hotjar", "clarity", "facebook", "doubleclick",
    ))


def _site_name(url: str) -> str:
    parsed = urlparse(str(url or ""))
    return parsed.netloc or "api-replay-profile"


def _looks_like_graphql(url: str, post_json: dict[str, Any] | None) -> bool:
    if "graphql" in str(url or "").lower():
        return True
    if not isinstance(post_json, dict):
        return False
    return bool(post_json.get("query") or post_json.get("operationName"))


def _infer_json_body_pagination_hints(post_json: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(post_json, dict):
        return {}
    page_path = _find_json_path(post_json, {"currentpage", "page", "pagenumber", "pagenum"})
    size_path = _find_json_path(post_json, {"pagesize", "limit", "first", "size", "count", "take"})
    cursor_path = _find_json_path(post_json, {"after", "cursor", "nextcursor", "continuation"})
    hints: dict[str, Any] = {}
    if page_path:
        hints["type"] = "page"
        hints["json_page_path"] = page_path
        value = _value_at_path(post_json, page_path)
        try:
            hints["start_page"] = max(1, int(value))
        except (TypeError, ValueError):
            hints["start_page"] = 1
    elif cursor_path:
        hints["type"] = "cursor"
        hints["json_cursor_path"] = cursor_path
        value = _value_at_path(post_json, cursor_path)
        if value not in (None, ""):
            hints["initial_cursor"] = str(value)
    if size_path:
        hints["json_page_size_path"] = size_path
        value = _value_at_path(post_json, size_path)
        try:
            hints["page_size"] = max(1, int(value))
        except (TypeError, ValueError):
            pass
    return hints


def _find_json_path(payload: Any, names: set[str], prefix: str = "") -> str:
    if isinstance(payload, dict):
        for key, value in payload.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            normalized = str(key).lower().replace("_", "").replace("-", "")
            if normalized in names and isinstance(value, (str, int, float)) or (normalized in names and value in (None, "")):
                return path
            found = _find_json_path(value, names, path)
            if found:
                return found
    elif isinstance(payload, list):
        for index, item in enumerate(payload[:20]):
            found = _find_json_path(item, names, f"{prefix}.{index}" if prefix else str(index))
            if found:
                return found
    return ""


def _value_at_path(payload: Any, path: str) -> Any:
    current = payload
    for part in str(path or "").split("."):
        if isinstance(current, dict):
            current = current.get(part)
        elif isinstance(current, list) and part.isdigit():
            index = int(part)
            current = current[index] if 0 <= index < len(current) else None
        else:
            return None
    return current


def _safe_replay_headers(headers: dict[str, Any]) -> dict[str, str]:
    allowed = {
        "accept", "accept-language", "content-type", "origin", "referer",
        "x-requested-with", "x-csrf-token", "x-xsrf-token", "x-magento-cache-id",
        "x-store",
        "store",
    }
    output: dict[str, str] = {}
    for key, value in dict(headers or {}).items():
        lowered = str(key).strip().lower()
        if lowered in allowed or lowered.startswith("x-"):
            text = str(value or "").strip()
            if text and len(text) <= 1000 and "\x00" not in text:
                output[str(key)] = text
    return output
