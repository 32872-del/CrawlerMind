"""Evidence-driven ecommerce extractors.

These helpers turn high-value ecommerce evidence patterns into CLM's normalized
product item shape.  They are intentionally pure: callers provide HTML or JSON
evidence and receive extracted items plus missing-field reasons.
"""
from __future__ import annotations

import html as html_lib
import json
import re
from typing import Any
from urllib.parse import parse_qs, urljoin, urlparse

from bs4 import BeautifulSoup


CLM_ITEM_FIELDS = (
    "title",
    "highest_price",
    "currency",
    "color",
    "size",
    "description",
    "image_url",
    "product_url",
    "category_level_1",
    "category_level_2",
    "source_evidence",
    "missing_reasons",
)


class UnsupportedExtractorContract(ValueError):
    """Raised when a fixture/profile contract names an unsupported extractor."""


def extract_items_from_contract(
    evidence: Any,
    contract: dict[str, Any],
    *,
    source_url: str = "",
) -> list[dict[str, Any]]:
    """Route evidence through the extractor named by an extraction contract."""
    strategy = contract.get("parser_strategy") if isinstance(contract.get("parser_strategy"), dict) else {}
    strategy_name = _text(strategy.get("name"))
    site = _text(contract.get("site"))
    contract_source_url = source_url or _text(contract.get("source_url"))

    if strategy_name == "gtm_data_attribute_extractor":
        if isinstance(evidence, str):
            return extract_gtm_data_attribute_items(
                evidence,
                base_url=_site_base_url(site),
                source_url=contract_source_url,
            )
        return extract_gtm_item_objects(evidence, source_url=contract_source_url)

    if strategy_name == "next_data_product_wall_extractor":
        return extract_next_data_product_wall_items(
            evidence,
            source_url=contract_source_url,
            brand="Nike" if site == "nike.com" else "",
        )

    if strategy_name == "next_data_graphql_ssr_cache_extractor":
        image_template = _image_template_from_contract(contract)
        return extract_next_data_graphql_ssr_items(
            evidence,
            base_url=_site_base_url(site),
            image_template=image_template,
            source_url=contract_source_url,
        )

    if strategy_name == "jsonld_product_extractor":
        if isinstance(evidence, str):
            return extract_jsonld_product_items(evidence, source_url=contract_source_url)
        return extract_jsonld_itemlist_items(evidence, source_url=contract_source_url)

    if strategy_name == "jsonld_itemlist_extractor":
        return extract_jsonld_itemlist_items(evidence, source_url=contract_source_url)

    if strategy_name == "shopify_product_grid_extractor":
        return extract_shopify_product_grid_items(evidence, source_url=contract_source_url)

    if strategy_name == "demandware_product_tile_extractor":
        if isinstance(evidence, str):
            return extract_demandware_product_tile_items(
                evidence,
                base_url=_site_base_url(site),
                source_url=contract_source_url,
            )
        return []

    raise UnsupportedExtractorContract(f"unsupported parser_strategy.name: {strategy_name or '<missing>'}")


def extract_gtm_data_attribute_items(
    html: str,
    *,
    base_url: str = "https://www.superdry.com",
    source_url: str = "",
) -> list[dict[str, Any]]:
    """Extract products from GTM ``data-gtm`` attributes in listing HTML."""
    soup = BeautifulSoup(html or "", "lxml")
    items: list[dict[str, Any]] = []

    dom_tiles = soup.select(".product-tile[data-gtm]")
    for tile_index, tile in enumerate(dom_tiles):
        gtm_payload = _parse_jsonish(tile.get("data-gtm"))
        ecommerce_items = _as_list(_dig(gtm_payload, "ecommerce", "items"))
        if not ecommerce_items:
            continue
        gtm_item = ecommerce_items[0]
        if not isinstance(gtm_item, dict):
            continue
        items.append(
            _gtm_item_to_clm(
                gtm_item,
                tile=tile,
                base_url=base_url,
                source_url=source_url,
                evidence_index=tile_index,
                evidence_type="html_data_gtm",
            )
        )
    text_payloads = _data_gtm_payloads_from_text(html)
    if len(items) >= len(text_payloads):
        return items

    # Broken or heavily truncated listing fragments can make lxml nest later
    # product tiles inside invalid markup.  Keep extracting the GTM evidence
    # even when sibling DOM fallbacks are unavailable.
    seen_ids = {_text(_dig(item.get("source_evidence"), "gtm_item_id")) for item in items}
    for payload_index, payload in enumerate(text_payloads):
        ecommerce_items = _as_list(_dig(payload, "ecommerce", "items"))
        if not ecommerce_items or not isinstance(ecommerce_items[0], dict):
            continue
        gtm_item = ecommerce_items[0]
        item_id = _text(gtm_item.get("item_id"))
        if item_id and item_id in seen_ids:
            continue
        items.append(
            _gtm_item_to_clm(
                gtm_item,
                tile=None,
                base_url=base_url,
                source_url=source_url,
                evidence_index=payload_index,
                evidence_type="html_data_gtm_regex_fallback",
            )
        )
    return items


