"""Profile-driven long-running ecommerce execution.

This module is the product-facing assembly layer for SCALE-RUNTIME-1.  It does
not add site rules.  It wires an explicit SiteProfile into the existing CLM
native execution stack:

SiteProfile -> URLFrontier -> BatchRunner -> SpiderRuntimeProcessor ->
ProductStore -> CheckpointStore -> profile-run-report/v1

It also contains the ecommerce callback translation layer that converts
SiteProfile data into SpiderRuntimeProcessor hooks (selectors, record
builders, link builders, pagination, API replay).
"""
from __future__ import annotations

import json
import re
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlencode, urljoin, urlparse, urlunparse

from autonomous_crawler.models.product import ProductRecord
from autonomous_crawler.runtime import BrowserRuntime, FetchRuntime, NativeParserRuntime, ParserRuntime, RuntimeResponse, RuntimeSelectorRequest
from autonomous_crawler.storage.checkpoint_store import CheckpointStore
from autonomous_crawler.storage.frontier import URLFrontier
from autonomous_crawler.storage.product_store import ProductStore
from autonomous_crawler.tools.api_replay_runtime import apply_api_replay_runtime
from autonomous_crawler.tools.link_discovery import LinkDiscoveryHelper, LinkDiscoveryRule
from autonomous_crawler.tools.replay_diagnostics import apply_replay_dynamic_inputs

from .backpressure import BackpressureConfig, BackpressureMonitor, classify_bottlenecks, recommendation_text
from .batch_runner import (
    BatchRunner,
    BatchRunnerConfig,
    BatchRunnerSummary,
    ProductRecordCheckpoint,
    RuleBasedBatchSupervisor,
)
from ..tools.coverage_report import CoverageCounters, build_coverage_report
from .multi_site_runner import MultiSiteRunner, MultiSiteRunnerConfig, MultiSiteRunSummary
from .profile_report import build_profile_run_report
from .site_profile import SiteProfile
from .spider_models import CrawlRequestEnvelope, SpiderRunSummary, make_spider_event
from .spider_runner import SpiderRuntimeProcessor


