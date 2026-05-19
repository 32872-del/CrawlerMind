"""Profile-driven ecommerce runner helpers.

This module translates explicit `SiteProfile` data into the callback hooks used
by `SpiderRuntimeProcessor`. It stays site-agnostic: selectors, link rules, and
quality expectations must come from the supplied profile.
"""
from __future__ import annotations

import re
import json
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qs, urlencode, urljoin, urlparse, urlunparse

from autonomous_crawler.models.product import ProductRecord
from autonomous_crawler.runtime import RuntimeResponse, RuntimeSelectorRequest
from autonomous_crawler.tools.link_discovery import LinkDiscoveryHelper, LinkDiscoveryRule

from .site_profile import SiteProfile
from .spider_models import CrawlRequestEnvelope


@dataclass(frozen=True)
class EcommerceProfileCallbacks:
    profile: SiteProfile
    run_id: str

    def selector_builder(
        self,
        request: CrawlRequestEnvelope,
        _item: dict[str, Any],
    ) -> list[RuntimeSelectorRequest]:
        selectors = selectors_for_kind(self.profile, request.kind)
        return [
            selector_request(name, spec)
            for name, spec in selectors.items()
            if name != "item_container"
        ]

    def record_builder(
        self,
        request: CrawlRequestEnvelope,
        response: RuntimeResponse,
        selector_results: list[Any],
    ) -> list[ProductRecord]:
        if is_api_request(request, self.profile):
            return api_records_for_response(self.profile, request, response, run_id=self.run_id)
        if request.kind != "detail":
            return []
        fields = selector_result_values(selector_results)
        fallback = product_fields_from_html(response.html or response.text, base_url=response.final_url or request.url)
        title = first_text(fields.get("title")) or first_text(as_list(fallback.get("title")))
        if not title:
            return []
        url = response.final_url or request.url
        category = str(request.meta.get("category") or self.profile.quality_expectations.get("category") or "")
        record = ProductRecord(
            run_id=self.run_id,
            source_site=self.profile.name,
            source_url=request.url,
            canonical_url=url,
            title=title,
            highest_price=parse_price(
                first_text(fields.get("highest_price") or fields.get("price"))
                or first_text(as_list(fallback.get("highest_price") or fallback.get("price")))
            ),
            currency=str(
                self.profile.quality_expectations.get("currency")
                or first_text(as_list(fallback.get("currency")))
                or ""
            ),
            colors=clean_list(fields.get("colors") or fields.get("color") or as_list(fallback.get("colors"))),
            sizes=clean_list(fields.get("sizes") or fields.get("size") or as_list(fallback.get("sizes"))),
            description=first_text(fields.get("description")) or first_text(as_list(fallback.get("description"))),
            image_urls=absolute_urls(
                clean_list(fields.get("image_urls") or fields.get("image") or as_list(fallback.get("image_urls"))),
                base_url=url,
            ),
            category=category,
            mode="profile-driven" if fields else "profile-fallback-html",
            raw_json={
                "profile": self.profile.name,
                "request_kind": request.kind,
                "selector_fields": fields,
                "html_fallback_fields": fallback,
            },
        )
        return [record]

    def link_builder(
        self,
        request: CrawlRequestEnvelope,
        response: RuntimeResponse,
    ) -> list[CrawlRequestEnvelope]:
        if is_api_request(request, self.profile):
            return next_api_requests(self.profile, request, response)
        if request.kind not in {"category", "list"}:
            return []
        rule = link_rule_from_profile(self.profile)
        result = LinkDiscoveryHelper().extract(
            response.html or response.text,
            base_url=response.final_url or request.url,
            run_id=request.run_id,
            parent_request=request,
            rules=rule,
        )
        requests = list(result.requests)
        requests.extend(hydration_product_requests(self.profile, request, response))
        return dedupe_requests(requests)


def make_ecommerce_profile_callbacks(profile: SiteProfile, *, run_id: str) -> EcommerceProfileCallbacks:
    return EcommerceProfileCallbacks(profile=profile, run_id=run_id)