def extract_gtm_item_objects(
    products: Any,
    *,
    source_url: str = "",
) -> list[dict[str, Any]]:
    """Map already parsed GTM product objects into CLM items."""
    items: list[dict[str, Any]] = []
    for index, product in enumerate(_as_list(products)):
        if isinstance(product, dict):
            items.append(
                _gtm_item_to_clm(
                    product,
                    tile=None,
                    base_url="",
                    source_url=source_url,
                    evidence_index=index,
                    evidence_type="gtm_item_object",
                )
            )
    return items


def extract_next_data_product_wall_items(
    evidence: Any,
    *,
    source_url: str = "",
    brand: str = "Nike",
) -> list[dict[str, Any]]:
    """Extract Nike-style product wall items from ``__NEXT_DATA__`` evidence."""
    products = _nike_products_from_evidence(evidence)
    items: list[dict[str, Any]] = []
    for index, product in enumerate(products):
        if not isinstance(product, dict):
            continue
        copy = product.get("copy") if isinstance(product.get("copy"), dict) else {}
        prices = product.get("prices") if isinstance(product.get("prices"), dict) else {}
        colors = product.get("displayColors") if isinstance(product.get("displayColors"), dict) else {}
        images = product.get("colorwayImages") if isinstance(product.get("colorwayImages"), dict) else {}
        pdp = product.get("pdpUrl") if isinstance(product.get("pdpUrl"), dict) else {}

        title = _join_title(copy.get("title"), copy.get("subTitle"))
        item = _base_item(
            title=title,
            highest_price=_number_or_none(prices.get("currentPrice")),
            currency=_text(prices.get("currency")),
            color=_text(colors.get("colorDescription")),
            size=None,
            description=None,
            image_url=_text(images.get("portraitURL")),
            product_url=_text(pdp.get("url")),
            category_level_1=_text(product.get("productType")),
            category_level_2=None,
            source_evidence={
                "copy_title": _text(copy.get("title")),
                "copy_subTitle": _text(copy.get("subTitle")),
                "prices_currentPrice": prices.get("currentPrice"),
                "displayColors_colorDescription": _text(colors.get("colorDescription")),
                "productCode": _text(product.get("productCode")),
                "brand": brand,
                "source_url": source_url,
                "evidence_type": "next_data_product_wall",
                "evidence_index": index,
            },
        )
        item["brand"] = brand
        item["sku"] = _text(product.get("productCode"))
        item["missing_reasons"].update({
            "size": "Not available in listing page - detail page only",
            "description": "Not available in listing page - detail page only",
            "category_level_2": "Not in productGroupings. Available in facet/category data separately.",
        })
        items.append(item)
    return items


