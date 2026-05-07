"""Adapters between Agent strategy state and spider_Uvex site_spec format."""
from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse


def build_site_spec(
    *,
    user_goal: str,
    target_url: str,
    recon_report: dict[str, Any],
    selectors: dict[str, str],
    mode: str = "http",
) -> dict[str, Any]:
    """Build a spider_Uvex-compatible site_spec draft.

    The draft is intentionally conservative: list and detail selectors are the
    same when only a listing page is known. Later MCP/sample-based recon can
    refine detail selectors using real product pages.
    """
    site_name = _site_name(target_url)
    spider_mode = _spider_mode(mode, recon_report)
    item_selector = selectors.get("item_container", "")
    link_selector = selectors.get("link", "a@href")
    title_selector = selectors.get("title", "h1, h2, h3")
    price_selector = selectors.get("price", ".price")
    image_selector = selectors.get("image", "img@src")

    return {
        "version": "1.0",
        "site": site_name,
        "goal": user_goal,
        "mode": spider_mode,
        "start_urls": [{"url": target_url}],
        "pagination": _pagination_spec(recon_report),
        "list": {
            "item_container": item_selector,
            "item_link": link_selector,
        },
        "detail": {
            "title": title_selector,
            "price": price_selector,
            "image_src": image_selector,
        },
        "variants": {},
        "wait_selector": item_selector or "",
        "sleep_time": 3 if spider_mode == "browser" else 0,
        "scroll_count": 2 if _needs_scroll(recon_report) else 0,
        "scroll_delay": 1.0,
        "dedupe": ["url"],
        "required_fields": ["handle", "title", "image_src", "price"],
        "source": "autonomous_crawler.strategy",
    }


def _site_name(target_url: str) -> str:
    parsed = urlparse(target_url)
    host = parsed.netloc or parsed.path or "site"
    name = re.sub(r"[^a-zA-Z0-9]+", "_", host).strip("_").lower()
    return name or "site"


def _spider_mode(mode: str, recon_report: dict[str, Any]) -> str:
    rendering = str(recon_report.get("rendering", "")).lower()
    anti_bot = recon_report.get("anti_bot", {})
    if mode == "browser" or rendering == "spa" or anti_bot.get("detected"):
        return "browser"
    if mode == "http":
        return "curl_cffi"
    return mode or "curl_cffi"


def _pagination_spec(recon_report: dict[str, Any]) -> dict[str, Any]:
    dom = recon_report.get("dom_structure", {})
    pagination_type = dom.get("pagination_type", "none")
    if pagination_type == "url_param":
        return {"page_param": "page", "max_pages": 1}
    if pagination_type == "next_link":
        return {"next_selector": "a[rel=next], .next, .pagination-next", "max_pages": 1}
    return {"max_pages": 1}


def _needs_scroll(recon_report: dict[str, Any]) -> bool:
    dom = recon_report.get("dom_structure", {})
    return dom.get("pagination_type") == "infinite_scroll"
