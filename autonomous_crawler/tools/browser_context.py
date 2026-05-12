"""Browser context configuration for Playwright execution.

This is the first productized browser execution layer. It gives CLM a stable
place to describe viewport, locale, timezone, headers, storage state, and proxy
settings without scattering Playwright kwargs across fetchers and observers.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .proxy_manager import redact_proxy_url
from .session_profile import redact_headers, redact_storage_state_path


VALID_LOAD_STATES = {"domcontentloaded", "load", "networkidle"}
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0 Safari/537.36"
)


@dataclass(frozen=True)
class BrowserViewport:
    width: int = 1365
    height: int = 768

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> "BrowserViewport":
        payload = payload or {}
        width = _bounded_int(payload.get("width"), default=1365, minimum=320, maximum=3840)
        height = _bounded_int(payload.get("height"), default=768, minimum=240, maximum=2160)
        return cls(width=width, height=height)

    def to_dict(self) -> dict[str, int]:
        return {"width": self.width, "height": self.height}


@dataclass(frozen=True)
class BrowserContextConfig:
    headless: bool = True
    user_agent: str = DEFAULT_USER_AGENT
    viewport: BrowserViewport = field(default_factory=BrowserViewport)
    locale: str = "en-US"
    timezone_id: str = "UTC"
    extra_http_headers: dict[str, str] = field(default_factory=dict)
    storage_state_path: str = ""
    proxy_url: str = ""
    java_script_enabled: bool = True
    ignore_https_errors: bool = False
    color_scheme: str = "light"

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | "BrowserContextConfig" | None) -> "BrowserContextConfig":
        if isinstance(payload, BrowserContextConfig):
            return payload
        payload = payload or {}
        return cls(
            headless=bool(payload.get("headless", True)),
            user_agent=_clean_string(payload.get("user_agent"), DEFAULT_USER_AGENT, max_len=300),
            viewport=BrowserViewport.from_dict(payload.get("viewport") if isinstance(payload.get("viewport"), dict) else {}),
            locale=_clean_string(payload.get("locale"), "en-US", max_len=35),
            timezone_id=_clean_string(payload.get("timezone_id"), "UTC", max_len=80),
            extra_http_headers=_string_dict(payload.get("extra_http_headers")),
            storage_state_path=_clean_string(payload.get("storage_state_path"), "", max_len=500),
            proxy_url=_clean_string(payload.get("proxy_url"), "", max_len=500),
            java_script_enabled=bool(payload.get("java_script_enabled", True)),
            ignore_https_errors=bool(payload.get("ignore_https_errors", False)),
            color_scheme=_clean_choice(payload.get("color_scheme"), {"light", "dark", "no-preference"}, "light"),
        )

    def with_runtime_overrides(
        self,
        *,
        headers: dict[str, str] | None = None,
        storage_state_path: str = "",
        proxy_url: str = "",
    ) -> "BrowserContextConfig":
        merged_headers = {**self.extra_http_headers, **(headers or {})}
        return BrowserContextConfig(
            headless=self.headless,
            user_agent=self.user_agent,
            viewport=self.viewport,
            locale=self.locale,
            timezone_id=self.timezone_id,
            extra_http_headers=merged_headers,
            storage_state_path=storage_state_path or self.storage_state_path,
            proxy_url=proxy_url or self.proxy_url,
            java_script_enabled=self.java_script_enabled,
            ignore_https_errors=self.ignore_https_errors,
            color_scheme=self.color_scheme,
        )

    def launch_options(self) -> dict[str, Any]:
        options: dict[str, Any] = {"headless": self.headless}
        if self.proxy_url:
            options["proxy"] = {"server": self.proxy_url}
        return options

    def context_options(self) -> dict[str, Any]:
        options: dict[str, Any] = {
            "user_agent": self.user_agent,
            "viewport": self.viewport.to_dict(),
            "locale": self.locale,
            "timezone_id": self.timezone_id,
            "java_script_enabled": self.java_script_enabled,
            "ignore_https_errors": self.ignore_https_errors,
            "color_scheme": self.color_scheme,
        }
        if self.extra_http_headers:
            options["extra_http_headers"] = dict(self.extra_http_headers)
        if self.storage_state_path:
            options["storage_state"] = self.storage_state_path
        return options

    def to_safe_dict(self) -> dict[str, Any]:
        return {
            "headless": self.headless,
            "user_agent": self.user_agent,
            "viewport": self.viewport.to_dict(),
            "locale": self.locale,
            "timezone_id": self.timezone_id,
            "extra_http_headers": redact_headers(self.extra_http_headers),
            "storage_state_path": redact_storage_state_path(self.storage_state_path),
            "proxy_url": redact_proxy_url(self.proxy_url),
            "java_script_enabled": self.java_script_enabled,
            "ignore_https_errors": self.ignore_https_errors,
            "color_scheme": self.color_scheme,
        }


def normalize_wait_until(value: str, default: str = "domcontentloaded") -> str:
    value = str(value or "").strip()
    return value if value in VALID_LOAD_STATES else default


def _bounded_int(value: Any, *, default: int, minimum: int, maximum: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, number))


def _clean_string(value: Any, default: str, *, max_len: int) -> str:
    text = str(value or "").strip()
    if not text:
        return default
    return text[:max_len]


def _string_dict(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    return {str(key): str(val) for key, val in value.items()}


def _clean_choice(value: Any, allowed: set[str], default: str) -> str:
    text = str(value or "").strip()
    return text if text in allowed else default