def extract_next_data_graphql_ssr_items(
    evidence: Any,
    *,
    base_url: str = "https://www.marksandspencer.com",
    image_template: str = "https://assets.digitalcontent.marksandspencer.app/image/upload/q_auto,f_auto/{assetId}",
    source_url: str = "",
) -> list[dict[str, Any]]:
    """Extract M&S-style GraphQL SSR product cache items."""
    products = _ms_products_from_evidence(evidence)
    items: list[dict[str, Any]] = []
    for index, product in enumerate(products):
        if not isinstance(product, dict):
            continue
        price = product.get("price") if isinstance(product.get("price"), dict) else {}
        list_price = price.get("listPrice") if isinstance(price.get("listPrice"), dict) else {}
        variants = _as_list(product.get("variants"))
        variant = variants[0] if variants and isinstance(variants[0], dict) else {}
        media_assets = _as_list(variant.get("mediaAssets")) if isinstance(variant, dict) else []
        media = media_assets[0] if media_assets and isinstance(media_assets[0], dict) else {}
        asset_id = _text(media.get("assetId"))
        seo_path = _text(product.get("seoPath"))
        description = _text(product.get("description")) or None

        item = _base_item(
            title=_text(product.get("title")),
            highest_price=_number_or_none(list_price.get("amount")),
            currency=_text(price.get("currency")),
            color=_query_param(seo_path, "color"),
            size=_text(variant.get("size")) if variant else None,
            description=description,
            image_url=image_template.format(assetId=asset_id) if asset_id else None,
            product_url=urljoin(base_url, seo_path) if seo_path else None,
            category_level_1=_text(product.get("productDefinition")),
            category_level_2=None,
            source_evidence={
                "product_id": _text(product.get("id")),
                "product_external_id": _text(product.get("productExternalId")),
                "variant_sku": _text(variant.get("skuId")) if variant else "",
                "variant_price": variant.get("price") if variant else None,
                "image_asset_id": asset_id,
                "source_url": source_url,
                "evidence_type": "next_data_graphql_ssr",
                "evidence_index": index,
            },
        )
        item["brand"] = _text(product.get("brand"))
        item["sku"] = _text(variant.get("skuId")) if variant else ""
        item["product_id"] = _text(product.get("id"))
        item["missing_reasons"]["category_level_2"] = "Not available in product response. Available in facets separately."
        if not description:
            item["missing_reasons"]["description"] = "Often null in GraphQL response."
        if not item.get("color"):
            item["missing_reasons"]["color"] = "Color query param not present in seoPath."
        if not item.get("size"):
            item["missing_reasons"]["size"] = "No variant size found."
        return_items = item
        items.append(return_items)
    return items


# ---------------------------------------------------------------------------
# JSON-LD Product / ItemList extractor
# ---------------------------------------------------------------------------


def extract_jsonld_product_items(
    html: str,
    *,
    source_url: str = "",
) -> list[dict[str, Any]]:
    """Extract CLM items from ``<script type="application/ld+json">`` Product objects.

    Handles both standalone Product schemas and ItemList containers holding
    Product entries.  Works with raw HTML from *requests* mode (no browser
    needed for most static-rendered pages).
    """
    soup = BeautifulSoup(html or "", "lxml")
    items: list[dict[str, Any]] = []
    scripts = soup.select('script[type="application/ld+json"]')
    for script_index, script in enumerate(scripts):
        text = script.string or script.get_text("", strip=False)
        data = _parse_jsonish(text)
        if data is None:
            continue
        for obj in _as_list(data):
            if not isinstance(obj, dict):
                continue
            schema_type = _text(obj.get("@type"))
            if schema_type == "ItemList":
                items.extend(
                    _jsonld_itemlist_to_clm(
                        obj,
                        source_url=source_url,
                        script_index=script_index,
                    )
                )
            elif schema_type == "Product":
                items.append(
                    _jsonld_product_to_clm(
                        obj,
                        source_url=source_url,
                        evidence_index=len(items),
                        script_index=script_index,
                    )
                )
    return items