def initial_requests_from_profile(
    profile: SiteProfile,
    *,
    run_id: str,
    category: str = "",
) -> list[CrawlRequestEnvelope]:
    """Build initial crawl requests from a profile without site-specific code."""
    requests: list[CrawlRequestEnvelope] = []
    endpoint = str(profile.api_hints.get("endpoint") or "").strip()
    if endpoint and profile.pagination_type() in {"page", "offset", "cursor"}:
        url = initial_api_url(profile)
        api_json = dict(profile.api_hints.get("post_json") or {}) if isinstance(profile.api_hints.get("post_json"), dict) else None
        requests.append(
            CrawlRequestEnvelope(
                run_id=run_id,
                url=url,
                method=str(profile.api_hints.get("method") or "GET"),
                priority=int(profile.api_hints.get("priority") or 10),
                kind=str(profile.api_hints.get("kind") or "api"),
                headers={"Content-Type": "application/json"} if api_json is not None else {},
                json=api_json,
                meta={
                    "category": category or str(
                        profile.api_hints.get("category")
                        or profile.quality_expectations.get("category")
                        or ""
                    )
                },
            )
        )
        if not profile.crawl_preferences.get("include_seed_urls_with_api"):
            return requests
    seed_urls = profile.crawl_preferences.get("seed_urls") or profile.constraints.get("seed_urls") or []
    requests.extend(
        CrawlRequestEnvelope(
            run_id=run_id,
            url=str(url),
            priority=10,
            kind=str(profile.crawl_preferences.get("seed_kind") or "list"),
            meta={
                "category": category or str(profile.quality_expectations.get("category") or ""),
                **runtime_meta_from_profile(profile),
            },
        )
        for url in seed_urls
        if str(url).strip()
    )
    return requests


def runtime_meta_from_profile(profile: SiteProfile) -> dict[str, Any]:
    access = profile.access_config if isinstance(profile.access_config, dict) else {}
    meta: dict[str, Any] = {}
    if isinstance(access.get("browser_config"), dict):
        meta["browser_config"] = dict(access.get("browser_config") or {})
    if access.get("wait_until"):
        meta["wait_until"] = str(access.get("wait_until"))
    if access.get("wait_selector"):
        meta["wait_selector"] = str(access.get("wait_selector"))
    if access.get("capture_xhr"):
        meta["capture_xhr"] = str(access.get("capture_xhr"))
    return meta


def selectors_for_kind(profile: SiteProfile, kind: str) -> dict[str, Any]:
    selectors = profile.selectors
    if isinstance(selectors.get(kind), dict):
        return dict(selectors[kind])
    if kind == "category" and isinstance(selectors.get("list"), dict):
        return dict(selectors["list"])
    if kind == "list" and isinstance(selectors.get("category"), dict):
        return dict(selectors["category"])
    return dict(selectors)


def selector_request(name: str, spec: Any) -> RuntimeSelectorRequest:
    if isinstance(spec, dict):
        payload = {
            "name": str(spec.get("name") or name),
            "selector": str(spec.get("selector") or ""),
            "selector_type": str(spec.get("selector_type") or "css"),
            "attribute": str(spec.get("attribute") or ""),
            "many": bool(spec.get("many", True)),
            "required": bool(spec.get("required", False)),
            "signature": spec.get("signature") if isinstance(spec.get("signature"), dict) else {},
        }
        return RuntimeSelectorRequest.from_dict(payload)
    selector, attribute = split_selector_attribute(str(spec or ""))
    return RuntimeSelectorRequest(
        name=str(name),
        selector=selector,
        attribute=attribute,
        many=not is_single_field(str(name)),
    )


def link_rule_from_profile(profile: SiteProfile) -> LinkDiscoveryRule:
    hints = profile.pagination_hints
    link_hints = hints.get("link_discovery") if isinstance(hints.get("link_discovery"), dict) else hints
    return LinkDiscoveryRule(
        allow=tuple(str(item) for item in (link_hints.get("allow") or ())),
        deny=tuple(str(item) for item in (link_hints.get("deny") or ())),
        allow_domains=tuple(str(item).lower() for item in (link_hints.get("allow_domains") or ())),
        deny_domains=tuple(str(item).lower() for item in (link_hints.get("deny_domains") or ())),
        restrict_css=tuple(str(item) for item in (link_hints.get("restrict_css") or ())),
        classify={str(key): str(value) for key, value in (link_hints.get("classify") or {}).items()},
        default_kind=str(link_hints.get("default_kind") or "page"),
        priority=int(link_hints.get("priority") or 0),
        max_links=int(link_hints.get("max_links") or 0),
    )


def hydration_product_requests(
    profile: SiteProfile,
    request: CrawlRequestEnvelope,
    response: RuntimeResponse,
) -> list[CrawlRequestEnvelope]:
    """Discover product detail URLs from rendered/hydrated ecommerce markup."""
    html_text = response.html or response.text
    if not html_text:
        return []
    base_url = response.final_url or request.url
    rule = link_rule_from_profile(profile)
    helper = LinkDiscoveryHelper()
    base_domain = urlparse(base_url).netloc.lower()
    urls = [
        url for url in product_urls_from_html(html_text, base_url=base_url)
        if not helper.drop_reason(url, rules=rule, base_domain=base_domain)
    ]
    max_links = int((profile.pagination_hints.get("link_discovery") or {}).get("max_links") or 300)
    requests: list[CrawlRequestEnvelope] = []
    for url in urls[:max_links]:
        requests.append(CrawlRequestEnvelope(
            run_id=request.run_id,
            url=url,
            priority=max(int(request.priority or 0), 20),
            kind="detail",
            depth=request.depth + 1,
            parent_url=request.url,
            meta={**dict(request.meta), "discovered_by": "hydration_product_links"},
        ))
    return requests


