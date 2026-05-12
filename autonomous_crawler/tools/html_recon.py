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

from .access_diagnostics import diagnose_access, detect_challenge
from .access_config import AccessConfig
from .api_candidates import build_api_candidates, build_direct_json_candidate
from .fetch_policy import BestFetchResult, FetchAttempt, fetch_best_page
from .site_zoo import fixture_by_url


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

MOCK_JS_SHELL_HTML = """
<html>
  <body>
    <div id="root"></div>
    <script src="/static/runtime.js"></script>
    <script src="/static/vendor.js"></script>
    <script src="/static/app.js"></script>
    <script>window.__APP_CONFIG__ = {"api": "/api/products"};</script>
    <script>fetch('/api/products?page=1')</script>
    <script>console.log('hydrate')</script>
  </body>
</html>
"""

MOCK_CHALLENGE_HTML = """
<html>
  <head><title>Just a moment...</title></head>
  <body>
    <div id="cf-challenge">Checking your browser before accessing this site.</div>
  </body>
</html>
"""

MOCK_STRUCTURED_HTML = """
<html>
  <head>
    <script type="application/ld+json">
      {"@context": "https://schema.org", "@type": "Product", "name": "Structured Jacket"}
    </script>
    <script id="__NEXT_DATA__" type="application/json">
      {"props": {"pageProps": {"products": [{"title": "Structured Jacket"}]}}}
    </script>
  </head>
  <body><main><h1>Structured Jacket</h1></main></body>
</html>
"""

MOCK_RENDERED_HTML = """
<html>
  <body>
    <main class="catalog-grid">
      <article class="catalog-card">
        <a class="product-link" href="/products/rendered">
          <h2 class="product-name">Rendered Product</h2>
          <span class="product-price">$42.00</span>
        </a>
      </article>
      <article class="catalog-card">
        <a class="product-link" href="/products/rendered-two">
          <h2 class="product-name">Rendered Product Two</h2>
          <span class="product-price">$84.00</span>
        </a>
      </article>
    </main>
  </body>
</html>
"""

MOCK_TAILWIND_LINKS_HTML = """
<html>
  <body>
    <nav>
      <div class="text-sm px-2">
        <a class="text-link dark:text-link-dark" href="/learn/a">Learn A</a>
      </div>
      <div class="text-sm px-2">
        <a class="text-link dark:text-link-dark" href="/learn/b">Learn B</a>
      </div>
    </nav>
  </body>
</html>
"""

# HN Algolia-style rendered DOM: modern SPA with CSS module class names,
# nested link/title structures, and bare-text score/metadata nodes.
MOCK_HN_ALGOLIA_HTML = """
<html>
  <body>
    <main class="content">
      <ol class="stories_list">
        <li class="stories_story">
          <article class="Story_storyContainer Story_story" data-testid="story-item">
            <div class="Story_titleRow">
              <a class="Story_titleLink" href="https://example.com/article-1" data-testid="story-link">
                <span class="Story_title" data-testid="story-title">Show HN: A New Search Engine</span>
              </a>
              <span class="Story_source">(example.com)</span>
            </div>
            <div class="Story_meta" data-testid="story-meta">
              123 points by user1 3 hours ago | 45 comments
            </div>
          </article>
        </li>
        <li class="stories_story">
          <article class="Story_storyContainer Story_story" data-testid="story-item">
            <div class="Story_titleRow">
              <a class="Story_titleLink" href="https://blog.example.org/post-2" data-testid="story-link">
                <span class="Story_title" data-testid="story-title">Ask HN: Best Practices for Crawling</span>
              </a>
              <span class="Story_source">(blog.example.org)</span>
            </div>
            <div class="Story_meta" data-testid="story-meta">
              89 points by user2 5 hours ago | 12 comments
            </div>
          </article>
        </li>
        <li class="stories_story">
          <article class="Story_storyContainer Story_story" data-testid="story-item">
            <div class="Story_titleRow">
              <a class="Story_titleLink" href="https://news.example.com/breaking" data-testid="story-link">
                <span class="Story_title" data-testid="story-title">Breaking: Major Tech Acquisition Announced</span>
              </a>
              <span class="Story_source">(news.example.com)</span>
            </div>
            <div class="Story_meta" data-testid="story-meta">
              456 points by user3 1 hour ago | 200 comments
            </div>
          </article>
        </li>
      </ol>
    </main>
  </body>
</html>
"""