def extract_jsonld_itemlist_items(
    evidence: Any,
    *,
    source_url: str = "",
) -> list[dict[str, Any]]:
    """Extract CLM items from a pre-parsed JSON-LD ItemList or Product list.

    Accepts a dict (single ItemList), a list of Product dicts, or a string
    containing JSON-LD markup.
    """
    if isinstance(evidence, str):
        return extract_jsonld_product_items(evidence, source_url=source_url)
    if isinstance(evidence, dict):
        schema_type = _text(evidence.get("@type"))
        if schema_type == "ItemList":
            return _jsonld_itemlist_to_clm(
                evidence, source_url=source_url, script_index=0
            )
        if schema_type == "Product":
            return [_jsonld_product_to_clm(evidence, source_url=source_url, evidence_index=0, script_index=0)]
    if isinstance(evidence, list):
        items: list[dict[str, Any]] = []
        for idx, obj in enumerate(evidence):
            if isinstance(obj, dict) and _text(obj.get("@type")) == "Product":
                items.append(
                    _jsonld_product_to_clm(obj, source_url=source_url, evidence_index=idx, script_index=0)
                )
        return items
    return []


def _jsonld_product_to_clm(
    product: dict[str, Any],
    *,
    source_url: str,
    evidence_index: int,
    script_index: int,
) -> dict[str, Any]:
    """Map a single JSON-LD Product object to a CLM item."""
    offers = product.get("offers")
    if isinstance(offers, dict):
        price = _number_or_none(offers.get("price") or offers.get("lowPrice"))
        currency = _text(offers.get("priceCurrency"))
    elif isinstance(offers, list) and offers:
        first = offers[0] if isinstance(offers[0], dict) else {}
        price = _number_or_none(first.get("price") or first.get("lowPrice"))
        currency = _text(first.get("priceCurrency"))
    else:
        price = None
        currency = ""

    image = product.get("image")
    image_url = None
    if isinstance(image, str):
        image_url = image
    elif isinstance(image, list) and image:
        image_url = image[0] if isinstance(image[0], str) else None

    brand_obj = product.get("brand")
    brand = ""
    if isinstance(brand_obj, dict):
        brand = _text(brand_obj.get("name"))
    elif isinstance(brand_obj, str):
        brand = brand_obj

    category = _text(product.get("category"))

    item = _base_item(
        title=_text(product.get("name")),
        highest_price=price,
        currency=currency,
        color=None,
        size=None,
        description=_text(product.get("description")) or None,
        image_url=image_url,
        product_url=_text(product.get("url")) or source_url or None,
        category_level_1=category or None,
        category_level_2=None,
        source_evidence={
            "schema_type": "Product",
            "sku": _text(product.get("sku")),
            "gtin": _text(product.get("gtin") or product.get("gtin13")),
            "brand": brand,
            "source_url": source_url,
            "evidence_type": "jsonld_product",
            "evidence_index": evidence_index,
            "script_index": script_index,
        },
    )
    item["brand"] = brand
    item["sku"] = _text(product.get("sku"))
    if not item.get("color"):
        item["missing_reasons"]["color"] = "Color not in JSON-LD Product schema."
    if not item.get("size"):
        item["missing_reasons"]["size"] = "Size not in JSON-LD Product schema."
    return item


def _jsonld_itemlist_to_clm(
    itemlist: dict[str, Any],
    *,
    source_url: str,
    script_index: int,
) -> list[dict[str, Any]]:
    """Extract all Product entries from a JSON-LD ItemList."""
    items_list = _as_list(itemlist.get("itemListElement"))
    results: list[dict[str, Any]] = []
    for idx, entry in enumerate(items_list):
        if not isinstance(entry, dict):
            continue
        item_obj = entry.get("item")
        if not isinstance(item_obj, dict):
            continue
        if _text(item_obj.get("@type")) != "Product":
            continue
        results.append(
            _jsonld_product_to_clm(
                item_obj,
                source_url=source_url,
                evidence_index=len(results),
                script_index=script_index,
            )
        )
    return results


# ---------------------------------------------------------------------------
# Shopify product grid JSON extractor
# ---------------------------------------------------------------------------


