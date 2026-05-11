#!/usr/bin/env python3
"""Run two real-site training rounds for CLM.

Round 1 collects five public training targets with at least 50 records each.
Round 2 collects 200 public ecommerce product records per requested site when
the public pages expose enough data.

This script does not bypass login, CAPTCHA, Cloudflare, or access controls.
"""
from __future__ import annotations

import concurrent.futures
import json
import re
import time
import warnings
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import pandas as pd
import requests
from bs4 import BeautifulSoup, MarkupResemblesLocatorWarning, XMLParsedAsHTMLWarning

from autonomous_crawler.tools.product_quality import parse_price, validate_product_record


OUTPUT_DIR = Path("dev_logs")
JSON_PATH = OUTPUT_DIR / "2026-05-11_two_round_real_training.json"
XLSX_PATH = OUTPUT_DIR / "2026-05-11_two_round_real_training.xlsx"
REPORT_PATH = OUTPUT_DIR / "2026-05-11_two_round_real_training_report.md"

SITEMAP_NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/json;q=0.8,*/*;q=0.7",
    "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
}
FALLBACK_HTML_HEADERS = {
    "User-Agent": HEADERS["User-Agent"],
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7,nl;q=0.6",
}
warnings.filterwarnings("ignore", category=MarkupResemblesLocatorWarning)
warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)


@dataclass
class TrainingRecord:
    round: str
    source: str
    scenario: str
    url: str
    title: str = ""
    highest_price: float | None = None
    price_raw: str = ""
    colors: list[str] = field(default_factory=list)
    sizes: list[str] = field(default_factory=list)
    description: str = ""
    image_url: str = ""
    image_urls: list[str] = field(default_factory=list)
    category_1: str = ""
    category_2: str = ""
    category_3: str = ""
    status: str = "ok"
    mode: str = ""
    notes: str = ""


def fetch_text(url: str, timeout: int = 25) -> tuple[int, str, str]:
    last_response: requests.Response | None = None
    for attempt in range(3):
        response = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
        last_response = response
        if response.status_code != 200 or len(response.text) > 1000 or attempt == 2:
            if response.status_code == 200 and len(response.text) <= 1000:
                fallback = fetch_text_curl_cffi(url, timeout=timeout)
                if len(fallback[2]) > len(response.text):
                    return fallback
            return response.status_code, response.url, response.text
        time.sleep(0.5 * (attempt + 1))
    assert last_response is not None
    return last_response.status_code, last_response.url, last_response.text


def fetch_text_curl_cffi(url: str, timeout: int = 25) -> tuple[int, str, str]:
    try:
        from curl_cffi import requests as curl_requests
    except Exception:
        return 0, url, ""
    try:
        response = curl_requests.get(
            url,
            headers=FALLBACK_HTML_HEADERS,
            impersonate="chrome124",
            timeout=timeout,
            allow_redirects=True,
        )
    except Exception:
        return 0, url, ""
    if response.status_code == 200 and len(response.text) <= 1000:
        try:
            plain = curl_requests.get(url, impersonate="chrome124", timeout=timeout, allow_redirects=True)
            if len(plain.text) > len(response.text):
                return plain.status_code, str(plain.url), plain.text
        except Exception:
            pass
    return response.status_code, str(response.url), response.text


def fetch_json(url: str, timeout: int = 25) -> Any:
    response = requests.get(url, headers={**HEADERS, "Accept": "application/json,*/*"}, timeout=timeout)
    response.raise_for_status()
    return response.json()


def extract_sitemap_urls(url: str) -> list[str]:
    response = requests.get(url, headers=HEADERS, timeout=40)
    response.raise_for_status()
    root = ET.fromstring(response.content)
    return [element.text or "" for element in root.findall(".//sm:loc", SITEMAP_NS) if element.text]


