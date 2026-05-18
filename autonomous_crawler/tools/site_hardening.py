"""Reusable site hardening helpers absorbed from mature spider scripts.

These helpers are deliberately site-agnostic.  They cover patterns that showed
up repeatedly in the external spider framework: cache only good pages, classify
bad/challenge HTML, normalize URLs, de-duplicate images by stable media keys,
extract hydration state, and map category paths into three export levels.
"""
from __future__ import annotations

import ast
import hashlib
import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse

from bs4 import BeautifulSoup


BAD_HTML_MARKERS = (
    "cf-challenge",
    "cf-browser-verification",
    "just a moment",
    "access denied",
    "akamai",
    "sec-if-cpt-container",
    "captcha",
    "robot check",
)

NOISE_IMAGE_MARKERS = (
    "svg-icons",
    "footer",
    "payment",
    "paypal",
    "rating-star",
    "wishlist",
    "basket-icon",
    "akam/",
    "pixel",
    "logo",
    "securepayment",
    "delivery.svg",
    "returns.svg",
    "click&collect",
    "favicon",
    "sprite",
    "placeholder",
)


def normalize_url(url: str, base: str = "", *, keep_query: bool = False, sort_query: bool = True) -> str:
    """Normalize a URL while preserving enough identity for product crawls."""
    if not url:
        return ""
    full = urljoin(base, str(url).strip())
    parsed = urlparse(full)
    if parsed.scheme not in {"http", "https"}:
        return ""
    query = parsed.query if keep_query else ""
    if query and sort_query:
        query = urlencode(sorted(parse_qsl(query, keep_blank_values=True)), doseq=True)
    path = parsed.path or "/"
    if path != "/":
        path = path.rstrip("/")
    return urlunparse((parsed.scheme, parsed.netloc.lower(), path, "", query, ""))


def is_bad_html(text: str, status: int | None = None, *, min_length: int = 600) -> bool:
    """Return True for empty, blocked, challenge-like, or server-error pages."""
    if status and int(status) >= 500:
        return True
    if not text or len(str(text)) < min_length:
        return True
    lowered = str(text).lower()
    return any(marker in lowered for marker in BAD_HTML_MARKERS)


def cache_key(value: str, *, prefix: str = "") -> str:
    raw = f"{prefix}|{value}".encode("utf-8", errors="ignore")
    return hashlib.md5(raw).hexdigest()


def read_good_page_cache(cache_dir: str | Path, key: str) -> dict[str, Any] | None:
    path = Path(cache_dir) / f"{key}.json"
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    if is_bad_html(str(payload.get("text") or ""), payload.get("status")):
        return None
    return payload


def write_good_page_cache(
    cache_dir: str | Path,
    key: str,
    *,
    url: str,
    text: str,
    status: int | None = None,
    extra: dict[str, Any] | None = None,
) -> bool:
    """Write cache only when the page looks usable."""
    if is_bad_html(text, status):
        return False
    path = Path(cache_dir)
    path.mkdir(parents=True, exist_ok=True)
    payload = {"url": url, "text": text, "status": status}
    if extra:
        payload.update(extra)
    (path / f"{key}.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return True


def image_key(url: str) -> str:
    parsed = urlparse(url)
    path = parsed.path.lower()
    parts = [part for part in path.split("/") if part]
    if "media/catalog/product" in path and len(parts) >= 2:
        return "/".join(parts[-3:])
    return f"{parsed.netloc.lower()}{path}"


def clean_product_images(
    images: list[str],
    *,
    base_url: str = "",
    required_contains: tuple[str, ...] = (),
    deny_markers: tuple[str, ...] = NOISE_IMAGE_MARKERS,
) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for image in images:
        full = normalize_url(str(image or ""), base_url, keep_query=True)
        lowered = full.lower()
        if not full or lowered.startswith("data:"):
            continue
        if any(marker in lowered for marker in deny_markers):
            continue
        if required_contains and not any(marker.lower() in lowered for marker in required_contains):
            continue
        key = image_key(full)
        if key in seen:
            continue
        seen.add(key)
        output.append(full)
    return output


def clean_text(value: Any) -> str:
    text = BeautifulSoup(str(value or ""), "html.parser").get_text(" ", strip=True)
    return re.sub(r"\s+", " ", text).strip()


def category_levels(path: list[str] | tuple[str, ...] | str) -> tuple[str, str, str]:
    if isinstance(path, str):
        parts = [part.strip() for part in re.split(r">|/|\|", path) if part.strip()]
    else:
        parts = [clean_text(part) for part in path if clean_text(part)]
    if not parts:
        return "", "", ""
    return parts[0], parts[1] if len(parts) > 1 else "", " > ".join(parts[2:]) if len(parts) > 2 else ""


def extract_json_script(html: str, *, script_id: str = "", marker: str = "") -> Any:
    """Extract JSON or JS-assigned hydration state from a page."""
    soup = BeautifulSoup(html or "", "html.parser")
    if script_id:
        node = soup.find("script", id=script_id)
        if node and node.string:
            try:
                return json.loads(node.string)
            except json.JSONDecodeError:
                return {}
    if marker:
        pos = (html or "").find(marker)
        if pos >= 0:
            end = html.find("</script>", pos)
            if end < 0:
                end = len(html)
            script = html[pos:end]
            expr = script.split("=", 1)[1].strip().rstrip(";") if "=" in script else script
            try:
                return json.loads(expr)
            except json.JSONDecodeError:
                try:
                    return json.loads(ast.literal_eval(expr))
                except Exception:
                    return {}
    return {}