def extract_shopify_product_grid_items(
    evidence: Any,
    *,
    source_url: str = "",
) -> list[dict[str, Any]]:
    """Extract CLM items from Shopify product grid JSON.

    Accepts:
    - A dict with a ``"products"`` key (e.g. from ``/collections/all.json``)
    - A list of product dicts
    - A raw HTML string containing a ``Shopify.analytics.meta.product`` object
      or a ``products`` JSON blob in a ``<script>`` tag.
    """
    products = _shopify_products_from_evidence(evidence)
    items: list[dict[str, Any]] = []
    for index, product in enumerate(products):
        if not isinstance(product, dict):
            continue
        variants = _as_list(product.get("variants"))
        first_variant = variants[0] if variants and isinstance(variants[0], dict) else {}

        # Price: prefer compare_at_price (original) > price
        compare_at = _number_or_none(first_variant.get("compare_at_price"))
        price = _number_or_none(first_variant.get("price"))
        highest_price = compare_at if compare_at and compare_at > (price or 0) else price

        # Image: product.image.src or images[0].src
        image_url = None
        img_obj = product.get("image") if isinstance(product.get("image"), dict) else None
        if img_obj:
            image_url = _text(img_obj.get("src"))
        if not image_url:
            images = _as_list(product.get("images"))
            if images and isinstance(images[0], dict):
                image_url = _text(images[0].get("src"))

        # Product URL
        handle = _text(product.get("handle"))
        product_url = f"https://{_shopify_domain_from_url(source_url)}/products/{handle}" if handle and source_url else None

        item = _base_item(
            title=_text(product.get("title")),
            highest_price=highest_price,
            currency="USD",
            color=_shopify_option_value(product, "Color"),
            size=_shopify_option_value(product, "Size"),
            description=_text(product.get("body_html"))[:500] or None,
            image_url=image_url,
            product_url=product_url,
            category_level_1=_text(product.get("product_type")) or None,
            category_level_2=None,
            source_evidence={
                "shopify_product_id": product.get("id"),
                "handle": handle,
                "vendor": _text(product.get("vendor")),
                "variant_count": len(variants),
                "source_url": source_url,
                "evidence_type": "shopify_product_grid",
                "evidence_index": index,
            },
        )
        item["brand"] = _text(product.get("vendor"))
        item["sku"] = _text(first_variant.get("sku")) if first_variant else ""
        item["product_id"] = str(product.get("id", ""))
        if not item.get("color"):
            item["missing_reasons"]["color"] = "No Color option in product variants."
        if not item.get("size"):
            item["missing_reasons"]["size"] = "No Size option in product variants."
        items.append(item)
    return items


def _shopify_products_from_evidence(evidence: Any) -> list[Any]:
    if isinstance(evidence, list):
        return evidence
    if isinstance(evidence, dict):
        if isinstance(evidence.get("products"), list):
            return evidence["products"]
        # Shopify analytics meta product (single product page)
        meta = evidence.get("Shopify", {})
        if isinstance(meta, dict):
            analytics = meta.get("analytics", {})
            if isinstance(analytics, dict):
                meta_product = analytics.get("meta", {}).get("product")
                if isinstance(meta_product, dict):
                    return [meta_product]
    if isinstance(evidence, str):
        # Try to find Shopify analytics in HTML
        match = re.search(
            r"Shopify\.analytics\.meta\.product\s*=\s*(\{.*?\});",
            evidence,
            re.DOTALL,
        )
        if match:
            parsed = _parse_jsonish(match.group(1))
            if isinstance(parsed, dict):
                return [parsed]
        # Try products JSON in script tag
        match = re.search(r'"products"\s*:\s*(\[.*?\])\s*[,}]', evidence, re.DOTALL)
        if match:
            parsed = _parse_jsonish(match.group(1))
            if isinstance(parsed, list):
                return parsed
    return []


def _shopify_option_value(product: dict, option_name: str) -> str | None:
    options = _as_list(product.get("options"))
    for opt in options:
        if isinstance(opt, dict) and _text(opt.get("name")).lower() == option_name.lower():
            values = _as_list(opt.get("values"))
            if values:
                return _text(values[0])
    return None


def _shopify_domain_from_url(url: str) -> str:
    if not url:
        return ""
    parsed = urlparse(url)
    return parsed.netloc or ""


# ---------------------------------------------------------------------------
# Demandware / SFCC product tile extractor
# ---------------------------------------------------------------------------


