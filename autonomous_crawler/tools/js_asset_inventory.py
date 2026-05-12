"""JS Asset Inventory and Signature Clue MVP.

Extracts script assets from HTML and analyzes JS text for suspicious keywords,
API endpoints, GraphQL strings, WebSocket URLs, and sourcemap references.
Generates a ranked "where to look next" report.

This module uses deterministic Python parsing and regex heuristics only.
No JS execution, no AST transform, no site-specific rules.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ScriptAsset:
    """A single <script> tag extracted from HTML."""
    url: str = ""
    inline_id: str = ""
    type_attr: str = ""
    is_module: bool = False
    is_nomodule: bool = False
    is_inline: bool = False
    size_estimate: int = 0
    sourcemap_hint: str = ""


@dataclass(frozen=True)
class KeywordHit:
    """A matched keyword inside JS text."""
    keyword: str
    category: str
    context_preview: str = ""


@dataclass
class JsAssetReport:
    """Ranked report for a single script asset."""
    asset: ScriptAsset
    score: int = 0
    reasons: list[str] = field(default_factory=list)
    endpoint_candidates: list[str] = field(default_factory=list)
    keyword_hits: list[KeywordHit] = field(default_factory=list)
    graphql_strings: list[str] = field(default_factory=list)
    websocket_urls: list[str] = field(default_factory=list)
    sourcemap_refs: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "asset": {
                "url": self.asset.url,
                "inline_id": self.asset.inline_id,
                "type_attr": self.asset.type_attr,
                "is_module": self.asset.is_module,
                "is_nomodule": self.asset.is_nomodule,
                "is_inline": self.asset.is_inline,
                "size_estimate": self.asset.size_estimate,
                "sourcemap_hint": self.asset.sourcemap_hint,
            },
            "score": self.score,
            "reasons": list(self.reasons),
            "endpoint_candidates": list(self.endpoint_candidates),
            "keyword_hits": [
                {"keyword": h.keyword, "category": h.category, "context_preview": h.context_preview}
                for h in self.keyword_hits
            ],
            "graphql_strings": list(self.graphql_strings),
            "websocket_urls": list(self.websocket_urls),
            "sourcemap_refs": list(self.sourcemap_refs),
        }


# ---------------------------------------------------------------------------
# Keyword definitions
# ---------------------------------------------------------------------------

SIGNATURE_KEYWORDS: tuple[tuple[str, str], ...] = (
    ("signature", "signature"),
    ("sign", "signature"),
    ("signed", "signature"),
    ("hmac", "signature"),
    ("sha256", "signature"),
    ("sha1", "signature"),
    ("md5", "signature"),
    ("encrypt", "encryption"),
    ("decrypt", "encryption"),
    ("encrypted", "encryption"),
    ("crypto", "encryption"),
    ("token", "token"),
    ("nonce", "token"),
    ("wbi", "token"),
    ("x-bogus", "token"),
    ("xbogus", "token"),
    ("verify", "verification"),
    ("captcha", "challenge"),
    ("recaptcha", "challenge"),
    ("hcaptcha", "challenge"),
    ("turnstile", "challenge"),
    ("geetest", "challenge"),
    ("anti-bot", "anti_bot"),
    ("antibot", "anti_bot"),
    ("fingerprint", "fingerprint"),
    ("canvas fingerprint", "fingerprint"),
    ("webgl fingerprint", "fingerprint"),
    ("webpack", "bundler"),
    ("__webpack_require__", "bundler"),
    ("vite", "bundler"),
    ("__vite_ssr_import__", "bundler"),
    ("define", "bundler"),
)

SIGNATURE_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\b\w*[Ss]ign(?:ature|ed)?(?:\w*)\b"), "signature"),
    (re.compile(r"\b\w*[Ee]ncrypt(?:ion|ed)?(?:\w*)\b"), "encryption"),
    (re.compile(r"\b\w*[Dd]ecrypt(?:ion|ed)?(?:\w*)\b"), "encryption"),
    (re.compile(r"\b\w*[Tt]oken(?:\w*)\b"), "token"),
    (re.compile(r"\b\w*[Nn]once(?:\w*)\b"), "token"),
    (re.compile(r"\b[Cc]rypto\w*\b"), "encryption"),
    (re.compile(r"\b[Hh]mac\w*\b"), "signature"),
    (re.compile(r"\b[Ss][Hh][Aa](?:256|1|512)\b"), "signature"),
    (re.compile(r"\b[Mm][Dd]5\b"), "signature"),
    (re.compile(r"\b[Cc]aptcha\w*\b"), "challenge"),
    (re.compile(r"\b[Rr]e[Cc]aptcha\b"), "challenge"),
    (re.compile(r"\b[Hh][Cc]aptcha\b"), "challenge"),
    (re.compile(r"\b[Tt]urnstile\b"), "challenge"),
    (re.compile(r"\b[Gg]ee[Tt]est\b"), "challenge"),
    (re.compile(r"\bwbi\b", re.I), "token"),
    (re.compile(r"\bx-?bogus\b", re.I), "token"),
    (re.compile(r"\bverify\w*\b", re.I), "verification"),
    (re.compile(r"\banti-?bot\w*\b", re.I), "anti_bot"),
    (re.compile(r"\bfingerprint\w*\b", re.I), "fingerprint"),
    (re.compile(r"\b__webpack_require__\b"), "bundler"),
    (re.compile(r"\b__vite_ssr_import__\b"), "bundler"),
)


# ---------------------------------------------------------------------------
# Regex patterns for endpoints, GraphQL, WebSocket, sourcemaps
# ---------------------------------------------------------------------------

_API_ENDPOINT_RE = re.compile(
    r"""(?:"|')([^"']*(?:/api/|/v\d/|graphql|/ajax|/rest|/service)[^"']{0,200})(?:"|')""",
    re.IGNORECASE,
)

