"""CLM-native HTML parser runtime.

This module implements the parser runtime with lxml/cssselect and adds a
CLM-native adaptive recovery path inspired by Scrapling: when a selector miss
occurs, the runtime can relocate a previously captured element signature by
structural similarity.
"""
from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

from lxml import html

from autonomous_crawler.storage.selector_memory import SelectorMemoryStore

from .adaptive_parser import build_element_signature, relocate
from .models import RuntimeSelectorRequest, RuntimeSelectorResult

try:
    from cssselect import HTMLTranslator
except ImportError:  # pragma: no cover - cssselect is a hard dependency
    HTMLTranslator = None  # type: ignore[assignment,misc]


class NativeParserRuntime:
    """ParserRuntime implementation backed by lxml + cssselect."""

    name: str = "native_parser"

    def parse(
        self,
        html_text: str,
        selectors: list[RuntimeSelectorRequest],
        *,
        url: str = "",
        selector_config: dict[str, object] | None = None,
    ) -> list[RuntimeSelectorResult]:
        if not html_text:
            return [
                RuntimeSelectorResult(
                    name=s.name,
                    selector=s.selector,
                    selector_type=s.selector_type,
                    matched=0,
                )
                for s in selectors
            ]

        try:
            parser = html.HTMLParser(recover=True)
            root = html.fromstring(html_text, parser=parser)
        except Exception as exc:
            return [
                RuntimeSelectorResult(
                    name=s.name,
                    selector=s.selector,
                    selector_type=s.selector_type,
                    error=f"html_parse_error: {type(exc).__name__}: {exc}",
                )
                for s in selectors
            ]

        selector_config = selector_config or {}
        results: list[RuntimeSelectorResult] = []
        for sel_req in selectors:
            results.append(self._extract_one(root, sel_req, selector_config=selector_config, url=url))
        return results

    @staticmethod
    def _extract_one(
        root: Any,
        req: RuntimeSelectorRequest,
        *,
        selector_config: dict[str, object] | None = None,
        url: str = "",
    ) -> RuntimeSelectorResult:
        selector_config = selector_config or {}
        try:
            if req.selector_type == "css":
                return _extract_css(root, req, selector_config=selector_config, url=url)
            if req.selector_type == "xpath":
                return _extract_xpath(root, req, selector_config=selector_config, url=url)
            if req.selector_type == "text":
                return _extract_text(root, req)
            if req.selector_type == "regex":
                return _extract_regex(root, req)
        except Exception as exc:
            return RuntimeSelectorResult(
                name=req.name,
                selector=req.selector,
                selector_type=req.selector_type,
                error=f"{type(exc).__name__}: {exc}",
            )

        return RuntimeSelectorResult(
            name=req.name,
            selector=req.selector,
            selector_type=req.selector_type,
            error=f"unsupported selector_type: {req.selector_type}",
        )


# ======================================================================
# Selector-type helpers
# ======================================================================

def _extract_css(
    root: Any,
    req: RuntimeSelectorRequest,
    *,
    selector_config: dict[str, object] | None = None,
    url: str = "",
) -> RuntimeSelectorResult:
    selector_config = selector_config or {}
    if HTMLTranslator is None:
        return RuntimeSelectorResult(
            name=req.name,
            selector=req.selector,
            selector_type="css",
            error="cssselect package is not installed",
        )

    try:
        xpath_expr = HTMLTranslator().css_to_xpath(req.selector)
    except Exception as exc:
        return RuntimeSelectorResult(
            name=req.name,
            selector=req.selector,
            selector_type="css",
            error=f"css_to_xpath_error: {type(exc).__name__}: {exc}",
        )

    matched = root.xpath(xpath_expr)
    if not matched:
        return _adaptive_recover(root, req, selector_config=selector_config, url=url)
    _adaptive_auto_save(matched, req, selector_config=selector_config, url=url)
    return _collect_from_elements(matched, req)


