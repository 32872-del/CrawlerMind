"""CLM-native adaptive element matching helpers.

This module absorbs the useful parser-side ideas from Scrapling's adaptive
selection model into CLM-owned code: element signatures, structural similarity,
relocation when a selector misses, and repeated-node discovery from a seed
element.  It intentionally has no Scrapling import.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Any


DEFAULT_RELOCATE_THRESHOLD = 40.0
DEFAULT_SIMILAR_THRESHOLD = 0.2
DEFAULT_IGNORE_ATTRIBUTES = ("href", "src")


@dataclass(frozen=True)
class AdaptiveMatch:
    """A matched element with its structural similarity score."""

    element: Any
    score: float


@dataclass(frozen=True)
class ElementSignature:
    """Serializable structural fingerprint for an HTML element."""

    tag: str
    attributes: dict[str, str] = field(default_factory=dict)
    text: str = ""
    path: tuple[str, ...] = ()
    parent_name: str = ""
    parent_attribs: dict[str, str] = field(default_factory=dict)
    parent_text: str = ""
    siblings: tuple[str, ...] = ()
    children: tuple[str, ...] = ()

    @classmethod
    def from_element(cls, element: Any) -> "ElementSignature":
        parent = _parent(element)
        parent_attribs: dict[str, str] = {}
        parent_name = ""
        parent_text = ""
        siblings: tuple[str, ...] = ()
        if parent is not None:
            parent_name = _tag(parent)
            parent_attribs = _clean_attributes(parent)
            parent_text = _direct_text(parent)
            siblings = tuple(_tag(child) for child in _children(parent) if child is not element)

        children = tuple(_tag(child) for child in _children(element))
        return cls(
            tag=_tag(element),
            attributes=_clean_attributes(element),
            text=_direct_text(element),
            path=_element_path(element),
            parent_name=parent_name,
            parent_attribs=parent_attribs,
            parent_text=parent_text,
            siblings=siblings,
            children=children,
        )

    @classmethod
    def from_mapping(cls, payload: dict[str, Any]) -> "ElementSignature":
        return cls(
            tag=str(payload.get("tag") or ""),
            attributes=_string_dict(payload.get("attributes")),
            text=str(payload.get("text") or ""),
            path=_string_tuple(payload.get("path")),
            parent_name=str(payload.get("parent_name") or ""),
            parent_attribs=_string_dict(payload.get("parent_attribs")),
            parent_text=str(payload.get("parent_text") or ""),
            siblings=_string_tuple(payload.get("siblings")),
            children=_string_tuple(payload.get("children")),
        )

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "tag": self.tag,
            "attributes": dict(self.attributes),
            "text": self.text,
            "path": list(self.path),
        }
        if self.parent_name:
            result["parent_name"] = self.parent_name
            result["parent_attribs"] = dict(self.parent_attribs)
            result["parent_text"] = self.parent_text
        if self.siblings:
            result["siblings"] = list(self.siblings)
        if self.children:
            result["children"] = list(self.children)
        return result


def build_element_signature(element: Any) -> dict[str, Any]:
    """Return a serializable signature for an lxml element."""

    return ElementSignature.from_element(element).to_dict()


def similarity_score(original: ElementSignature | dict[str, Any], candidate: Any) -> float:
    """Return a Scrapling-style structural similarity percentage."""

    signature = _signature(original)
    data = ElementSignature.from_element(candidate)
    score = 0.0
    checks = 0

    score += 1.0 if signature.tag == data.tag else 0.0
    checks += 1

    if signature.text:
        score += SequenceMatcher(None, signature.text, data.text).ratio()
        checks += 1

    score += _dict_similarity(signature.attributes, data.attributes)
    checks += 1

    for attrib in ("class", "id", "href", "src"):
        if signature.attributes.get(attrib):
            score += SequenceMatcher(
                None,
                signature.attributes[attrib],
                data.attributes.get(attrib, ""),
            ).ratio()
            checks += 1

    score += SequenceMatcher(None, signature.path, data.path).ratio()
    checks += 1

    if signature.parent_name:
        if data.parent_name:
            score += SequenceMatcher(None, signature.parent_name, data.parent_name).ratio()
            checks += 1
            score += _dict_similarity(signature.parent_attribs, data.parent_attribs)
            checks += 1
            if signature.parent_text:
                score += SequenceMatcher(None, signature.parent_text, data.parent_text).ratio()
                checks += 1

    if signature.siblings:
        score += SequenceMatcher(None, signature.siblings, data.siblings).ratio()
        checks += 1

    if signature.children:
        score += SequenceMatcher(None, signature.children, data.children).ratio()
        checks += 1

    if not checks:
        return 0.0
    return round((score / checks) * 100, 2)


def relocate(
    root: Any,
    signature: ElementSignature | dict[str, Any],
    *,
    threshold: float = DEFAULT_RELOCATE_THRESHOLD,
    many: bool = True,
) -> list[AdaptiveMatch]:
    """Find the highest-scoring element(s) matching a saved signature."""

    original = _signature(signature)
    score_table: dict[float, list[Any]] = {}
    for candidate in _iter_elements(root):
        score = similarity_score(original, candidate)
        score_table.setdefault(score, []).append(candidate)

    if not score_table:
        return []

    highest = max(score_table)
    if highest < threshold:
        return []

    matches = [AdaptiveMatch(element=element, score=highest) for element in score_table[highest]]
    return matches if many else matches[:1]


def find_similar(
    element: Any,
    *,
    similarity_threshold: float = DEFAULT_SIMILAR_THRESHOLD,
    ignore_attributes: tuple[str, ...] = DEFAULT_IGNORE_ATTRIBUTES,
    match_text: bool = False,
) -> list[AdaptiveMatch]:
    """Find repeated elements similar to a seed element at the same depth."""

    root = _document_root(element)
    parent = _parent(element)
    grandparent = _parent(parent) if parent is not None else None
    target_depth = _depth(element)
    target_attrs = _filtered_attributes(element, ignore_attributes)
    path_tags = tuple(tag for tag in (_tag(grandparent), _tag(parent), _tag(element)) if tag)

    matches: list[AdaptiveMatch] = []
    for candidate in _iter_elements(root):
        if candidate is element:
            continue
        if _depth(candidate) != target_depth:
            continue
        if _candidate_path_tail(candidate, len(path_tags)) != path_tags:
            continue

        score = _alike_score(
            target_attrs,
            _filtered_attributes(candidate, ignore_attributes),
            _direct_text(element),
            _direct_text(candidate),
            match_text=match_text,
        )
        if score >= similarity_threshold:
            matches.append(AdaptiveMatch(element=candidate, score=round(score, 4)))

    return matches


def _signature(value: ElementSignature | dict[str, Any]) -> ElementSignature:
    if isinstance(value, ElementSignature):
        return value
    return ElementSignature.from_mapping(value if isinstance(value, dict) else {})


def _dict_similarity(first: dict[str, str], second: dict[str, str]) -> float:
    return (
        SequenceMatcher(None, tuple(first.keys()), tuple(second.keys())).ratio() * 0.5
        + SequenceMatcher(None, tuple(first.values()), tuple(second.values())).ratio() * 0.5
    )


def _alike_score(
    original_attrs: dict[str, str],
    candidate_attrs: dict[str, str],
    original_text: str,
    candidate_text: str,
    *,
    match_text: bool,
) -> float:
    score = 0.0
    checks = 0
    if original_attrs:
        for key, value in original_attrs.items():
            score += SequenceMatcher(None, value, candidate_attrs.get(key, "")).ratio()
            checks += 1
    elif not candidate_attrs:
        score += 1.0
        checks += 1

    if match_text:
        score += SequenceMatcher(None, _clean_spaces(original_text), _clean_spaces(candidate_text)).ratio()
        checks += 1

    if not checks:
        return 0.0
    return score / checks


def _clean_attributes(element: Any) -> dict[str, str]:
    try:
        return {
            str(key): str(value).strip()
            for key, value in dict(element.attrib).items()
            if value is not None and str(value).strip()
        }
    except Exception:
        return {}


def _filtered_attributes(element: Any, ignored: tuple[str, ...]) -> dict[str, str]:
    ignored_set = set(ignored)
    return {key: value for key, value in _clean_attributes(element).items() if key not in ignored_set}


def _string_dict(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    return {str(key): str(val) for key, val in value.items() if val is not None}


def _string_tuple(value: Any) -> tuple[str, ...]:
    if isinstance(value, str):
        return (value,)
    if not isinstance(value, (list, tuple)):
        return ()
    return tuple(str(item) for item in value if item is not None)


def _element_path(element: Any) -> tuple[str, ...]:
    path: list[str] = []
    current = element
    while current is not None:
        tag = _tag(current)
        if tag:
            path.append(tag)
        current = _parent(current)
    return tuple(reversed(path))


def _candidate_path_tail(element: Any, length: int) -> tuple[str, ...]:
    if length <= 0:
        return ()
    path = _element_path(element)
    return path[-length:]


def _document_root(element: Any) -> Any:
    current = element
    while _parent(current) is not None:
        current = _parent(current)
    return current


def _depth(element: Any) -> int:
    depth = 0
    current = _parent(element)
    while current is not None:
        depth += 1
        current = _parent(current)
    return depth


def _iter_elements(root: Any) -> list[Any]:
    try:
        return [node for node in root.iter() if isinstance(_tag(node), str) and _tag(node)]
    except Exception:
        return []


def _children(element: Any) -> list[Any]:
    try:
        return list(element.iterchildren())
    except Exception:
        return []


def _parent(element: Any) -> Any:
    if element is None:
        return None
    try:
        return element.getparent()
    except Exception:
        return None


def _tag(element: Any) -> str:
    try:
        tag = element.tag
    except Exception:
        return ""
    return tag if isinstance(tag, str) else ""


def _direct_text(element: Any) -> str:
    try:
        return (element.text or "").strip()
    except Exception:
        return ""


def _clean_spaces(value: str) -> str:
    return " ".join(str(value or "").split())
