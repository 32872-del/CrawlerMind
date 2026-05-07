"""Deterministic HTML recon helpers for the MVP crawler workflow.

These helpers intentionally stay small and predictable. They are not meant to
beat a full MCP/browser recon pass; they provide a local fallback that gives
Strategy concrete selectors instead of hardcoded placeholders.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup, Tag


DEFAULT_RECON_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

MOCK_PRODUCT_HTML = """
<html>
  <body>
    <main class="catalog-grid">
      <article class="catalog-card">
        <a class="product-link" href="/products/alpha">
          <img class="product-photo" src="/images/alpha.jpg" />
          <h2 class="product-name">Alpha Jacket</h2>
          <span class="product-price">$129.90</span>
        </a>
      </article>
      <article class="catalog-card">
        <a class="product-link" href="/products/beta">
          <img class="product-photo" src="/images/beta.jpg" />
          <h2 class="product-name">Beta Pants</h2>
          <span class="product-price">$89.50</span>
        </a>
      </article>
    </main>
  </body>
</html>
"""

MOCK_RANKING_HTML = """
<html>
  <body>
    <div class="category-wrap_iQLoo">
      <a class="img-wrapper_29V76" href="/s?wd=alpha">
        <div class="index_1Ew5p">1</div>
        <img src="/alpha.jpg" />
      </a>
      <div class="trend_2RttY"><div class="hot-index_1Bl1a">12345</div></div>
      <div class="content_1YWBm">
        <a class="title_dIF3B" href="/s?wd=alpha">
          <div class="c-single-text-ellipsis">Alpha Topic</div>
        </a>
        <div class="hot-desc_1m_jR">Alpha summary</div>
      </div>
    </div>
    <div class="category-wrap_iQLoo">
      <a class="img-wrapper_29V76" href="/s?wd=beta">
        <div class="index_1Ew5p">2</div>
        <img src="/beta.jpg" />
      </a>
      <div class="trend_2RttY"><div class="hot-index_1Bl1a">67890</div></div>
      <div class="content_1YWBm">
        <a class="title_dIF3B" href="/s?wd=beta">
          <div class="c-single-text-ellipsis">Beta Topic</div>
        </a>
        <div class="hot-desc_1m_jR">Beta summary</div>
      </div>
    </div>
  </body>
</html>
"""

PRICE_RE = re.compile(
    r"(?i)(?:[$€£¥]\s*\d[\d\s,.]*|\d[\d\s,.]*(?:pln|usd|eur|gbp|cny|rmb|zł))"
)
API_RE = re.compile(r"""["']([^"']*(?:/api/|graphql|fetch|ajax)[^"']*)["']""", re.I)
BOT_PATTERNS = [
    "cloudflare",
    "cf-challenge",
    "captcha",
    "datadome",
    "perimeterx",
    "access denied",
    "checking your browser",
]


@dataclass
class FetchResult:
    url: str
    html: str
    status_code: int | None = None
    error: str = ""


def fetch_html(url: str, headers: dict[str, str] | None = None) -> FetchResult:
    """Fetch HTML for recon.

    The mock scheme keeps tests deterministic without network access.
    """
    if url == "mock://catalog":
        return FetchResult(url=url, html=MOCK_PRODUCT_HTML, status_code=200)
    if url == "mock://ranking":
        return FetchResult(url=url, html=MOCK_RANKING_HTML, status_code=200)

    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return FetchResult(url=url, html="", error=f"unsupported scheme: {url}")

    merged_headers = {**DEFAULT_RECON_HEADERS, **(headers or {})}
    try:
        with httpx.Client(
            follow_redirects=True,
            timeout=httpx.Timeout(20.0, connect=10.0),
            headers=merged_headers,
        ) as client:
            response = client.get(url)
            response.raise_for_status()
            return FetchResult(
                url=str(response.url),
                html=response.text,
                status_code=response.status_code,
            )
    except httpx.HTTPError as exc:
        return FetchResult(url=url, html="", error=str(exc))


