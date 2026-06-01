"""HTML pagination link detection and following.

Detects common pagination patterns:
- Next page links (<a> with "next", ">", ">>", etc.)
- Page number links (<a> with page numbers)
- Load more buttons
- Infinite scroll triggers (handled by browser runtime)

Returns a list of URLs to follow for pagination.
"""
from __future__ import annotations

import re
from typing import Any
from urllib.parse import urljoin, urlparse, parse_qs, urlencode, urlunparse

from bs4 import BeautifulSoup


# Common "next page" link patterns
_NEXT_PATTERNS = [
    re.compile(r"^next$", re.IGNORECASE),
    re.compile(r"^>$"),
    re.compile(r"^>>$"),
    re.compile(r"^»$"),
    re.compile(r"^下一页", re.IGNORECASE),
    re.compile(r"^next\s*page", re.IGNORECASE),
    re.compile(r"^suivant$", re.IGNORECASE),
    re.compile(r"^volgende$", re.IGNORECASE),
    re.compile(r"^weiter$", re.IGNORECASE),
    re.compile(r"^siguiente$", re.IGNORECASE),
]

# Common pagination container patterns
_PAGINATION_SELECTORS = [
    "nav.pagination",
    "div.pagination",
    "ul.pagination",
    "[class*='pagination']",
    "[class*='pager']",
    "[aria-label='pagination']",
    "[aria-label='Pagination']",
    ".page-numbers",
    ".pagination-links",
]


def detect_pagination_links(
    html: str,
    current_url: str,
    *,
    max_pages: int = 10,
) -> list[str]:
    """Detect pagination URLs from an HTML page.

    Returns a list of URLs to follow, starting from the next page.
    """
    soup = BeautifulSoup(html, "html.parser")
    next_urls: list[str] = []

    # Strategy 1: Find "next" links in pagination containers
    next_url = _find_next_link(soup, current_url)
    if next_url:
        next_urls.append(next_url)
        # Try to find more pages by following the pattern
        remaining = max_pages - 1
        if remaining > 0:
            more_urls = _infer_remaining_pages(current_url, next_url, remaining)
            next_urls.extend(more_urls)

    # Strategy 2: Find page number links
    if not next_urls:
        page_urls = _find_page_number_links(soup, current_url, max_pages)
        next_urls.extend(page_urls)

    # Strategy 3: Detect URL-based pagination (?page=2, ?p=2, etc.)
    if not next_urls:
        url_pages = _detect_url_pagination(current_url, html, max_pages)
        next_urls.extend(url_pages)

    return list(dict.fromkeys(next_urls))  # Dedupe preserving order


def _find_next_link(soup: BeautifulSoup, current_url: str) -> str | None:
    """Find the 'next page' link in the HTML."""
    # Look in pagination containers first
    for selector in _PAGINATION_SELECTORS:
        containers = soup.select(selector)
        for container in containers:
            link = _find_next_in_container(container, current_url)
            if link:
                return link

    # Look for rel="next" link (most reliable)
    next_link = soup.find("a", attrs={"rel": "next"})
    if next_link and next_link.get("href"):
        return _resolve_url(next_link["href"], current_url)

    # Look for <link rel="next"> in head
    head_link = soup.find("link", attrs={"rel": "next"})
    if head_link and head_link.get("href"):
        return _resolve_url(head_link["href"], current_url)

    # Broader search: any link with "next" in text/class/aria-label
    for a_tag in soup.find_all("a", href=True):
        text = (a_tag.get_text(strip=True) or "").strip()
        classes = " ".join(a_tag.get("class") or [])
        aria = a_tag.get("aria-label", "")

        for pattern in _NEXT_PATTERNS:
            if pattern.search(text) or pattern.search(classes) or pattern.search(aria):
                return _resolve_url(a_tag["href"], current_url)

        # Check for common class patterns
        if re.search(r"next|forward|pagination-next", classes, re.IGNORECASE):
            return _resolve_url(a_tag["href"], current_url)

    return None


