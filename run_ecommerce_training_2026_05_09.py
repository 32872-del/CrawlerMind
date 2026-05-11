#!/usr/bin/env python3
"""Small real-site ecommerce training run for Crawler-Mind.

The run is intentionally low-volume. It only reads public pages/public JSON and
records challenge/login cases as diagnosis rows instead of trying to bypass.
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import httpx
import pandas as pd
from bs4 import BeautifulSoup


OUTPUT_DIR = Path("dev_logs") / "training"
EXCEL_PATH = OUTPUT_DIR / "2026-05-09_ecommerce_training_sample.xlsx"
JSON_PATH = OUTPUT_DIR / "2026-05-09_ecommerce_training_sample.json"
REPORT_PATH = OUTPUT_DIR / "2026-05-09_ecommerce_training_summary.md"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; CrawlerMindTraining/0.1; "
        "low-volume; +https://github.com/32872-del/CrawlerMind)"
    )
}

MAX_PRODUCTS_PER_SITE = 5


@dataclass
class ProductRow:
    source_site: str
    category: str
    source_url: str
    product_title: str = ""
    highest_price: str = ""
    colors: str = ""
    sizes: str = ""
    product_description: str = ""
    image_urls: str = ""
    mode: str = ""
    status: str = "ok"
    notes: str = ""


def clean_text(value: str | None, limit: int = 2000) -> str:
    if not value:
        return ""
    raw = str(value)
    if "<" in raw and ">" in raw:
        text = BeautifulSoup(raw, "lxml").get_text(" ", strip=True)
    else:
        text = raw
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit]


def unique_join(values: list[str], sep: str = " | ") -> str:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        value = clean_text(str(value), limit=500)
        if value and value not in seen:
            seen.add(value)
            output.append(value)
    return sep.join(output)


def normalize_url(base_url: str, url: str | None) -> str:
    if not url:
        return ""
    if url.startswith("//"):
        return "https:" + url
    return urljoin(base_url, url)


def extract_prices(text: str) -> list[float]:
    prices: list[float] = []
    patterns = [
        r"€\s*([0-9]+(?:[.,][0-9]{1,2})?)",
        r"([0-9]+(?:[.,][0-9]{1,2})?)\s*zł",
        r"([0-9]+(?:[.,][0-9]{1,2})?)\s*EUR",
    ]
    for pattern in patterns:
        for match in re.findall(pattern, text, flags=re.I):
            try:
                prices.append(float(match.replace(",", ".")))
            except ValueError:
                continue
    return prices


def format_highest_price(raw_values: list[str], currency_hint: str = "") -> str:
    joined = " ".join(raw_values)
    prices = extract_prices(joined)
    if not prices and currency_hint:
        for value in raw_values:
            value = str(value).strip()
            if re.fullmatch(r"[0-9]+(?:[.,][0-9]{1,2})?", value):
                try:
                    prices.append(float(value.replace(",", ".")))
                except ValueError:
                    continue
    if not prices:
        return unique_join(raw_values)
    highest = max(prices)
    if currency_hint == "EUR" or "€" in joined:
        return f"€{highest:g}"
    if currency_hint == "PLN" or "zł" in joined:
        return f"{highest:g} zł"
    return f"{highest:g}"


def extract_balanced_json(text: str, marker: str) -> dict[str, Any]:
    marker_index = text.find(marker)
    if marker_index < 0:
        return {}
    start = text.find("{", marker_index + len(marker))
    if start < 0:
        return {}
    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start : index + 1])
                except json.JSONDecodeError:
                    return {}
    return {}


def extract_magento_config_options(html: str) -> dict[str, list[str]]:
    config = extract_balanced_json(html, '"jsonConfig"')
    options: dict[str, list[str]] = {"colors": [], "sizes": []}
    attributes = config.get("attributes") if isinstance(config, dict) else {}
    if not isinstance(attributes, dict):
        return options
    for attribute in attributes.values():
        if not isinstance(attribute, dict):
            continue
        label = str(attribute.get("label") or attribute.get("code") or "").lower()
        values = [
            str(option.get("label"))
            for option in attribute.get("options", [])
            if isinstance(option, dict) and option.get("label")
        ]
        if any(key in label for key in ["rozmiar", "size", "maat"]):
            options["sizes"].extend(values)
        elif any(key in label for key in ["kolor", "color", "colour", "kleur"]):
            options["colors"].extend(values)
    return options


def detect_challenge(html: str, status_code: int) -> str:
    lowered = html.lower()
    if status_code in {401, 403, 429} and "just a moment" in lowered and "cloudflare" in lowered:
        return "Cloudflare challenge page"
    if "cf-chl" in lowered or "challenge-platform" in lowered:
        return "Cloudflare challenge page"
    if "captcha" in lowered:
        return "CAPTCHA/challenge signal"
    return ""


def fetch(client: httpx.Client, url: str) -> httpx.Response:
    return client.get(url, follow_redirects=True, timeout=30)


def collect_shoesme(client: httpx.Client) -> list[ProductRow]:
    url = "https://www.shoesme.nl/"
    try:
        response = fetch(client, url)
    except Exception as exc:
        return [
            ProductRow(
                source_site="shoesme",
                category="homepage",
                source_url=url,
                mode="diagnosis_only",
                status="failed",
                notes=f"request failed: {exc!r}",
            )
        ]
    challenge = detect_challenge(response.text, response.status_code)
    return [
        ProductRow(
            source_site="shoesme",
            category="homepage",
            source_url=str(response.url),
            mode="diagnosis_only",
            status="blocked" if challenge else "needs_manual_recon",
            notes=challenge
            or f"homepage fetched status={response.status_code}; product extraction not attempted",
        )
    ]


def collect_donsje(client: httpx.Client) -> list[ProductRow]:
    url = "https://donsje.com/products.json?limit=5"
    response = fetch(client, url)
    data = response.json()
    rows: list[ProductRow] = []
    for product in data.get("products", [])[:MAX_PRODUCTS_PER_SITE]:
        variants = product.get("variants") or []
        options = product.get("options") or []
        colors: list[str] = []
        sizes: list[str] = []
        for option in options:
            name = str(option.get("name", "")).lower()
            values = [str(v) for v in option.get("values", [])]
            if "color" in name or "kleur" in name:
                colors.extend(values)
            elif "size" in name or "maat" in name:
                sizes.extend(values)
        if not colors:
            colors.extend(str(v.get("option1", "")) for v in variants)
        if not sizes:
            sizes.extend(str(v.get("option2", "")) for v in variants)
        price_values = [str(v.get("price", "")) for v in variants if v.get("price") is not None]
        images = [str(img.get("src", "")) for img in product.get("images", []) if img.get("src")]
        handle = product.get("handle", "")
        product_url = f"https://donsje.com/nl/products/{handle}" if handle else str(response.url)
        rows.append(
            ProductRow(
                source_site="donsje",
                category=product.get("product_type") or "products.json",
                source_url=product_url,
                product_title=product.get("title", ""),
                highest_price=format_highest_price(price_values, "EUR"),
                colors=unique_join(colors),
                sizes=unique_join(sizes),
                product_description=clean_text(product.get("body_html"), limit=1200),
                image_urls=unique_join(images),
                mode="public_shopify_json",
                notes=f"variants={len(variants)}; public products.json endpoint",
            )
        )
    return rows


def collect_magento_list(
    client: httpx.Client,
    site_name: str,
    category: str,
    list_url: str,
    currency_hint: str,
) -> list[ProductRow]:
    response = fetch(client, list_url)
    soup = BeautifulSoup(response.text, "lxml")
    cards = soup.select(".product-item")[:MAX_PRODUCTS_PER_SITE]
    rows: list[ProductRow] = []
    for card in cards:
        link = card.select_one(".product-item-name a, a.product-item-link, a.product-item-photo, a[href]")
        product_url = normalize_url(list_url, link.get("href") if link else "")
        card_title = clean_text(link.get_text(" ", strip=True) if link else "")
        card_price = clean_text(card.select_one(".price").get_text(" ", strip=True) if card.select_one(".price") else "")
        card_img = card.select_one("img")
        card_image = normalize_url(
            list_url,
            card_img.get("src") or card_img.get("data-src") or card_img.get("data-original") if card_img else "",
        )
        if product_url:
            rows.append(
                enrich_magento_detail(
                    client=client,
                    site_name=site_name,
                    category=category,
                    detail_url=product_url,
                    fallback_title=card_title,
                    fallback_price=card_price,
                    fallback_image=card_image,
                    currency_hint=currency_hint,
                )
            )
    if not rows:
        rows.append(
            ProductRow(
                source_site=site_name,
                category=category,
                source_url=str(response.url),
                mode="static_dom_list",
                status="failed",
                notes=f"no .product-item cards found; status={response.status_code}",
            )
        )
    return rows


def enrich_magento_detail(
    client: httpx.Client,
    site_name: str,
    category: str,
    detail_url: str,
    fallback_title: str,
    fallback_price: str,
    fallback_image: str,
    currency_hint: str,
) -> ProductRow:
    try:
        response = fetch(client, detail_url)
    except Exception as exc:
        return ProductRow(
            source_site=site_name,
            category=category,
            source_url=detail_url,
            product_title=fallback_title,
            highest_price=fallback_price,
            image_urls=fallback_image,
            mode="static_dom_detail",
            status="partial",
            notes=f"detail request failed: {exc!r}",
        )
    soup = BeautifulSoup(response.text, "lxml")
    title = clean_text(soup.select_one("h1").get_text(" ", strip=True) if soup.select_one("h1") else fallback_title)
    price_texts = [clean_text(node.get_text(" ", strip=True)) for node in soup.select(".price, [data-price-amount]")]
    if fallback_price:
        price_texts.append(fallback_price)
    description_nodes = [
        ".product.attribute.overview .value",
        ".product.attribute.description .value",
        ".product.info.detailed",
        ".additional-attributes-wrapper",
    ]
    description_parts: list[str] = []
    for selector in description_nodes:
        node = soup.select_one(selector)
        if node:
            description_parts.append(clean_text(node.get_text(" ", strip=True), limit=900))
    image_values: list[str] = []
    for img in soup.select(".product.media img, .gallery-placeholder img, img"):
        src = img.get("src") or img.get("data-src") or img.get("data-original")
        full = normalize_url(str(response.url), src)
        if full and not full.startswith("data:image") and "/logo" not in full.lower():
            image_values.append(full)
    if fallback_image and not fallback_image.startswith("data:image"):
        image_values.append(fallback_image)
    color_candidates: list[str] = []
    size_candidates: list[str] = []
    for selector in [".swatch-option", ".swatch-attribute", ".product-options-wrapper option"]:
        for node in soup.select(selector):
            label = node.get("aria-label") or node.get("option-label") or node.get("title") or node.get_text(" ", strip=True)
            label = clean_text(label, limit=120)
            if not label:
                continue
            parent_text = clean_text(node.parent.get_text(" ", strip=True) if node.parent else "", limit=300).lower()
            if any(key in parent_text for key in ["rozmiar", "size", "maat"]):
                size_candidates.append(label)
            elif any(key in parent_text for key in ["color", "colour", "kolor", "kleur"]):
                color_candidates.append(label)
            else:
                color_candidates.append(label)
    config_options = extract_magento_config_options(response.text)
    color_candidates.extend(config_options["colors"])
    size_candidates.extend(config_options["sizes"])
    return ProductRow(
        source_site=site_name,
        category=category,
        source_url=str(response.url),
        product_title=title,
        highest_price=format_highest_price(price_texts, currency_hint),
        colors=unique_join(color_candidates),
        sizes=unique_join(size_candidates),
        product_description=unique_join(description_parts, sep=" "),
        image_urls=unique_join(image_values),
        mode="static_dom_list_plus_detail",
        status="ok",
        notes=f"list price={fallback_price}; detail status={response.status_code}",
    )


def collect_bosch(client: httpx.Client) -> list[ProductRow]:
    url = "https://www.bosch.de/produkte-und-services/zuhause/"
    response = fetch(client, url)
    soup = BeautifulSoup(response.text, "lxml")
    groups = []
    for heading in soup.select("h2"):
        title = clean_text(heading.get_text(" ", strip=True))
        if title in {"Hausgeräte", "Elektrowerkzeuge", "Gartengeräte"}:
            block = heading
            for _ in range(5):
                if block.parent:
                    block = block.parent
            link = block.select_one("a[href]")
            img = block.select_one("img")
            groups.append(
                ProductRow(
                    source_site="bosch",
                    category="products-and-services/at-home",
                    source_url=normalize_url(str(response.url), link.get("href") if link else url),
                    product_title=title,
                    product_description=clean_text(block.get_text(" ", strip=True), limit=1200),
                    image_urls=normalize_url(str(response.url), img.get("src") if img else ""),
                    mode="static_corporate_product_category_page",
                    status="partial",
                    notes="Bosch.de is a corporate product/service page; no retail price, color, or size fields exposed on this page.",
                )
            )
    return groups[:MAX_PRODUCTS_PER_SITE] or [
        ProductRow(
            source_site="bosch",
            category="products-and-services/at-home",
            source_url=str(response.url),
            mode="static_corporate_product_category_page",
            status="failed",
            notes="No product/service category headings found.",
        )
    ]


def collect_all() -> dict[str, list[ProductRow]]:
    with httpx.Client(headers=HEADERS, follow_redirects=True, timeout=30) as client:
        return {
            "shoesme": collect_shoesme(client),
            "donsje": collect_donsje(client),
            "clausporto": collect_magento_list(
                client,
                site_name="clausporto",
                category="home-products/candle",
                list_url="https://clausporto.com/en/home-products/candle",
                currency_hint="EUR",
            ),
            "uvex": collect_magento_list(
                client,
                site_name="uvex",
                category="produkty/kaski-rowerowe",
                list_url="https://uvex.com.pl/produkty/kaski-rowerowe/",
                currency_hint="PLN",
            ),
            "bosch": collect_bosch(client),
        }


def write_outputs(results: dict[str, list[ProductRow]]) -> dict[str, Any]:
    OUTPUT_DIR.mkdir(exist_ok=True)
    serializable = {site: [asdict(row) for row in rows] for site, rows in results.items()}
    JSON_PATH.write_text(json.dumps(serializable, ensure_ascii=False, indent=2), encoding="utf-8")
    with pd.ExcelWriter(EXCEL_PATH, engine="openpyxl") as writer:
        for site, rows in serializable.items():
            frame = pd.DataFrame(rows)
            frame.to_excel(writer, sheet_name=site[:31], index=False)
    summary = {
        site: {
            "rows": len(rows),
            "ok": sum(1 for row in rows if row.status == "ok"),
            "partial": sum(1 for row in rows if row.status == "partial"),
            "blocked": sum(1 for row in rows if row.status == "blocked"),
            "failed": sum(1 for row in rows if row.status == "failed"),
            "with_price": sum(1 for row in rows if row.highest_price),
            "with_images": sum(1 for row in rows if row.image_urls),
            "with_description": sum(1 for row in rows if row.product_description),
        }
        for site, rows in results.items()
    }
    lines = [
        "# 2026-05-09 Ecommerce Training Summary",
        "",
        f"Generated at: {datetime.now().isoformat(timespec='seconds')}",
        f"Excel: `{EXCEL_PATH.as_posix()}`",
        f"JSON: `{JSON_PATH.as_posix()}`",
        "",
        "## Site Results",
        "",
    ]
    for site, item in summary.items():
        lines.append(
            f"- {site}: rows={item['rows']}, ok={item['ok']}, partial={item['partial']}, "
            f"blocked={item['blocked']}, failed={item['failed']}, with_price={item['with_price']}, "
            f"with_images={item['with_images']}, with_description={item['with_description']}"
        )
    lines.extend(
        [
            "",
            "## Notes",
            "",
            "- Shoesme returned a Cloudflare challenge and was recorded as diagnosis-only.",
            "- Donsje exposed a public Shopify `products.json` endpoint with variants, sizes, color, images, and prices.",
            "- Clausporto and uvex were collected through static Magento-style list/detail pages.",
            "- Bosch.de is a corporate product/service page, so rows are partial and price/color/size are intentionally blank.",
            "- This run is low-volume training evidence, not a full-site crawl.",
        ]
    )
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"summary": summary, "excel": str(EXCEL_PATH), "json": str(JSON_PATH), "report": str(REPORT_PATH)}


def main() -> None:
    results = collect_all()
    output = write_outputs(results)
    print(json.dumps(output, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
