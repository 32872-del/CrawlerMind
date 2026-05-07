"""Extractor Agent - Extracts structured data from raw HTML/API responses.

Responsibilities (README Section 7):
- Structured extraction
- Schema normalization
- Confidence scoring
"""
from __future__ import annotations

import re
from typing import Any

from bs4 import BeautifulSoup

from .base import preserve_state


RESERVED_SELECTOR_KEYS = {"item_container"}


@preserve_state
def extractor_node(state: dict[str, Any]) -> dict[str, Any]:
    """Extract structured data from raw_html using selectors from crawl_strategy.

    This is a STUB implementation. In production, this node will:
    1. Get selectors from crawl_strategy
    2. Parse raw_html with BeautifulSoup
    3. Extract fields using CSS selectors
    4. Normalize and clean data
    5. Compute confidence score
    """
    raw_html = state.get("raw_html", {})
    strategy = state.get("crawl_strategy", {})
    selectors = strategy.get("selectors", {})
    max_items = int(strategy.get("max_items", 0) or 0)
    recon_report = state.get("recon_report", {})
    target_fields = recon_report.get("target_fields", ["title", "price"])

    # --- STUB: Simple extraction using BeautifulSoup ---
    items = []
    for url, html in raw_html.items():
        if not html or not isinstance(html, str):
            continue
        soup = BeautifulSoup(html, "lxml")
        container_selector = selectors.get("item_container", ".product-item")
        try:
            containers = soup.select(container_selector)
        except Exception:
            continue

        for i, container in enumerate(containers):
            item: dict[str, Any] = {"url": url, "index": i}

            for field, expression in selectors.items():
                if field in RESERVED_SELECTOR_KEYS:
                    continue
                value = _extract_value(container, expression)
                if value in {"", None}:
                    continue
                if field == "price":
                    value = _clean_price(value)
                item[field] = value

            # Only include items with at least a title
            if item.get("title"):
                if "rank" in selectors:
                    item["rank"] = str(len(items) + 1)
                items.append(item)
                if max_items and len(items) >= max_items:
                    break
        if max_items and len(items) >= max_items:
            break

    # Compute confidence over requested fields only. System fields such as
    # url/index/link should not inflate confidence beyond 1.0.
    if items:
        fields_found = set()
        requested_fields_found = set()
        for item in items:
            fields_found.update(k for k, v in item.items() if v)
            requested_fields_found.update(
                field for field in target_fields if item.get(field)
            )
        confidence = min(
            len(requested_fields_found) / max(len(target_fields), 1),
            1.0,
        )
    else:
        fields_found = set()
        confidence = 0.0

    return {
        "status": "extracted",
        "extracted_data": {
            "items": items,
            "fields_found": list(fields_found) if items else [],
            "confidence": confidence,
            "item_count": len(items),
        },
        "messages": state.get("messages", []) + [f"[Extractor] Extracted {len(items)} items, confidence={confidence:.2f}, fields={list(fields_found) if items else []}"],
    }


def _extract_value(container, expression: str) -> str:
    if not expression:
        return ""
    if "@" in expression:
        css_sel, attr = expression.rsplit("@", 1)
    else:
        css_sel, attr = expression, "text"
    try:
        element = container.select_one(css_sel)
    except Exception:
        return ""
    if not element:
        return ""
    if attr == "text":
        return element.get_text(" ", strip=True)
    if attr == "html":
        return "".join(str(child) for child in element.contents).strip()
    return element.get(attr, "") or ""


def _clean_price(value: Any) -> float | str:
    price_text = str(value)
    cleaned = re.sub(r"[^\d.,]", "", price_text.replace(",", "."))
    try:
        return float(cleaned)
    except ValueError:
        return price_text
