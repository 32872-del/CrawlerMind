"""Generic product list/detail/variant task helpers."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup


@dataclass(frozen=True)
class ProductTask:
    kind: str
    url: str
    depth: int = 0
    parent_url: str = ""
    payload: dict[str, Any] | None = None

    def to_frontier_payload(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "depth": self.depth,
            "parent_url": self.parent_url,
            "payload": self.payload or {},
        }


def extract_list_tasks(html: str, base_url: str, link_selector: str) -> list[ProductTask]:
    soup = BeautifulSoup(html or "", "lxml")
    tasks: list[ProductTask] = []
    for link in soup.select(link_selector):
        href = link.get("href")
        if not href:
            continue
        tasks.append(ProductTask(kind="detail_page", url=urljoin(base_url, href), depth=1, parent_url=base_url))
    return _dedupe_tasks(tasks)


def extract_variant_tasks(html: str, base_url: str, selector: str = ".variant-link@href") -> list[ProductTask]:
    css, attr = _selector_attr(selector)
    soup = BeautifulSoup(html or "", "lxml")
    tasks: list[ProductTask] = []
    for element in soup.select(css):
        value = element.get(attr)
        if not value:
            continue
        payload = {}
        if element.get("data-color"):
            payload["color"] = element.get("data-color")
        tasks.append(ProductTask(kind="variant_page", url=urljoin(base_url, value), depth=2, parent_url=base_url, payload=payload))
    return _dedupe_tasks(tasks)


def extract_detail_record(html: str, base_url: str, selectors: dict[str, str]) -> dict[str, Any]:
    soup = BeautifulSoup(html or "", "lxml")
    root_selector = selectors.get("item_container", "body")
    root = soup.select_one(root_selector) or soup
    record: dict[str, Any] = {"url": base_url}
    for field, selector in selectors.items():
        if field == "item_container":
            continue
        value = _extract_value(root, selector, base_url)
        if value:
            record[field] = value
    return record


def _extract_value(root: Any, selector: str, base_url: str) -> str:
    css, attr = _selector_attr(selector)
    element = root.select_one(css)
    if not element:
        return ""
    if attr == "text":
        return element.get_text(" ", strip=True)
    value = element.get(attr, "")
    if attr in {"href", "src"}:
        return urljoin(base_url, value)
    return value or ""


def _selector_attr(selector: str) -> tuple[str, str]:
    if "@" not in selector:
        return selector, "text"
    css, attr = selector.rsplit("@", 1)
    return css, attr or "text"


def _dedupe_tasks(tasks: list[ProductTask]) -> list[ProductTask]:
    seen: set[tuple[str, str]] = set()
    result: list[ProductTask] = []
    for task in tasks:
        key = (task.kind, task.url)
        if key in seen:
            continue
        seen.add(key)
        result.append(task)
    return result