def _extract_xpath(
    root: Any,
    req: RuntimeSelectorRequest,
    *,
    selector_config: dict[str, object] | None = None,
    url: str = "",
) -> RuntimeSelectorResult:
    selector_config = selector_config or {}
    try:
        matched = root.xpath(req.selector)
    except Exception as exc:
        return RuntimeSelectorResult(
            name=req.name,
            selector=req.selector,
            selector_type="xpath",
            error=f"xpath_error: {type(exc).__name__}: {exc}",
        )

    if matched and isinstance(matched[0], str):
        values = list(matched) if req.many else matched[:1]
        return RuntimeSelectorResult(
            name=req.name,
            values=values,
            selector=req.selector,
            selector_type="xpath",
            matched=len(values),
        )

    if not matched:
        return _adaptive_recover(root, req, selector_config=selector_config, url=url)
    _adaptive_auto_save(matched, req, selector_config=selector_config, url=url)
    return _collect_from_elements(matched, req)


def _extract_text(root: Any, req: RuntimeSelectorRequest) -> RuntimeSelectorResult:
    needle = req.selector.strip()
    if not needle:
        return RuntimeSelectorResult(
            name=req.name,
            selector=req.selector,
            selector_type="text",
            matched=0,
        )

    needle_lower = needle.lower()
    values: list[str] = []

    for elem in root.iter():
        direct_text = _direct_text(elem).strip()
        if not direct_text:
            continue
        if needle_lower in direct_text.lower():
            values.append(direct_text)
            if not req.many:
                break

    return RuntimeSelectorResult(
        name=req.name,
        values=values,
        selector=req.selector,
        selector_type="text",
        matched=len(values),
    )


def _extract_regex(root: Any, req: RuntimeSelectorRequest) -> RuntimeSelectorResult:
    try:
        full_text = _all_text(root)
        values = re.findall(req.selector, full_text)
        values = [str(m) for m in values]
    except re.error as exc:
        return RuntimeSelectorResult(
            name=req.name,
            selector=req.selector,
            selector_type="regex",
            error=f"regex_error: {type(exc).__name__}: {exc}",
        )

    if not req.many:
        values = values[:1]

    return RuntimeSelectorResult(
        name=req.name,
        values=values,
        selector=req.selector,
        selector_type="regex",
        matched=len(values),
    )


def _adaptive_recover(
    root: Any,
    req: RuntimeSelectorRequest,
    *,
    selector_config: dict[str, object],
    url: str = "",
) -> RuntimeSelectorResult:
    enabled = bool(
        req.signature
        or selector_config.get("adaptive_enabled")
        or selector_config.get("adaptive")
    )
    if not enabled:
        return RuntimeSelectorResult(
            name=req.name,
            selector=req.selector,
            selector_type=req.selector_type,
            matched=0,
        )

    signature = req.signature or _adaptive_signature_from_config(req, selector_config, url=url)
    if not signature:
        return RuntimeSelectorResult(
            name=req.name,
            selector=req.selector,
            selector_type=req.selector_type,
            matched=0,
        )

    threshold = float(selector_config.get("adaptive_threshold", 40.0) or 40.0)
    matches = relocate(root, signature, threshold=threshold, many=req.many)
    if not matches:
        return RuntimeSelectorResult(
            name=req.name,
            selector=req.selector,
            selector_type=req.selector_type,
            matched=0,
        )
    _adaptive_record_recovery(matches[0].score, req, selector_config=selector_config, url=url)

    values: list[str] = []
    for match in matches:
        value = _selector_value(match.element, req)
        if value:
            values.append(value)
        if not req.many and values:
            break

    return RuntimeSelectorResult(
        name=req.name,
        values=values,
        selector=req.selector,
        selector_type=req.selector_type,
        matched=len(values),
    )