def build_recon_report(url: str, html: str) -> dict[str, Any]:
    soup = BeautifulSoup(html or "", "lxml")
    dom_structure = infer_dom_structure(soup, base_url=url)
    return {
        "target_url": url,
        "frontend_framework": detect_framework(html),
        "rendering": detect_rendering(html),
        "anti_bot": detect_anti_bot(html),
        "api_endpoints": discover_api_endpoints(html, base_url=url),
        "dom_structure": dom_structure,
    }


def detect_framework(html: str) -> str:
    lowered = html.lower()
    if "__next_data__" in lowered or "/_next/static/" in lowered:
        return "nextjs"
    if "__nuxt__" in lowered or "/_nuxt/" in lowered:
        return "nuxt"
    if "ng-version" in lowered or "ng-app" in lowered:
        return "angular"
    if "data-reactroot" in lowered or "react-dom" in lowered:
        return "react"
    if "data-v-" in lowered or "__vue__" in lowered:
        return "vue"
    return "unknown"


def detect_rendering(html: str) -> str:
    lowered = html.lower()
    if "__next_data__" in lowered or "__nuxt__" in lowered:
        return "ssr"
    if len(BeautifulSoup(html or "", "lxml").get_text(" ", strip=True)) < 80 and (
        "id=\"root\"" in lowered or "id=\"app\"" in lowered
    ):
        return "spa"
    return "static"


def detect_anti_bot(html: str) -> dict[str, Any]:
    lowered = html.lower()
    matches = [pattern for pattern in BOT_PATTERNS if pattern in lowered]
    return {
        "detected": bool(matches),
        "type": matches[0] if matches else "none",
        "severity": "high" if matches else "low",
        "indicators": matches,
    }


def discover_api_endpoints(html: str, base_url: str = "") -> list[str]:
    endpoints: list[str] = []
    seen = set()
    for match in API_RE.finditer(html or ""):
        candidate = match.group(1)
        if candidate.startswith("data:") or len(candidate) > 300:
            continue
        if "/" not in candidate and not candidate.lower().startswith("graphql"):
            continue
        if base_url and candidate.startswith("/"):
            candidate = urljoin(base_url, candidate)
        if candidate not in seen:
            seen.add(candidate)
            endpoints.append(candidate)
    return endpoints[:20]


def infer_dom_structure(soup: BeautifulSoup, base_url: str = "") -> dict[str, Any]:
    candidates = _container_candidates(soup)
    best = candidates[0] if candidates else {}
    field_selectors = best.get("field_selectors", {}) if best else {}
    product_selector = best.get("selector", "")

    pagination_type = "none"
    if soup.select_one("a[rel=next], .next, .pagination-next, .pages-item-next"):
        pagination_type = "next_link"
    elif re.search(r"[?&](?:page|p)=\d+", str(soup), re.I):
        pagination_type = "url_param"

    return {
        "is_product_list": bool(best),
        "has_pagination": pagination_type != "none",
        "pagination_type": pagination_type,
        "product_selector": product_selector,
        "item_count": best.get("count", 0) if best else 0,
        "field_selectors": field_selectors,
        "candidates": candidates[:5],
    }


def _container_candidates(soup: BeautifulSoup) -> list[dict[str, Any]]:
    grouped: dict[str, list[Tag]] = {}
    for element in soup.find_all(["article", "li", "div", "section"]):
        if not isinstance(element, Tag):
            continue
        selector = _stable_selector(element)
        if not selector:
            continue
        grouped.setdefault(selector, []).append(element)

    candidates: list[dict[str, Any]] = []
    for selector, elements in grouped.items():
        if len(elements) < 2:
            continue
        sample = elements[0]
        fields = _infer_field_selectors(sample)
        score = _score_container(elements, fields)
        if score <= 0:
            continue
        candidates.append(
            {
                "selector": selector,
                "count": len(elements),
                "score": score,
                "field_selectors": fields,
            }
        )

    return sorted(candidates, key=lambda item: item["score"], reverse=True)


