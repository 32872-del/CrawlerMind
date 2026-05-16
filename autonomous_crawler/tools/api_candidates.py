"""API candidate discovery and safe JSON/GraphQL extraction helpers."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlencode, urljoin, urlparse, parse_qs, urlunparse

import httpx

from .site_zoo import API_LIST_JSON


# ---------------------------------------------------------------------------
# GraphQL mock fixtures (training / testing)
# ---------------------------------------------------------------------------

_GRAPHQL_COUNTRIES: dict[str, Any] = {
    "data": {
        "countries": [
            {"code": "CN", "name": "China", "capital": "Beijing", "continent": {"name": "Asia", "code": "AS"}},
            {"code": "US", "name": "United States", "capital": "Washington D.C.", "continent": {"name": "North America", "code": "NA"}},
            {"code": "GB", "name": "United Kingdom", "capital": "London", "continent": {"name": "Europe", "code": "EU"}},
        ]
    }
}

_GRAPHQL_CHARACTERS_PAGE: dict[str, list[dict[str, Any]]] = {
    "": [
        {
            "id": "1",
            "name": "Character Alpha",
            "status": "Alive",
            "species": "Human",
            "origin": {"name": "Earth", "dimension": "C-137"},
            "episode": [
                {"id": "e1", "name": "Pilot", "episode": "S01E01"},
                {"id": "e2", "name": "Lawnmower Dog", "episode": "S01E02"},
            ],
        },
        {
            "id": "2",
            "name": "Character Beta",
            "status": "Dead",
            "species": "Alien",
            "origin": {"name": "Gazorpazorp", "dimension": "C-35"},
            "episode": [
                {"id": "e3", "name": "Anatomy Park", "episode": "S01E03"},
            ],
        },
    ],
    "cursor_page2": [
        {
            "id": "3",
            "name": "Character Gamma",
            "status": "Alive",
            "species": "Robot",
            "origin": {"name": "Earth", "dimension": "C-137"},
            "episode": [
                {"id": "e4", "name": "M. Night Shaym-Aliens!", "episode": "S01E04"},
                {"id": "e5", "name": "Meeseeks and Destroy", "episode": "S01E05"},
                {"id": "e6", "name": "Rick Potion #9", "episode": "S01E06"},
            ],
        },
        {
            "id": "4",
            "name": "Character Delta",
            "status": "Alive",
            "species": "Human",
            "origin": {"name": "Dimension C-500A", "dimension": "C-500A"},
            "episode": [],
        },
    ],
}

_GRAPHQL_CHARACTERS_PAGE_INFO: dict[str, dict[str, Any]] = {
    "": {"hasNextPage": True, "endCursor": "cursor_page2"},
    "cursor_page2": {"hasNextPage": False, "endCursor": None},
}

_GRAPHQL_ERROR_RESPONSE: dict[str, Any] = {
    "errors": [
        {
            "message": "Cannot query field 'nonexistent' on type 'Query'.",
            "locations": [{"line": 1, "column": 9}],
            "path": ["nonexistent"],
            "extensions": {"code": "GRAPHQL_VALIDATION_FAILED"},
        }
    ]
}

_GRAPHQL_RATE_LIMIT_RESPONSE: dict[str, Any] = {
    "data": None,
    "errors": [
        {
            "message": "API rate limit exceeded. Please wait before retrying.",
            "extensions": {
                "code": "RATE_LIMITED",
                "retryAfter": 30,
                "limit": 100,
                "remaining": 0,
            },
        }
    ],
}


def build_graphql_nested_fields_query() -> str:
    """Return a sample GraphQL query with nested fields (training fixture)."""
    return """
    query GetCharacters($page: Int) {
        characters(page: $page) {
            results {
                id
                name
                status
                species
                origin {
                    name
                    dimension
                }
                episode {
                    id
                    name
                    episode
                }
            }
        }
    }
    """


def build_graphql_cursor_query() -> str:
    """Return a sample Relay-style cursor pagination query (training fixture)."""
    return """
    query GetCharactersCursor($after: String) {
        characters(after: $after, first: 2) {
            pageInfo {
                hasNextPage
                endCursor
            }
            edges {
                node {
                    id
                    name
                    status
                    species
                    origin {
                        name
                        dimension
                    }
                    episode {
                        id
                        name
                        episode
                    }
                }
            }
        }
    }
    """


_TRACKING_URL_PATTERNS = (
    "google-analytics", "googletagmanager", "analytics.google",
    "telemetry", "/collect", "/pixel", "/beacon", "/metrics",
    "/tracking", "segment.io", "segment.com", "mixpanel.com",
    "amplitude.com", "hotjar.com", "fullstory.com", "clarity.ms",
    "facebook.net/tr", "doubleclick.net", "adservice.google",
    "stats.", "pixel.", "track.",
)


def is_tracking_url(url: str) -> bool:
    """Return True if the URL matches known analytics/telemetry patterns."""
    lowered = url.lower()
    return any(pattern in lowered for pattern in _TRACKING_URL_PATTERNS)


def build_api_candidates(api_hints: list[str], base_url: str = "") -> list[dict[str, Any]]:
    """Rank API-like hints into Strategy-ready candidates."""
    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()
    for hint in api_hints:
        url = urljoin(base_url, hint) if base_url else hint
        if url in seen:
            continue
        seen.add(url)
        if is_tracking_url(url):
            continue
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


def fetch_json_api(
    url: str,
    headers: dict[str, str] | None = None,
    method: str = "GET",
    post_data: str | dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Fetch a JSON API response, with deterministic mock support."""
    if url in {"mock://api/products", "mock://site-zoo/api-products"}:
        return {"ok": True, "url": url, "data": API_LIST_JSON, "status_code": 200}
    if url == "mock://api/search-post" and method.upper() == "POST":
        return {
            "ok": True,
            "url": url,
            "data": {"hits": [{"title": "POST Alpha"}, {"title": "POST Beta"}]},
            "status_code": 200,
        }

    paged = _mock_paged_response(url)
    if paged is not None:
        return paged

    method = method.upper()
    if method not in {"GET", "POST"}:
        raise ValueError(f"Unsupported JSON API method: {method}")

    merged_headers = {"Accept": "application/json", **(headers or {})}
    if method == "POST":
        merged_headers.setdefault("Content-Type", "application/json")

    with httpx.Client(
        follow_redirects=True,
        timeout=httpx.Timeout(20.0, connect=10.0),
        headers=merged_headers,
    ) as client:
        if method == "POST":
            response = client.post(url, content=_coerce_json_post_content(post_data))
        else:
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
    # Mock GraphQL endpoints for training
    mock_result = _mock_graphql_response(url, query, variables)
    if mock_result is not None:
        return mock_result

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