def _adaptive_signature_from_config(
    req: RuntimeSelectorRequest,
    selector_config: dict[str, object],
    *,
    url: str = "",
) -> dict[str, object]:
    signatures = selector_config.get("adaptive_signatures")
    if isinstance(signatures, dict):
        candidate = signatures.get(req.name) or signatures.get(req.selector)
        if isinstance(candidate, dict):
            return candidate
    store = _selector_memory_store(selector_config)
    if store is not None:
        return store.load_signature(
            site_key=_adaptive_site_key(selector_config, url),
            name=req.name,
            selector=req.selector,
            selector_type=req.selector_type,
            attribute=req.attribute,
        )
    return {}


def _adaptive_auto_save(
    elements: list[Any],
    req: RuntimeSelectorRequest,
    *,
    selector_config: dict[str, object],
    url: str = "",
) -> None:
    if not elements:
        return
    if not (selector_config.get("adaptive_auto_save") or selector_config.get("adaptive_memory_path")):
        return
    store = _selector_memory_store(selector_config)
    if store is None:
        return
    try:
        signature = build_element_signature(elements[0])
        store.save_signature(
            site_key=_adaptive_site_key(selector_config, url),
            name=req.name,
            selector=req.selector,
            selector_type=req.selector_type,
            attribute=req.attribute,
            signature=signature,
        )
    except Exception:
        return


def _adaptive_record_recovery(
    score: float,
    req: RuntimeSelectorRequest,
    *,
    selector_config: dict[str, object],
    url: str = "",
) -> None:
    store = _selector_memory_store(selector_config)
    if store is None or not hasattr(store, "record_recovery"):
        return
    try:
        store.record_recovery(
            site_key=_adaptive_site_key(selector_config, url),
            name=req.name,
            selector=req.selector,
            selector_type=req.selector_type,
            attribute=req.attribute,
            score=score,
        )
    except Exception:
        return


def _selector_memory_store(selector_config: dict[str, object]) -> SelectorMemoryStore | None:
    configured = selector_config.get("adaptive_memory")
    if isinstance(configured, SelectorMemoryStore):
        return configured
    if configured is not None and hasattr(configured, "load_signature") and hasattr(configured, "save_signature"):
        return configured  # type: ignore[return-value]
    path = str(selector_config.get("adaptive_memory_path") or "").strip()
    if not path:
        return None
    try:
        return SelectorMemoryStore(path)
    except Exception:
        return None


def _adaptive_site_key(selector_config: dict[str, object], url: str) -> str:
    configured = str(
        selector_config.get("adaptive_site_key")
        or selector_config.get("site_key")
        or ""
    ).strip()
    if configured:
        return configured[:200]
    parsed = urlparse(url)
    if parsed.netloc:
        return parsed.netloc.lower()[:200]
    return "default"


def _selector_value(element: Any, req: RuntimeSelectorRequest) -> str:
    if req.attribute:
        return _get_attr(element, req.attribute)
    return _get_text(element)


# ======================================================================
# Element helpers
# ======================================================================

def _collect_from_elements(
    elements: list[Any],
    req: RuntimeSelectorRequest,
) -> RuntimeSelectorResult:
    values: list[str] = []
    attr = req.attribute

    for elem in elements:
        if attr:
            val = _get_attr(elem, attr)
        else:
            val = _get_text(elem)
        values.append(val)
        if not req.many:
            break

    return RuntimeSelectorResult(
        name=req.name,
        values=values,
        selector=req.selector,
        selector_type=req.selector_type,
        matched=len(values),
    )


def _get_text(elem: Any) -> str:
    try:
        return elem.text_content().strip()
    except Exception:
        return ""


def _get_attr(elem: Any, attr: str) -> str:
    try:
        val = elem.get(attr)
        if val is not None:
            return str(val)
    except Exception:
        pass
    return ""


def _direct_text(elem: Any) -> str:
    try:
        return (elem.text or "").strip()
    except Exception:
        return ""


def _all_text(elem: Any) -> str:
    try:
        parts = [t.strip() for t in elem.itertext() if t.strip()]
        return " ".join(parts)
    except Exception:
        try:
            return elem.text_content()
        except Exception:
            return ""