# Variant: articles with <time> elements and explicit points spans.
MOCK_HN_ALGOLIA_VARIANT_HTML = """
<html>
  <body>
    <main class="content">
      <ol class="stories_list">
        <li class="stories_story">
          <article class="Story_storyContainer Story_story" data-testid="story-item">
            <div class="Story_titleRow">
              <a class="Story_titleLink" href="https://example.com/a" data-testid="story-link">
                <span class="Story_title" data-testid="story-title">First Article</span>
              </a>
            </div>
            <div class="Story_meta">
              <span class="Story_score" data-testid="story-score">72 points</span>
              by <a class="Story_user" href="/user/alpha">alpha</a>
              <time datetime="2026-05-09T10:00:00Z">2 hours ago</time>
              | <a href="/item/111">34 comments</a>
            </div>
          </article>
        </li>
        <li class="stories_story">
          <article class="Story_storyContainer Story_story" data-testid="story-item">
            <div class="Story_titleRow">
              <a class="Story_titleLink" href="https://example.com/b" data-testid="story-link">
                <span class="Story_title" data-testid="story-title">Second Article</span>
              </a>
            </div>
            <div class="Story_meta">
              <span class="Story_score" data-testid="story-score">210 points</span>
              by <a class="Story_user" href="/user/beta">beta</a>
              <time datetime="2026-05-09T08:00:00Z">4 hours ago</time>
              | <a href="/item/222">88 comments</a>
            </div>
          </article>
        </li>
        <li class="stories_story">
          <article class="Story_storyContainer Story_story" data-testid="story-item">
            <div class="Story_titleRow">
              <a class="Story_titleLink" href="https://example.com/c" data-testid="story-link">
                <span class="Story_title" data-testid="story-title">Third Article</span>
              </a>
            </div>
            <div class="Story_meta">
              <span class="Story_score" data-testid="story-score">15 points</span>
              by <a class="Story_user" href="/user/gamma">gamma</a>
              <time datetime="2026-05-09T12:00:00Z">30 minutes ago</time>
              | <a href="/item/332">2 comments</a>
            </div>
          </article>
        </li>
      </ol>
    </main>
  </body>
</html>
"""

PRICE_RE = re.compile(
    r"(?i)(?:[$€£¥]\s*\d[\d\s,.]*|\d[\d\s,.]*(?:pln|usd|eur|gbp|cny|rmb|zł))"
)
SCORE_RE = re.compile(r"(?:\d+(?:\.\d+)?\s*(?:分|/10)?|评分)", re.I)
POINTS_RE = re.compile(r"\b\d+\s*(?:points?|votes?|likes?|upvotes?)\b", re.I)
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
    if url == "mock://js-shell":
        return FetchResult(url=url, html=MOCK_JS_SHELL_HTML, status_code=200)
    if url == "mock://challenge":
        return FetchResult(url=url, html=MOCK_CHALLENGE_HTML, status_code=403)
    if url == "mock://structured":
        return FetchResult(url=url, html=MOCK_STRUCTURED_HTML, status_code=200)
    if url == "mock://json-direct":
        return FetchResult(url=url, html='[{"title":"JSON Alpha"},{"title":"JSON Beta"}]', status_code=200)
    if url == "mock://api/graphql-countries":
        return FetchResult(url=url, html='{"data":{"countries":[]}}', status_code=200)
    if url == "mock://tailwind-links":
        return FetchResult(url=url, html=MOCK_TAILWIND_LINKS_HTML, status_code=200)
    if url == "mock://hn-algolia":
        return FetchResult(url=url, html=MOCK_HN_ALGOLIA_HTML, status_code=200)
    if url == "mock://hn-algolia-variant":
        return FetchResult(url=url, html=MOCK_HN_ALGOLIA_VARIANT_HTML, status_code=200)
    site_zoo_fixture = fixture_by_url(url)
    if site_zoo_fixture:
        status_code = 403 if site_zoo_fixture.category == "challenge" else 200
        return FetchResult(url=url, html=site_zoo_fixture.html, status_code=status_code)

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


def fetch_best_html(
    url: str,
    headers: dict[str, str] | None = None,
    access_config: dict[str, Any] | None = None,
) -> BestFetchResult:
    """Fetch the best available HTML for recon, including deterministic mocks."""
    mock = _mock_best_fetch(url)
    if mock is not None:
        return mock

    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        attempt = FetchAttempt(mode="none", url=url, error=f"unsupported scheme: {url}")
        attempt.score = -100
        attempt.reasons = [f"error:{attempt.error}"]
        return BestFetchResult(
            url=url,
            html="",
            status_code=None,
            mode="none",
            score=-100,
            attempts=[attempt],
            error=attempt.error,
        )

    merged_headers = {**DEFAULT_RECON_HEADERS, **(headers or {})}
    resolved_access = AccessConfig.from_dict(access_config)
    return fetch_best_page(
        url,
        headers=merged_headers,
        session_profile=resolved_access.session_profile,
        proxy_config=resolved_access.proxy,
        rate_limit_policy=resolved_access.rate_limit,
        browser_options={"browser_context": resolved_access.browser_context},
    )