_GRAPHQL_STRING_RE = re.compile(
    r"""(?:"|')((?:query|mutation|subscription)\s+\w+[^"']{0,500})(?:"|')""",
    re.IGNORECASE,
)

_GRAPHQL_OP_RE = re.compile(
    r"""(?:"|')(\{[^"']*(?:query|mutation)[^"']{0,500}\})(?:"|')""",
    re.IGNORECASE,
)

_WEBSOCKET_RE = re.compile(
    r"""(?:"|')(wss?://[^"']+)(?:"|')""",
    re.IGNORECASE,
)

_SOURCEMAP_RE = re.compile(
    r"//#\s*sourceMappingURL\s*=\s*(\S+)",
    re.IGNORECASE,
)

_SOURCEMAP_COMMENT_RE = re.compile(
    r"/[/*]\s*#\s*sourceMappingURL\s*=\s*(\S+)",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# HTML extraction
# ---------------------------------------------------------------------------

def extract_script_assets(html: str, base_url: str = "") -> list[ScriptAsset]:
    """Extract <script> tags from HTML as ScriptAsset records."""
    soup = BeautifulSoup(html or "", "lxml")
    assets: list[ScriptAsset] = []
    for idx, script in enumerate(soup.find_all("script")):
        src = script.get("src", "")
        type_attr = str(script.get("type", ""))
        is_module = type_attr == "module"
        is_nomodule = script.has_attr("nomodule")
        is_inline = not bool(src)
        inline_text = script.get_text("", strip=True) if is_inline else ""
        size_estimate = len(inline_text) if is_inline else 0
        sourcemap_hint = ""
        if is_inline:
            sm_match = _SOURCEMAP_RE.search(inline_text) or _SOURCEMAP_COMMENT_RE.search(inline_text)
            if sm_match:
                sourcemap_hint = sm_match.group(1)

        asset = ScriptAsset(
            url=urljoin(base_url, src) if src else "",
            inline_id=f"inline_{idx}" if is_inline else "",
            type_attr=type_attr,
            is_module=is_module,
            is_nomodule=is_nomodule,
            is_inline=is_inline,
            size_estimate=size_estimate,
            sourcemap_hint=sourcemap_hint,
        )
        assets.append(asset)
    return assets


def extract_inline_scripts(html: str) -> list[str]:
    """Extract inline JS text from HTML <script> tags."""
    soup = BeautifulSoup(html or "", "lxml")
    scripts: list[str] = []
    for script in soup.find_all("script"):
        if not script.get("src"):
            text = script.get_text("", strip=True)
            if text:
                scripts.append(text)
    return scripts


# ---------------------------------------------------------------------------
# JS analysis
# ---------------------------------------------------------------------------

def analyze_js_text(js_text: str) -> dict[str, Any]:
    """Analyze JS text for keywords, endpoints, GraphQL, WebSocket, sourcemaps.

    Returns a dict with keys: keyword_hits, endpoint_candidates,
    graphql_strings, websocket_urls, sourcemap_refs.
    """
    keyword_hits = _find_keyword_hits(js_text)
    endpoint_candidates = _find_api_endpoints(js_text)
    graphql_strings = _find_graphql_strings(js_text)
    websocket_urls = _find_websocket_urls(js_text)
    sourcemap_refs = _find_sourcemap_refs(js_text)
    return {
        "keyword_hits": keyword_hits,
        "endpoint_candidates": endpoint_candidates,
        "graphql_strings": graphql_strings,
        "websocket_urls": websocket_urls,
        "sourcemap_refs": sourcemap_refs,
    }


def _find_keyword_hits(js_text: str) -> list[KeywordHit]:
    """Find signature/encryption/token/challenge keywords in JS text."""
    hits: list[KeywordHit] = []
    seen: set[tuple[str, str]] = set()
    text_lower = js_text.lower()

    for keyword, category in SIGNATURE_KEYWORDS:
        kw_lower = keyword.lower()
        if kw_lower in text_lower:
            key = (kw_lower, category)
            if key not in seen:
                seen.add(key)
                context = _extract_context(js_text, kw_lower)
                hits.append(KeywordHit(keyword=keyword, category=category, context_preview=context))

    for pattern, category in SIGNATURE_PATTERNS:
        for match in pattern.finditer(js_text[:100_000]):
            matched = match.group(0)
            key = (matched.lower(), category)
            if key not in seen:
                seen.add(key)
                context = _extract_context(js_text, matched.lower())
                hits.append(KeywordHit(keyword=matched, category=category, context_preview=context))

    return hits


def _find_api_endpoints(js_text: str) -> list[str]:
    """Find API-like endpoint strings in JS text."""
    endpoints: list[str] = []
    seen: set[str] = set()
    for match in _API_ENDPOINT_RE.finditer(js_text[:200_000]):
        candidate = match.group(1)
        if len(candidate) > 300 or candidate.startswith("data:"):
            continue
        if candidate not in seen:
            seen.add(candidate)
            endpoints.append(candidate)
    return endpoints


def _find_graphql_strings(js_text: str) -> list[str]:
    """Find GraphQL query/mutation/subscription strings in JS text."""
    graphql: list[str] = []
    seen: set[str] = set()
    for pattern in (_GRAPHQL_STRING_RE, _GRAPHQL_OP_RE):
        for match in pattern.finditer(js_text[:200_000]):
            candidate = match.group(1)
            if len(candidate) > 1000:
                candidate = candidate[:1000] + "..."
            if candidate not in seen:
                seen.add(candidate)
                graphql.append(candidate)
    return graphql


def _find_websocket_urls(js_text: str) -> list[str]:
    """Find WebSocket (ws://, wss://) URLs in JS text."""
    urls: list[str] = []
    seen: set[str] = set()
    for match in _WEBSOCKET_RE.finditer(js_text[:200_000]):
        url = match.group(1)
        if url not in seen:
            seen.add(url)
            urls.append(url)
    return urls


def _find_sourcemap_refs(js_text: str) -> list[str]:
    """Find sourceMappingURL references in JS text."""
    refs: list[str] = []
    seen: set[str] = set()
    for pattern in (_SOURCEMAP_RE, _SOURCEMAP_COMMENT_RE):
        for match in pattern.finditer(js_text[:500_000]):
            ref = match.group(1)
            if ref not in seen:
                seen.add(ref)
                refs.append(ref)
    return refs


def _extract_context(text: str, keyword_lower: str, window: int = 60) -> str:
    """Extract a short context window around a keyword match."""
    idx = text.lower().find(keyword_lower)
    if idx < 0:
        return ""
    start = max(0, idx - window)
    end = min(len(text), idx + len(keyword_lower) + window)
    snippet = text[start:end].replace("\n", " ").strip()
    if start > 0:
        snippet = "..." + snippet
    if end < len(text):
        snippet = snippet + "..."
    return snippet[:200]


# ---------------------------------------------------------------------------
# Scoring and ranking
# ---------------------------------------------------------------------------

def score_asset(
    asset: ScriptAsset,
    analysis: dict[str, Any],
) -> tuple[int, list[str]]:
    """Score a script asset based on its analysis results."""
    score = 0
    reasons: list[str] = []

    keyword_hits: list[KeywordHit] = analysis.get("keyword_hits", [])
    endpoint_candidates = analysis.get("endpoint_candidates", [])
    graphql_strings = analysis.get("graphql_strings", [])
    websocket_urls = analysis.get("websocket_urls", [])
    sourcemap_refs = analysis.get("sourcemap_refs", [])

    # Keyword scoring by category
    categories = {h.category for h in keyword_hits}
    if "signature" in categories:
        score += 30
        reasons.append("signature_keyword")
    if "encryption" in categories:
        score += 28
        reasons.append("encryption_keyword")
    if "token" in categories:
        score += 25
        reasons.append("token_keyword")
    if "challenge" in categories:
        score += 22
        reasons.append("challenge_keyword")
    if "anti_bot" in categories:
        score += 20
        reasons.append("anti_bot_keyword")
    if "fingerprint" in categories:
        score += 18
        reasons.append("fingerprint_keyword")
    if "verification" in categories:
        score += 15
        reasons.append("verification_keyword")
    if "bundler" in categories:
        score += 5
        reasons.append("bundler_keyword")

    # Endpoint scoring
    if endpoint_candidates:
        score += min(len(endpoint_candidates) * 8, 40)
        reasons.append(f"api_endpoints:{len(endpoint_candidates)}")

    # GraphQL scoring
    if graphql_strings:
        score += min(len(graphql_strings) * 15, 45)
        reasons.append(f"graphql_strings:{len(graphql_strings)}")

    # WebSocket scoring
    if websocket_urls:
        score += min(len(websocket_urls) * 12, 36)
        reasons.append(f"websocket_urls:{len(websocket_urls)}")

    # Sourcemap scoring
    if sourcemap_refs:
        score += 10
        reasons.append(f"sourcemap_refs:{len(sourcemap_refs)}")
    if asset.sourcemap_hint:
        score += 5
        reasons.append("inline_sourcemap_hint")

    # Module scripts are more likely to contain app logic
    if asset.is_module:
        score += 3
        reasons.append("type_module")

    # Inline scripts with config hints
    if asset.is_inline and asset.size_estimate > 100:
        score += 2
        reasons.append("inline_script")

    return score, reasons


def build_js_inventory(
    html: str,
    base_url: str = "",
    inline_scripts: list[str] | None = None,
) -> list[JsAssetReport]:
    """Build a ranked JS asset inventory from HTML.

    Args:
        html: The page HTML.
        base_url: Base URL for resolving relative script src.
        inline_scripts: Optional pre-extracted inline JS texts. If None,
            extracted from HTML automatically.

    Returns:
        List of JsAssetReport sorted by score descending.
    """
    assets = extract_script_assets(html, base_url=base_url)
    if inline_scripts is None:
        inline_scripts = extract_inline_scripts(html)

    reports: list[JsAssetReport] = []
    inline_idx = 0
    for asset in assets:
        if asset.is_inline:
            js_text = inline_scripts[inline_idx] if inline_idx < len(inline_scripts) else ""
            inline_idx += 1
        else:
            js_text = ""

        analysis = analyze_js_text(js_text)
        score, reasons = score_asset(asset, analysis)

        report = JsAssetReport(
            asset=asset,
            score=score,
            reasons=reasons,
            endpoint_candidates=analysis.get("endpoint_candidates", []),
            keyword_hits=analysis.get("keyword_hits", []),
            graphql_strings=analysis.get("graphql_strings", []),
            websocket_urls=analysis.get("websocket_urls", []),
            sourcemap_refs=analysis.get("sourcemap_refs", []),
        )
        reports.append(report)

    reports.sort(key=lambda r: r.score, reverse=True)
    return reports


def build_inventory_summary(reports: list[JsAssetReport]) -> dict[str, Any]:
    """Build a summary dict from a list of JsAssetReport."""
    total_assets = len(reports)
    scored_assets = sum(1 for r in reports if r.score > 0)
    all_endpoints: list[str] = []
    all_keywords: list[str] = []
    all_graphql: list[str] = []
    all_ws: list[str] = []
    all_sourcemaps: list[str] = []
    for r in reports:
        all_endpoints.extend(r.endpoint_candidates)
        all_graphql.extend(r.graphql_strings)
        all_ws.extend(r.websocket_urls)
        all_sourcemaps.extend(r.sourcemap_refs)
        for h in r.keyword_hits:
            if h.keyword not in all_keywords:
                all_keywords.append(h.keyword)
    return {
        "total_assets": total_assets,
        "scored_assets": scored_assets,
        "top_assets": [r.to_dict() for r in reports[:10]],
        "all_endpoint_candidates": _dedupe_preserve_order(all_endpoints),
        "all_keyword_hits": all_keywords,
        "all_graphql_strings": _dedupe_preserve_order(all_graphql),
        "all_websocket_urls": _dedupe_preserve_order(all_ws),
        "all_sourcemap_refs": _dedupe_preserve_order(all_sourcemaps),
    }


def _dedupe_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result
