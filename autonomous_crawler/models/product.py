"""Generic product record model for ecommerce crawling.

This module defines a site-agnostic product record and a category-aware
deduplication key builder. It does not contain any site-specific logic.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


VALID_STATUSES = frozenset({"ok", "partial", "blocked", "failed"})


@dataclass
class ProductRecord:
    """A generic, site-agnostic product record for ecommerce crawling."""

    run_id: str = ""
    source_site: str = ""
    source_url: str = ""
    canonical_url: str = ""
    title: str = ""
    highest_price: float | None = None
    currency: str = ""
    colors: list[str] = field(default_factory=list)
    sizes: list[str] = field(default_factory=list)
    description: str = ""
    image_urls: list[str] = field(default_factory=list)
    category: str = ""
    status: str = "ok"
    mode: str = ""
    notes: str = ""
    raw_json: dict[str, Any] | None = None
    dedupe_key: str = ""
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self) -> None:
        now = utc_now_iso()
        if not self.created_at:
            self.created_at = now
        if not self.updated_at:
            self.updated_at = now
        if self.status not in VALID_STATUSES:
            raise ValueError(f"Invalid status {self.status!r}, expected one of {sorted(VALID_STATUSES)}")
        if not self.dedupe_key:
            self.dedupe_key = build_product_dedupe_key(self)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_product_dedupe_key(record: ProductRecord) -> str:
    """Build a category-aware deduplication key from a product record.

    Default strategy: source_site + category + canonical_url (or title fallback).
    This is intentionally generic. Site-specific overrides can replace this
    function at the store layer if needed.
    """
    parts = [
        record.source_site or "",
        record.category or "",
        record.canonical_url or record.source_url or record.title or "",
    ]
    raw = "|".join(parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def record_to_row(record: ProductRecord) -> dict[str, Any]:
    """Convert a ProductRecord to a flat dict suitable for SQLite insertion."""
    return {
        "run_id": record.run_id,
        "source_site": record.source_site,
        "source_url": record.source_url,
        "canonical_url": record.canonical_url,
        "title": record.title,
        "highest_price": record.highest_price,
        "currency": record.currency,
        "colors": _list_to_json(record.colors),
        "sizes": _list_to_json(record.sizes),
        "description": record.description,
        "image_urls": _list_to_json(record.image_urls),
        "category": record.category,
        "status": record.status,
        "mode": record.mode,
        "notes": record.notes,
        "raw_json": _dict_to_json(record.raw_json),
        "dedupe_key": record.dedupe_key,
        "created_at": record.created_at,
        "updated_at": record.updated_at,
    }


def row_to_record(row: dict[str, Any]) -> ProductRecord:
    """Convert a SQLite row dict back to a ProductRecord."""
    return ProductRecord(
        run_id=row.get("run_id", ""),
        source_site=row.get("source_site", ""),
        source_url=row.get("source_url", ""),
        canonical_url=row.get("canonical_url", ""),
        title=row.get("title", ""),
        highest_price=row.get("highest_price"),
        currency=row.get("currency", ""),
        colors=_json_to_list(row.get("colors")),
        sizes=_json_to_list(row.get("sizes")),
        description=row.get("description", ""),
        image_urls=_json_to_list(row.get("image_urls")),
        category=row.get("category", ""),
        status=row.get("status", "ok"),
        mode=row.get("mode", ""),
        notes=row.get("notes", ""),
        raw_json=_json_to_dict(row.get("raw_json")),
        dedupe_key=row.get("dedupe_key", ""),
        created_at=row.get("created_at", ""),
        updated_at=row.get("updated_at", ""),
    )


def _list_to_json(value: list[str] | None) -> str:
    if not value:
        return "[]"
    import json
    return json.dumps(value, ensure_ascii=False)


def _dict_to_json(value: dict[str, Any] | None) -> str:
    if not value:
        return "{}"
    import json
    return json.dumps(value, ensure_ascii=False)


def _json_to_list(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        return value
    import json
    try:
        parsed = json.loads(value)
        if isinstance(parsed, list):
            return parsed
    except (json.JSONDecodeError, TypeError):
        pass
    return []


def _json_to_dict(value: Any) -> dict[str, Any] | None:
    if not value:
        return None
    if isinstance(value, dict):
        return value
    import json
    try:
        parsed = json.loads(value)
        if isinstance(parsed, dict):
            return parsed
    except (json.JSONDecodeError, TypeError):
        pass
    return None