# ---------------------------------------------------------------------------
# Ecommerce profile callbacks and helpers
# ---------------------------------------------------------------------------


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
    if endpoint and (profile.pagination_type() in {"page", "offset", "cursor"} or profile.api_hints.get("kind") == "api"):
        url = initial_api_url(profile)
        api_json = initial_api_json(profile)
        headers = api_headers_from_profile(profile, has_json=api_json is not None)
        url, headers, api_json = apply_profile_replay_diagnostics(
            profile,
            url=url,
            headers=headers,
            json_body=api_json,
        )
        requests.append(
            CrawlRequestEnvelope(
                run_id=run_id,
                url=url,
                method=str(profile.api_hints.get("method") or "GET"),
                priority=int(profile.api_hints.get("priority") or 10),
                kind=str(profile.api_hints.get("kind") or "api"),
                headers=headers,
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
    if pagination.get("json_page_path") or pagination.get("json_cursor_path"):
        return str(profile.api_hints.get("endpoint") or "")
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


def initial_api_json(profile: SiteProfile) -> Any:
    api_json = clone_json(profile.api_hints.get("post_json")) if isinstance(profile.api_hints.get("post_json"), dict) else None
    if not isinstance(api_json, dict):
        return None
    pagination = profile.pagination_hints
    if pagination.get("json_page_path"):
        set_value_at_path(api_json, str(pagination.get("json_page_path")), int(pagination.get("start_page") or 1))
    if pagination.get("json_page_size_path") and pagination.get("page_size"):
        set_value_at_path(api_json, str(pagination.get("json_page_size_path")), int(pagination.get("page_size") or 0))
    if pagination.get("json_cursor_path") and pagination.get("initial_cursor") not in (None, ""):
        set_value_at_path(api_json, str(pagination.get("json_cursor_path")), pagination.get("initial_cursor"))
    return api_json


def api_headers_from_profile(profile: SiteProfile, *, has_json: bool) -> dict[str, str]:
    headers: dict[str, str] = {}
    raw_headers = profile.api_hints.get("headers") if isinstance(profile.api_hints.get("headers"), dict) else {}
    for key, value in raw_headers.items():
        name = str(key).strip()
        text = str(value or "").strip()
        if name and text:
            headers[name] = text
    if has_json and not any(key.lower() == "content-type" for key in headers):
        headers["Content-Type"] = "application/json"
    return headers


def apply_profile_replay_diagnostics(
    profile: SiteProfile,
    *,
    url: str,
    headers: dict[str, str],
    json_body: Any,
) -> tuple[str, dict[str, str], Any]:
    diagnostics = profile.api_hints.get("replay_diagnostics")
    if isinstance(diagnostics, dict):
        url, headers, json_body = apply_replay_dynamic_inputs(
            url=url,
            headers=headers,
            json_body=json_body,
            diagnostics=diagnostics,
        )
    replay = apply_api_replay_runtime(
        api_hints=profile.api_hints,
        url=url,
        headers=headers,
        json_body=json_body,
        method=str(profile.api_hints.get("method") or "GET"),
    )
    return replay.url, replay.headers, replay.json_body


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
    next_json = next_api_json(profile, request, response)
    json_pagination = isinstance(next_json, dict) and (
        bool(pagination.get("json_page_path"))
        or bool(pagination.get("json_cursor_path"))
        or bool(pagination.get("json_offset_path"))
    )
    if mode == "page":
        next_url = request.url if json_pagination else next_page_url(request.url, pagination)
    elif mode == "offset":
        item_count = len(api_records_for_response(profile, request, response, run_id=request.run_id))
        next_url = next_offset_url(request.url, pagination, item_count=item_count)
    elif mode == "cursor":
        payload = response_json(response)
        cursor = value_at_path(payload, str(pagination.get("next_cursor_path") or ""))
        if pagination.get("json_cursor_path"):
            next_url = request.url if cursor not in (None, "") else ""
        else:
            next_url = next_cursor_url(request.url, pagination, cursor)
    if not next_url:
        return []
    next_headers = dict(request.headers)
    next_url, next_headers, next_json = apply_profile_replay_diagnostics(
        profile,
        url=next_url,
        headers=next_headers,
        json_body=next_json,
    )
    return [
        CrawlRequestEnvelope(
            run_id=request.run_id,
            url=next_url,
            method=str(profile.api_hints.get("method") or request.method or "GET"),
            priority=int(profile.api_hints.get("priority") or request.priority),
            kind=str(profile.api_hints.get("kind") or request.kind or "api"),
            depth=request.depth + 1,
            parent_url=request.url,
            headers=next_headers,
            json=next_json,
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
        json_page_path = str(profile.pagination_hints.get("json_page_path") or "")
        if json_page_path:
            try:
                return int(value_at_path(request.json, json_page_path) or profile.pagination_hints.get("start_page") or 1)
            except (TypeError, ValueError):
                return int(profile.pagination_hints.get("start_page") or 1)
        variables = request.json.get("variables")
        if isinstance(variables, dict):
            try:
                return int(variables.get("currentPage") or 1)
            except (TypeError, ValueError):
                return 1
    page_param = str(profile.pagination_hints.get("page_param") or "page")
    return int_query_value(request.url, page_param, int(profile.pagination_hints.get("start_page") or 1))


def next_api_json(profile: SiteProfile, request: CrawlRequestEnvelope, response: RuntimeResponse | None = None) -> Any:
    if not isinstance(request.json, dict):
        return request.json
    payload = clone_json(request.json)
    pagination = profile.pagination_hints
    if pagination.get("json_page_path"):
        path = str(pagination.get("json_page_path"))
        try:
            current = int(value_at_path(payload, path) or pagination.get("start_page") or 1)
        except (TypeError, ValueError):
            current = int(pagination.get("start_page") or 1)
        set_value_at_path(payload, path, current + 1)
        if pagination.get("json_page_size_path") and pagination.get("page_size"):
            set_value_at_path(payload, str(pagination.get("json_page_size_path")), int(pagination.get("page_size") or 0))
        return payload
    if pagination.get("json_cursor_path") and response is not None:
        cursor = value_at_path(response_json(response), str(pagination.get("next_cursor_path") or ""))
        if cursor not in (None, ""):
            set_value_at_path(payload, str(pagination.get("json_cursor_path")), cursor)
        return payload
    variables = payload.get("variables")
    if isinstance(variables, dict):
        variables["currentPage"] = int(variables.get("currentPage") or 1) + 1
        if profile.pagination_hints.get("page_size"):
            variables["pageSize"] = int(profile.pagination_hints.get("page_size") or variables.get("pageSize") or 50)
    return payload


def clone_json(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False))


def set_value_at_path(payload: Any, path: str, value: Any) -> bool:
    parts = [part for part in str(path or "").split(".") if part]
    if not parts:
        return False
    current = payload
    for part in parts[:-1]:
        if isinstance(current, dict):
            if part not in current or not isinstance(current[part], (dict, list)):
                current[part] = {}
            current = current[part]
        elif isinstance(current, list) and part.isdigit():
            index = int(part)
            if not (0 <= index < len(current)):
                return False
            current = current[index]
        else:
            return False
    last = parts[-1]
    if isinstance(current, dict):
        current[last] = value
        return True
    if isinstance(current, list) and last.isdigit():
        index = int(last)
        if 0 <= index < len(current):
            current[index] = value
            return True
    return False


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


# ---------------------------------------------------------------------------
# Profile long-run configuration, executor, and helpers
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ProfileLongRunConfig:
    """Configuration for a profile-driven long-running crawl."""

    run_id: str
    worker_id: str = "profile-longrun"
    batch_size: int = 20
    max_batches: int = 0
    lease_seconds: int = 300
    retry_failed: bool = False
    mode: str = "static"
    timeout_ms: int = 30000
    item_workers: int = 1
    category: str = ""
    sample_limit: int = 20
    output_report_path: str = ""
    supervision_mode: str = "off"
    adaptive_item_workers: bool = True
    min_item_workers: int = 1
    max_item_workers: int = 0

    def __post_init__(self) -> None:
        if not str(self.run_id or "").strip():
            raise ValueError("run_id is required")
        if self.batch_size < 1:
            raise ValueError("batch_size must be >= 1")
        if self.max_batches < 0:
            raise ValueError("max_batches must be >= 0")
        if self.lease_seconds < 0:
            raise ValueError("lease_seconds must be >= 0")
        if self.sample_limit < 0:
            raise ValueError("sample_limit must be >= 0")
        if self.item_workers < 1:
            raise ValueError("item_workers must be >= 1")
        if self.min_item_workers < 1:
            raise ValueError("min_item_workers must be >= 1")
        if self.max_item_workers < 0:
            raise ValueError("max_item_workers must be >= 0")
        if self.max_item_workers and self.max_item_workers < self.min_item_workers:
            raise ValueError("max_item_workers must be >= min_item_workers")
        mode = str(self.supervision_mode or "off").strip().lower()
        if mode not in {"off", "observe", "managed"}:
            raise ValueError("supervision_mode must be off, observe, or managed")


@dataclass
class ProfileLongRunResult:
    """Serializable result for a profile long-run pass."""

    accepted: bool
    run_id: str
    profile_name: str
    status: str
    runner_summary: BatchRunnerSummary
    frontier_stats: dict[str, int]
    product_stats: dict[str, Any]
    quality_summary: dict[str, Any]
    report: dict[str, Any]
    checkpoint_latest: dict[str, Any] | None = None
    sample_records: list[dict[str, Any]] = field(default_factory=list)
    failures: list[dict[str, Any]] = field(default_factory=list)
    backpressure: dict[str, Any] | None = None
    diagnostics: dict[str, Any] | None = None
    coverage_report: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "accepted": self.accepted,
            "run_id": self.run_id,
            "profile_name": self.profile_name,
            "status": self.status,
            "runner_summary": self.runner_summary.as_dict(),
            "frontier_stats": dict(self.frontier_stats),
            "product_stats": dict(self.product_stats),
            "quality_summary": dict(self.quality_summary),
            "checkpoint_latest": self.checkpoint_latest,
            "sample_records": list(self.sample_records),
            "failures": list(self.failures),
            "report": dict(self.report),
            "backpressure": self.backpressure,
            "diagnostics": self.diagnostics,
            "coverage_report": self.coverage_report,
        }


class ProfileLongRunExecutor:
    """Reusable executor for profile-driven ecommerce long runs."""

    def __init__(
        self,
        *,
        profile: SiteProfile,
        fetch_runtime: FetchRuntime | None = None,
        browser_runtime: BrowserRuntime | None = None,
        parser: ParserRuntime | None = None,
        frontier: URLFrontier | None = None,
        product_store: ProductStore | None = None,
        checkpoint_store: CheckpointStore | None = None,
        runtime_dir: str | Path | None = None,
    ) -> None:
        if fetch_runtime is None and browser_runtime is None:
            raise ValueError("fetch_runtime or browser_runtime is required")
        self.profile = profile
        self.fetch_runtime = fetch_runtime
        self.browser_runtime = browser_runtime
        self.parser = parser or NativeParserRuntime()
        self._temp_dir: tempfile.TemporaryDirectory[str] | None = None
        root: Path | None = None
        if runtime_dir or frontier is None or product_store is None or checkpoint_store is None:
            root = Path(runtime_dir) if runtime_dir else self._make_temp_dir()
            root.mkdir(parents=True, exist_ok=True)
        self.frontier = frontier or URLFrontier(root / "frontier.sqlite3")  # type: ignore[operator]
        self.product_store = product_store or ProductStore(root / "products.sqlite3")  # type: ignore[operator]
        self.checkpoint_store = checkpoint_store or CheckpointStore(root / "checkpoints.sqlite3")  # type: ignore[operator]

    def close(self) -> None:
        if self._temp_dir is not None:
            self._temp_dir.cleanup()
            self._temp_dir = None

    def run(self, config: ProfileLongRunConfig) -> ProfileLongRunResult:
        self.checkpoint_store.start_run(config.run_id, {"profile": self.profile.to_dict()})
        self.seed_frontier(config)
        effective_mode = effective_runtime_mode(self.profile, config.mode)

        callbacks = make_ecommerce_profile_callbacks(self.profile, run_id=config.run_id)
        processor = SpiderRuntimeProcessor(
            run_id=config.run_id,
            fetch_runtime=self.fetch_runtime,
            browser_runtime=self.browser_runtime,
            parser=self.parser,
            checkpoint_store=self.checkpoint_store,
            mode=effective_mode,
            timeout_ms=config.timeout_ms,
            selector_builder=callbacks.selector_builder,
            record_builder=callbacks.record_builder,
            link_builder=callbacks.link_builder,
        )
        effective_seed_kind = str(self.profile.crawl_preferences.get("seed_kind") or "").lower()
        backpressure_monitor = BackpressureMonitor(
            BackpressureConfig(latency_pause_ms=120000.0)
            if effective_seed_kind == "api"
            else BackpressureConfig(latency_pause_ms=60000.0, consecutive_slow_threshold=5)
        )
        runner_summary = BatchRunner(
            frontier=self.frontier,
            processor=processor,
            config=BatchRunnerConfig(
                run_id=config.run_id,
                worker_id=config.worker_id,
                batch_size=config.batch_size,
                max_batches=config.max_batches,
                lease_seconds=config.lease_seconds,
                retry_failed=config.retry_failed,
                item_workers=config.item_workers,
                adaptive_item_workers=config.adaptive_item_workers,
                min_item_workers=config.min_item_workers,
                max_item_workers=config.max_item_workers,
            ),
            checkpoint=ProductRecordCheckpoint(self.product_store),
            backpressure=backpressure_monitor,
            supervisor=RuleBasedBatchSupervisor()
            if config.supervision_mode in {"observe", "managed"}
            else None,
        ).run()

        frontier_stats = self.frontier.stats()
        if runner_summary.status in ("aborted", "paused"):
            status = runner_summary.status
        else:
            status = run_status_from_frontier(frontier_stats, runner_summary)
        self._save_batch_checkpoint(config, runner_summary, status=status)
        if status == "completed":
            self.checkpoint_store.mark_completed(config.run_id)
        elif status == "paused":
            self.checkpoint_store.mark_paused(config.run_id, "bounded profile long-run pass")

        records = self.product_store.list_records(config.run_id, limit=max(config.sample_limit, 1))
        failures = self.checkpoint_store.list_failures(config.run_id)
        quality_summary = profile_quality_summary(
            self.product_store.list_records(config.run_id, limit=10000),
            failed_urls=[str(item.get("url") or "") for item in failures if item.get("url")],
            pagination_stop_reason=infer_stop_reason(self.profile, frontier_stats, runner_summary),
            frontier_stats=frontier_stats,
            quality_policy=self.profile.quality_expectations,
        )
        coverage_report = build_coverage_report(
            _coverage_counters_from_run(
                self.profile,
                runner_summary,
                frontier_stats,
                failures,
                self.product_store.get_run_stats(config.run_id),
                quality_summary,
            ),
            target_records=int(self.profile.quality_expectations.get("min_items") or 0),
        )
        sample_records = [product_record_sample(record) for record in records[: config.sample_limit or 0]]

        # Compute diagnostics from backpressure signals + item errors + frontier
        bp_signals = backpressure_monitor.current_signals()
        bottlenecks = classify_bottlenecks(
            bp_signals,
            item_errors=runner_summary.item_errors,
            frontier_stats=frontier_stats,
        )
        recommendation = recommendation_text(bp_signals, bottlenecks)
        diagnostics = {
            "bottlenecks": bottlenecks,
            "recommendation": recommendation,
            "backpressure_signals": bp_signals.as_dict(),
            "supervision": build_supervision_diagnostics(runner_summary),
            "coverage_report": coverage_report.to_dict(),
            "throughput": {
                "adaptive_item_workers": bool(config.adaptive_item_workers),
                "initial_workers": int(config.item_workers),
                "min_workers": int(config.min_item_workers),
                "max_workers": int(config.max_item_workers or config.item_workers * 2),
                "worker_history": list(runner_summary.worker_history),
                "batch_history": list(runner_summary.batch_history[-50:]),
            },
        }

        report = build_profile_run_report(
            profile_name=self.profile.name,
            run_id=config.run_id,
            runner_summary=runner_summary,
            quality_summary=quality_summary,
            sample_records=sample_records,
            failures=failures,
            runtime_backend=runtime_backend_name(self.fetch_runtime, self.browser_runtime, effective_mode),
            parser_backend=getattr(self.parser, "name", type(self.parser).__name__),
            stop_reason=quality_summary.get("pagination_stop_reason", ""),
            target=first_seed_url(self.profile),
            backpressure=runner_summary.backpressure,
            diagnostics=diagnostics,
        )
        if config.output_report_path:
            write_report(config.output_report_path, report)
        return ProfileLongRunResult(
            accepted=is_accepted_profile_run(status, quality_summary, self.product_store.get_run_stats(config.run_id)),
            run_id=config.run_id,
            profile_name=self.profile.name,
            status=status,
            runner_summary=runner_summary,
            frontier_stats=frontier_stats,
            product_stats=self.product_store.get_run_stats(config.run_id),
            quality_summary=quality_summary,
            report=report,
            checkpoint_latest=self.checkpoint_store.load_latest(config.run_id),
            sample_records=sample_records,
            failures=failures,
            backpressure=runner_summary.backpressure,
            diagnostics=diagnostics,
            coverage_report=coverage_report.to_dict(),
        )

    def seed_frontier(self, config: ProfileLongRunConfig) -> dict[str, int]:
        requests = initial_requests_from_profile(
            self.profile,
            run_id=config.run_id,
            category=config.category,
        )
        totals = {"added": 0, "skipped": 0, "invalid": 0}
        for request in requests:
            added = self.frontier.add_urls(
                [request.url],
                priority=request.priority,
                kind=request.kind,
                depth=request.depth,
                parent_url=request.parent_url,
                payload=frontier_payload_from_request(request),
            )
            for key in totals:
                totals[key] += int(added.get(key, 0))
        return totals

    def _save_batch_checkpoint(
        self,
        config: ProfileLongRunConfig,
        summary: BatchRunnerSummary,
        *,
        status: str,
    ) -> None:
        spider_summary = SpiderRunSummary(
            run_id=config.run_id,
            status=status,
            batches=summary.batches,
            claimed=summary.claimed,
            succeeded=summary.succeeded,
            failed=summary.failed,
            retried=summary.retried,
            records_saved=summary.records_saved,
            discovered_urls=summary.discovered_urls,
            checkpoint_errors=summary.checkpoint_errors,
            frontier_stats=dict(summary.frontier_stats),
        )
        self.checkpoint_store.save_batch_checkpoint(
            run_id=config.run_id,
            batch_id=f"{config.worker_id}-pass-{summary.batches}",
            frontier_items=[],
            summary=spider_summary,
            events=[
                make_spider_event(
                    "checkpoint_saved",
                    "profile long-run checkpoint saved",
                    worker_id=config.worker_id,
                    status=status,
                    claimed=summary.claimed,
                    records_saved=summary.records_saved,
                )
            ],
        )

    def _make_temp_dir(self) -> Path:
        self._temp_dir = tempfile.TemporaryDirectory(prefix="clm_profile_longrun_")
        return Path(self._temp_dir.name)


def run_profile_longrun(
    *,
    profile: SiteProfile,
    config: ProfileLongRunConfig,
    fetch_runtime: FetchRuntime | None = None,
    browser_runtime: BrowserRuntime | None = None,
    parser: ParserRuntime | None = None,
    frontier: URLFrontier | None = None,
    product_store: ProductStore | None = None,
    checkpoint_store: CheckpointStore | None = None,
    runtime_dir: str | Path | None = None,
) -> ProfileLongRunResult:
    executor = ProfileLongRunExecutor(
        profile=profile,
        fetch_runtime=fetch_runtime,
        browser_runtime=browser_runtime,
        parser=parser,
        frontier=frontier,
        product_store=product_store,
        checkpoint_store=checkpoint_store,
        runtime_dir=runtime_dir,
    )
    try:
        return executor.run(config)
    finally:
        if runtime_dir is None and frontier is None and product_store is None and checkpoint_store is None:
            executor.close()


def _coverage_counters_from_run(
    profile: SiteProfile,
    runner_summary: BatchRunnerSummary,
    frontier_stats: dict[str, int],
    failures: list[dict[str, Any]],
    product_stats: dict[str, Any],
    quality_summary: dict[str, Any],
) -> CoverageCounters:
    failure_buckets = dict(runner_summary.frontier_stats or {})
    blocked = int(runner_summary.frontier_stats.get("failed", 0) or 0)
    records_saved = int(product_stats.get("total") or runner_summary.records_saved or 0)
    discovered_urls = int(frontier_stats.get("done", 0) or 0) + int(frontier_stats.get("queued", 0) or 0)
    fetched_success = int(runner_summary.succeeded or 0)
    attempted_fetches = int(runner_summary.claimed or 0)
    fetch_failed = int(runner_summary.failed or 0)
    rendered = max(fetched_success - fetch_failed, 0)
    parsed_records = int(quality_summary.get("total_records") or records_saved or 0)
    quality_passed = int(quality_summary.get("quality_gate", {}).get("passed_records") or parsed_records)
    if quality_passed <= 0 and parsed_records > 0:
        quality_passed = parsed_records
    exported_unique = records_saved
    duplicate_dropped = int(quality_summary.get("duplicate_count") or 0)
    missing_required_fields = 0
    field_completeness = quality_summary.get("field_completeness") if isinstance(quality_summary.get("field_completeness"), dict) else {}
    for field in profile.target_fields or []:
        if float(field_completeness.get(field, 0.0) or 0.0) < 0.8:
            missing_required_fields += 1
    stale_or_invalid_pages = sum(1 for item in failures if str(item.get("bucket") or "").lower() in {"invalid_page", "stale_page"})
    return CoverageCounters(
        estimated_inventory=max(int(profile.quality_expectations.get("min_items") or 0), discovered_urls, records_saved),
        discovered_urls=discovered_urls,
        attempted_fetches=attempted_fetches,
        time_budget_exhausted=bool(frontier_stats.get("running") or frontier_stats.get("queued")),
        fetched_success=fetched_success,
        blocked_or_challenged=blocked,
        fetch_failed=fetch_failed,
        render_attempted=attempted_fetches,
        render_success=rendered,
        render_failed=max(attempted_fetches - rendered, 0),
        parsed_records=parsed_records,
        quality_passed=quality_passed,
        quality_failed=max(parsed_records - quality_passed, 0),
        exported_unique=exported_unique,
        duplicate_dropped=duplicate_dropped,
        stale_or_invalid_pages=stale_or_invalid_pages,
        missing_required_fields=missing_required_fields,
        catalog_exhausted=bool(frontier_stats.get("queued", 0) == 0 and frontier_stats.get("running", 0) == 0),
    )


def effective_runtime_mode(profile: SiteProfile, configured_mode: str) -> str:
    mode = str(configured_mode or "static").strip().lower()
    if mode in {"dynamic", "protected"}:
        return mode
    access = profile.access_config if isinstance(profile.access_config, dict) else {}
    profile_mode = str(access.get("mode") or access.get("runtime_mode") or "").strip().lower()
    if profile_mode in {"browser", "playwright"}:
        return "dynamic"
    if profile_mode in {"dynamic", "protected"}:
        return profile_mode
    return "static"


def run_multi_profile_longrun(
    jobs: dict[str, dict[str, Any]],
    *,
    max_sites: int = 5,
    fetch_runtime_factory: Any = None,
    parser_factory: Any = None,
) -> MultiSiteRunSummary:
    """Run up to five profile long-runs concurrently.

    Each job payload accepts:
    - profile or profile_path
    - config or ProfileLongRunConfig kwargs
    - runtime_dir

    Runtime instances are created per site by default so HTTP sessions,
    cookies, and future browser contexts do not leak across domains.
    """
    if fetch_runtime_factory is None:
        from autonomous_crawler.runtime import NativeFetchRuntime

        def fetch_runtime_factory() -> NativeFetchRuntime:
            return NativeFetchRuntime(reuse_httpx_client=True)

    def make_job(name: str, payload: dict[str, Any]):
        def _run() -> dict[str, Any]:
            profile = _profile_from_job_payload(payload)
            config = _config_from_job_payload(name, payload)
            fetch_runtime = fetch_runtime_factory()
            parser = parser_factory() if parser_factory is not None else None
            try:
                result = run_profile_longrun(
                    profile=profile,
                    config=config,
                    fetch_runtime=fetch_runtime,
                    parser=parser,
                    runtime_dir=payload.get("runtime_dir") or None,
                )
                return result.to_dict()
            finally:
                close = getattr(fetch_runtime, "close", None)
                if callable(close):
                    close()

        return _run

    site_jobs = {str(name): make_job(str(name), dict(payload or {})) for name, payload in jobs.items()}
    return MultiSiteRunner(site_jobs, MultiSiteRunnerConfig(max_sites=max_sites)).run()


def _profile_from_job_payload(payload: dict[str, Any]) -> SiteProfile:
    profile_payload = payload.get("profile")
    if profile_payload is not None:
        if isinstance(profile_payload, SiteProfile):
            return profile_payload
        if isinstance(profile_payload, dict):
            return SiteProfile.from_dict(profile_payload)
        raise ValueError("profile must be a SiteProfile or dict")
    profile_path = str(payload.get("profile_path") or "").strip()
    if profile_path:
        return SiteProfile.load(profile_path)
    raise ValueError("profile or profile_path is required")


def _config_from_job_payload(name: str, payload: dict[str, Any]) -> ProfileLongRunConfig:
    raw = payload.get("config")
    if isinstance(raw, ProfileLongRunConfig):
        return raw
    config_payload = dict(raw or {})
    for key in (
        "run_id",
        "worker_id",
        "batch_size",
        "max_batches",
        "lease_seconds",
        "retry_failed",
        "mode",
        "timeout_ms",
        "item_workers",
        "adaptive_item_workers",
        "min_item_workers",
        "max_item_workers",
        "category",
        "sample_limit",
        "output_report_path",
    ):
        if key in payload and key not in config_payload:
            config_payload[key] = payload[key]
    if not str(config_payload.get("run_id") or "").strip():
        config_payload["run_id"] = f"profile-{name}"
    if not str(config_payload.get("worker_id") or "").strip():
        config_payload["worker_id"] = f"multi-profile-{name}"
    return ProfileLongRunConfig(**config_payload)


def frontier_payload_from_request(request: CrawlRequestEnvelope) -> dict[str, Any]:
    return {
        "request_id": request.request_id,
        "method": request.method,
        "priority": request.priority,
        "kind": request.kind,
        "depth": request.depth,
        "parent_url": request.parent_url,
        "session_id": request.session_id,
        "session_profile_id": request.session_profile_id,
        "headers": dict(request.headers),
        "cookies": dict(request.cookies),
        "params": dict(request.params),
        "data": request.data,
        "json": request.json,
        "meta": dict(request.meta),
        "dont_filter": request.dont_filter,
        "retry_count": request.retry_count,
        "max_retries": request.max_retries,
        "fingerprint": request.fingerprint,
    }


def run_status_from_frontier(
    frontier_stats: dict[str, int],
    summary: BatchRunnerSummary,
) -> str:
    if frontier_stats.get("queued") or frontier_stats.get("running"):
        return "paused"
    if summary.failed or frontier_stats.get("failed"):
        return "partial"
    return "completed"


def infer_stop_reason(
    profile: SiteProfile,
    frontier_stats: dict[str, int],
    summary: BatchRunnerSummary,
) -> str:
    if frontier_stats.get("queued") or frontier_stats.get("running"):
        return "bounded_pass_paused"
    if frontier_stats.get("failed"):
        return "frontier_failed_items"
    if summary.discovered_urls:
        return "frontier_exhausted"
    return infer_pagination_stop_reason(profile, last_item_count=summary.records_saved, next_request_count=0)


def build_supervision_diagnostics(summary: BatchRunnerSummary) -> dict[str, Any]:
    events = list(summary.supervision_events or [])
    action_counts: dict[str, int] = {}
    highest = "info"
    for event in events:
        action = str(event.get("action") or "unknown")
        action_counts[action] = action_counts.get(action, 0) + 1
        severity = str(event.get("severity") or "info")
        if severity == "critical":
            highest = "critical"
        elif severity == "warning" and highest != "critical":
            highest = "warning"
    last = events[-1] if events else {}
    recommended_next_action = ""
    if last:
        action = str(last.get("action") or "")
        if action in {"pause", "abort", "repair_after_run"}:
            recommended_next_action = "ai_rerun"
        elif action == "slow_down":
            recommended_next_action = "reduce_concurrency"
    return {
        "enabled": bool(events),
        "event_count": len(events),
        "action_counts": action_counts,
        "highest_severity": highest,
        "last_event": last,
        "recommended_next_action": recommended_next_action,
    }


def product_record_sample(record: ProductRecord) -> dict[str, Any]:
    return {
        "title": record.title,
        "highest_price": record.highest_price,
        "currency": record.currency,
        "colors": list(record.colors),
        "sizes": list(record.sizes),
        "description": record.description,
        "image_urls": list(record.image_urls),
        "category": record.category,
        "canonical_url": record.canonical_url,
        "dedupe_key": record.dedupe_key,
    }


def runtime_backend_name(
    fetch_runtime: FetchRuntime | None,
    browser_runtime: BrowserRuntime | None,
    mode: str,
) -> str:
    if str(mode or "").lower() in {"dynamic", "protected"} and browser_runtime is not None:
        return getattr(browser_runtime, "name", type(browser_runtime).__name__)
    if fetch_runtime is not None:
        return getattr(fetch_runtime, "name", type(fetch_runtime).__name__)
    if browser_runtime is not None:
        return getattr(browser_runtime, "name", type(browser_runtime).__name__)
    return ""


def is_accepted_profile_run(
    status: str,
    quality_summary: dict[str, Any],
    product_stats: dict[str, Any],
) -> bool:
    if status == "failed":
        return False
    if int(product_stats.get("total") or 0) <= 0:
        return False
    gate = quality_summary.get("quality_gate") if isinstance(quality_summary.get("quality_gate"), dict) else {}
    return not bool(gate.get("should_fail"))


def first_seed_url(profile: SiteProfile) -> str:
    endpoint = str(profile.api_hints.get("endpoint") or "").strip()
    if endpoint:
        return endpoint
    seed_urls = profile.crawl_preferences.get("seed_urls") or profile.constraints.get("seed_urls") or []
    return str(seed_urls[0]) if seed_urls else ""


def write_report(path: str | Path, report: dict[str, Any]) -> None:
    import json

    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