def extract_demandware_product_tile_items(
    html: str,
    *,
    base_url: str = "",
    source_url: str = "",
) -> list[dict[str, Any]]:
    """Extract CLM items from Salesforce Commerce Cloud (Demandware) product tiles.

    SFCC product tiles typically have:
    - ``.product-tile`` container with ``data-pid`` (product ID)
    - ``.product-tile__name`` or ``.pdp-link a`` for title
    - ``.product-tile__price .sales .value`` for price
    - ``.product-tile__image`` img for image
    - ``data-product-impression`` or ``data-gtm`` for structured data
    - Inline JS like ``var productViewObj = {...}``

    This extractor uses DOM tile parsing as primary, with JS data object
    fallback.
    """
    soup = BeautifulSoup(html or "", "lxml")
    items: list[dict[str, Any]] = []

    # Primary: DOM tile parsing
    tiles = soup.select(".product-tile[data-pid]")
    for tile_index, tile in enumerate(tiles):
        pid = _text(tile.get("data-pid"))
        title_el = (
            tile.select_one(".product-tile__name")
            or tile.select_one(".pdp-link a")
            or tile.select_one("a.link")
        )
        title_text = title_el.get_text(strip=True) if title_el else ""
        price_el = (
            tile.select_one(".product-tile__price .sales .value")
            or tile.select_one(".price .sales .value")
            or tile.select_one(".price .value")
        )
        img_el = tile.select_one(".product-tile__image img") or tile.select_one("img.tile-image")
        link_el = tile.select_one(".pdp-link a") or tile.select_one("a[href]")

        price_text = _text(price_el.get("content")) if price_el else _text(price_el)
        image_src = _text(img_el.get("src")) if img_el else None
        href = _text(link_el.get("href")) if link_el else None

        item = _base_item(
            title=title_text,
            highest_price=_number_or_none(price_text),
            currency="USD",
            color=None,
            size=None,
            description=None,
            image_url=image_src,
            product_url=urljoin(base_url, href) if href else None,
            category_level_1=None,
            category_level_2=None,
            source_evidence={
                "pid": pid,
                "source_url": source_url,
                "evidence_type": "demandware_html_tile",
                "evidence_index": tile_index,
            },
        )
        item["sku"] = pid
        item["missing_reasons"].update({
            "color": "Not available in product tile - detail page only.",
            "size": "Not available in product tile - detail page only.",
            "description": "Not available in product tile.",
            "category_level_1": "Not in tile data.",
        })
        if not image_src:
            item["missing_reasons"]["image_url"] = "Image not in tile."
        if not href:
            item["missing_reasons"]["product_url"] = "Link not in tile."
        items.append(item)

    # Fallback: JS product impression data
    if not items:
        items = _demandware_js_product_tiles(html, base_url=base_url, source_url=source_url)

    return items


def _demandware_js_product_tiles(
    html: str,
    *,
    base_url: str,
    source_url: str,
) -> list[dict[str, Any]]:
    """Fallback: extract product data from inline JS product impression objects."""
    items: list[dict[str, Any]] = []
    # Match common SFCC JS patterns: productImpressions, dataLayer push
    for match in re.finditer(
        r"productImpressions\s*=\s*(\[.*?\]);",
        html or "",
        re.DOTALL,
    ):
        products = _parse_jsonish(match.group(1))
        if not isinstance(products, list):
            continue
        for idx, prod in enumerate(products):
            if not isinstance(prod, dict):
                continue
            item = _base_item(
                title=_text(prod.get("name") or prod.get("product_name")),
                highest_price=_number_or_none(prod.get("price") or prod.get("product_price")),
                currency=_text(prod.get("currency")) or "USD",
                color=None,
                size=None,
                description=None,
                image_url=_text(prod.get("image") or prod.get("product_image")),
                product_url=_text(prod.get("url") or prod.get("product_url")),
                category_level_1=_text(prod.get("category") or prod.get("product_category")) or None,
                category_level_2=None,
                source_evidence={
                    "pid": _text(prod.get("id") or prod.get("product_id")),
                    "source_url": source_url,
                    "evidence_type": "demandware_js_impression",
                    "evidence_index": len(items),
                },
            )
            item["sku"] = _text(prod.get("id") or prod.get("product_id"))
            item["missing_reasons"].update({
                "color": "Not in product impression data.",
                "size": "Not in product impression data.",
                "description": "Not in product impression data.",
            })
            items.append(item)
    return items