def _mock_graphql_response(
    url: str,
    query: str,
    variables: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Return a deterministic mock GraphQL response, or None if not a mock URL."""
    variables = variables or {}

    # Countries (nested fields, simple)
    if url == "mock://api/graphql-countries":
        return {"ok": True, "url": url, "data": _GRAPHQL_COUNTRIES, "status_code": 200}

    # Characters with nested fields + episodes
    if url == "mock://api/graphql-nested":
        return {"ok": True, "url": url, "data": {"data": {"characters": {"results": [
            {
                "id": "1", "name": "Nested Alpha", "status": "Alive", "species": "Human",
                "origin": {"name": "Earth", "dimension": "C-137"},
                "episode": [
                    {"id": "e1", "name": "Pilot", "episode": "S01E01"},
                    {"id": "e2", "name": "Lawnmower Dog", "episode": "S01E02"},
                ],
            },
            {
                "id": "2", "name": "Nested Beta", "status": "Dead", "species": "Alien",
                "origin": {"name": "Gazorpazorp", "dimension": "C-35"},
                "episode": [{"id": "e3", "name": "Anatomy Park", "episode": "S01E03"}],
            },
        ]}}}, "status_code": 200}

    # Cursor-paginated GraphQL (Relay-style)
    if url == "mock://api/graphql-paginated":
        cursor = variables.get("after") or ""
        page_items = _GRAPHQL_CHARACTERS_PAGE.get(cursor, [])
        page_info = _GRAPHQL_CHARACTERS_PAGE_INFO.get(cursor, {"hasNextPage": False, "endCursor": None})
        edges = [{"node": item} for item in page_items]
        return {
            "ok": True, "url": url,
            "data": {"data": {"characters": {"pageInfo": page_info, "edges": edges}}},
            "status_code": 200,
        }

    # Error response
    if url == "mock://api/graphql-error":
        return {"ok": True, "url": url, "data": _GRAPHQL_ERROR_RESPONSE, "status_code": 200}

    # Rate-limited response (simulates 429)
    if url == "mock://api/graphql-rate-limited":
        return {"ok": False, "url": url, "data": _GRAPHQL_RATE_LIMIT_RESPONSE, "status_code": 429}

    return None


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
    for key in ("items", "products", "data", "results", "records", "hits", "quotes"):
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


def _coerce_json_post_content(post_data: str | dict[str, Any] | None) -> str:
    if post_data is None:
        return "{}"
    if isinstance(post_data, dict):
        return json.dumps(post_data)
    text = str(post_data).strip()
    if not text:
        return "{}"
    try:
        json.loads(text)
    except json.JSONDecodeError:
        return json.dumps({"query": text})
    return text


def normalize_api_records(records: list[dict[str, Any]], max_items: int = 0) -> list[dict[str, Any]]:
    """Normalize common API record field names into CLM item fields."""
    normalized: list[dict[str, Any]] = []
    for index, record in enumerate(records):
        item = dict(record)
        normalized_title = _extract_title(record.get("title"))
        if normalized_title:
            item["title"] = normalized_title
        elif "title" not in item:
            item["title"] = (
                record.get("name")
                or record.get("label")
                or record.get("headline")
                or record.get("text")
            )
        if "link" not in item:
            item["link"] = (
                record.get("html_url")
                or record.get("url")
                or record.get("href")
                or record.get("permalink")
                or record.get("siteUrl")
            )
        if "image" not in item:
            item["image"] = (
                record.get("image")
                or record.get("image_src")
                or record.get("thumbnail")
                or _first_nested(record, ["coverImage", "medium"], ["pic"])
            )
        if "hot_score" not in item:
            item["hot_score"] = (
                record.get("score")
                or record.get("points")
                or record.get("num_comments")
                or record.get("comments")
                or record.get("rating")
                or record.get("ups")
                or record.get("heat")
                or record.get("popularity")
                or record.get("averageScore")
                or _first_nested(record, ["stat", "view"], ["stat", "like"], ["stat", "coin"])
            )
        if "summary" not in item:
            item["summary"] = (
                record.get("summary")
                or record.get("description")
                or record.get("text")
                or record.get("body")
                or record.get("story_text")
                or _first_nested(record, ["author", "name"])
            )
        if "rank" not in item:
            rank = (
                record.get("rank")
                or record.get("position")
                or _first_nested(record, ["stat", "his_rank"], ["stat", "now_rank"])
            )
            item["rank"] = rank if rank not in {None, 0, ""} else index + 1
        item.setdefault("index", index)
        if item.get("title"):
            normalized.append(item)
        if max_items and len(normalized) >= max_items:
            break
    return normalized


def _extract_title(value: Any) -> str | None:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        for key in ("english", "romaji", "native", "userPreferred"):
            candidate = value.get(key)
            if candidate:
                return str(candidate)
    return None


def _first_nested(record: dict[str, Any], *paths: list[str]) -> Any:
    for path in paths:
        current: Any = record
        for key in path:
            if not isinstance(current, dict):
                current = None
                break
            current = current.get(key)
        if current not in {None, ""}:
            return current
    return None


# ---------------------------------------------------------------------------
# Pagination mock data
# ---------------------------------------------------------------------------

_PAGED_PRODUCTS: dict[int, list[dict[str, Any]]] = {
    1: [
        {"title": "Paged Alpha", "price": 10.0, "page": 1},
        {"title": "Paged Beta", "price": 20.0, "page": 1},
        {"title": "Paged Gamma", "price": 30.0, "page": 1},
    ],
    2: [
        {"title": "Paged Delta", "price": 40.0, "page": 2},
        {"title": "Paged Epsilon", "price": 50.0, "page": 2},
        {"title": "Paged Zeta", "price": 60.0, "page": 2},
    ],
    3: [
        {"title": "Paged Eta", "price": 70.0, "page": 3},
        {"title": "Paged Theta", "price": 80.0, "page": 3},
        {"title": "Paged Iota", "price": 90.0, "page": 3},
    ],
}

_OFFSET_PRODUCTS: list[dict[str, Any]] = [
    {"title": "Offset Alpha", "price": 11.0},
    {"title": "Offset Beta", "price": 22.0},
    {"title": "Offset Gamma", "price": 33.0},
    {"title": "Offset Delta", "price": 44.0},
    {"title": "Offset Epsilon", "price": 55.0},
    {"title": "Offset Zeta", "price": 66.0},
    {"title": "Offset Eta", "price": 77.0},
    {"title": "Offset Theta", "price": 88.0},
    {"title": "Offset Iota", "price": 99.0},
]

_CURSOR_PRODUCTS: dict[str, list[dict[str, Any]]] = {
    "": [
        {"title": "Cursor Alpha", "price": 15.0},
        {"title": "Cursor Beta", "price": 25.0},
        {"title": "Cursor Gamma", "price": 35.0},
    ],
    "page2": [
        {"title": "Cursor Delta", "price": 45.0},
        {"title": "Cursor Epsilon", "price": 55.0},
        {"title": "Cursor Zeta", "price": 65.0},
    ],
    "page3": [
        {"title": "Cursor Eta", "price": 75.0},
        {"title": "Cursor Theta", "price": 85.0},
        {"title": "Cursor Iota", "price": 95.0},
    ],
}

_CURSOR_NEXT: dict[str, str | None] = {
    "": "page2",
    "page2": "page3",
    "page3": None,
}

# Stuck cursor fixture: next_cursor always equals current cursor
_CURSOR_STUCK: dict[str, list[dict[str, Any]]] = {
    "": [{"title": "Stuck Alpha"}],
    "stuck": [{"title": "Stuck Beta"}],
}
_CURSOR_STUCK_NEXT: dict[str, str | None] = {
    "": "stuck",
    "stuck": "stuck",
}

# Duplicate items across pages for dedupe testing
_DEDUPED_PRODUCTS: dict[int, list[dict[str, Any]]] = {
    1: [
        {"id": "a1", "title": "Dedup Alpha"},
        {"id": "b2", "title": "Dedup Beta"},
    ],
    2: [
        {"id": "b2", "title": "Dedup Beta"},  # duplicate
        {"id": "c3", "title": "Dedup Gamma"},
    ],
}

# Empty pages fixture: pages 2+ are empty
_EMPTY_AFTER_FIRST: dict[int, list[dict[str, Any]]] = {
    1: [{"title": "First Only", "id": "f1"}],
}

# ---------------------------------------------------------------------------
# 50+ record pagination fixtures (training / stress)
# ---------------------------------------------------------------------------

_ITEM_NAMES = [
    "Laptop", "Phone", "Tablet", "Monitor", "Keyboard", "Mouse", "Headset",
    "Speaker", "Webcam", "Printer", "Scanner", "Router", "Switch", "Hub",
    "Cable", "Adapter", "Charger", "Battery", "Case", "Stand", "Dock",
    "Drive", "SSD", "RAM", "GPU", "CPU", "Motherboard", "PSU", "Fan",
    "Cooler", "Microphone", "Amplifier", "Receiver", "Antenna", "Remote",
    "Sensor", "Camera", "Lens", "Tripod", "Flash", "Filter", "Bag",
    "Strap", "Mount", "Arm", "Light", "Panel", "Board", "Chip", "Module",
    "Connector", "Relay", "Fuse", "Wire", "Plug",
]

_GQL_NAMES = [
    "Rick", "Morty", "Summer", "Beth", "Jerry", "Birdperson", "Squanchy",
    "Mr. Meeseeks", "Evil Morty", "Unity", "Tammy", "Abradolf Lincler",
    "Krombopulos Michael", "Scary Terry", "Noob Noob", "Gearhead",
    "Revolver Ocelot", "Phoenixperson", "Supernova", "Crocubot",
    "Arthricia", "Frank Palicky", "Scroopy Noopers", "King Jellybean",
    "Photography Raptor", "Pencilvester", "Tinkles", "Sleepy Gary",
    "Hamurai", "Amish Cyborg", "Reverse Giraffe", "Mr. Poopybutthole",
    "Gene Vagina", "Principal Vagina", "Dr. Xenon Bloom", "Revolio Clockberg",
    "Squanch", "Brad", "Nancy", "Joyce", "Ethan", "Logan",
    "Counselor Rick", "Doofus Rick", "Cop Rick", "Cowboy Rick",
    "Tiny Rick", "Pickle Rick", "Toxic Rick", "Cool Rick",
    "Theta Rick", "Morty Jr.", "Gazorpazorpfield", "Roy",
]


def _generate_page_products(page: int, page_size: int = 10) -> list[dict[str, Any]]:
    """Generate a page of products (0-indexed page)."""
    start = page * page_size
    return [
        {"id": f"p{start + i}", "title": f"{_ITEM_NAMES[(start + i) % len(_ITEM_NAMES)]} {start + i}", "price": round(9.99 + (start + i) * 3.14, 2)}
        for i in range(page_size)
        if start + i < len(_ITEM_NAMES)
    ]


def _generate_offset_products(offset: int, limit: int) -> list[dict[str, Any]]:
    """Generate a slice of products for offset pagination."""
    return [
        {"id": f"o{offset + i}", "title": f"{_ITEM_NAMES[(offset + i) % len(_ITEM_NAMES)]} v2 #{offset + i}", "price": round(19.99 + (offset + i) * 2.71, 2)}
        for i in range(limit)
        if offset + i < len(_ITEM_NAMES)
    ]


def _generate_cursor_products(cursor: str) -> tuple[list[dict[str, Any]], str | None]:
    """Generate items for cursor pagination. Returns (items, next_cursor)."""
    page_map = {
        "": 0, "ckpt_10": 1, "ckpt_20": 2, "ckpt_30": 3, "ckpt_40": 4,
    }
    next_map: dict[str, str | None] = {
        "": "ckpt_10", "ckpt_10": "ckpt_20", "ckpt_20": "ckpt_30",
        "ckpt_30": "ckpt_40", "ckpt_40": None,
    }
    page_idx = page_map.get(cursor, 0)
    start = page_idx * 10
    items = [
        {"id": f"c{start + i}", "title": f"{_GQL_NAMES[(start + i) % len(_GQL_NAMES)]} #{start + i}", "score": (start + i) * 10}
        for i in range(10)
        if start + i < len(_GQL_NAMES)
    ]
    return items, next_map.get(cursor)


# 50+ page-based data: 6 pages of 10 = 60 items (last page has 4)
_PAGED_PRODUCTS_50: dict[int, list[dict[str, Any]]] = {
    p: _generate_page_products(p) for p in range(6)
}

# 50+ offset-based data: 60 items total
_OFFSET_PRODUCTS_50: list[dict[str, Any]] = [
    {"id": f"o{i}", "title": f"{_ITEM_NAMES[i % len(_ITEM_NAMES)]} v2 #{i}", "price": round(19.99 + i * 2.71, 2)}
    for i in range(min(60, len(_ITEM_NAMES)))
]


def _mock_paged_response(url: str) -> dict[str, Any] | None:
    """Return a deterministic mock paginated response, or None if not a mock URL."""
    parsed = urlparse(url)
    params = parse_qs(parsed.query, keep_blank_values=True)

    def _param(name: str, default: str = "") -> str:
        values = params.get(name, [default])
        return values[0] if values else default

    host = parsed.hostname or ""
    path = parsed.path or ""

    # Page-based: mock://api/paged-products?page=N
    if host == "api" and path == "/paged-products":
        page = int(_param("page", "1"))
        items = _PAGED_PRODUCTS.get(page, [])
        total_pages = len(_PAGED_PRODUCTS)
        next_page = page + 1 if page < total_pages else None
        data: dict[str, Any] = {
            "items": items,
            "page": page,
            "total_pages": total_pages,
            "total": sum(len(v) for v in _PAGED_PRODUCTS.values()),
        }
        if next_page is not None:
            data["next_page"] = next_page
        return {"ok": True, "url": url, "data": data, "status_code": 200}

    # Offset-based: mock://api/offset-products?offset=N&limit=M
    if host == "api" and path == "/offset-products":
        offset = int(_param("offset", "0"))
        limit = int(_param("limit", "3"))
        sliced = _OFFSET_PRODUCTS[offset : offset + limit]
        total = len(_OFFSET_PRODUCTS)
        next_offset = offset + limit if offset + limit < total else None
        data = {
            "items": sliced,
            "offset": offset,
            "limit": limit,
            "total": total,
        }
        if next_offset is not None:
            data["next_offset"] = next_offset
        return {"ok": True, "url": url, "data": data, "status_code": 200}

    # Cursor-based: mock://api/cursor-products?cursor=X
    if host == "api" and path == "/cursor-products":
        cursor = _param("cursor", "")
        items = _CURSOR_PRODUCTS.get(cursor, [])
        next_cursor = _CURSOR_NEXT.get(cursor)
        data = {"items": items}
        if next_cursor is not None:
            data["next_cursor"] = next_cursor
        if cursor:
            data["cursor"] = cursor
        return {"ok": True, "url": url, "data": data, "status_code": 200}

    # Stuck cursor: mock://api/cursor-stuck?cursor=X
    if host == "api" and path == "/cursor-stuck":
        cursor = _param("cursor", "")
        items = _CURSOR_STUCK.get(cursor, [])
        next_cursor = _CURSOR_STUCK_NEXT.get(cursor)
        data = {"items": items}
        if next_cursor is not None:
            data["next_cursor"] = next_cursor
        if cursor:
            data["cursor"] = cursor
        return {"ok": True, "url": url, "data": data, "status_code": 200}

    # Dedupe fixture: mock://api/duped-products?page=N
    if host == "api" and path == "/duped-products":
        page = int(_param("page", "1"))
        items = _DEDUPED_PRODUCTS.get(page, [])
        total_pages = len(_DEDUPED_PRODUCTS)
        next_page = page + 1 if page < total_pages else None
        data = {"items": items, "page": page, "total_pages": total_pages}
        if next_page is not None:
            data["next_page"] = next_page
        return {"ok": True, "url": url, "data": data, "status_code": 200}

    # Empty-after-first: mock://api/empty-after-first?page=N
    if host == "api" and path == "/empty-after-first":
        page = int(_param("page", "1"))
        items = _EMPTY_AFTER_FIRST.get(page, [])
        total_pages = 3
        next_page = page + 1 if page < total_pages else None
        data = {"items": items, "page": page, "total_pages": total_pages}
        if next_page is not None:
            data["next_page"] = next_page
        return {"ok": True, "url": url, "data": data, "status_code": 200}

    # 50+ page-based: mock://api/paged-products-50?page=N (60 items, 6 pages)
    if host == "api" and path == "/paged-products-50":
        page = int(_param("page", "1"))
        zero_idx = page - 1
        items = _PAGED_PRODUCTS_50.get(zero_idx, [])
        total_pages = len(_PAGED_PRODUCTS_50)
        next_page = page + 1 if page < total_pages else None
        total = sum(len(v) for v in _PAGED_PRODUCTS_50.values())
        data = {"items": items, "page": page, "total_pages": total_pages, "total": total}
        if next_page is not None:
            data["next_page"] = next_page
        return {"ok": True, "url": url, "data": data, "status_code": 200}

    # 50+ offset-based: mock://api/offset-products-50?offset=N&limit=10
    if host == "api" and path == "/offset-products-50":
        offset = int(_param("offset", "0"))
        limit = int(_param("limit", "10"))
        sliced = _OFFSET_PRODUCTS_50[offset: offset + limit]
        total = len(_OFFSET_PRODUCTS_50)
        next_offset = offset + limit if offset + limit < total else None
        data = {"items": sliced, "offset": offset, "limit": limit, "total": total}
        if next_offset is not None:
            data["next_offset"] = next_offset
        return {"ok": True, "url": url, "data": data, "status_code": 200}

    # 50+ cursor-based: mock://api/cursor-products-50?cursor=X (60 items, 5 pages)
    if host == "api" and path == "/cursor-products-50":
        cursor = _param("cursor", "")
        items, next_cursor = _generate_cursor_products(cursor)
        data: dict[str, Any] = {"items": items}
        if next_cursor is not None:
            data["next_cursor"] = next_cursor
        if cursor:
            data["cursor"] = cursor
        return {"ok": True, "url": url, "data": data, "status_code": 200}

    return None


# ---------------------------------------------------------------------------
# Pagination spec detection & multi-page fetch
# ---------------------------------------------------------------------------

_CURSOR_FIELD_CANDIDATES = (
    "next_cursor", "nextPage", "next_page_token",
    "after", "page_token",
)
_NEXT_PAGE_FIELD_CANDIDATES = ("next_page", "nextPage", "next_page_number")
_NEXT_OFFSET_FIELD_CANDIDATES = ("next_offset", "nextOffset")


def _detect_pagination_fields(data: dict[str, Any]) -> dict[str, Any]:
    """Inspect a JSON response for pagination hints.

    Returns a dict describing detected pagination fields:
      - next_cursor: cursor value for cursor-based pagination
      - next_page: page number for page-based pagination
      - next_offset: offset for offset-based pagination
    Only includes keys where a value was found.
    """
    result: dict[str, Any] = {}
    if not isinstance(data, dict):
        return result
    for field_name in _CURSOR_FIELD_CANDIDATES:
        value = data.get(field_name)
        if value is not None and value != "":
            result["next_cursor"] = str(value)
            break
    for field_name in _NEXT_PAGE_FIELD_CANDIDATES:
        value = data.get(field_name)
        if value is not None:
            try:
                result["next_page"] = int(value)
            except (ValueError, TypeError):
                result["next_page"] = value
            break
    for field_name in _NEXT_OFFSET_FIELD_CANDIDATES:
        value = data.get(field_name)
        if value is not None:
            try:
                result["next_offset"] = int(value)
            except (ValueError, TypeError):
                result["next_offset"] = value
            break
    return result


@dataclass
class PaginationSpec:
    """Describes how to paginate a JSON API."""
    type: str = "none"  # "page", "offset", "cursor", "none"
    page_param: str = "page"
    limit_param: str = "limit"
    offset_param: str = "offset"
    cursor_param: str = "cursor"
    limit: int = 10
    max_pages: int = 10
    empty_page_threshold: int = 2
    dedupe_key_fields: tuple[str, ...] = ("url", "link", "objectID", "id", "object_id")


@dataclass
class PaginatedResult:
    """Aggregated result from multi-page fetching."""
    all_items: list[dict[str, Any]] = field(default_factory=list)
    pages_fetched: int = 0
    pagination_type: str = "none"
    api_responses: list[dict[str, Any]] = field(default_factory=list)
    deduplicated_count: int = 0
    stop_reason: str = ""


def _dedupe_items(
    items: list[dict[str, Any]],
    key_fields: tuple[str, ...],
) -> tuple[list[dict[str, Any]], int]:
    """Remove duplicate items based on stable key fields.

    Returns (deduplicated_list, number_of_duplicates_removed).
    Falls back to title+hash if no key field matches.
    """
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    dupes = 0
    for item in items:
        key = _item_dedupe_key(item, key_fields)
        if key in seen:
            dupes += 1
            continue
        seen.add(key)
        unique.append(item)
    return unique, dupes


def _item_dedupe_key(item: dict[str, Any], key_fields: tuple[str, ...]) -> str:
    for field_name in key_fields:
        value = item.get(field_name)
        if value is not None and value != "":
            return f"{field_name}:{value}"
    title = item.get("title", "")
    return f"title:{title}"


def fetch_paginated_api(
    url: str,
    pagination: PaginationSpec | None = None,
    headers: dict[str, str] | None = None,
    method: str = "GET",
    post_data: str | dict[str, Any] | None = None,
    max_items: int = 0,
) -> PaginatedResult:
    """Fetch a JSON API across multiple pages.

    Args:
        url: Base API URL (or first page URL).
        pagination: PaginationSpec describing how to paginate.
        headers: HTTP headers.
        method: HTTP method.
        post_data: POST body for POST-based APIs.
        max_items: Stop after collecting this many items (0 = unlimited).

    Returns:
        PaginatedResult with aggregated items and metadata.
    """
    if pagination is None:
        pagination = PaginationSpec()

    result = PaginatedResult(pagination_type=pagination.type)

    if pagination.type == "none":
        response = fetch_json_api(url, headers=headers, method=method, post_data=post_data)
        result.api_responses.append(response)
        records = extract_records_from_json(response.get("data"))
        items = normalize_api_records(records, max_items=max_items)
        result.all_items = items
        result.pages_fetched = 1
        return result

    if pagination.type == "page":
        _fetch_page_pagination(url, pagination, headers, method, post_data, max_items, result)
    elif pagination.type == "offset":
        _fetch_offset_pagination(url, pagination, headers, method, post_data, max_items, result)
    elif pagination.type == "cursor":
        _fetch_cursor_pagination(url, pagination, headers, method, post_data, max_items, result)
    else:
        response = fetch_json_api(url, headers=headers, method=method, post_data=post_data)
        result.api_responses.append(response)
        records = extract_records_from_json(response.get("data"))
        result.all_items = normalize_api_records(records, max_items=max_items)
        result.pages_fetched = 1

    return result


def _fetch_page_pagination(
    url: str,
    spec: PaginationSpec,
    headers: dict[str, str] | None,
    method: str,
    post_data: str | dict[str, Any] | None,
    max_items: int,
    result: PaginatedResult,
) -> None:
    current_page = 1
    visited_urls: set[str] = set()
    consecutive_empty = 0
    for _ in range(spec.max_pages):
        if max_items and len(result.all_items) >= max_items:
            result.stop_reason = "max_items"
            break
        page_url = _set_query_param(url, spec.page_param, str(current_page))
        if page_url in visited_urls:
            result.stop_reason = "repeated_url"
            break
        visited_urls.add(page_url)
        response = fetch_json_api(page_url, headers=headers, method=method, post_data=post_data)
        result.api_responses.append(response)
        records = extract_records_from_json(response.get("data"))
        if not records:
            consecutive_empty += 1
            if consecutive_empty >= spec.empty_page_threshold:
                result.stop_reason = "empty_pages"
                break
        else:
            consecutive_empty = 0
            new_items = normalize_api_records(records, max_items=0)
            result.all_items.extend(new_items)
            result.pages_fetched += 1
            result.all_items, dupes = _dedupe_items(result.all_items, spec.dedupe_key_fields)
            result.deduplicated_count += dupes
            if max_items and len(result.all_items) > max_items:
                result.all_items = result.all_items[:max_items]
        next_hint = _detect_pagination_fields(response.get("data", {}))
        next_page = next_hint.get("next_page")
        if next_page is not None:
            current_page = int(next_page)
        else:
            result.stop_reason = result.stop_reason or "no_next_hint"
            break


def _fetch_offset_pagination(
    url: str,
    spec: PaginationSpec,
    headers: dict[str, str] | None,
    method: str,
    post_data: str | dict[str, Any] | None,
    max_items: int,
    result: PaginatedResult,
) -> None:
    current_offset = 0
    visited_urls: set[str] = set()
    consecutive_empty = 0
    for _ in range(spec.max_pages):
        if max_items and len(result.all_items) >= max_items:
            result.stop_reason = "max_items"
            break
        offset_url = _set_query_param(url, spec.offset_param, str(current_offset))
        offset_url = _set_query_param(offset_url, spec.limit_param, str(spec.limit))
        if offset_url in visited_urls:
            result.stop_reason = "repeated_url"
            break
        visited_urls.add(offset_url)
        response = fetch_json_api(offset_url, headers=headers, method=method, post_data=post_data)
        result.api_responses.append(response)
        records = extract_records_from_json(response.get("data"))
        if not records:
            consecutive_empty += 1
            if consecutive_empty >= spec.empty_page_threshold:
                result.stop_reason = "empty_pages"
                break
        else:
            consecutive_empty = 0
            new_items = normalize_api_records(records, max_items=0)
            result.all_items.extend(new_items)
            result.pages_fetched += 1
            result.all_items, dupes = _dedupe_items(result.all_items, spec.dedupe_key_fields)
            result.deduplicated_count += dupes
            if max_items and len(result.all_items) > max_items:
                result.all_items = result.all_items[:max_items]
        next_hint = _detect_pagination_fields(response.get("data", {}))
        next_offset = next_hint.get("next_offset")
        if next_offset is not None:
            current_offset = int(next_offset)
        else:
            result.stop_reason = result.stop_reason or "no_next_hint"
            break


def _fetch_cursor_pagination(
    url: str,
    spec: PaginationSpec,
    headers: dict[str, str] | None,
    method: str,
    post_data: str | dict[str, Any] | None,
    max_items: int,
    result: PaginatedResult,
) -> None:
    cursor_value = ""
    visited_urls: set[str] = set()
    consecutive_empty = 0
    for _ in range(spec.max_pages):
        if max_items and len(result.all_items) >= max_items:
            result.stop_reason = "max_items"
            break
        cursor_url = _set_query_param(url, spec.cursor_param, cursor_value)
        if cursor_url in visited_urls:
            result.stop_reason = "repeated_url"
            break
        visited_urls.add(cursor_url)
        response = fetch_json_api(cursor_url, headers=headers, method=method, post_data=post_data)
        result.api_responses.append(response)
        records = extract_records_from_json(response.get("data"))
        if not records:
            consecutive_empty += 1
            if consecutive_empty >= spec.empty_page_threshold:
                result.stop_reason = "empty_pages"
                break
        else:
            consecutive_empty = 0
            new_items = normalize_api_records(records, max_items=0)
            result.all_items.extend(new_items)
            result.pages_fetched += 1
            result.all_items, dupes = _dedupe_items(result.all_items, spec.dedupe_key_fields)
            result.deduplicated_count += dupes
            if max_items and len(result.all_items) > max_items:
                result.all_items = result.all_items[:max_items]
        next_hint = _detect_pagination_fields(response.get("data", {}))
        next_cursor = next_hint.get("next_cursor")
        if next_cursor is not None:
            if str(next_cursor) == cursor_value:
                result.stop_reason = "cursor_stuck"
                break
            cursor_value = str(next_cursor)
        else:
            result.stop_reason = result.stop_reason or "no_next_hint"
            break


def _set_query_param(url: str, param: str, value: str) -> str:
    parsed = urlparse(url)
    params = parse_qs(parsed.query, keep_blank_values=True)
    params[param] = [value]
    new_query = urlencode(params, doseq=True)
    return urlunparse(parsed._replace(query=new_query))