def _score_container(elements: list[Tag], fields: dict[str, str]) -> int:
    score = min(len(elements), 10)
    score += 4 if fields.get("title") else 0
    score += 4 if fields.get("price") else 0
    score += 2 if fields.get("link") else 0
    score += 2 if fields.get("image") else 0
    score += 3 if fields.get("rank") else 0
    score += 3 if fields.get("hot_score") else 0
    score += 1 if fields.get("summary") else 0
    text_lengths = [len(element.get_text(" ", strip=True)) for element in elements[:5]]
    if text_lengths and max(text_lengths) > 1000:
        score -= 4
    return score


def _infer_field_selectors(container: Tag) -> dict[str, str]:
    fields: dict[str, str] = {}

    title = container.select_one("[class*=title], [class*=name], h1, h2, h3, h4")
    if not title:
        title = container.select_one("a[title], a")
    if title:
        title_child = title.select_one(".c-single-text-ellipsis")
        fields["title"] = (
            f"{_relative_selector(title)} .c-single-text-ellipsis"
            if title_child
            else _relative_selector(title)
        )

    price = _find_price_element(container)
    if price:
        fields["price"] = _relative_selector(price)

    image = container.select_one("img[src], img[data-src], source[srcset]")
    if image:
        attr = "srcset" if image.name == "source" else image.get("src") and "src"
        if not attr:
            attr = "data-src" if image.get("data-src") else "src"
        fields["image"] = f"{_relative_selector(image)}@{attr}"

    link = _find_primary_link(container, title)
    if link:
        fields["link"] = f"{_relative_selector(link)}@href"

    rank = container.select_one("[class*=index], [class*=rank], [data-rank]")
    if rank:
        fields["rank"] = _relative_selector(rank)

    hot_score = container.select_one("[class*=hot-index], [class*=hot_score], [class*=score], [class*=heat]")
    if hot_score:
        fields["hot_score"] = _relative_selector(hot_score)

    summary = container.select_one("[class*=desc], [class*=summary], [class*=intro]")
    if summary:
        fields["summary"] = _relative_selector(summary)

    return fields


def _find_primary_link(container: Tag, title: Tag | None = None) -> Tag | None:
    """Prefer title/topic links over image or wrapper links."""
    selectors = [
        "a.title_dIF3B[href]",
        "a[class*=title][href]",
        "a[class*=name][href]",
    ]
    for selector in selectors:
        link = container.select_one(selector)
        if link:
            return link

    current = title
    while isinstance(current, Tag) and current is not container:
        if current.name == "a" and current.get("href"):
            return current
        current = current.parent

    return container.select_one("a[href]")


def _find_price_element(container: Tag) -> Tag | None:
    explicit = container.select_one("[class*=price], [data-price], [itemprop=price]")
    if explicit:
        return explicit
    for element in container.find_all(["span", "div", "p", "strong", "b"]):
        if PRICE_RE.search(element.get_text(" ", strip=True)):
            return element
    return None


def _stable_selector(element: Tag) -> str:
    classes = [
        cls
        for cls in element.get("class", [])
        if not re.search(r"\d{3,}|active|selected|hover|open", str(cls), re.I)
    ]
    if classes:
        return "." + ".".join(str(cls) for cls in classes[:2])
    if element.get("data-testid"):
        return f'{element.name}[data-testid="{element["data-testid"]}"]'
    if element.get("itemtype"):
        return f'{element.name}[itemtype="{element["itemtype"]}"]'
    return ""


def _relative_selector(element: Tag) -> str:
    classes = [
        cls
        for cls in element.get("class", [])
        if not re.search(r"\d{3,}|active|selected|hover|open", str(cls), re.I)
    ]
    if classes:
        return "." + ".".join(str(cls) for cls in classes[:2])
    if element.get("itemprop"):
        return f'{element.name}[itemprop="{element["itemprop"]}"]'
    return str(element.name)