def extract_next_data_json_from_html(html: str) -> dict[str, Any] | None:
    """Return parsed ``script#__NEXT_DATA__`` JSON from rendered HTML."""
    soup = BeautifulSoup(html or "", "lxml")
    script = soup.select_one("script#__NEXT_DATA__")
    if script is None:
        return None
    text = script.string if script.string is not None else script.get_text("", strip=False)
    parsed = _parse_jsonish(text)
    return parsed if isinstance(parsed, dict) else None


def _gtm_item_to_clm(
    item: dict[str, Any],
    *,
    tile: Any,
    base_url: str,
    source_url: str,
    evidence_index: int,
    evidence_type: str,
) -> dict[str, Any]:
    image_url = _tile_image_url(tile) if tile is not None else None
    product_url = _tile_product_url(tile, base_url) if tile is not None else None
    clm_item = _base_item(
        title=_text(item.get("item_name")),
        highest_price=_number_or_none(item.get("price")),
        currency=_text(item.get("currency")) or "GBP",
        color=_text(item.get("item_colour")),
        size=None,
        description=None,
        image_url=image_url,
        product_url=product_url,
        category_level_1=_text(item.get("item_category")),
        category_level_2=_text(item.get("item_category2")),
        source_evidence={
            "gtm_item_name": _text(item.get("item_name")),
            "gtm_item_id": _text(item.get("item_id")),
            "gtm_price": item.get("price"),
            "gtm_item_colour": _text(item.get("item_colour")),
            "source_url": source_url,
            "evidence_type": evidence_type,
            "evidence_index": evidence_index,
        },
    )
    clm_item["brand"] = _text(item.get("item_brand"))
    clm_item["sku"] = _text(item.get("item_sku"))
    clm_item["original_price"] = _number_or_none(item.get("item_orig_price"))
    clm_item["season"] = _text(item.get("item_season"))
    clm_item["product_id"] = _text(item.get("item_id"))
    clm_item["missing_reasons"].update({
        "size": "Not available in listing page - detail page only",
        "description": "Not available in listing page - detail page only",
    })
    if not image_url:
        clm_item["missing_reasons"]["image_url"] = "Image URL not available in this evidence."
    if not product_url:
        clm_item["missing_reasons"]["product_url"] = "Product URL not available in this evidence."
    return clm_item


def _base_item(
    *,
    title: str,
    highest_price: float | None,
    currency: str,
    color: str | None,
    size: str | None,
    description: str | None,
    image_url: str | None,
    product_url: str | None,
    category_level_1: str,
    category_level_2: str | None,
    source_evidence: dict[str, Any],
) -> dict[str, Any]:
    item = {
        "title": title,
        "highest_price": highest_price,
        "currency": currency,
        "color": color or None,
        "size": size or None,
        "description": description or None,
        "image_url": image_url or None,
        "product_url": product_url or None,
        "category_level_1": category_level_1 or None,
        "category_level_2": category_level_2 or None,
        "source_evidence": source_evidence,
        "missing_reasons": {},
    }
    for field in CLM_ITEM_FIELDS:
        if field in ("source_evidence", "missing_reasons"):
            continue
        if item.get(field) in (None, "", []):
            item["missing_reasons"].setdefault(field, "Field not present in source evidence.")
    return item


def _nike_products_from_evidence(evidence: Any) -> list[Any]:
    data = _coerce_json(evidence)
    if isinstance(data, list):
        return data
    if not isinstance(data, dict):
        return []
    wall = _dig(data, "props", "pageProps", "initialState", "Wall")
    if not isinstance(wall, dict):
        wall = _dig(data, "Wall")
    groupings = _as_list(_dig(wall, "productGroupings") if isinstance(wall, dict) else None)
    products: list[Any] = []
    for grouping in groupings:
        if isinstance(grouping, dict):
            products.extend(_as_list(grouping.get("products")))
    return products


