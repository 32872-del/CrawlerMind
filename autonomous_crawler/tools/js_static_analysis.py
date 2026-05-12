"""JS Static Analysis: string table, function/call clues, ranked report.

Extends the JS Asset Inventory with deeper regex-based static analysis:
string literal extraction, function declaration/assignment detection,
suspicious call identification, and a ranked report.

Deterministic, dependency-light. No JS execution, no AST parser, no
deobfuscation, no source-map download.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class StringEntry:
    """A string literal extracted from JS text."""
    value: str
    kind: str = "quoted"  # quoted, template, url
    is_endpoint: bool = False
    is_url: bool = False


@dataclass(frozen=True)
class FunctionClue:
    """A function declaration or assignment detected in JS text."""
    name: str
    kind: str  # declaration, arrow, assignment, method
    suspicious: bool = False
    suspicion_reason: str = ""


@dataclass(frozen=True)
class CallClue:
    """A function call that matches a suspicious keyword pattern."""
    call_expression: str
    matched_keyword: str
    category: str
    context: str = ""


@dataclass
class StaticAnalysisReport:
    """Ranked static-analysis report for a JS text."""
    string_count: int = 0
    endpoint_strings: list[str] = field(default_factory=list)
    url_strings: list[str] = field(default_factory=list)
    suspicious_functions: list[FunctionClue] = field(default_factory=list)
    suspicious_calls: list[CallClue] = field(default_factory=list)
    score: int = 0
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "string_count": self.string_count,
            "endpoint_strings": list(self.endpoint_strings),
            "url_strings": list(self.url_strings),
            "suspicious_functions": [
                {"name": f.name, "kind": f.kind, "suspicious": f.suspicious, "reason": f.suspicion_reason}
                for f in self.suspicious_functions
            ],
            "suspicious_calls": [
                {"call": c.call_expression, "keyword": c.matched_keyword, "category": c.category, "context": c.context}
                for c in self.suspicious_calls
            ],
            "score": self.score,
            "reasons": list(self.reasons),
        }


# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

# String literals: double-quoted, single-quoted, template literals
_DOUBLE_QUOTED_RE = re.compile(r'"((?:[^"\\]|\\.){0,500})"')
_SINGLE_QUOTED_RE = re.compile(r"'((?:[^'\\]|\\.){0,500})'")
_TEMPLATE_LITERAL_RE = re.compile(r'`((?:[^`\\]|\\.){0,500})`')

# URL / endpoint patterns
_URL_RE = re.compile(
    r"""(?:"|')(https?://[^"'\s]{3,300})(?:"|')""",
    re.IGNORECASE,
)
_API_PATH_RE = re.compile(
    r"""(?:"|')(/(?:api|v\d|graphql|ajax|rest|service|auth|login|oauth)[^"'\s]{0,200})(?:"|')""",
    re.IGNORECASE,
)
_WS_RE = re.compile(r"""(?:"|')(wss?://[^"'\s]{3,300})(?:"|')""", re.IGNORECASE)

# Function declarations: function name(...) { ... }
_FUNC_DECL_RE = re.compile(
    r"""\bfunction\s+([a-zA-Z_$][\w$]*)\s*\(""",
)

# Arrow / assignment: const/let/var name = (...) => { ... } or function(...) { ... }
_FUNC_ASSIGN_RE = re.compile(
    r"""\b(?:const|let|var)\s+([a-zA-Z_$][\w$]*)\s*=\s*(?:\([^)]*\)\s*=>|function\b)""",
)

# Method shorthand: name(...) { ... } inside object/class (simplified)
_METHOD_RE = re.compile(
    r"""^\s*([a-zA-Z_$][\w$]*)\s*\([^)]*\)\s*\{""",
    re.MULTILINE,
)

# Suspicious call pattern: any call whose callee contains a suspicious keyword
_SUSPICIOUS_KEYWORDS: tuple[tuple[str, str], ...] = (
    ("sign", "signature"),
    ("signature", "signature"),
    ("signed", "signature"),
    ("hmac", "signature"),
    ("sha256", "signature"),
    ("sha1", "signature"),
    ("md5", "signature"),
    ("encrypt", "encryption"),
    ("decrypt", "encryption"),
    ("crypto", "encryption"),
    ("token", "token"),
    ("nonce", "token"),
    ("wbi", "token"),
    ("xbogus", "token"),
    ("x-bogus", "token"),
    ("verify", "verification"),
    ("captcha", "challenge"),
    ("recaptcha", "challenge"),
    ("hcaptcha", "challenge"),
    ("turnstile", "challenge"),
    ("geetest", "challenge"),
    ("fingerprint", "fingerprint"),
    ("antibot", "anti_bot"),
    ("anti-bot", "anti_bot"),
)

# Build a combined regex that matches a call expression containing a suspicious keyword
_SUSPICIOUS_CALL_RE = re.compile(
    r"""(?:\b(?:[\w$.]+[.])*)(\w*(?:sign|signature|signed|hmac|sha256|sha1|md5|encrypt|decrypt|crypto|token|nonce|wbi|xbogus|x-?bogus|verify|captcha|recaptcha|hcaptcha|turnstile|geetest|fingerprint|antibot|anti-?bot)\w*)\s*\(""",
    re.IGNORECASE,
)

# Also match when the object/namespace contains the keyword: e.g. hcaptcha.getResponse()
_SUSPICIOUS_OBJ_CALL_RE = re.compile(
    r"""\b(\w*(?:sign|signature|signed|hmac|sha256|sha1|md5|encrypt|decrypt|crypto|token|nonce|wbi|xbogus|x-?bogus|verify|captcha|recaptcha|hcaptcha|turnstile|geetest|fingerprint|antibot|anti-?bot)\w*)\.(\w+)\s*\(""",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# String extraction
# ---------------------------------------------------------------------------

def extract_strings(js_text: str, max_strings: int = 500) -> list[StringEntry]:
    """Extract string literals from JS text.

    Returns quoted, template, and URL/API-looking strings. Deduplicates
    by value.
    """
    entries: list[StringEntry] = []
    seen: set[str] = set()

    for pattern, kind in (
        (_DOUBLE_QUOTED_RE, "quoted"),
        (_SINGLE_QUOTED_RE, "quoted"),
        (_TEMPLATE_LITERAL_RE, "template"),
    ):
        for match in pattern.finditer(js_text[:300_000]):
            value = match.group(1).strip()
            if not value or len(value) < 2:
                continue
            # Skip template interpolation content
            if kind == "template":
                value = re.sub(r"\$\{[^}]*\}", "<expr>", value)
            if value in seen:
                continue
            seen.add(value)
            is_url = bool(_URL_RE.match(f'"{value}"') or _WS_RE.match(f'"{value}"'))
            is_endpoint = bool(_API_PATH_RE.match(f'"{value}"'))
            entries.append(StringEntry(
                value=value,
                kind=kind,
                is_endpoint=is_endpoint,
                is_url=is_url,
            ))
            if len(entries) >= max_strings:
                return entries

    return entries


def extract_endpoint_strings(js_text: str) -> list[str]:
    """Extract API endpoint and URL strings from JS text."""
    endpoints: list[str] = []
    seen: set[str] = set()

    for pattern in (_URL_RE, _API_PATH_RE, _WS_RE):
        for match in pattern.finditer(js_text[:300_000]):
            value = match.group(1).strip()
            if value not in seen and len(value) >= 3:
                seen.add(value)
                endpoints.append(value)

    return endpoints


# ---------------------------------------------------------------------------
# Function / call extraction
# ---------------------------------------------------------------------------

def extract_functions(js_text: str) -> list[FunctionClue]:
    """Extract function declarations and assignments from JS text."""
    functions: list[FunctionClue] = []
    seen: set[str] = set()

    for match in _FUNC_DECL_RE.finditer(js_text[:300_000]):
        name = match.group(1)
        if name in seen:
            continue
        seen.add(name)
        functions.append(FunctionClue(
            name=name,
            kind="declaration",
            suspicious=_is_suspicious_name(name),
            suspicion_reason=_suspicion_reason(name),
        ))

    for match in _FUNC_ASSIGN_RE.finditer(js_text[:300_000]):
        name = match.group(1)
        if name in seen:
            continue
        seen.add(name)
        functions.append(FunctionClue(
            name=name,
            kind="arrow" if "=>" in match.group(0) else "assignment",
            suspicious=_is_suspicious_name(name),
            suspicion_reason=_suspicion_reason(name),
        ))

    for match in _METHOD_RE.finditer(js_text[:300_000]):
        name = match.group(1)
        if name in seen:
            continue
        seen.add(name)
        functions.append(FunctionClue(
            name=name,
            kind="method",
            suspicious=_is_suspicious_name(name),
            suspicion_reason=_suspicion_reason(name),
        ))

    return functions


def extract_suspicious_calls(js_text: str) -> list[CallClue]:
    """Extract function calls whose names contain suspicious keywords."""
    calls: list[CallClue] = []
    seen: set[str] = set()

    for match in _SUSPICIOUS_CALL_RE.finditer(js_text[:300_000]):
        callee = match.group(1)
        call_expr = match.group(0).rstrip("(").strip()
        key = callee.lower()
        if key in seen:
            continue
        seen.add(key)
        category = _keyword_category(callee)
        context = _extract_context(js_text, callee.lower())
        calls.append(CallClue(
            call_expression=call_expr,
            matched_keyword=callee,
            category=category,
            context=context,
        ))

    # Also match object.method() where object name contains keyword
    for match in _SUSPICIOUS_OBJ_CALL_RE.finditer(js_text[:300_000]):
        obj_name = match.group(1)
        method_name = match.group(2)
        full_expr = f"{obj_name}.{method_name}"
        key = full_expr.lower()
        if key in seen:
            continue
        seen.add(key)
        category = _keyword_category(obj_name)
        context = _extract_context(js_text, obj_name.lower())
        calls.append(CallClue(
            call_expression=full_expr,
            matched_keyword=obj_name,
            category=category,
            context=context,
        ))

    return calls


def _is_suspicious_name(name: str) -> bool:
    lower = name.lower()
    for keyword, _ in _SUSPICIOUS_KEYWORDS:
        if keyword in lower:
            return True
    return False


def _suspicion_reason(name: str) -> str:
    lower = name.lower()
    for keyword, category in _SUSPICIOUS_KEYWORDS:
        if keyword in lower:
            return category
    return ""


def _keyword_category(name: str) -> str:
    lower = name.lower()
    for keyword, category in _SUSPICIOUS_KEYWORDS:
        if keyword in lower:
            return category
    return "unknown"


def _extract_context(text: str, keyword_lower: str, window: int = 60) -> str:
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
# Scoring
# ---------------------------------------------------------------------------

def score_static_analysis(
    string_entries: list[StringEntry],
    functions: list[FunctionClue],
    calls: list[CallClue],
) -> tuple[int, list[str]]:
    """Score a static analysis result."""
    score = 0
    reasons: list[str] = []

    # Endpoint strings
    endpoint_count = sum(1 for s in string_entries if s.is_endpoint or s.is_url)
    if endpoint_count:
        score += min(endpoint_count * 6, 30)
        reasons.append(f"endpoint_strings:{endpoint_count}")

    # Suspicious function names
    suspicious_funcs = [f for f in functions if f.suspicious]
    if suspicious_funcs:
        categories = {f.suspicion_reason for f in suspicious_funcs}
        if "signature" in categories:
            score += 25
            reasons.append("suspicious_signature_func")
        if "encryption" in categories:
            score += 23
            reasons.append("suspicious_encryption_func")
        if "token" in categories:
            score += 20
            reasons.append("suspicious_token_func")
        if "challenge" in categories:
            score += 18
            reasons.append("suspicious_challenge_func")
        if "fingerprint" in categories:
            score += 16
            reasons.append("suspicious_fingerprint_func")
        if "verification" in categories:
            score += 12
            reasons.append("suspicious_verification_func")
        if "anti_bot" in categories:
            score += 14
            reasons.append("suspicious_anti_bot_func")

    # Suspicious calls
    if calls:
        call_categories = {c.category for c in calls}
        if "signature" in call_categories:
            score += 30
            reasons.append("signature_call")
        if "encryption" in call_categories:
            score += 28
            reasons.append("encryption_call")
        if "token" in call_categories:
            score += 25
            reasons.append("token_call")
        if "challenge" in call_categories:
            score += 22
            reasons.append("challenge_call")
        if "fingerprint" in call_categories:
            score += 18
            reasons.append("fingerprint_call")
        if "verification" in call_categories:
            score += 15
            reasons.append("verification_call")
        if "anti_bot" in call_categories:
            score += 16
            reasons.append("anti_bot_call")

    # Large string table hints at obfuscated or config-heavy code
    string_count = len(string_entries)
    if string_count > 100:
        score += 5
        reasons.append(f"large_string_table:{string_count}")

    return score, reasons


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def analyze_js_static(js_text: str) -> StaticAnalysisReport:
    """Run full static analysis on JS text and return a ranked report.

    Extracts string literals, function declarations/assignments, and
    suspicious call expressions. Scores and ranks findings.
    """
    string_entries = extract_strings(js_text)
    functions = extract_functions(js_text)
    calls = extract_suspicious_calls(js_text)

    endpoint_strings = [
        s.value for s in string_entries if s.is_endpoint
    ]
    url_strings = [
        s.value for s in string_entries if s.is_url
    ]

    score, reasons = score_static_analysis(string_entries, functions, calls)

    return StaticAnalysisReport(
        string_count=len(string_entries),
        endpoint_strings=endpoint_strings,
        url_strings=url_strings,
        suspicious_functions=[f for f in functions if f.suspicious],
        suspicious_calls=calls,
        score=score,
        reasons=reasons,
    )
