"""API candidate discovery and safe JSON/GraphQL extraction helpers."""
from __future__ import annotations

import json
from typing import Any
from urllib.parse import urljoin

import httpx

from .site_zoo import API_LIST_JSON


def build_api_candidates(api_hints: list[str], base_url: str = "") -> list[dict[str, Any]]:
    """Rank API-like hints into Strategy-ready candidates."""
    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()
    for hint in api_hints:
        url = urljoin(base_url, hint) if base_url else hint
        if url in seen:
            continue
        seen.add(url)
        lowered = url.lower()
        score = 0
        if "api" in lowered:
            score += 20
        if "graphql" in lowered:
            score += 18
        if any(token in lowered for token in ("product", "products", "catalog", "items", "search")):
            score += 12
        if "page" in lowered or "offset" in lowered or "limit" in lowered:
            score += 4
        candidates.append({
            "url": url,
            "method": "GET",
            "score": score,
            "reason": "api_hint_url_keywords",
        })
    return sorted(candidates, key=lambda item: item["score"], reverse=True)


def build_direct_json_candidate(url: str) -> dict[str, Any]:
    """Return a Strategy-ready candidate for a URL that is already JSON."""
    return {
        "url": url,
        "method": "GET",
        "score": 60,
        "reason": "target_url_is_json",
    }


def build_graphql_candidate(
    url: str,
    query: str,
    variables: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a Strategy-ready candidate for an explicit GraphQL query."""
    return {
        "url": url,
        "method": "POST",
        "kind": "graphql",
        "query": query,
        "variables": variables or {},
        "score": 70,
        "reason": "explicit_graphql_query",
    }


def fetch_json_api(url: str, headers: dict[str, str] | None = None) -> dict[str, Any]:
    """Fetch a JSON API response, with deterministic mock support."""
    if url in {"mock://api/products", "mock://site-zoo/api-products"}:
        return {"ok": True, "url": url, "data": API_LIST_JSON, "status_code": 200}

    with httpx.Client(
        follow_redirects=True,
        timeout=httpx.Timeout(20.0, connect=10.0),
        headers=headers,
    ) as client:
        response = client.get(url)
        response.raise_for_status()
        return {
            "ok": True,
            "url": str(response.url),
            "data": response.json(),
            "status_code": response.status_code,
        }


def fetch_graphql_api(
    url: str,
    query: str,
    variables: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    """POST a GraphQL query and return the decoded JSON response."""
    if url == "mock://api/graphql-countries":
        return {
            "ok": True,
            "url": url,
            "data": {
                "data": {
                    "countries": [
                        {"code": "CN", "name": "China", "capital": "Beijing"},
                        {"code": "US", "name": "United States", "capital": "Washington D.C."},
                    ]
                }
            },
            "status_code": 200,
        }

    merged_headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        **(headers or {}),
    }
    payload = {"query": query, "variables": variables or {}}
    with httpx.Client(
        follow_redirects=True,
        timeout=httpx.Timeout(20.0, connect=10.0),
        headers=merged_headers,
    ) as client:
        response = client.post(url, content=json.dumps(payload))
        response.raise_for_status()
        return {
            "ok": True,
            "url": str(response.url),
            "data": response.json(),
            "status_code": response.status_code,
        }


def extract_records_from_json(data: Any) -> list[dict[str, Any]]:
    """Extract list-like records from common JSON response shapes."""
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if not isinstance(data, dict):
        return []
    if isinstance(data.get("children"), list):
        records: list[dict[str, Any]] = []
        for child in data["children"]:
            if isinstance(child, dict) and isinstance(child.get("data"), dict):
                records.append(child["data"])
            elif isinstance(child, dict):
                records.append(child)
        if records:
            return records
    for key in ("items", "products", "data", "results", "records"):
        value = data.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
        if isinstance(value, dict):
            nested = extract_records_from_json(value)
            if nested:
                return nested
    for value in data.values():
        nested = extract_records_from_json(value)
        if nested:
            return nested
    return []


def normalize_api_records(records: list[dict[str, Any]], max_items: int = 0) -> list[dict[str, Any]]:
    """Normalize common API record field names into CLM item fields."""
    normalized: list[dict[str, Any]] = []
    for index, record in enumerate(records):
        item = dict(record)
        if "title" not in item:
            item["title"] = record.get("name") or record.get("label") or record.get("headline")
        if "link" not in item:
            item["link"] = record.get("url") or record.get("href") or record.get("permalink")
        if "image" not in item:
            item["image"] = record.get("image") or record.get("image_src") or record.get("thumbnail")
        if "hot_score" not in item:
            item["hot_score"] = record.get("score") or record.get("ups") or record.get("heat")
        item.setdefault("index", index)
        if item.get("title"):
            normalized.append(item)
        if max_items and len(normalized) >= max_items:
            break
    return normalized
