"""CLM-native link discovery helper.

SCRAPLING-ABSORB-3D absorbs the practical LinkExtractor ideas into a
profile-driven CLM helper: allow/deny patterns, domain filters, restricted
scopes, ignored extensions, canonicalization, URL classification, and drop
events.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any
from xml.etree import ElementTree
from urllib.parse import urldefrag, urljoin, urlparse, urlunparse

from lxml import html as lxml_html

from autonomous_crawler.runners.spider_models import CrawlRequestEnvelope
from autonomous_crawler.runtime import RuntimeEvent


DEFAULT_DENY_EXTENSIONS = (
    ".7z", ".avi", ".bmp", ".css", ".csv", ".doc", ".docx", ".gif",
    ".gz", ".ico", ".jpeg", ".jpg", ".js", ".mp3", ".mp4",
    ".mpeg", ".pdf", ".png", ".rar", ".svg", ".tar", ".webp", ".xls",
    ".xlsx", ".zip",
)


@dataclass(frozen=True)
class LinkDiscoveryRule:
    allow: tuple[str, ...] = ()
    deny: tuple[str, ...] = ()
    allow_domains: tuple[str, ...] = ()
    deny_domains: tuple[str, ...] = ()
    restrict_css: tuple[str, ...] = ()
    restrict_xpath: tuple[str, ...] = ()
    tags: tuple[str, ...] = ("a", "area")
    attrs: tuple[str, ...] = ("href",)
    deny_extensions: tuple[str, ...] = DEFAULT_DENY_EXTENSIONS
    keep_fragment: bool = False
    classify: dict[str, str] = field(default_factory=dict)
    default_kind: str = "page"
    priority: int = 0
    max_links: int = 0


@dataclass
class LinkDiscoveryResult:
    requests: list[CrawlRequestEnvelope] = field(default_factory=list)
    events: list[RuntimeEvent] = field(default_factory=list)
    dropped: dict[str, int] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "requests": [request.to_safe_dict() for request in self.requests],
            "events": [event.to_dict() for event in self.events],
            "dropped": dict(self.dropped),
        }


class LinkDiscoveryHelper:
    """Extract and classify links from HTML according to profile rules."""

    def extract(
        self,
        html: str,
        *,
        base_url: str,
        run_id: str,
        rules: LinkDiscoveryRule | None = None,
        parent_request: CrawlRequestEnvelope | None = None,
    ) -> LinkDiscoveryResult:
        rules = rules or LinkDiscoveryRule()
        result = LinkDiscoveryResult()
        seen: set[str] = set()
        nodes = _restricted_nodes(html, rules)
        base_domain = _domain(base_url)
        parent_depth = parent_request.depth if parent_request else 0

        for node in nodes:
            for tag in rules.tags:
                for element in node.iter(tag):
                    for attr in rules.attrs:
                        raw_url = str(element.get(attr) or "").strip()
                        if not raw_url:
                            continue
                        normalized = canonicalize_discovered_url(
                            raw_url,
                            base_url=base_url,
                            keep_fragment=rules.keep_fragment,
                        )
                        if not normalized:
                            _record_drop(result, "invalid")
                            continue
                        reason = self.drop_reason(normalized, rules=rules, base_domain=base_domain)
                        if reason:
                            _record_drop(result, reason)
                            result.events.append(RuntimeEvent(
                                type="spider.link_dropped",
                                message="link dropped",
                                data={"url": normalized, "reason": reason},
                            ))
                            continue
                        if normalized in seen:
                            _record_drop(result, "duplicate")
                            continue
                        seen.add(normalized)
                        kind = self.classify_url(normalized, rules=rules)
                        result.requests.append(CrawlRequestEnvelope(
                            run_id=run_id,
                            url=normalized,
                            priority=rules.priority,
                            kind=kind,
                            depth=parent_depth + 1,
                            parent_url=parent_request.url if parent_request else base_url,
                            meta={"discovered_by": "link_discovery"},
                        ))
                        if rules.max_links and len(result.requests) >= rules.max_links:
                            result.events.append(RuntimeEvent(
                                type="spider.links_discovered",
                                message="link discovery capped",
                                data={"count": len(result.requests), "max_links": rules.max_links},
                            ))
                            return result

        result.events.append(RuntimeEvent(
            type="spider.links_discovered",
            message="links discovered",
            data={"count": len(result.requests), "dropped": dict(result.dropped)},
        ))
        return result

    def matches(self, url: str, rules: LinkDiscoveryRule | None = None, *, base_domain: str = "") -> bool:
        rules = rules or LinkDiscoveryRule()
        return not self.drop_reason(url, rules=rules, base_domain=base_domain)

    def drop_reason(self, url: str, *, rules: LinkDiscoveryRule, base_domain: str = "") -> str:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return "invalid"
        domain = parsed.netloc.lower()
        if rules.allow_domains and not _domain_allowed(domain, rules.allow_domains):
            return "offsite"
        if not rules.allow_domains and base_domain and not _same_or_subdomain(domain, base_domain):
            return "offsite"
        if rules.deny_domains and _domain_allowed(domain, rules.deny_domains):
            return "denied_domain"
        path = parsed.path.lower()
        if rules.deny_extensions and path.endswith(tuple(ext.lower() for ext in rules.deny_extensions)):
            return "ignored_extension"
        if rules.deny and _matches_any(url, rules.deny):
            return "denied_pattern"
        if rules.allow and not _matches_any(url, rules.allow):
            return "not_allowed_pattern"
        return ""

    def classify_url(self, url: str, rules: LinkDiscoveryRule | None = None) -> str:
        rules = rules or LinkDiscoveryRule()
        for kind, pattern in rules.classify.items():
            try:
                if re.search(pattern, url):
                    return str(kind)
            except re.error:
                continue
        path = urlparse(url).path.lower()
        if "/api/" in path or path.endswith(".json"):
            return "api"
        if any(token in path for token in ("/product/", "/products/", "/p/")):
            return "detail"
        if any(token in path for token in ("/category/", "/collections/", "/c/")):
            return "category"
        if any(token in path for token in ("/search", "/list", "/catalog")):
            return "list"
        return rules.default_kind


@dataclass(frozen=True)
class SitemapDiscoveryRule:
    allow_domains: tuple[str, ...] = ()
    deny_domains: tuple[str, ...] = ()
    keep_fragment: bool = False
    default_kind: str = "page"
    priority: int = 0
    max_urls: int = 0


@dataclass
class SitemapDiscoveryResult:
    requests: list[CrawlRequestEnvelope] = field(default_factory=list)
    sitemap_urls: list[str] = field(default_factory=list)
    events: list[RuntimeEvent] = field(default_factory=list)
    dropped: dict[str, int] = field(default_factory=dict)
    error: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "requests": [request.to_safe_dict() for request in self.requests],
            "sitemap_urls": list(self.sitemap_urls),
            "events": [event.to_dict() for event in self.events],
            "dropped": dict(self.dropped),
            "error": self.error,
        }


class SitemapDiscoveryHelper:
    """Parse local sitemap XML into CLM crawl requests.

    The helper is intentionally network-free. Callers provide sitemap XML text
    fetched by an existing runtime, fixture, or profile loader.
    """

    def parse(
        self,
        xml_text: str,
        *,
        sitemap_url: str,
        run_id: str,
        rules: SitemapDiscoveryRule | None = None,
        parent_request: CrawlRequestEnvelope | None = None,
    ) -> SitemapDiscoveryResult:
        rules = rules or SitemapDiscoveryRule()
        result = SitemapDiscoveryResult()
        base_domain = _domain(sitemap_url)
        parent_depth = parent_request.depth if parent_request else 0
        seen: set[str] = set()

        try:
            root = ElementTree.fromstring(xml_text or "")
        except ElementTree.ParseError as exc:
            result.error = f"ParseError: {exc}"
            result.events.append(RuntimeEvent(
                type="spider.sitemap_parse_failed",
                message="sitemap XML parse failed",
                data={"sitemap_url": sitemap_url, "error": result.error},
            ))
            return result

        root_name = _local_name(root.tag)
        for loc in _iter_sitemap_locs(root):
            normalized = canonicalize_discovered_url(
                loc,
                base_url=sitemap_url,
                keep_fragment=rules.keep_fragment,
            )
            if not normalized:
                _record_sitemap_drop(result, "invalid")
                continue
            reason = _sitemap_drop_reason(normalized, rules=rules, base_domain=base_domain)
            if reason:
                _record_sitemap_drop(result, reason)
                result.events.append(RuntimeEvent(
                    type="spider.sitemap_url_dropped",
                    message="sitemap URL dropped",
                    data={"url": normalized, "reason": reason},
                ))
                continue
            if normalized in seen:
                _record_sitemap_drop(result, "duplicate")
                continue
            seen.add(normalized)
            if root_name == "sitemapindex":
                result.sitemap_urls.append(normalized)
            else:
                result.requests.append(CrawlRequestEnvelope(
                    run_id=run_id,
                    url=normalized,
                    priority=rules.priority,
                    kind=rules.default_kind,
                    depth=parent_depth + 1,
                    parent_url=parent_request.url if parent_request else sitemap_url,
                    meta={"discovered_by": "sitemap", "sitemap_url": sitemap_url},
                ))
            if rules.max_urls and len(result.requests) + len(result.sitemap_urls) >= rules.max_urls:
                result.events.append(RuntimeEvent(
                    type="spider.sitemap_discovered",
                    message="sitemap discovery capped",
                    data={
                        "sitemap_url": sitemap_url,
                        "request_count": len(result.requests),
                        "sitemap_count": len(result.sitemap_urls),
                        "max_urls": rules.max_urls,
                    },
                ))
                return result

        result.events.append(RuntimeEvent(
            type="spider.sitemap_discovered",
            message="sitemap parsed",
            data={
                "sitemap_url": sitemap_url,
                "kind": root_name,
                "request_count": len(result.requests),
                "sitemap_count": len(result.sitemap_urls),
                "dropped": dict(result.dropped),
            },
        ))
        return result


def canonicalize_discovered_url(raw_url: str, *, base_url: str, keep_fragment: bool = False) -> str:
    try:
        joined = urljoin(base_url, raw_url.strip())
        if not keep_fragment:
            joined = urldefrag(joined).url
        parsed = urlparse(joined)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return ""
        scheme = parsed.scheme.lower()
        netloc = parsed.netloc.lower()
        path = parsed.path or "/"
        return urlunparse((scheme, netloc, path, "", parsed.query, parsed.fragment if keep_fragment else ""))
    except Exception:
        return ""


def _restricted_nodes(html: str, rules: LinkDiscoveryRule) -> list[Any]:
    try:
        root = lxml_html.fromstring(html or "<html></html>")
    except Exception:
        root = lxml_html.fromstring("<html></html>")
    nodes: list[Any] = []
    for selector in rules.restrict_css:
        try:
            nodes.extend(root.cssselect(selector))
        except Exception:
            continue
    for selector in rules.restrict_xpath:
        try:
            nodes.extend(root.xpath(selector))
        except Exception:
            continue
    return nodes or [root]


def _matches_any(url: str, patterns: tuple[str, ...]) -> bool:
    for pattern in patterns:
        try:
            if re.search(pattern, url):
                return True
        except re.error:
            continue
    return False


def _domain_allowed(domain: str, allowed: tuple[str, ...]) -> bool:
    return any(_same_or_subdomain(domain, item.lower()) for item in allowed)


def _same_or_subdomain(domain: str, base_domain: str) -> bool:
    return domain == base_domain or domain.endswith("." + base_domain)


def _domain(url: str) -> str:
    return urlparse(url).netloc.lower()


def _record_drop(result: LinkDiscoveryResult, reason: str) -> None:
    result.dropped[reason] = result.dropped.get(reason, 0) + 1


def _record_sitemap_drop(result: SitemapDiscoveryResult, reason: str) -> None:
    result.dropped[reason] = result.dropped.get(reason, 0) + 1


def _iter_sitemap_locs(root: ElementTree.Element) -> list[str]:
    locs: list[str] = []
    for element in root.iter():
        if _local_name(element.tag) == "loc":
            text = (element.text or "").strip()
            if text:
                locs.append(text)
    return locs


def _local_name(tag: str) -> str:
    return str(tag).rsplit("}", 1)[-1].lower()


def _sitemap_drop_reason(url: str, *, rules: SitemapDiscoveryRule, base_domain: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return "invalid"
    domain = parsed.netloc.lower()
    allowed_domains = tuple(item.lower() for item in rules.allow_domains)
    if allowed_domains and domain not in allowed_domains:
        return "offsite"
    if not allowed_domains and base_domain and domain != base_domain:
        return "offsite"
    denied_domains = tuple(item.lower() for item in rules.deny_domains)
    if denied_domains and domain in denied_domains:
        return "denied_domain"
    return ""
