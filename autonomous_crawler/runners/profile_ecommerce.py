"""Profile-driven ecommerce runner helpers.

This module translates explicit `SiteProfile` data into the callback hooks used
by `SpiderRuntimeProcessor`. It stays site-agnostic: selectors, link rules, and
quality expectations must come from the supplied profile.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

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
        if request.kind != "detail":
            return []
        fields = selector_result_values(selector_results)
        title = first_text(fields.get("title"))
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
            highest_price=parse_price(first_text(fields.get("highest_price") or fields.get("price"))),
            currency=str(self.profile.quality_expectations.get("currency") or ""),
            colors=clean_list(fields.get("colors") or fields.get("color")),
            sizes=clean_list(fields.get("sizes") or fields.get("size")),
            description=first_text(fields.get("description")),
            image_urls=absolute_urls(clean_list(fields.get("image_urls") or fields.get("image")), base_url=url),
            category=category,
            mode="profile-driven",
            raw_json={
                "profile": self.profile.name,
                "request_kind": request.kind,
                "selector_fields": fields,
            },
        )
        return [record]

    def link_builder(
        self,
        request: CrawlRequestEnvelope,
        response: RuntimeResponse,
    ) -> list[CrawlRequestEnvelope]:
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
        return result.requests


def make_ecommerce_profile_callbacks(profile: SiteProfile, *, run_id: str) -> EcommerceProfileCallbacks:
    return EcommerceProfileCallbacks(profile=profile, run_id=run_id)


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
    from urllib.parse import urljoin

    result: list[str] = []
    for value in values:
        joined = urljoin(base_url, value)
        parsed = urlparse(joined)
        if parsed.scheme in {"http", "https"} and parsed.netloc:
            result.append(joined)
    return result