def _mock_best_fetch(url: str) -> BestFetchResult | None:
    fixture_map = {
        "mock://catalog": MOCK_PRODUCT_HTML,
        "mock://ranking": MOCK_RANKING_HTML,
        "mock://structured": MOCK_STRUCTURED_HTML,
        "mock://json-direct": '[{"title":"JSON Alpha"},{"title":"JSON Beta"}]',
        "mock://api/graphql-countries": '{"data":{"countries":[]}}',
        "mock://tailwind-links": MOCK_TAILWIND_LINKS_HTML,
        "mock://hn-algolia": MOCK_HN_ALGOLIA_HTML,
        "mock://hn-algolia-variant": MOCK_HN_ALGOLIA_VARIANT_HTML,
    }
    if url in fixture_map:
        attempt = FetchAttempt(mode="mock", url=url, html=fixture_map[url], status_code=200)
        attempt.score, attempt.reasons = (100, ["mock_fixture"])
        attempt.diagnostics = diagnose_access(attempt.html, url=url)
        return BestFetchResult(url=url, html=attempt.html, status_code=200, mode="mock", score=100, attempts=[attempt])

    if url == "mock://challenge":
        attempt = FetchAttempt(mode="mock", url=url, html=MOCK_CHALLENGE_HTML, status_code=403)
        attempt.score, attempt.reasons = (0, ["mock_challenge"])
        attempt.diagnostics = diagnose_access(attempt.html, url=url)
        return BestFetchResult(url=url, html=attempt.html, status_code=403, mode="mock", score=0, attempts=[attempt])

    if url == "mock://js-shell":
        http_attempt = FetchAttempt(mode="requests", url=url, html=MOCK_JS_SHELL_HTML, status_code=200)
        http_attempt.score, http_attempt.reasons = (-5, ["mock_js_shell", "js_shell"])
        http_attempt.diagnostics = diagnose_access(http_attempt.html, url=url)
        browser_attempt = FetchAttempt(mode="browser", url=url, html=MOCK_RENDERED_HTML, status_code=200)
        browser_attempt.score, browser_attempt.reasons = (90, ["mock_rendered", "dom_candidates"])
        browser_attempt.diagnostics = diagnose_access(browser_attempt.html, url=url)
        return BestFetchResult(
            url=url,
            html=MOCK_RENDERED_HTML,
            status_code=200,
            mode="browser",
            score=90,
            attempts=[http_attempt, browser_attempt],
        )
    site_zoo_fixture = fixture_by_url(url)
    if site_zoo_fixture:
        status_code = 403 if site_zoo_fixture.category == "challenge" else 200
        attempt = FetchAttempt(
            mode="mock",
            url=url,
            html=site_zoo_fixture.html,
            status_code=status_code,
        )
        attempt.score, attempt.reasons = (100, ["site_zoo_fixture"])
        if site_zoo_fixture.category == "challenge":
            attempt.score, attempt.reasons = (0, ["site_zoo_challenge"])
        attempt.diagnostics = diagnose_access(attempt.html, url=url)
        return BestFetchResult(
            url=url,
            html=attempt.html,
            status_code=status_code,
            mode="mock",
            score=attempt.score,
            attempts=[attempt],
        )
    return None


def build_recon_report(url: str, html: str) -> dict[str, Any]:
    if _looks_like_json_payload(html):
        access_diagnostics = diagnose_access(html, url=url)
        return {
            "target_url": url,
            "frontend_framework": "api",
            "rendering": "api",
            "anti_bot": detect_anti_bot(html),
            "api_endpoints": [url],
            "api_candidates": [build_direct_json_candidate(url)],
            "dom_structure": {
                "is_product_list": False,
                "has_pagination": False,
                "pagination_type": "none",
                "product_selector": "",
                "item_count": 0,
                "field_selectors": {},
                "candidates": [],
            },
            "access_diagnostics": access_diagnostics,
        }

    soup = BeautifulSoup(html or "", "lxml")
    dom_structure = infer_dom_structure(soup, base_url=url)
    access_diagnostics = diagnose_access(
        html,
        url=url,
        target_selector=dom_structure.get("product_selector", ""),
    )
    return {
        "target_url": url,
        "frontend_framework": detect_framework(html),
        "rendering": detect_rendering(html),
        "anti_bot": detect_anti_bot(html),
        "api_endpoints": discover_api_endpoints(html, base_url=url),
        "api_candidates": build_api_candidates(
            access_diagnostics.get("signals", {}).get("api_hints", []),
            base_url=url,
        ),
        "dom_structure": dom_structure,
        "access_diagnostics": access_diagnostics,
    }