def product_urls_from_html(html_text: str, *, base_url: str) -> list[str]:
    urls: list[str] = []
    try:
        from lxml import html as lxml_html

        root = lxml_html.fromstring(html_text)
        for element in root.xpath("//a[@href]"):
            href = str(element.get("href") or "").strip()
            if not href:
                continue
            text = " ".join(str(part).strip() for part in element.xpath(".//text()") if str(part).strip())
            class_text = str(element.get("class") or "")
            aria = str(element.get("aria-label") or "")
            absolute = urljoin(base_url, href)
            if _looks_like_product_link(absolute, text=text, class_text=class_text, aria=aria):
                urls.append(_strip_fragment(absolute))
    except Exception:
        pass
    return dedupe_strings(urls)


def product_fields_from_html(html_text: str, *, base_url: str) -> dict[str, Any]:
    if not html_text:
        return {}
    fields: dict[str, Any] = {}
    for product in _jsonld_products(html_text):
        fields.update(_fields_from_jsonld_product(product, base_url=base_url))
        if fields.get("title"):
            break
    try:
        from lxml import html as lxml_html

        root = lxml_html.fromstring(html_text)
        fields.setdefault("title", first_text(_xpath_strings(root, [
            "//meta[@property='og:title']/@content",
            "//meta[@name='twitter:title']/@content",
            "string((//h1 | //*[@itemprop='name'])[1])",
            "string(//title[1])",
        ])))
        fields.setdefault("description", first_text(_xpath_strings(root, [
            "//meta[@name='description']/@content",
            "//meta[@property='og:description']/@content",
            "string((//*[@itemprop='description'] | //*[contains(@class,'description')])[1])",
        ])))
        fields.setdefault("image_urls", absolute_urls(_xpath_strings(root, [
            "//meta[@property='og:image']/@content",
            "//meta[@name='twitter:image']/@content",
            "//*[@itemprop='image']/@src",
        ]), base_url=base_url))
        price_text = first_text(_xpath_strings(root, [
            "//meta[@property='product:price:amount']/@content",
            "//*[@itemprop='price']/@content",
            "string((//*[contains(@class,'price')])[1])",
        ]))
        if price_text and not fields.get("highest_price"):
            fields["highest_price"] = price_text
        currency = first_text(_xpath_strings(root, [
            "//meta[@property='product:price:currency']/@content",
            "//*[@itemprop='priceCurrency']/@content",
        ]))
        if currency and not fields.get("currency"):
            fields["currency"] = currency
    except Exception:
        pass
    return {key: value for key, value in fields.items() if value not in ("", [], None)}


def _jsonld_products(html_text: str) -> list[dict[str, Any]]:
    products: list[dict[str, Any]] = []
    for raw in re.findall(r"<script[^>]+type=[\"']application/ld\+json[\"'][^>]*>(.*?)</script>", html_text, re.I | re.S):
        try:
            payload = json.loads(_strip_script_json(raw))
        except Exception:
            continue
        products.extend(_walk_jsonld_products(payload))
    return products


def _walk_jsonld_products(value: Any) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    if isinstance(value, dict):
        type_value = value.get("@type") or value.get("type")
        types = type_value if isinstance(type_value, list) else [type_value]
        if any(str(item).lower() == "product" for item in types):
            found.append(value)
        for key in ("@graph", "graph", "itemListElement"):
            found.extend(_walk_jsonld_products(value.get(key)))
    elif isinstance(value, list):
        for item in value:
            found.extend(_walk_jsonld_products(item))
    return found


def _fields_from_jsonld_product(product: dict[str, Any], *, base_url: str) -> dict[str, Any]:
    offers = product.get("offers")
    offer = offers[0] if isinstance(offers, list) and offers else offers if isinstance(offers, dict) else {}
    image = product.get("image")
    images = image if isinstance(image, list) else [image] if image else []
    return {
        "title": first_text(as_list(product.get("name"))),
        "description": first_text(as_list(product.get("description"))),
        "highest_price": first_text(as_list(offer.get("highPrice") or offer.get("price"))),
        "currency": first_text(as_list(offer.get("priceCurrency"))),
        "colors": clean_list(as_list(product.get("color"))),
        "sizes": clean_list(as_list(product.get("size"))),
        "image_urls": absolute_urls(clean_list(as_list(images)), base_url=base_url),
    }


