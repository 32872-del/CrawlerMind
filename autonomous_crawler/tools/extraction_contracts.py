"""Automatic extraction contract discovery for ecommerce evidence.

This module bridges raw page/API evidence and CLM's contract-driven ecommerce
extractors.  It deliberately stays conservative: a strategy is only promoted
when the detector sees a recognizable evidence shape, and confidence is boosted
when the generated contract can actually extract sample items.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import json
import re
from typing import Any
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from .ecommerce_extractors import extract_items_from_contract


AUTOCONTRACT_VERSION = "extraction-contract-discovery/v1"


@dataclass(frozen=True)
class ExtractionContractCandidate:
    """One detected extraction contract plus validation metadata."""

    contract: dict[str, Any]
    confidence: float
    reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    sample_items: list[dict[str, Any]] = field(default_factory=list)
    sample_count: int = 0
    extraction_error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": AUTOCONTRACT_VERSION,
            "contract": dict(self.contract),
            "confidence": round(float(self.confidence), 4),
            "reasons": list(self.reasons),
            "warnings": list(self.warnings),
            "sample_count": int(self.sample_count),
            "sample_items": [dict(item) for item in self.sample_items],
            "extraction_error": self.extraction_error,
        }


def discover_extraction_contracts(
    evidence: Any,
    *,
    source_url: str = "",
    site: str = "",
    max_candidates: int = 6,
    sample_items: int = 5,
) -> dict[str, Any]:
    """Detect extraction contracts and validate them against supplied evidence."""
    site_name = _site_name(site, source_url)
    raw_candidates = _detect_candidates(evidence, source_url=source_url, site=site_name)
    candidates = [
        _validate_candidate(
            evidence,
            candidate,
            source_url=source_url,
            sample_items=sample_items,
        )
        for candidate in raw_candidates
    ]
    candidates.sort(key=lambda item: (item.sample_count > 0, item.confidence), reverse=True)
    candidates = candidates[:max_candidates]
    best = candidates[0] if candidates else None
    return {
        "schema_version": AUTOCONTRACT_VERSION,
        "source_url": source_url,
        "site": site_name,
        "candidate_count": len(candidates),
        "best_contract": best.contract if best else None,
        "best_confidence": round(float(best.confidence), 4) if best else 0.0,
        "best_sample_count": best.sample_count if best else 0,
        "candidates": [candidate.to_dict() for candidate in candidates],
        "warnings": [] if candidates else ["No supported extraction evidence pattern detected."],
    }


def discover_best_extraction_contract(
    evidence: Any,
    *,
    source_url: str = "",
    site: str = "",
    sample_items: int = 5,
) -> dict[str, Any] | None:
    """Return the best contract dict, or ``None`` when no pattern is detected."""
    result = discover_extraction_contracts(
        evidence,
        source_url=source_url,
        site=site,
        sample_items=sample_items,
    )
    best = result.get("best_contract")
    return dict(best) if isinstance(best, dict) else None


def build_extract_from_contract_extra_context(
    evidence: Any,
    *,
    source_url: str = "",
    site: str = "",
    max_items: int = 100,
) -> dict[str, Any]:
    """Build managed-action ``extra_context`` for auto contract extraction."""
    discovery = discover_extraction_contracts(
        evidence,
        source_url=source_url,
        site=site,
        sample_items=min(max_items, 5),
    )
    contract = discovery.get("best_contract")
    if not isinstance(contract, dict):
        return {
            "extraction_contract_discovery": discovery,
            "extraction_contract": None,
            "extraction_evidence": None,
        }
    return {
        "extraction_contract_discovery": discovery,
        "extraction_contract": contract,
        "extraction_evidence": evidence,
        "source_url": source_url,
        "max_items": max_items,
    }


def _detect_candidates(evidence: Any, *, source_url: str, site: str) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    if isinstance(evidence, str):
        candidates.extend(_detect_html_candidates(evidence, source_url=source_url, site=site))
        parsed = _parse_json_string(evidence)
        if parsed is not None:
            candidates.extend(_detect_json_candidates(parsed, source_url=source_url, site=site))
    elif isinstance(evidence, (dict, list)):
        candidates.extend(_detect_json_candidates(evidence, source_url=source_url, site=site))
    return _dedupe_contracts(candidates)


def _detect_html_candidates(html: str, *, source_url: str, site: str) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html or "", "lxml")
    candidates: list[dict[str, Any]] = []

    data_gtm_count = len(soup.select("[data-gtm]"))
    if data_gtm_count:
        candidates.append(_contract(
            site=site,
            source_url=source_url,
            source_type="html_listing_page",
            runtime="requests",
            strategy_name="gtm_data_attribute_extractor",
            description="Extract products from ecommerce.items inside GTM data-gtm attributes.",
            confidence=0.74,
            reasons=[
                f"Found {data_gtm_count} elements with data-gtm attributes.",
                "GTM payloads often contain ecommerce.items product metadata.",
            ],
            parser_strategy_extra={
                "entry_selector": ".product-tile[data-gtm], [data-gtm]",
                "attribute": "data-gtm",
            },
        ))

    jsonld_product_count, jsonld_itemlist_count = _jsonld_type_counts(soup)
    if jsonld_product_count:
        candidates.append(_contract(
            site=site,
            source_url=source_url,
            source_type="html_structured_data",
            runtime="requests",
            strategy_name="jsonld_product_extractor",
            description="Extract products from schema.org Product JSON-LD scripts.",
            confidence=0.68,
            reasons=[f"Found {jsonld_product_count} JSON-LD Product object(s)."],
            parser_strategy_extra={"entry_selector": 'script[type="application/ld+json"]'},
        ))
    if jsonld_itemlist_count:
        candidates.append(_contract(
            site=site,
            source_url=source_url,
            source_type="html_structured_data",
            runtime="requests",
            strategy_name="jsonld_itemlist_extractor",
            description="Extract products from schema.org ItemList JSON-LD scripts.",
            confidence=0.7,
            reasons=[f"Found {jsonld_itemlist_count} JSON-LD ItemList object(s)."],
            parser_strategy_extra={"entry_selector": 'script[type="application/ld+json"]'},
        ))

    next_data = _next_data_from_soup(soup)
    if isinstance(next_data, dict):
        candidates.extend(_detect_next_data_candidates(next_data, source_url=source_url, site=site))

    tile_count = len(soup.select(".product-tile[data-pid]"))
    has_demandware_js = "productImpressions" in html
    if tile_count or has_demandware_js:
        candidates.append(_contract(
            site=site,
            source_url=source_url,
            source_type="html_listing_page",
            runtime="requests",
            strategy_name="demandware_product_tile_extractor",
            description="Extract products from Demandware/SFCC product tiles or productImpressions JS.",
            confidence=0.62,
            reasons=[
                f"Found {tile_count} .product-tile[data-pid] element(s).",
                "Found productImpressions JS fallback." if has_demandware_js else "",
            ],
            parser_strategy_extra={
                "entry_selector": ".product-tile[data-pid]",
                "fallback": "productImpressions JavaScript array",
            },
        ))

    if "Shopify.analytics.meta.product" in html or re.search(r'"products"\s*:\s*\[', html):
        candidates.append(_contract(
            site=site,
            source_url=source_url,
            source_type="html_or_json_listing",
            runtime="requests",
            strategy_name="shopify_product_grid_extractor",
            description="Extract products from Shopify product JSON or analytics meta product.",
            confidence=0.6,
            reasons=["Found Shopify analytics or products JSON marker in HTML."],
        ))

    return candidates


def _detect_json_candidates(evidence: Any, *, source_url: str, site: str) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []

    if _has_nike_wall_products(evidence):
        candidates.append(_contract(
            site=site or "nike.com",
            source_url=source_url,
            source_type="nextjs_ssr_listing_page",
            runtime="browser",
            strategy_name="next_data_product_wall_extractor",
            description="Extract Nike-style products from __NEXT_DATA__.initialState.Wall.productGroupings.",
            confidence=0.78,
            reasons=["Found Wall.productGroupings products in JSON evidence."],
        ))

    if _has_graphql_ssr_products(evidence):
        candidates.append(_contract(
            site=site,
            source_url=source_url,
            source_type="nextjs_graphql_ssr_listing_page",
            runtime="browser",
            strategy_name="next_data_graphql_ssr_cache_extractor",
            description="Extract products from Next.js GraphQL SSR product cache.",
            confidence=0.8,
            reasons=["Found GraphQL SSR product search results with products array."],
        ))

    if _has_shopify_products(evidence):
        candidates.append(_contract(
            site=site,
            source_url=source_url,
            source_type="shopify_product_json",
            runtime="requests",
            strategy_name="shopify_product_grid_extractor",
            description="Extract products from Shopify products JSON or analytics meta product.",
            confidence=0.7,
            reasons=["Found Shopify-like product JSON shape."],
        ))

    jsonld_type = _jsonld_evidence_type(evidence)
    if jsonld_type == "ItemList":
        candidates.append(_contract(
            site=site,
            source_url=source_url,
            source_type="jsonld_itemlist",
            runtime="requests",
            strategy_name="jsonld_itemlist_extractor",
            description="Extract products from pre-parsed JSON-LD ItemList.",
            confidence=0.72,
            reasons=["Found pre-parsed JSON-LD ItemList."],
        ))
    elif jsonld_type == "Product":
        candidates.append(_contract(
            site=site,
            source_url=source_url,
            source_type="jsonld_product",
            runtime="requests",
            strategy_name="jsonld_product_extractor",
            description="Extract product from pre-parsed JSON-LD Product.",
            confidence=0.68,
            reasons=["Found pre-parsed JSON-LD Product."],
        ))

    return candidates


def _detect_next_data_candidates(data: dict[str, Any], *, source_url: str, site: str) -> list[dict[str, Any]]:
    return _detect_json_candidates(data, source_url=source_url, site=site)


def _validate_candidate(
    evidence: Any,
    contract: dict[str, Any],
    *,
    source_url: str,
    sample_items: int,
) -> ExtractionContractCandidate:
    confidence = float(contract.get("confidence") or 0.0)
    reasons = list(contract.get("detection", {}).get("reasons") or [])
    warnings: list[str] = []
    error = ""
    items: list[dict[str, Any]] = []
    try:
        items = extract_items_from_contract(evidence, contract, source_url=source_url)
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        warnings.append("Candidate extractor raised an error during sample validation.")
    if items:
        confidence = min(0.98, confidence + min(0.18, len(items) * 0.03))
        reasons.append(f"Extractor validation produced {len(items)} sample item(s).")
    else:
        confidence = max(0.05, confidence - 0.25)
        warnings.append("Candidate did not extract sample items from supplied evidence.")
    return ExtractionContractCandidate(
        contract=contract,
        confidence=confidence,
        reasons=_clean_list(reasons),
        warnings=_clean_list(warnings),
        sample_items=items[:sample_items],
        sample_count=len(items),
        extraction_error=error,
    )


def _contract(
    *,
    site: str,
    source_url: str,
    source_type: str,
    runtime: str,
    strategy_name: str,
    description: str,
    confidence: float,
    reasons: list[str],
    parser_strategy_extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    strategy: dict[str, Any] = {
        "name": strategy_name,
        "description": description,
    }
    if parser_strategy_extra:
        strategy.update(parser_strategy_extra)
    return {
        "contract_version": "1.0",
        "site": site,
        "source_url": source_url,
        "source_type": source_type,
        "recommended_clm_runtime": runtime,
        "parser_strategy": strategy,
        "field_paths": _field_paths_for_strategy(strategy_name),
        "missing_fields": _missing_fields_for_strategy(strategy_name),
        "confidence": confidence,
        "detection": {
            "schema_version": AUTOCONTRACT_VERSION,
            "reasons": _clean_list(reasons),
            "generated_by": "CLM automatic extraction contract discovery",
        },
    }


def _field_paths_for_strategy(strategy_name: str) -> dict[str, Any]:
    common_optional = {
        "color": {"path": None, "type": "string|null", "required": False},
        "size": {"path": None, "type": "string|null", "required": False},
        "description": {"path": None, "type": "string|null", "required": False},
    }
    if strategy_name == "gtm_data_attribute_extractor":
        return {
            "title": {"path": "ecommerce.items[0].item_name", "type": "string", "required": True},
            "highest_price": {"path": "ecommerce.items[0].price", "type": "number", "required": True},
            "currency": {"path": "ecommerce.items[0].currency", "type": "string", "required": False},
            "color": {"path": "ecommerce.items[0].item_colour", "type": "string", "required": False},
            "image_url": {"path": "sibling img tile source", "type": "string", "required": False},
            "product_url": {"path": "sibling product link href", "type": "string", "required": False},
        }
    if strategy_name == "next_data_product_wall_extractor":
        return {
            "title": {"path": "copy.title + copy.subTitle", "type": "string", "required": True},
            "highest_price": {"path": "prices.currentPrice", "type": "number", "required": True},
            "currency": {"path": "prices.currency", "type": "string", "required": True},
            "color": {"path": "displayColors.colorDescription", "type": "string", "required": False},
            "image_url": {"path": "colorwayImages.portraitURL", "type": "string", "required": False},
            "product_url": {"path": "pdpUrl.url", "type": "string", "required": False},
        }
    if strategy_name == "next_data_graphql_ssr_cache_extractor":
        return {
            "title": {"path": "products[].title", "type": "string", "required": True},
            "highest_price": {"path": "products[].price.listPrice.amount", "type": "number", "required": True},
            "currency": {"path": "products[].price.currency", "type": "string", "required": True},
            "color": {"path": "products[].seoPath query param color", "type": "string", "required": False},
            "size": {"path": "products[].variants[0].size", "type": "string", "required": False},
            "image_url": {"path": "variants[0].mediaAssets[0].assetId template", "type": "string", "required": False},
            "product_url": {"path": "products[].seoPath", "type": "string", "required": False},
        }
    if strategy_name in {"jsonld_product_extractor", "jsonld_itemlist_extractor"}:
        return {
            "title": {"path": "Product.name", "type": "string", "required": True},
            "highest_price": {"path": "Product.offers.price", "type": "number", "required": False},
            "currency": {"path": "Product.offers.priceCurrency", "type": "string", "required": False},
            "description": {"path": "Product.description", "type": "string", "required": False},
            "image_url": {"path": "Product.image", "type": "string", "required": False},
            "product_url": {"path": "Product.url", "type": "string", "required": False},
        }
    if strategy_name == "shopify_product_grid_extractor":
        return {
            "title": {"path": "products[].title", "type": "string", "required": True},
            "highest_price": {"path": "variants[0].compare_at_price || variants[0].price", "type": "number", "required": False},
            "color": {"path": "options[name=Color].values[0]", "type": "string", "required": False},
            "size": {"path": "options[name=Size].values[0]", "type": "string", "required": False},
            "description": {"path": "products[].body_html", "type": "html|string", "required": False},
            "image_url": {"path": "image.src || images[0].src", "type": "string", "required": False},
        }
    if strategy_name == "demandware_product_tile_extractor":
        return {
            "title": {"path": ".product-tile__name || .pdp-link a", "type": "string", "required": True},
            "highest_price": {"path": ".price .value content/text", "type": "number", "required": False},
            "image_url": {"path": ".product-tile__image img src", "type": "string", "required": False},
            "product_url": {"path": ".pdp-link a href", "type": "string", "required": False},
            **common_optional,
        }
    return {}


def _missing_fields_for_strategy(strategy_name: str) -> list[str]:
    if strategy_name in {
        "gtm_data_attribute_extractor",
        "next_data_product_wall_extractor",
        "jsonld_product_extractor",
        "jsonld_itemlist_extractor",
        "demandware_product_tile_extractor",
    }:
        return ["size", "description"]
    if strategy_name == "shopify_product_grid_extractor":
        return []
    if strategy_name == "next_data_graphql_ssr_cache_extractor":
        return ["category_level_2"]
    return []


def _jsonld_type_counts(soup: BeautifulSoup) -> tuple[int, int]:
    product_count = 0
    itemlist_count = 0
    for script in soup.select('script[type="application/ld+json"]'):
        parsed = _parse_json_string(script.string or script.get_text("", strip=False))
        for obj in _walk_jsonld_objects(parsed):
            schema_type = _schema_type(obj)
            if schema_type == "Product":
                product_count += 1
            elif schema_type == "ItemList":
                itemlist_count += 1
    return product_count, itemlist_count


def _next_data_from_soup(soup: BeautifulSoup) -> dict[str, Any] | None:
    script = soup.select_one("script#__NEXT_DATA__")
    if script is None:
        return None
    parsed = _parse_json_string(script.string or script.get_text("", strip=False))
    return parsed if isinstance(parsed, dict) else None


def _has_nike_wall_products(value: Any) -> bool:
    if isinstance(value, list):
        return any(_looks_like_nike_wall_product(item) for item in value[:5])
    wall = _dig(value, "props", "pageProps", "initialState", "Wall")
    if not isinstance(wall, dict):
        wall = _dig(value, "Wall")
    groups = _dig(wall, "productGroupings") if isinstance(wall, dict) else None
    return any(isinstance(group, dict) and group.get("products") for group in _as_list(groups))


def _looks_like_nike_wall_product(value: Any) -> bool:
    return isinstance(value, dict) and (
        isinstance(value.get("copy"), dict)
        and isinstance(value.get("prices"), dict)
        and ("productCode" in value or "colorwayImages" in value or "pdpUrl" in value)
    )


def _has_graphql_ssr_products(value: Any) -> bool:
    if isinstance(value, dict) and isinstance(value.get("products"), list):
        return _looks_like_graphql_product_list(value["products"])
    results = _dig(value, "props", "pageProps", "serverSideGqlResponseFed", "productPageData", "search", "results")
    if isinstance(results, dict) and isinstance(results.get("products"), list):
        return True
    results = _dig(value, "serverSideGqlResponseFed", "productPageData", "search", "results")
    return isinstance(results, dict) and isinstance(results.get("products"), list)


def _looks_like_graphql_product_list(products: list[Any]) -> bool:
    if not products:
        return False
    first = products[0]
    return isinstance(first, dict) and (
        "seoPath" in first
        and (
            isinstance(first.get("price"), dict)
            or any(isinstance(item, dict) and "mediaAssets" in item for item in _as_list(first.get("variants")))
        )
    )


def _has_shopify_products(value: Any) -> bool:
    if isinstance(value, dict) and isinstance(value.get("products"), list):
        return any(_looks_like_shopify_product(item) for item in value["products"][:5])
    if isinstance(value, list):
        return any(_looks_like_shopify_product(item) for item in value[:5])
    if isinstance(value, dict):
        product = _dig(value, "Shopify", "analytics", "meta", "product")
        return _looks_like_shopify_product(product)
    return False


def _looks_like_shopify_product(value: Any) -> bool:
    return isinstance(value, dict) and (
        "handle" in value
        or "variants" in value and ("vendor" in value or "product_type" in value)
    )


def _jsonld_evidence_type(value: Any) -> str:
    if isinstance(value, dict):
        return _schema_type(value)
    if isinstance(value, list):
        types = {_schema_type(item) for item in value if isinstance(item, dict)}
        if "Product" in types:
            return "Product"
    return ""


def _walk_jsonld_objects(value: Any) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    if isinstance(value, dict):
        output.append(value)
        graph = value.get("@graph")
        if isinstance(graph, list):
            output.extend(item for item in graph if isinstance(item, dict))
    elif isinstance(value, list):
        for item in value:
            if isinstance(item, dict):
                output.extend(_walk_jsonld_objects(item))
    return output


def _schema_type(value: dict[str, Any]) -> str:
    raw_type = value.get("@type")
    if isinstance(raw_type, list):
        return str(raw_type[0] if raw_type else "").strip()
    return str(raw_type or "").strip()


def _parse_json_string(value: str) -> Any:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _site_name(site: str, source_url: str) -> str:
    if site:
        return site.strip().lower()
    parsed = urlparse(source_url or "")
    return parsed.netloc.lower().removeprefix("www.")


def _dedupe_contracts(contracts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    output: list[dict[str, Any]] = []
    for contract in contracts:
        strategy = contract.get("parser_strategy") if isinstance(contract.get("parser_strategy"), dict) else {}
        key = f"{contract.get('site', '')}:{strategy.get('name', '')}:{contract.get('source_type', '')}"
        if key in seen:
            continue
        seen.add(key)
        output.append(contract)
    return output


def _clean_list(values: list[Any]) -> list[str]:
    return [str(item).strip() for item in values if str(item or "").strip()]


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