def _looks_like_json_payload(text: str) -> bool:
    stripped = (text or "").lstrip()
    return stripped.startswith("{") or stripped.startswith("[")


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
    soup = BeautifulSoup(html or "", "lxml")
    text_len = len(soup.get_text(" ", strip=True))
    script_count = len(soup.find_all("script"))
    has_app_root = "id=\"root\"" in lowered or "id=\"app\"" in lowered
    if (text_len < 80 and has_app_root) or (text_len < 500 and script_count >= 5 and has_app_root):
        return "spa"
    return "static"


def detect_anti_bot(html: str) -> dict[str, Any]:
    if _looks_like_json_payload(html):
        return {
            "detected": False,
            "type": "none",
            "severity": "low",
            "indicators": [],
        }
    challenge = detect_challenge(html)
    lowered = html.lower()
    matches = [pattern for pattern in BOT_PATTERNS if pattern in lowered]
    if challenge and challenge not in matches:
        matches.insert(0, challenge)
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
    score += 1 if fields.get("date") else 0
    text_lengths = [len(element.get_text(" ", strip=True)) for element in elements[:5]]
    if text_lengths and max(text_lengths) > 1000:
        score -= 4
    return score


def _infer_field_selectors(container: Tag) -> dict[str, str]:
    fields: dict[str, str] = {}

    title = container.select_one("[class*=title], [class*=name], h1, h2, h3, h4")
    if not title:
        title = container.select_one("[data-testid*=title]")
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

    hot_score = container.select_one(
        "[class*=hot-index], [class*=hot_score], [class*=score], "
        "[class*=heat], [class*=rating_num], [property*=ratingValue], "
        "[itemprop=ratingValue]"
    )
    if not hot_score:
        hot_score = _find_score_element(container)
    if hot_score:
        fields["hot_score"] = _relative_selector(hot_score)

    summary = container.select_one("[class*=desc], [class*=summary], [class*=intro]")
    if not summary:
        summary = container.select_one("[data-testid*=summary], [data-testid*=desc]")
    if summary:
        fields["summary"] = _relative_selector(summary)

    time_el = container.select_one("time[datetime]")
    if time_el:
        fields["date"] = _relative_selector(time_el) + "@datetime"
    elif container.select_one("[class*=time], [class*=date]"):
        fields["date"] = _relative_selector(container.select_one("[class*=time], [class*=date]"))

    return fields


def _find_primary_link(container: Tag, title: Tag | None = None) -> Tag | None:
    """Prefer title/topic links over image or wrapper links."""
    selectors = [
        "a.title_dIF3B[href]",
        "a[class*=title][href]",
        "a[class*=name][href]",
        "a[data-testid*=link][href]",
        "a[data-testid*=title][href]",
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


def _find_score_element(container: Tag) -> Tag | None:
    # Check data-testid attributes first (most specific).
    testid_score = container.select_one("[data-testid*=score], [data-testid*=points]")
    if testid_score:
        return testid_score

    # Check explicit score/points class names.
    class_score = container.select_one("[class*=score], [class*=points], [class*=hot-index]")
    if class_score and POINTS_RE.search(class_score.get_text(" ", strip=True)):
        return class_score

    # Check text content for score patterns.
    for element in container.find_all(["span", "div", "strong", "b"]):
        text = element.get_text(" ", strip=True)
        if SCORE_RE.fullmatch(text) and not PRICE_RE.search(text):
            return element
        if POINTS_RE.search(text) and not PRICE_RE.search(text):
            return element
    return None


def _stable_selector(element: Tag) -> str:
    classes = [
        cls
        for cls in element.get("class", [])
        if _is_safe_css_class(str(cls))
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
        if _is_safe_css_class(str(cls))
    ]
    if classes:
        return "." + ".".join(str(cls) for cls in classes[:2])
    if element.get("itemprop"):
        return f'{element.name}[itemprop="{element["itemprop"]}"]'
    return str(element.name)


def _is_safe_css_class(class_name: str) -> bool:
    """Return whether a class can be emitted as a simple CSS selector."""
    if re.search(r"\d{3,}|active|selected|hover|open", class_name, re.I):
        return False
    return bool(re.fullmatch(r"-?[_a-zA-Z][_a-zA-Z0-9-]*", class_name))
