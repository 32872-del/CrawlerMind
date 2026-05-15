"""Scrapling HTML parser runtime adapter.

Wraps Scrapling's ``Selector`` behind the CLM ``ParserRuntime`` protocol
so workflow layers never import Scrapling directly.
"""
from __future__ import annotations

from typing import Any

from .models import RuntimeSelectorRequest, RuntimeSelectorResult

_HAS_SCRAPLING = True
try:
    from scrapling import Selector
except ImportError:
    _HAS_SCRAPLING = False


class ScraplingParserRuntime:
    """``ParserRuntime`` adapter backed by Scrapling's ``Selector``."""

    name: str = "scrapling_parser"

    def parse(
        self,
        html: str,
        selectors: list[RuntimeSelectorRequest],
        *,
        url: str = "",
        selector_config: dict[str, object] | None = None,
    ) -> list[RuntimeSelectorResult]:
        if not _HAS_SCRAPLING:
            return [
                RuntimeSelectorResult(
                    name=s.name,
                    selector=s.selector,
                    selector_type=s.selector_type,
                    error="scrapling package is not installed",
                )
                for s in selectors
            ]

        try:
            root = Selector(content=html, url=url)
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

        results: list[RuntimeSelectorResult] = []
        for sel_req in selectors:
            results.append(self._extract_one(root, sel_req))
        return results

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_one(
        root: Any,
        req: RuntimeSelectorRequest,
    ) -> RuntimeSelectorResult:
        stype = req.selector_type
        selector = req.selector

        try:
            if stype == "css":
                return _extract_css(root, req)
            if stype == "xpath":
                return _extract_xpath(root, req)
            if stype == "text":
                return _extract_text(root, req)
            if stype == "regex":
                return _extract_regex(root, req)
        except Exception as exc:
            return RuntimeSelectorResult(
                name=req.name,
                selector=selector,
                selector_type=stype,
                error=f"{type(exc).__name__}: {exc}",
            )

        return RuntimeSelectorResult(
            name=req.name,
            selector=selector,
            selector_type=stype,
            error=f"unsupported selector_type: {stype}",
        )


# ------------------------------------------------------------------
# Selector-type helpers
# ------------------------------------------------------------------

def _extract_css(root: Any, req: RuntimeSelectorRequest) -> RuntimeSelectorResult:
    matched_elements = root.css(req.selector)
    return _collect_from_elements(matched_elements, req)


def _extract_xpath(root: Any, req: RuntimeSelectorRequest) -> RuntimeSelectorResult:
    matched_elements = root.xpath(req.selector)
    return _collect_from_elements(matched_elements, req)


def _extract_text(root: Any, req: RuntimeSelectorRequest) -> RuntimeSelectorResult:
    """Text-based extraction: find_by_text with partial, case-insensitive match."""
    try:
        matched_elements = root.find_by_text(
            req.selector,
            first_match=False,
            partial=True,
            case_sensitive=False,
            clean_match=True,
        )
    except Exception:
        matched_elements = []
    return _collect_from_elements(matched_elements, req)


def _extract_regex(root: Any, req: RuntimeSelectorRequest) -> RuntimeSelectorResult:
    """Regex extraction: apply regex to the full text of the document."""
    try:
        import re
        full_text = str(root.get_all_text())
        values = re.findall(req.selector, full_text)
        values = [str(m) for m in values]
    except Exception as exc:
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


def _collect_from_elements(
    elements: Any,
    req: RuntimeSelectorRequest,
) -> RuntimeSelectorResult:
    """Extract values from a list of Scrapling Selector elements."""
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
    """Get text content from a Scrapling Selector element."""
    try:
        return str(elem.get_all_text(separator=" ", strip=True))
    except Exception:
        try:
            return str(elem.text)
        except Exception:
            return ""


def _get_attr(elem: Any, attr: str) -> str:
    """Get an attribute value from a Scrapling Selector element."""
    try:
        attribs = elem.attrib
        if attr in attribs:
            return str(attribs[attr])
    except Exception:
        pass
    return ""