def _strip_script_json(value: str) -> str:
    return re.sub(r"^\s*<!--|-->\s*$", "", value or "").strip()


def _strip_fragment(url: str) -> str:
    parsed = urlparse(url)
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, parsed.query, ""))


def _xpath_strings(root: Any, expressions: list[str]) -> list[str]:
    values: list[str] = []
    for expr in expressions:
        try:
            result = root.xpath(expr)
        except Exception:
            continue
        values.extend(as_list(result))
    return clean_list(values)


def _looks_like_product_link(url: str, *, text: str = "", class_text: str = "", aria: str = "") -> bool:
    parsed = urlparse(url)
    path = parsed.path.lower()
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return False
    blocked = (
        "/cart", "/checkout", "/customer", "/account", "/login", "/privacy", "/terms",
        "/blog", "/contact", "/search", "/wishlist", "/compare",
    )
    if any(token in path for token in blocked):
        return False
    combined = f"{text} {class_text} {aria}".lower()
    if any(token in combined for token in ("add to cart", "do koszyka", "price", "cena", "product", "produkt")):
        return True
    if any(token in path for token in ("/product/", "/products/", "/produkt/", "/produkty/", "/p/")):
        return True
    if path.endswith(".html") and re.search(r"/[^/]*[a-z][a-z0-9-]*-\d{2,}[^/]*\.html$", path):
        return True
    return False


def dedupe_requests(requests: list[CrawlRequestEnvelope]) -> list[CrawlRequestEnvelope]:
    output: list[CrawlRequestEnvelope] = []
    seen: set[str] = set()
    for request in requests:
        key = request.canonical_url()
        if key in seen:
            continue
        seen.add(key)
        output.append(request)
    return output


def dedupe_strings(values: list[str]) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        if text and text not in seen:
            output.append(text)
            seen.add(text)
    return output


def is_api_request(request: CrawlRequestEnvelope, profile: SiteProfile) -> bool:
    if request.kind in {"api", "api_list", "api_page"}:
        return True
    endpoint = str(profile.api_hints.get("endpoint") or "").strip()
    if not endpoint or profile.pagination_type() not in {"page", "offset", "cursor"}:
        return False
    endpoint_parts = urlparse(endpoint)
    request_parts = urlparse(request.url)
    return (
        endpoint_parts.scheme == request_parts.scheme
        and endpoint_parts.netloc == request_parts.netloc
        and endpoint_parts.path == request_parts.path
    )


def initial_api_url(profile: SiteProfile) -> str:
    pagination = profile.pagination_hints
    params = dict(profile.api_hints.get("params") or {})
    mode = profile.pagination_type()
    if mode == "page":
        params[str(pagination.get("page_param") or "page")] = int(pagination.get("start_page") or 1)
    elif mode == "offset":
        params[str(pagination.get("offset_param") or "offset")] = int(pagination.get("start_offset") or 0)
    elif mode == "cursor":
        initial_cursor = str(pagination.get("initial_cursor") or "").strip()
        if initial_cursor:
            params[str(pagination.get("cursor_param") or "cursor")] = initial_cursor
    if pagination.get("page_size") is not None:
        params[str(pagination.get("page_size_param") or pagination.get("limit_param") or "limit")] = int(
            pagination.get("page_size") or 0
        )
    return with_query_params(str(profile.api_hints.get("endpoint") or ""), params)


def api_records_for_response(
    profile: SiteProfile,
    request: CrawlRequestEnvelope,
    response: RuntimeResponse,
    *,
    run_id: str,
) -> list[ProductRecord]:
    payload = response_json(response)
    items = value_at_path(payload, profile.api_items_path())
    if not isinstance(items, list):
        return []
    mapping = profile.api_field_mapping()
    records: list[ProductRecord] = []
    category = str(request.meta.get("category") or profile.quality_expectations.get("category") or "")
    for item in items:
        if not isinstance(item, dict):
            continue
        title = first_text(as_list(mapped_value(item, mapping, "title")))
        if not title:
            continue
        canonical_url = first_text(as_list(mapped_value(item, mapping, "canonical_url") or mapped_value(item, mapping, "url")))
        if canonical_url:
            if not canonical_url.endswith(".html") and item.get("url_suffix"):
                canonical_url = f"{canonical_url}{item.get('url_suffix')}"
            canonical_url = urljoin(response.final_url or request.url, canonical_url)
        else:
            canonical_url = response.final_url or request.url
        record = ProductRecord(
            run_id=run_id,
            source_site=profile.name,
            source_url=request.url,
            canonical_url=canonical_url,
            title=title,
            highest_price=parse_price(first_text(as_list(
                mapped_value(item, mapping, "highest_price") or mapped_value(item, mapping, "price")
            ))),
            currency=str(
                first_text(as_list(mapped_value(item, mapping, "currency")))
                or profile.quality_expectations.get("currency")
                or ""
            ),
            colors=clean_list(as_list(mapped_value(item, mapping, "colors") or mapped_value(item, mapping, "color"))),
            sizes=clean_list(as_list(mapped_value(item, mapping, "sizes") or mapped_value(item, mapping, "size"))),
            description=first_text(as_list(mapped_value(item, mapping, "description"))),
            image_urls=absolute_urls(
                clean_list(as_list(mapped_value(item, mapping, "image_urls") or mapped_value(item, mapping, "image"))),
                base_url=response.final_url or request.url,
            ),
            category=category,
            mode="profile-api-pagination",
            raw_json={"profile": profile.name, "request_kind": request.kind, "api_item": item},
        )
        records.append(record)
    return records


