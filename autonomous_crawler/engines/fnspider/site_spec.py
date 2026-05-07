from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup


DEFAULT_REQUIRED_FIELDS = ["handle", "title", "image_src", "price"]


class SiteSpecError(ValueError):
    pass


def load_site_spec(path_or_spec: str | dict[str, Any]) -> dict[str, Any]:
    if isinstance(path_or_spec, dict):
        spec = path_or_spec
    else:
        path = Path(path_or_spec)
        spec = json.loads(path.read_text(encoding="utf-8"))
    validate_site_spec(spec)
    return spec


def validate_site_spec(spec: dict[str, Any]) -> None:
    if not isinstance(spec, dict):
        raise SiteSpecError("site spec must be a JSON object")
    if not spec.get("site"):
        raise SiteSpecError("site spec requires a site name")
    if not isinstance(spec.get("start_urls", []), list):
        raise SiteSpecError("start_urls must be a list")
    list_spec = spec.get("list", {})
    detail_spec = spec.get("detail", {})
    if not isinstance(list_spec, dict):
        raise SiteSpecError("list must be an object")
    if not isinstance(detail_spec, dict):
        raise SiteSpecError("detail must be an object")
    if not list_spec.get("item_link"):
        raise SiteSpecError("list.item_link is required")
    for field in spec.get("required_fields", DEFAULT_REQUIRED_FIELDS):
        if field in {"handle", "sole_id"}:
            continue
        if field not in detail_spec and field != "image_src":
            raise SiteSpecError(f"detail.{field} is required by required_fields")


def normalize_site_spec(spec: dict[str, Any]) -> dict[str, Any]:
    validate_site_spec(spec)
    normalized = dict(spec)
    normalized.setdefault("mode", "browser")
    normalized.setdefault("start_urls", [])
    normalized.setdefault("pagination", {})
    normalized.setdefault("variants", {})
    normalized.setdefault("dedupe", ["categories_1", "categories_2", "categories_3", "url"])
    normalized.setdefault("required_fields", DEFAULT_REQUIRED_FIELDS)
    normalized.setdefault("driver", {})
    return normalized


def selector_parts(expression: str) -> tuple[str, str]:
    if "@" not in expression:
        return expression.strip(), "text"
    selector, attr = expression.rsplit("@", 1)
    return selector.strip(), attr.strip() or "text"


def select_values(soup: BeautifulSoup, expression: str, base_url: str = "") -> list[str]:
    selector, attr = selector_parts(expression)
    if not selector:
        return []
    result: list[str] = []
    for element in soup.select(selector):
        if attr == "text":
            value = element.get_text(" ", strip=True)
        elif attr == "html":
            value = "".join(str(child) for child in element.contents).strip()
        else:
            value = element.get(attr, "")
        if not value:
            continue
        if attr in {"href", "src", "srcset"} and base_url:
            value = urljoin(base_url, value)
        result.append(value)
    return result


def first_value(soup: BeautifulSoup, expressions: str | list[str], base_url: str = "") -> str:
    for expression in _as_list(expressions):
        values = select_values(soup, expression, base_url=base_url)
        if values:
            return values[0]
    return ""


def all_values(soup: BeautifulSoup, expressions: str | list[str], base_url: str = "") -> list[str]:
    seen = set()
    result = []
    for expression in _as_list(expressions):
        for value in select_values(soup, expression, base_url=base_url):
            if value not in seen:
                seen.add(value)
                result.append(value)
    return result


def clean_price(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    text = text.replace("\xa0", " ").replace(" ", "")
    text = re.sub(r"[^\d,.\-]", "", text)
    if not text:
        return None
    if "," in text and "." in text:
        text = text.replace(".", "").replace(",", ".")
    elif "," in text:
        text = text.replace(",", ".")
    try:
        return float(text)
    except ValueError:
        match = re.search(r"\d+(?:\.\d+)?", text)
        return float(match.group(0)) if match else None


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if item]
    return [str(value)]