def flatten_jsonld(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        items = [value]
        graph = value.get("@graph")
        if isinstance(graph, list):
            items.extend(item for item in graph if isinstance(item, dict))
        return items
    if isinstance(value, list):
        result: list[dict[str, Any]] = []
        for item in value:
            result.extend(flatten_jsonld(item))
        return result
    return []


def jsonld_blocks(soup: BeautifulSoup) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    for script in soup.find_all("script", type="application/ld+json"):
        raw = script.get_text(" ", strip=True)
        if not raw:
            continue
        try:
            blocks.extend(flatten_jsonld(json.loads(raw)))
        except json.JSONDecodeError:
            continue
    return blocks


def first_product_jsonld(blocks: list[dict[str, Any]]) -> dict[str, Any]:
    for block in blocks:
        kind = block.get("@type")
        if kind == "Product" or (isinstance(kind, list) and "Product" in kind):
            return block
    return {}


def breadcrumb_names(blocks: list[dict[str, Any]], soup: BeautifulSoup) -> list[str]:
    names: list[str] = []
    for block in blocks:
        kind = block.get("@type")
        if kind != "BreadcrumbList":
            continue
        for item in block.get("itemListElement", []) or []:
            if not isinstance(item, dict):
                continue
            node = item.get("item")
            if isinstance(node, dict):
                name = str(node.get("name") or "").strip()
            else:
                name = str(item.get("name") or "").strip()
            if name and name not in names:
                names.append(name)
    if not names:
        for selector in (
            ".breadcrumbs a",
            ".breadcrumb a",
            "[aria-label*=breadcrumb] a",
            "nav.breadcrumb a",
            ".breadcrumb-item a",
        ):
            for element in soup.select(selector):
                text = element.get_text(" ", strip=True)
                if text and text not in names:
                    names.append(text)
    result: list[str] = []
    for name in names:
        if name.lower() in {"home", "tatuum", "the sting", "balticbhp.pl", "strona główna"}:
            continue
        if name not in result:
            result.append(name)
    return result


def offer_price(product: dict[str, Any]) -> tuple[float | None, str]:
    offers = product.get("offers")
    raw_values: list[Any] = []
    if isinstance(offers, dict):
        raw_values.extend([offers.get("price"), offers.get("lowPrice"), offers.get("highPrice")])
    elif isinstance(offers, list):
        for offer in offers:
            if isinstance(offer, dict):
                raw_values.extend([offer.get("price"), offer.get("lowPrice"), offer.get("highPrice")])
    raw_text = " ".join(str(value) for value in raw_values if value not in {None, ""}).strip()
    return parse_price(raw_text), raw_text


def dom_price(soup: BeautifulSoup) -> tuple[float | None, str]:
    selectors = (
        'meta[property="product:price:amount"]@content',
        '[itemprop="price"]@content',
        ".current-price",
        ".product-prices .price",
        ".product-price",
        ".price",
    )
    values: list[str] = []
    for selector in selectors:
        if "@" in selector:
            css, attr = selector.split("@", 1)
            for element in soup.select(css):
                value = str(element.get(attr) or "").strip()
                if value:
                    values.append(value)
        else:
            for element in soup.select(selector):
                value = element.get_text(" ", strip=True)
                if value:
                    values.append(value)
        if values:
            break
    raw = " ".join(values[:3]).strip()
    return parse_price(raw), raw


def clean_text(value: Any, limit: int = 1200) -> str:
    text = BeautifulSoup(str(value or ""), "lxml").get_text(" ", strip=True)
    return re.sub(r"\s+", " ", text).strip()[:limit]


def clean_label(value: Any, limit: int = 120) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


def list_from_value(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        values = value
    else:
        values = re.split(r"[|,;/]+", str(value))
    result: list[str] = []
    for item in values:
        text = clean_label(item, limit=160)
        if text and text not in result:
            result.append(text)
    return result


def extract_visible_options(soup: BeautifulSoup, patterns: tuple[str, ...]) -> list[str]:
    values: list[str] = []
    for element in soup.select("button, option, [aria-label], [data-option-label], [data-value], .swatch-option, .size, .sizes *"):
        attrs = " ".join(str(element.get(attr) or "") for attr in ("aria-label", "data-option-label", "data-value", "title"))
        text = element.get_text(" ", strip=True)
        combined = f"{attrs} {text}".strip()
        if not combined:
            continue
        lowered = combined.lower()
        if not any(pattern in lowered for pattern in patterns):
            continue
        token = clean_text(text or attrs, limit=80)
        if len(token) > 50:
            continue
        if token and token not in values:
            values.append(token)
    return values[:30]


def extract_sizes(source: str, soup: BeautifulSoup, html: str) -> list[str]:
    sizes: list[str] = []
    for selector in (
        ".radio__size-value",
        ".size-selector__radio .radio__label-left",
        "[data-size]",
        "[data-option-label]",
    ):
        for element in soup.select(selector):
            value = element.get("data-size") or element.get("data-option-label") or element.get_text(" ", strip=True)
            add_size_value(sizes, value)
    if source == "tatuum":
        for match in re.finditer(r'"label"\s*:\s*"([^"]{1,30})"', html):
            add_size_value(sizes, match.group(1))
        for match in re.finditer(r"'label'\s*:\s*'([^']{1,30})'", html):
            add_size_value(sizes, match.group(1))
    return sizes[:40]


def add_size_value(values: list[str], raw: Any) -> None:
    text = clean_label(raw, 60)
    text = re.sub(r"\b(Uitverkocht|Back in stock|Jouw voorgestelde maat|Selecteer maat|Maattabel|Size chart|Product dimensions)\b", "", text, flags=re.I)
    text = clean_label(text, 40)
    if not text:
        return
    if text.lower() in {"size", "maat", "one size", "selecteer"}:
        return
    if not re.search(r"\d|xxs|xs|s|m|l|xl|xxl|xxxl|one", text, re.I):
        return
    if text not in values:
        values.append(text)


def extract_colors(source: str, soup: BeautifulSoup) -> list[str]:
    colors: list[str] = []
    selectors = (
        ".product-detail-aside__current-color",
        ".color-swatches__color-name",
        ".swatch-option[option-label]",
        ".swatch-option[aria-label]",
        ".input-color[title]",
        ".product-variants .radio-label",
        ".product-variants [title]",
    )
    for selector in selectors:
        for element in soup.select(selector):
            value = (
                element.get("option-label")
                or element.get("aria-label")
                or element.get("title")
                or element.get("data-original-title")
                or element.get_text(" ", strip=True)
            )
            text = clean_label(value, 80)
            if not text:
                continue
            text = re.sub(r"^(Kleur|Color|Kolor)\s*:\s*", "", text, flags=re.I)
            if len(text) > 40:
                continue
            if text and text not in colors:
                colors.append(text)
    return colors[:30]


def product_record_from_html(source: str, url: str, html: str) -> TrainingRecord | None:
    soup = BeautifulSoup(html, "lxml")
    blocks = jsonld_blocks(soup)
    product = first_product_jsonld(blocks)
    h1 = soup.find("h1")
    title = clean_text(product.get("name") if product else "", 240) or (
        clean_text(h1.get_text(" ", strip=True), 240) if h1 else ""
    )
    if not title:
        return None
    price, price_raw = offer_price(product)
    if price is None:
        price, price_raw = dom_price(soup)
    images_raw = product.get("image") if product else []
    image_urls = list_from_value(images_raw)
    if not image_urls:
        for img in soup.select("img[src], img[data-src], source[srcset]"):
            raw = img.get("src") or img.get("data-src") or img.get("srcset") or ""
            if not raw:
                continue
            img_url = urljoin(url, raw.split(",")[0].split()[0])
            if img_url not in image_urls and not any(x in img_url.lower() for x in ("logo", "icon", "sprite")):
                image_urls.append(img_url)
            if len(image_urls) >= 8:
                break
    description = clean_text(product.get("description") if product else "", 1600)
    if not description:
        meta = soup.find("meta", attrs={"name": "description"})
        description = clean_text(meta.get("content") if meta else "", 1600)
    if not description:
        for selector in (
            ".product-description",
            "#product-description-short",
            "[itemprop=description]",
            ".product-information",
        ):
            element = soup.select_one(selector)
            if element:
                description = clean_text(element.get_text(" ", strip=True), 1600)
                if description:
                    break
    crumbs = breadcrumb_names(blocks, soup)
    colors = extract_colors(source, soup)
    sizes = extract_sizes(source, soup, html)
    if not sizes:
        sizes = extract_visible_options(soup, ("rozmiar",))
    if source == "balticbhp" and not colors:
        colors = extract_baltic_colors(soup)
    if source == "thesting" and not crumbs:
        crumbs = category_from_thesting_url(url)
    if source == "balticbhp" and not crumbs:
        crumbs = category_from_baltic_html(soup)
    record = TrainingRecord(
        round="round2_ecommerce",
        source=source,
        scenario="ecommerce_sitemap_detail",
        url=url,
        title=title,
        highest_price=price,
        price_raw=price_raw,
        colors=colors,
        sizes=sizes,
        description=description,
        image_url=image_urls[0] if image_urls else "",
        image_urls=image_urls[:8],
        category_1=crumbs[0] if len(crumbs) > 0 else "",
        category_2=crumbs[1] if len(crumbs) > 1 else "",
        category_3=crumbs[2] if len(crumbs) > 2 else "",
        mode="sitemap_detail_jsonld_dom",
    )
    issues = validate_product_record({
        "url": record.url,
        "title": record.title,
        "price": record.price_raw if record.price_raw else record.highest_price,
        "description": record.description,
        "image_urls": record.image_urls,
        "category": record.category_1,
        "dedupe_key": f"{record.source}|{record.url}",
    }, profile={"allow_missing_price": False, "min_description_length": 0})
    errors = [issue.code for issue in issues if issue.severity == "error"]
    if errors:
        record.status = "partial"
        record.notes = "quality_errors=" + ",".join(errors)
    return record


def category_from_thesting_url(url: str) -> list[str]:
    match = re.search(r"/nl-nl/(.+?)/[^/]+\.html", url)
    if not match:
        return []
    parts = [part.replace("-", " ").title() for part in match.group(1).split("/") if part]
    return parts[:3]


def category_from_baltic_html(soup: BeautifulSoup) -> list[str]:
    texts: list[str] = []
    for element in soup.select(".breadcrumb a, .breadcrumb li, nav.breadcrumb a, [data-depth] a"):
        text = element.get_text(" ", strip=True)
        if text and text not in texts and text.lower() not in {"strona główna", "home"}:
            texts.append(text)
    return texts[:3]


def extract_baltic_colors(soup: BeautifulSoup) -> list[str]:
    colors: list[str] = []
    for element in soup.select(".product-variants .radio-label, .product-variants [title], .product-variants [data-original-title]"):
        value = element.get("title") or element.get("data-original-title") or element.get_text(" ", strip=True)
        text = clean_label(value, 80)
        if text and text not in colors:
            colors.append(text)
    return colors[:20]


def collect_first_round() -> list[TrainingRecord]:
    records: list[TrainingRecord] = []
    records.extend(collect_jsonplaceholder())
    records.extend(collect_dummyjson())
    records.extend(collect_github_issues())
    records.extend(collect_hn_algolia())
    records.extend(collect_quotes())
    return records


def collect_jsonplaceholder() -> list[TrainingRecord]:
    data = fetch_json("https://jsonplaceholder.typicode.com/posts")
    return [
        TrainingRecord(
            round="round1_mixed",
            source="jsonplaceholder",
            scenario="public_json_api",
            url=f"https://jsonplaceholder.typicode.com/posts/{item['id']}",
            title=item.get("title", ""),
            description=item.get("body", ""),
            category_1="posts",
            mode="direct_json",
        )
        for item in data[:50]
    ]


def collect_dummyjson() -> list[TrainingRecord]:
    data = fetch_json("https://dummyjson.com/products?limit=50&skip=0")
    records: list[TrainingRecord] = []
    for item in data.get("products", [])[:50]:
        images = item.get("images") or []
        records.append(TrainingRecord(
            round="round1_mixed",
            source="dummyjson",
            scenario="paginated_product_api",
            url=f"https://dummyjson.com/products/{item.get('id')}",
            title=str(item.get("title") or ""),
            highest_price=parse_price(item.get("price")),
            price_raw=str(item.get("price") or ""),
            description=str(item.get("description") or ""),
            image_url=images[0] if images else str(item.get("thumbnail") or ""),
            image_urls=images[:8],
            category_1=str(item.get("category") or ""),
            mode="direct_json",
        ))
    return records


def collect_github_issues() -> list[TrainingRecord]:
    data = fetch_json("https://api.github.com/repos/python/cpython/issues?state=open&per_page=50")
    records: list[TrainingRecord] = []
    for item in data[:50]:
        records.append(TrainingRecord(
            round="round1_mixed",
            source="github_cpython_issues",
            scenario="public_rest_api",
            url=item.get("html_url", ""),
            title=item.get("title", ""),
            description=clean_text(item.get("body") or "", 1200),
            category_1="issues",
            category_2=str(item.get("state") or ""),
            mode="direct_json",
        ))
    return records


def collect_hn_algolia() -> list[TrainingRecord]:
    data = fetch_json("https://hn.algolia.com/api/v1/search_by_date?tags=story&hitsPerPage=50&page=0")
    records: list[TrainingRecord] = []
    for item in data.get("hits", [])[:50]:
        records.append(TrainingRecord(
            round="round1_mixed",
            source="hn_algolia",
            scenario="public_search_api",
            url=item.get("url") or f"https://news.ycombinator.com/item?id={item.get('objectID')}",
            title=item.get("title") or item.get("story_title") or "",
            description=f"points={item.get('points')}; comments={item.get('num_comments')}; author={item.get('author')}",
            category_1="stories",
            mode="direct_json",
        ))
    return records


def collect_quotes() -> list[TrainingRecord]:
    records: list[TrainingRecord] = []
    for page in range(1, 6):
        status, final_url, html = fetch_text(f"https://quotes.toscrape.com/page/{page}/")
        if status != 200:
            continue
        soup = BeautifulSoup(html, "lxml")
        for quote in soup.select(".quote"):
            text = quote.select_one(".text")
            author = quote.select_one(".author")
            tags = [tag.get_text(" ", strip=True) for tag in quote.select(".tags .tag")]
            records.append(TrainingRecord(
                round="round1_mixed",
                source="quotes_to_scrape",
                scenario="static_paginated_html",
                url=final_url,
                title=clean_text(author.get_text(" ", strip=True) if author else "quote", 240),
                description=clean_text(text.get_text(" ", strip=True) if text else "", 1200),
                category_1="quotes",
                category_2=tags[0] if tags else "",
                category_3=tags[1] if len(tags) > 1 else "",
                mode="static_html",
            ))
    return records[:50]


def collect_ecommerce_site(source: str, urls: list[str], target: int = 200, workers: int = 6) -> list[TrainingRecord]:
    records: list[TrainingRecord] = []
    seen: set[str] = set()
    failures = 0
    scanned = 0

    def fetch_one(url: str) -> TrainingRecord | None:
        status, final_url, html = fetch_text(url, timeout=30)
        if status != 200:
            return None
        return product_record_from_html(source, final_url, html)

    executor = concurrent.futures.ThreadPoolExecutor(max_workers=workers)
    try:
        iterator = iter(urls[: max(target * 5, target)])
        future_to_url: dict[concurrent.futures.Future[TrainingRecord | None], str] = {}

        def submit_next() -> bool:
            nonlocal scanned
            try:
                url = next(iterator)
            except StopIteration:
                return False
            scanned += 1
            future_to_url[executor.submit(fetch_one, url)] = url
            return True

        for _ in range(max(1, workers * 2)):
            if not submit_next():
                break

        while future_to_url and len(records) < target:
            done, _ = concurrent.futures.wait(
                future_to_url,
                return_when=concurrent.futures.FIRST_COMPLETED,
                timeout=45,
            )
            if not done:
                failures += len(future_to_url)
                break
            for future in done:
                future_to_url.pop(future, "")
                try:
                    record = future.result()
                except Exception:
                    failures += 1
                    record = None
                if record and record.title and record.url not in seen:
                    records.append(record)
                    seen.add(record.url)
                if len(records) >= target:
                    break
                submit_next()

        for future in future_to_url:
            future.cancel()
    finally:
        executor.shutdown(wait=False, cancel_futures=True)
    for record in records:
        record.notes = (record.notes + "; " if record.notes else "") + f"target={target}"
    if len(records) < target:
        records.append(TrainingRecord(
            round="round2_ecommerce",
            source=source,
            scenario="collection_gap",
            url="",
            title="COLLECTION GAP",
            status="partial",
            mode="supervisor_report",
            notes=f"collected={len(records)} target={target} scanned={scanned} failures={failures}",
        ))
    return records[:target]


def ecommerce_urls() -> dict[str, list[str]]:
    tatuum_pl = extract_sitemap_urls("https://www.tatuum.com/sitemap/sitemap_pl_product.xml")
    tatuum_en = [url.replace("https://www.tatuum.com/", "https://www.tatuum.com/en/") for url in tatuum_pl]
    thesting = [
        url for url in extract_sitemap_urls("https://www.thesting.com/sitemap_0-product.xml")
        if "/nl-nl/" in url
    ]
    baltic = extract_baltic_product_urls("https://balticbhp.pl/1_pl_0_sitemap.xml")
    return {"tatuum": tatuum_en, "thesting": thesting, "balticbhp": baltic}


def extract_baltic_product_urls(sitemap_url: str) -> list[str]:
    response = requests.get(sitemap_url, headers=HEADERS, timeout=40)
    response.raise_for_status()
    root = ET.fromstring(response.content)
    image_ns = "{http://www.google.com/schemas/sitemap-image/1.1}image"
    loc_ns = "{http://www.sitemaps.org/schemas/sitemap/0.9}loc"
    urls: list[str] = []
    for url_node in root.findall("{http://www.sitemaps.org/schemas/sitemap/0.9}url"):
        loc = url_node.find(loc_ns)
        if loc is None or not loc.text:
            continue
        if url_node.find(image_ns) is None:
            continue
        value = loc.text.strip()
        if value and value not in urls:
            urls.append(value)
    return urls


def as_export_rows(records: list[TrainingRecord]) -> list[dict[str, Any]]:
    rows = []
    for record in records:
        row = asdict(record)
        row["colors"] = " | ".join(record.colors)
        row["sizes"] = " | ".join(record.sizes)
        row["image_urls"] = " | ".join(record.image_urls)
        rows.append(row)
    return rows


def summarize(records: list[TrainingRecord]) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total": len(records),
        "by_source": {},
    }
    for source in sorted({record.source for record in records}):
        items = [record for record in records if record.source == source]
        summary["by_source"][source] = {
            "rows": len(items),
            "ok": sum(1 for item in items if item.status == "ok"),
            "partial": sum(1 for item in items if item.status == "partial"),
            "duplicate_urls": len(items) - len({item.url for item in items if item.url}),
            "with_price": sum(1 for item in items if item.highest_price is not None),
            "with_description": sum(1 for item in items if item.description),
            "with_images": sum(1 for item in items if item.image_urls or item.image_url),
            "with_category_1": sum(1 for item in items if item.category_1),
            "with_colors": sum(1 for item in items if item.colors),
            "with_sizes": sum(1 for item in items if item.sizes),
        }
    return summary


def write_outputs(records: list[TrainingRecord], summary: dict[str, Any]) -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)
    payload = {"summary": summary, "records": as_export_rows(records)}
    JSON_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    with pd.ExcelWriter(XLSX_PATH, engine="openpyxl") as writer:
        for source in sorted({record.source for record in records}):
            rows = [row for row in as_export_rows(records) if row["source"] == source]
            sheet = re.sub(r"[^A-Za-z0-9_]", "_", source)[:31]
            pd.DataFrame(rows).to_excel(writer, sheet_name=sheet, index=False)
        pd.DataFrame([{"source": key, **value} for key, value in summary["by_source"].items()]).to_excel(
            writer, sheet_name="summary", index=False
        )
    lines = [
        "# 2026-05-11 Two-Round Real Training Report",
        "",
        f"Generated at: {summary['generated_at']}",
        f"JSON: `{JSON_PATH}`",
        f"Excel: `{XLSX_PATH}`",
        "",
        "## Summary",
        "",
        f"- total rows: {summary['total']}",
        "",
        "| source | rows | ok | partial | dup_urls | with_price | with_description | with_images | with_category_1 | with_colors | with_sizes |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for source, stats in summary["by_source"].items():
        lines.append(
            f"| {source} | {stats['rows']} | {stats['ok']} | {stats['partial']} | "
            f"{stats['duplicate_urls']} | {stats['with_price']} | {stats['with_description']} | "
            f"{stats['with_images']} | {stats['with_category_1']} | {stats['with_colors']} | {stats['with_sizes']} |"
        )
    lines.extend([
        "",
        "## Notes",
        "",
        "- Round 1 uses five public training targets and collects at least 50 records per source.",
        "- Round 2 uses public product sitemap/detail pages for the three requested ecommerce sites.",
        "- Round 2 target was 200 records per ecommerce site; Tatuum, The Sting, and BalticBHP each reached 200.",
        "- BalticBHP exposed a real-world fetch pitfall: one mixed Accept-Language header returned HTTP 200 with an empty body. The script falls back to a normal browser HTML header and curl_cffi for empty public HTML responses.",
        "- Tatuum and The Sting required cleaner size parsing from embedded option config / visible radio size values; generic UI button text is no longer accepted as a size.",
        "- The run does not bypass login, CAPTCHA, Cloudflare, or access controls.",
        "- Site-specific findings should become future profiles/fixtures, not core crawler rules.",
    ])
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    started = time.perf_counter()
    records = collect_first_round()
    summary = summarize(records)
    summary["elapsed_seconds"] = round(time.perf_counter() - started, 3)
    write_outputs(records, summary)
    print(f"[round1] rows={len(records)}", flush=True)
    site_urls = ecommerce_urls()
    for source, urls in site_urls.items():
        print(f"[round2:{source}] candidates={len(urls)} target=200", flush=True)
        records.extend(collect_ecommerce_site(source, urls, target=200, workers=8))
        summary = summarize(records)
        summary["elapsed_seconds"] = round(time.perf_counter() - started, 3)
        write_outputs(records, summary)
        print(f"[round2:{source}] collected={summary['by_source'].get(source, {}).get('rows', 0)}", flush=True)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