def next_api_requests(
    profile: SiteProfile,
    request: CrawlRequestEnvelope,
    response: RuntimeResponse,
) -> list[CrawlRequestEnvelope]:
    pagination = profile.pagination_hints
    mode = profile.pagination_type()
    if no_more_api_pages(profile, request, response):
        return []
    next_url = ""
    if mode == "page":
        next_url = next_page_url(request.url, pagination)
    elif mode == "offset":
        item_count = len(api_records_for_response(profile, request, response, run_id=request.run_id))
        next_url = next_offset_url(request.url, pagination, item_count=item_count)
    elif mode == "cursor":
        payload = response_json(response)
        cursor = value_at_path(payload, str(pagination.get("next_cursor_path") or ""))
        next_url = next_cursor_url(request.url, pagination, cursor)
    if not next_url:
        return []
    return [
        CrawlRequestEnvelope(
            run_id=request.run_id,
            url=next_url,
            method=str(profile.api_hints.get("method") or request.method or "GET"),
            priority=int(profile.api_hints.get("priority") or request.priority),
            kind=str(profile.api_hints.get("kind") or request.kind or "api"),
            depth=request.depth + 1,
            parent_url=request.url,
            headers=dict(request.headers),
            json=next_api_json(profile, request),
            meta={**dict(request.meta), "discovered_by": "api_pagination"},
        )
    ]


def no_more_api_pages(profile: SiteProfile, request: CrawlRequestEnvelope, response: RuntimeResponse) -> bool:
    payload = response_json(response)
    total = value_at_path(payload, str(profile.api_hints.get("total_path") or ""))
    items = value_at_path(payload, profile.api_items_path())
    item_count = len(items) if isinstance(items, list) else 0
    if item_count <= 0:
        return True
    page_size = int(profile.pagination_hints.get("page_size") or profile.api_hints.get("page_size") or item_count)
    current_page = _current_api_page(profile, request)
    try:
        total_int = int(total)
    except (TypeError, ValueError):
        total_int = 0
    if total_int and current_page * page_size >= total_int:
        return True
    max_items = int(profile.crawl_preferences.get("max_items") or 0)
    if max_items and current_page * page_size >= max_items:
        return True
    return False


def _current_api_page(profile: SiteProfile, request: CrawlRequestEnvelope) -> int:
    if isinstance(request.json, dict):
        variables = request.json.get("variables")
        if isinstance(variables, dict):
            try:
                return int(variables.get("currentPage") or 1)
            except (TypeError, ValueError):
                return 1
    page_param = str(profile.pagination_hints.get("page_param") or "page")
    return int_query_value(request.url, page_param, int(profile.pagination_hints.get("start_page") or 1))


def next_api_json(profile: SiteProfile, request: CrawlRequestEnvelope) -> Any:
    if not isinstance(request.json, dict):
        return request.json
    payload = json.loads(json.dumps(request.json))
    variables = payload.get("variables")
    if isinstance(variables, dict):
        variables["currentPage"] = int(variables.get("currentPage") or 1) + 1
        if profile.pagination_hints.get("page_size"):
            variables["pageSize"] = int(profile.pagination_hints.get("page_size") or variables.get("pageSize") or 50)
    return payload


def next_page_url(url: str, pagination: dict[str, Any]) -> str:
    page_param = str(pagination.get("page_param") or "page")
    current = int_query_value(url, page_param, int(pagination.get("start_page") or 1))
    next_page = current + 1
    max_pages = int(pagination.get("max_pages") or 0)
    if max_pages and next_page > max_pages:
        return ""
    return with_query_params(url, {page_param: next_page})