def _ms_products_from_evidence(evidence: Any) -> list[Any]:
    data = _coerce_json(evidence)
    if not isinstance(data, dict):
        return []
    if isinstance(data.get("products"), list):
        return data["products"]
    results = _dig(data, "props", "pageProps", "serverSideGqlResponseFed", "productPageData", "search", "results")
    if isinstance(results, dict):
        return _as_list(results.get("products"))
    results = _dig(data, "serverSideGqlResponseFed", "productPageData", "search", "results")
    if isinstance(results, dict):
        return _as_list(results.get("products"))
    return []


def _tile_image_url(tile: Any) -> str | None:
    image = tile.select_one("img.tile-image[srcset]") or tile.select_one("img.tile-image[src]")
    if image is None:
        return None
    srcset = image.get("srcset")
    if srcset:
        parsed = _parse_srcset(srcset)
        if parsed:
            return parsed
    src = image.get("src")
    return html_lib.unescape(src).strip() if src else None


def _tile_product_url(tile: Any, base_url: str) -> str | None:
    link = tile.select_one(".tile-image-wrapper-link[href]") or tile.select_one("a[href]")
    if link is None:
        return None
    href = link.get("href")
    if not href:
        return None
    return urljoin(base_url, html_lib.unescape(href).strip())


def _parse_srcset(value: str) -> str | None:
    best_url = ""
    best_score = -1.0
    for raw_part in str(value or "").split(","):
        part = html_lib.unescape(raw_part).strip()
        if not part:
            continue
        pieces = part.split()
        url = pieces[0].strip()
        score = 1.0
        if len(pieces) > 1:
            descriptor = pieces[1].strip().lower()
            try:
                if descriptor.endswith("w"):
                    score = float(descriptor[:-1])
                elif descriptor.endswith("x"):
                    score = float(descriptor[:-1]) * 1000
            except ValueError:
                score = 1.0
        width_match = re.search(r"[?&]width=(\d+)", url)
        if width_match:
            score = max(score, float(width_match.group(1)))
        if score > best_score:
            best_url = url
            best_score = score
    return best_url or None


def _data_gtm_payloads_from_text(html: str) -> list[Any]:
    payloads: list[Any] = []
    for match in re.finditer(r"""data-gtm=(["'])(.*?)\1""", html or "", flags=re.DOTALL):
        parsed = _parse_jsonish(match.group(2))
        if parsed is not None:
            payloads.append(parsed)
    return payloads


def _parse_jsonish(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    text = html_lib.unescape(str(value or "")).strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _coerce_json(evidence: Any) -> Any:
    if isinstance(evidence, (dict, list)):
        return evidence
    if isinstance(evidence, str):
        parsed_next_data = extract_next_data_json_from_html(evidence)
        if parsed_next_data is not None:
            return parsed_next_data
        return _parse_jsonish(evidence)
    return None


def _dig(value: Any, *path: str) -> Any:
    current = value
    for part in path:
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if value is None:
        return []
    return [value]


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _number_or_none(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text:
        return None
    match = re.search(r"-?\d+(?:[.,]\d+)?", text)
    if not match:
        return None
    try:
        return float(match.group(0).replace(",", "."))
    except ValueError:
        return None


def _join_title(primary: Any, secondary: Any) -> str:
    parts = [_text(primary), _text(secondary)]
    parts = [part for part in parts if part]
    return " - ".join(parts)


def _query_param(url_or_path: str, name: str) -> str | None:
    if not url_or_path:
        return None
    values = parse_qs(urlparse(url_or_path).query).get(name)
    if not values:
        return None
    return values[0]


def _site_base_url(site: str) -> str:
    site = site.strip().lower()
    if not site:
        return ""
    if site.startswith("http://") or site.startswith("https://"):
        return site
    return f"https://www.{site}"


def _image_template_from_contract(contract: dict[str, Any]) -> str:
    fields = contract.get("field_paths") if isinstance(contract.get("field_paths"), dict) else {}
    image = fields.get("image_url") if isinstance(fields.get("image_url"), dict) else {}
    template = _text(image.get("template"))
    return template or "https://assets.digitalcontent.marksandspencer.app/image/upload/q_auto,f_auto/{assetId}"
