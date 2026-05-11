"""Generic product record quality validation.

This module validates product records without embedding site-specific scraping
rules. Site differences should be expressed through a profile/config layer, not
hard-coded here.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any

from ..models.product import ProductRecord


MISSING_URL = "missing_url"
MISSING_TITLE = "missing_title"
EMPTY_IMAGES = "empty_images"
NOISE_ONLY_IMAGES = "noise_only_images"
UNPARSABLE_PRICE = "unparsable_price"
NEGATIVE_PRICE = "negative_price"
MISSING_BODY = "missing_body"
SHORT_BODY = "short_body"
MISSING_HANDLE = "missing_handle"
MISSING_DEDUPE_KEY = "missing_dedupe_key"
MISSING_CATEGORY = "missing_category"
DATA_IMAGE_URL = "data_image_url"
BLOCKED_WITHOUT_NOTES = "blocked_without_notes"

SEVERITY_INFO = "info"
SEVERITY_WARNING = "warning"
SEVERITY_ERROR = "error"

VALID_SEVERITIES = frozenset({SEVERITY_INFO, SEVERITY_WARNING, SEVERITY_ERROR})


_IMAGE_NOISE_PATTERNS = (
    "/logo", "logo.", "logo_", "-logo", "_logo",
    "/icon", "icon.", "icon_", "-icon", "_icon",
    "favicon", "sprite", "placeholder", "noimage", "no-image",
    "default-image", "payment", "visa", "mastercard", "paypal", "amex",
    "trustpilot", "trust-badge", "badge", "secure", "size-chart",
    "size-guide", "maattabel", "facebook.com/tr", "facebook.net",
    "facebook_", "instagram_", "twitter_", "pinterest_", "instagram.",
    "twitter.", "pinterest.", "pixel", "beacon", "analytics",
    "google_pay", "apple_pay", "inpost", "pay-po", "autopay",
    "outlet.jpg",
)

_CURRENCY_TOKENS = (
    "EUR", "USD", "GBP", "CHF", "SEK", "DKK", "NOK", "PLN",
    "euro", "dollar", "pound", "zl", "zloty", "kr",
    "\u20ac", "$", "\u00a3", "\u00a5", "z\u0142",
)
_FREE_RE = re.compile(r"^(free|gratis|kostenlos|gratuit)$", re.IGNORECASE)
_NUMBER_RE = re.compile(r"-?\d+(?:[.,\s]\d{3})*(?:[.,]\d{1,2})?|-?\d+")


@dataclass(frozen=True)
class ProductQualityIssue:
    code: str
    severity: str
    field: str
    message: str

    def __post_init__(self) -> None:
        if self.severity not in VALID_SEVERITIES:
            raise ValueError(f"Invalid severity: {self.severity}")


DEFAULT_PROFILE: dict[str, Any] = {
    "required_fields": ("url", "title"),
    "allow_partial": True,
    "allow_missing_price": False,
    "min_description_length": 0,
    "image_required": True,
    "price_required": True,
    "dedupe_key_required": False,
}


def parse_price(raw: Any) -> float | None:
    """Parse a price-like value into a float.

    The parser is intentionally generic. It supports common currency symbols,
    European comma decimals, simple thousands separators, and price ranges. For
    ranges, it returns the highest number because CLM's normalized ecommerce
    field is currently `highest_price`.
    """
    if raw is None:
        return None
    if isinstance(raw, bool):
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    text = str(raw).strip()
    if not text:
        return None
    if _FREE_RE.match(text):
        return 0.0
    for token in _CURRENCY_TOKENS:
        text = re.sub(re.escape(token), " ", text, flags=re.IGNORECASE)
    matches = _NUMBER_RE.findall(text)
    if not matches:
        return None
    values: list[float] = []
    for match in matches:
        normalized = _normalize_number(match)
        try:
            values.append(float(normalized))
        except ValueError:
            continue
    if not values:
        return None
    return max(values)


def validate_product_record(
    record: ProductRecord | dict[str, Any],
    profile: dict[str, Any] | None = None,
) -> list[ProductQualityIssue]:
    """Validate one generic product record.

    Profiles may tighten or relax generic rules. They must not contain
    site-specific selectors or extraction hacks.
    """
    profile_cfg = {**DEFAULT_PROFILE, **(profile or {})}
    data = _record_to_mapping(record)
    issues: list[ProductQualityIssue] = []

    status = str(data.get("status") or "ok").strip().lower()
    is_blocked = status == "blocked"
    is_partial = status == "partial"
    partial_allowed = bool(profile_cfg.get("allow_partial", True))

    url = _first_text(data, "canonical_url", "url", "source_url")
    title = _first_text(data, "title", "product_title")
    price_raw = data.get("highest_price") if data.get("highest_price") is not None else data.get("price")
    description = _first_text(data, "description", "body", "product_description")
    images = _image_list(data.get("image_urls") or data.get("image_src"))
    notes = _first_text(data, "notes")
    handle = _first_text(data, "handle")
    category = _first_text(data, "category", "categories_1")
    dedupe_key = _first_text(data, "dedupe_key", "sole_id")

    if is_blocked:
        if not notes:
            issues.append(_issue(BLOCKED_WITHOUT_NOTES, SEVERITY_WARNING, "notes", "Blocked records should explain the block reason."))
        return issues

    required = set(profile_cfg.get("required_fields") or ())
    if "url" in required and not url:
        issues.append(_issue(MISSING_URL, SEVERITY_ERROR, "url", "Product URL is required."))

    if "title" in required and not title:
        severity = SEVERITY_WARNING if is_partial and partial_allowed else SEVERITY_ERROR
        issues.append(_issue(MISSING_TITLE, severity, "title", "Product title is required."))

    parsed_price = parse_price(price_raw)
    price_required = bool(profile_cfg.get("price_required", True))
    allow_missing_price = bool(profile_cfg.get("allow_missing_price", False))
    if price_raw is not None and price_raw != "":
        if parsed_price is None:
            severity = SEVERITY_INFO if is_partial and partial_allowed else SEVERITY_WARNING
            issues.append(_issue(UNPARSABLE_PRICE, severity, "price", f"Cannot parse price: {price_raw!r}."))
        elif parsed_price < 0:
            issues.append(_issue(NEGATIVE_PRICE, SEVERITY_ERROR, "price", f"Negative price: {parsed_price}."))
    elif price_required and not allow_missing_price and not (is_partial and partial_allowed):
        issues.append(_issue(UNPARSABLE_PRICE, SEVERITY_WARNING, "price", "Price is missing."))

    image_required = bool(profile_cfg.get("image_required", True))
    if images:
        for image in images:
            if image.startswith("data:"):
                issues.append(_issue(DATA_IMAGE_URL, SEVERITY_INFO, "image_urls", "data: URI image found."))
                break
        non_noise = [image for image in images if not _is_noise_image(image) and not image.startswith("data:")]
        if not non_noise and image_required and not (is_partial and partial_allowed):
            issues.append(_issue(NOISE_ONLY_IMAGES, SEVERITY_WARNING, "image_urls", "All image URLs look like noise."))
    elif image_required and not (is_partial and partial_allowed):
        issues.append(_issue(EMPTY_IMAGES, SEVERITY_WARNING, "image_urls", "No product images found."))

    min_description_length = int(profile_cfg.get("min_description_length") or 0)
    if not description and not (is_partial and partial_allowed):
        issues.append(_issue(MISSING_BODY, SEVERITY_INFO, "description", "Product description is empty."))
    elif min_description_length and len(description) < min_description_length:
        issues.append(
            _issue(
                SHORT_BODY,
                SEVERITY_WARNING,
                "description",
                f"Description is {len(description)} chars; minimum is {min_description_length}.",
            )
        )

    if not handle:
        issues.append(_issue(MISSING_HANDLE, SEVERITY_INFO, "handle", "No stable product handle is set."))

    if not category:
        issues.append(_issue(MISSING_CATEGORY, SEVERITY_INFO, "category", "No category context is set."))

    if not dedupe_key:
        severity = SEVERITY_WARNING if profile_cfg.get("dedupe_key_required") else SEVERITY_INFO
        issues.append(_issue(MISSING_DEDUPE_KEY, severity, "dedupe_key", "No product dedupe key is set."))

    return issues


def has_errors(issues: list[ProductQualityIssue]) -> bool:
    return any(issue.severity == SEVERITY_ERROR for issue in issues)


def issue_counts(issues: list[ProductQualityIssue]) -> dict[str, int]:
    counts = {SEVERITY_ERROR: 0, SEVERITY_WARNING: 0, SEVERITY_INFO: 0}
    for issue in issues:
        counts[issue.severity] += 1
    return counts


def _normalize_number(value: str) -> str:
    value = value.strip().replace("\u00a0", " ")
    if "," in value and "." in value:
        if value.rfind(",") > value.rfind("."):
            value = value.replace(".", "").replace(" ", "").replace(",", ".")
        else:
            value = value.replace(",", "").replace(" ", "")
    elif "," in value:
        parts = value.split(",")
        if len(parts[-1]) in {1, 2}:
            value = "".join(parts[:-1]).replace(" ", "") + "." + parts[-1]
        else:
            value = value.replace(",", "").replace(" ", "")
    elif "." in value:
        parts = value.split(".")
        if len(parts) > 2 or len(parts[-1]) == 3:
            value = "".join(parts)
        value = value.replace(" ", "")
    else:
        value = value.replace(" ", "")
    return value


def _record_to_mapping(record: ProductRecord | dict[str, Any]) -> dict[str, Any]:
    if isinstance(record, ProductRecord):
        return asdict(record)
    return dict(record or {})


def _first_text(data: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = data.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _image_list(raw: Any) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(item).strip() for item in raw if str(item).strip()]
    text = str(raw).strip()
    if not text:
        return []
    if text.startswith("[") and text.endswith("]"):
        try:
            import json

            parsed = json.loads(text)
            if isinstance(parsed, list):
                return [str(item).strip() for item in parsed if str(item).strip()]
        except json.JSONDecodeError:
            pass
    separator = "|" if "|" in text else ","
    return [part.strip() for part in text.split(separator) if part.strip()]


def _is_noise_image(url: str) -> bool:
    lowered = url.lower()
    return any(pattern in lowered for pattern in _IMAGE_NOISE_PATTERNS)


def _issue(code: str, severity: str, field: str, message: str) -> ProductQualityIssue:
    return ProductQualityIssue(code=code, severity=severity, field=field, message=message)