def next_offset_url(url: str, pagination: dict[str, Any], *, item_count: int) -> str:
    if item_count <= 0:
        return ""
    offset_param = str(pagination.get("offset_param") or "offset")
    page_size = int(pagination.get("page_size") or item_count)
    current = int_query_value(url, offset_param, int(pagination.get("start_offset") or 0))
    next_offset = current + page_size
    max_offset = int(pagination.get("max_offset") or 0)
    if max_offset and next_offset > max_offset:
        return ""
    max_pages = int(pagination.get("max_pages") or 0)
    if max_pages and page_size > 0 and (next_offset // page_size) + 1 > max_pages:
        return ""
    return with_query_params(url, {offset_param: next_offset})


def next_cursor_url(url: str, pagination: dict[str, Any], cursor: Any) -> str:
    text = str(cursor or "").strip()
    if not text:
        return ""
    return with_query_params(url, {str(pagination.get("cursor_param") or "cursor"): text})


def profile_quality_summary(
    records: list[ProductRecord],
    *,
    failed_urls: list[str] | None = None,
    pagination_stop_reason: str = "",
    frontier_stats: dict[str, int] | None = None,
    min_items: int = 0,
    required_fields: Any = None,
    field_thresholds: dict[str, float] | None = None,
    max_duplicate_rate: float = 0.0,
    max_failed_url_count: int = 0,
    gate_mode: str = "",
    fail_on_gate: bool = False,
    quality_policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    total = len(records)
    dedupe_keys = [record.dedupe_key for record in records if record.dedupe_key]
    duplicate_count = len(dedupe_keys) - len(set(dedupe_keys))
    duplicate_rate = round(duplicate_count / total, 4) if total else 0.0
    field_completeness = {
        "title": completeness(records, lambda record: record.title),
        "price": completeness(records, lambda record: record.highest_price is not None),
        "highest_price": completeness(records, lambda record: record.highest_price is not None),
        "category": completeness(records, lambda record: record.category),
        "description": completeness(records, lambda record: record.description),
        "image_urls": completeness(records, lambda record: record.image_urls),
        "colors": completeness(records, lambda record: record.colors),
        "sizes": completeness(records, lambda record: record.sizes),
    }
    failed_url_count = len(failed_urls or [])
    policy = normalize_quality_policy(
        quality_policy,
        min_items=min_items,
        required_fields=required_fields,
        field_thresholds=field_thresholds,
        max_duplicate_rate=max_duplicate_rate,
        max_failed_url_count=max_failed_url_count,
        gate_mode=gate_mode,
        fail_on_gate=fail_on_gate,
    )
    quality_gate = profile_quality_gate(
        total_records=total,
        min_items=int(policy["min_items"]),
        field_thresholds=dict(policy["field_thresholds"]),
        field_completeness=field_completeness,
        duplicate_rate=duplicate_rate,
        max_duplicate_rate=float(policy["max_duplicate_rate"]),
        failed_url_count=failed_url_count,
        max_failed_url_count=int(policy["max_failed_url_count"]),
        mode=str(policy["mode"]),
    )
    return {
        "total_records": total,
        "min_items": int(policy["min_items"]),
        "meets_min_items": total >= int(policy["min_items"]),
        "field_completeness": field_completeness,
        "duplicate_count": duplicate_count,
        "duplicate_rate": duplicate_rate,
        "duplicate_key_strategy": duplicate_key_strategy_summary(),
        "failed_urls": list(failed_urls or []),
        "failed_url_count": failed_url_count,
        "pagination_stop_reason": pagination_stop_reason or "not_recorded",
        "frontier_stats": dict(frontier_stats or {}),
        "quality_policy": policy,
        "quality_gate": quality_gate,
    }


def profile_quality_gate(
    *,
    total_records: int,
    min_items: int,
    field_thresholds: dict[str, float],
    field_completeness: dict[str, float],
    duplicate_rate: float,
    max_duplicate_rate: float,
    failed_url_count: int,
    max_failed_url_count: int,
    mode: str = "warn",
) -> dict[str, Any]:
    fail_on_gate = mode == "fail"
    field_checks = [
        {
            "name": f"field:{field}",
            "field": field,
            "passed": field_completeness.get(normalize_quality_field(field), 0.0) >= threshold,
            "expected": threshold,
            "actual": field_completeness.get(normalize_quality_field(field), 0.0),
        }
        for field, threshold in sorted(field_thresholds.items())
    ]
    checks = [
        {
            "name": "min_items",
            "passed": total_records >= min_items,
            "expected": min_items,
            "actual": total_records,
        },
        {
            "name": "duplicate_rate",
            "passed": duplicate_rate <= max_duplicate_rate,
            "expected": max_duplicate_rate,
            "actual": duplicate_rate,
        },
        {
            "name": "failed_url_count",
            "passed": failed_url_count <= max_failed_url_count,
            "expected": max_failed_url_count,
            "actual": failed_url_count,
        },
    ] + field_checks
    for check in checks:
        check["severity"] = "pass" if check["passed"] else ("fail" if fail_on_gate else "warn")
    passed = all(bool(check["passed"]) for check in checks)
    return {
        "mode": mode,
        "passed": passed,
        "should_fail": bool(fail_on_gate and not passed),
        "severity": "pass" if passed else ("fail" if fail_on_gate else "warn"),
        "checks": checks,
    }


def normalize_quality_policy(
    policy: dict[str, Any] | None,
    *,
    min_items: int = 0,
    required_fields: Any = None,
    field_thresholds: dict[str, float] | None = None,
    max_duplicate_rate: float = 0.0,
    max_failed_url_count: int = 0,
    gate_mode: str = "",
    fail_on_gate: bool = False,
) -> dict[str, Any]:
    source = dict(policy or {})
    nested = source.get("quality_gate") if isinstance(source.get("quality_gate"), dict) else {}
    thresholds: dict[str, float] = {}
    thresholds.update(required_field_thresholds(required_fields))
    thresholds.update(required_field_thresholds(source.get("required_fields")))
    thresholds.update(required_field_thresholds(nested.get("required_fields")))
    thresholds.update(numeric_field_thresholds(field_thresholds))
    thresholds.update(numeric_field_thresholds(source.get("field_thresholds")))
    thresholds.update(numeric_field_thresholds(nested.get("field_thresholds")))
    mode = normalize_gate_mode(
        str(
            gate_mode
            or source.get("mode")
            or nested.get("mode")
            or ("fail" if fail_on_gate else "warn")
        )
    )
    return {
        "mode": mode,
        "min_items": int(first_present(source.get("min_items"), nested.get("min_items"), min_items, default=0) or 0),
        "field_thresholds": thresholds,
        "max_duplicate_rate": float(first_present(
            source.get("max_duplicate_rate"),
            nested.get("max_duplicate_rate"),
            source.get("duplicate_rate"),
            nested.get("duplicate_rate"),
            max_duplicate_rate,
            default=0.0,
        ) or 0.0),
        "max_failed_url_count": int(first_present(
            source.get("max_failed_url_count"),
            nested.get("max_failed_url_count"),
            source.get("failed_url_count"),
            nested.get("failed_url_count"),
            max_failed_url_count,
            default=0,
        ) or 0),
    }


def required_field_thresholds(value: Any) -> dict[str, float]:
    if not value:
        return {}
    if isinstance(value, dict):
        return numeric_field_thresholds(value)
    thresholds: dict[str, float] = {}
    for item in value if isinstance(value, (list, tuple, set)) else [value]:
        if isinstance(item, dict):
            thresholds.update(numeric_field_thresholds(item))
            continue
        field = normalize_quality_field(str(item).strip())
        if field:
            thresholds[field] = 1.0
    return thresholds


def numeric_field_thresholds(value: Any) -> dict[str, float]:
    if not isinstance(value, dict):
        return {}
    thresholds: dict[str, float] = {}
    for key, raw_threshold in value.items():
        field = normalize_quality_field(str(key).strip())
        if not field:
            continue
        try:
            threshold = float(raw_threshold)
        except (TypeError, ValueError):
            threshold = 1.0
        thresholds[field] = min(max(threshold, 0.0), 1.0)
    return thresholds


def first_present(*values: Any, default: Any = None) -> Any:
    for value in values:
        if value is not None:
            return value
    return default


def normalize_gate_mode(value: str) -> str:
    text = str(value or "").strip().lower()
    if text in {"fail", "hard_fail", "enforce"}:
        return "fail"
    return "warn"


def normalize_quality_field(field: str) -> str:
    if field == "highest_price":
        return "price"
    if field in {"image", "images", "image_url"}:
        return "image_urls"
    return str(field)


def duplicate_key_strategy_summary() -> dict[str, Any]:
    return {
        "field": "dedupe_key",
        "source": "ProductRecord",
        "strategy": "sha256(source_site | category | canonical_url_or_source_url_or_title)[:32]",
        "category_aware": True,
        "notes": [
            "The runner compares generated ProductRecord.dedupe_key values.",
            "Duplicate rate quality depends on profile canonical URL mapping quality.",
        ],
    }


def infer_pagination_stop_reason(
    profile: SiteProfile,
    *,
    last_url: str = "",
    last_item_count: int = 0,
    next_request_count: int = 0,
) -> str:
    if next_request_count:
        return "has_next_page"
    mode = profile.pagination_type()
    if mode == "page":
        max_pages = int(profile.pagination_hints.get("max_pages") or 0)
        current = int_query_value(last_url, str(profile.pagination_hints.get("page_param") or "page"), 1)
        if max_pages and current >= max_pages:
            return "max_pages"
    if mode == "offset":
        max_offset = int(profile.pagination_hints.get("max_offset") or 0)
        current = int_query_value(last_url, str(profile.pagination_hints.get("offset_param") or "offset"), 0)
        if max_offset and current >= max_offset:
            return "max_offset"
    if mode == "cursor":
        return "no_next_cursor"
    if last_item_count <= 0:
        return "empty_page"
    if mode:
        return f"{mode}_pagination_stopped"
    return "no_pagination"


def selector_result_values(selector_results: list[Any]) -> dict[str, list[str]]:
    fields: dict[str, list[str]] = {}
    for result in selector_results:
        if getattr(result, "error", ""):
            continue
        fields[str(getattr(result, "name", ""))] = [
            str(value).strip()
            for value in list(getattr(result, "values", []) or [])
            if str(value).strip()
        ]
    return fields


def completeness(records: list[ProductRecord], getter: Any) -> float:
    if not records:
        return 0.0
    present = 0
    for record in records:
        value = getter(record)
        if isinstance(value, bool):
            ok = value
        else:
            ok = bool(value)
        if ok:
            present += 1
    return round(present / len(records), 4)


def response_json(response: RuntimeResponse) -> Any:
    if response.items:
        return {"items": response.items}
    text = response.text or response.html
    if not text and response.body:
        text = response.body.decode("utf-8", errors="replace")
    try:
        return json.loads(text or "{}")
    except json.JSONDecodeError:
        return {}


def value_at_path(payload: Any, path: str) -> Any:
    if not path:
        return payload
    current = payload
    for part in path.split("."):
        if isinstance(current, dict):
            current = current.get(part)
        elif isinstance(current, list) and part.isdigit():
            index = int(part)
            current = current[index] if 0 <= index < len(current) else None
        else:
            return None
    return current


def mapped_value(item: dict[str, Any], mapping: dict[str, Any], field: str) -> Any:
    spec = mapping.get(field, field)
    if isinstance(spec, list):
        values = [value_at_path(item, str(path)) for path in spec]
        if field in {"highest_price", "price"}:
            prices = [parse_price(str(value)) for value in values if value is not None]
            prices = [value for value in prices if value is not None]
            return max(prices) if prices else None
        for value in values:
            if value not in (None, "", []):
                return value
        return None
    return value_at_path(item, str(spec))


def as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        result: list[str] = []
        for item in value:
            result.extend(as_list(item))
        return result
    if isinstance(value, tuple):
        result: list[str] = []
        for item in value:
            result.extend(as_list(item))
        return result
    return [str(value)]


def int_query_value(url: str, name: str, default: int) -> int:
    try:
        values = parse_qs(urlparse(url).query).get(name)
        return int(values[0]) if values else default
    except (TypeError, ValueError):
        return default


def with_query_params(url: str, params: dict[str, Any]) -> str:
    parsed = urlparse(url)
    query = parse_qs(parsed.query, keep_blank_values=True)
    for key, value in params.items():
        if value is None or str(value) == "":
            continue
        query[str(key)] = [str(value)]
    encoded = urlencode(query, doseq=True)
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path or "/", "", encoded, parsed.fragment))


def split_selector_attribute(spec: str) -> tuple[str, str]:
    if "@" not in spec:
        return spec, ""
    selector, attribute = spec.rsplit("@", 1)
    if not selector.strip() or not attribute.strip():
        return spec, ""
    return selector.strip(), attribute.strip()


def is_single_field(name: str) -> bool:
    return name in {"title", "highest_price", "price", "description", "canonical_url"}


def first_text(values: list[str] | None) -> str:
    if not values:
        return ""
    return str(values[0]).strip()


def clean_list(values: list[str] | None) -> list[str]:
    if not values:
        return []
    return [str(value).strip() for value in values if str(value).strip()]


def parse_price(value: str) -> float | None:
    match = re.search(r"\d+(?:[.,]\d+)?", str(value or ""))
    if not match:
        return None
    try:
        return float(match.group(0).replace(",", "."))
    except ValueError:
        return None


def absolute_urls(values: list[str], *, base_url: str) -> list[str]:
    result: list[str] = []
    for value in values:
        joined = urljoin(base_url, value)
        parsed = urlparse(joined)
        if parsed.scheme in {"http", "https"} and parsed.netloc:
            result.append(joined)
    return result