def _find_next_in_container(container: Any, current_url: str) -> str | None:
    """Find the next page link within a pagination container."""
    # Look for rel="next" inside container
    next_link = container.find("a", attrs={"rel": "next"})
    if next_link and next_link.get("href"):
        return _resolve_url(next_link["href"], current_url)

    # Look for active/current page, then find the next sibling link
    active = container.find(attrs={"class": re.compile(r"active|current|selected", re.I)})
    if active:
        # Find the next <a> after the active element
        for sibling in active.find_all_next("a", href=True, limit=3):
            text = sibling.get_text(strip=True)
            # Skip if it's a "previous" link
            if re.search(r"prev|back|<|«|上", text, re.I):
                continue
            return _resolve_url(sibling["href"], current_url)

    # Look for "next" text links
    for a_tag in container.find_all("a", href=True):
        text = (a_tag.get_text(strip=True) or "").strip()
        for pattern in _NEXT_PATTERNS:
            if pattern.search(text):
                return _resolve_url(a_tag["href"], current_url)

    return None


def _find_page_number_links(
    soup: BeautifulSoup,
    current_url: str,
    max_pages: int,
) -> list[str]:
    """Find page number links (e.g., 1, 2, 3, ...)."""
    urls: list[str] = []

    for selector in _PAGINATION_SELECTORS:
        containers = soup.select(selector)
        for container in containers:
            links = container.find_all("a", href=True)
            page_links: list[tuple[int, str]] = []

            for link in links:
                text = link.get_text(strip=True)
                # Try to parse as page number
                try:
                    page_num = int(text)
                    url = _resolve_url(link["href"], current_url)
                    page_links.append((page_num, url))
                except ValueError:
                    continue

            if page_links:
                page_links.sort(key=lambda x: x[0])
                # Only return pages after current (page 1)
                for page_num, url in page_links:
                    if page_num > 1 and len(urls) < max_pages - 1:
                        urls.append(url)
                break

    return urls


def _detect_url_pagination(
    current_url: str,
    html: str,
    max_pages: int,
) -> list[str]:
    """Detect pagination from URL patterns (?page=2, ?p=2, etc.)."""
    parsed = urlparse(current_url)
    params = parse_qs(parsed.query, keep_blank_values=True)

    # Common page parameter names
    page_params = ["page", "p", "pg", "pn", "pagina", "seite"]

    for param in page_params:
        if param in params:
            try:
                current_page = int(params[param][0])
                urls: list[str] = []
                for i in range(current_page + 1, current_page + max_pages):
                    new_params = dict(params)
                    new_params[param] = [str(i)]
                    new_query = urlencode(new_params, doseq=True)
                    new_url = urlunparse(parsed._replace(query=new_query))
                    urls.append(new_url)
                return urls[:max_pages - 1]
            except (ValueError, IndexError):
                continue

    return []


def _infer_remaining_pages(
    current_url: str,
    next_url: str,
    remaining: int,
) -> list[str]:
    """Try to infer remaining page URLs from current → next pattern."""
    urls: list[str] = []

    # Check if URL has a page parameter
    curr_parsed = urlparse(current_url)
    next_parsed = urlparse(next_url)

    curr_params = parse_qs(curr_parsed.query)
    next_params = parse_qs(next_parsed.query)

    page_params = ["page", "p", "pg", "pn"]

    for param in page_params:
        if param in curr_params and param in next_params:
            try:
                curr_page = int(curr_params[param][0])
                next_page = int(next_params[param][0])
                step = next_page - curr_page

                if step > 0:
                    for i in range(next_page + step, next_page + step * (remaining + 1), step):
                        new_params = dict(next_params)
                        new_params[param] = [str(i)]
                        new_query = urlencode(new_params, doseq=True)
                        new_url = urlunparse(next_parsed._replace(query=new_query))
                        urls.append(new_url)
                    return urls
            except (ValueError, IndexError):
                continue

    return urls


def _resolve_url(href: str, base_url: str) -> str:
    """Resolve a relative URL against a base URL."""
    if href.startswith(("http://", "https://")):
        return href
    return urljoin(base_url, href)
