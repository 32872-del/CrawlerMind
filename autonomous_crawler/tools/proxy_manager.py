"""Proxy configuration helpers with safe defaults.

Proxy support is opt-in. The manager only selects configured proxy URLs and
redacts credentials from any serializable output.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse, urlunparse


SUPPORTED_PROXY_SCHEMES = {"http", "https", "socks5"}


@dataclass(frozen=True)
class ProxyConfig:
    enabled: bool = False
    default_proxy: str = ""
    per_domain: dict[str, str] = field(default_factory=dict)
    provider: str = "manual"

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> "ProxyConfig":
        payload = payload or {}
        per_domain = payload.get("per_domain") or {}
        if not isinstance(per_domain, dict):
            per_domain = {}
        return cls(
            enabled=bool(payload.get("enabled", False)),
            default_proxy=str(payload.get("default_proxy") or ""),
            per_domain={str(k).lower(): str(v) for k, v in per_domain.items()},
            provider=str(payload.get("provider") or "manual"),
        )

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.enabled:
            return errors
        proxies = [self.default_proxy, *self.per_domain.values()]
        if not any(proxies):
            errors.append("proxy enabled but no proxy URL configured")
        for proxy_url in [value for value in proxies if value]:
            parsed = urlparse(proxy_url)
            if parsed.scheme not in SUPPORTED_PROXY_SCHEMES or not parsed.netloc:
                errors.append(f"unsupported proxy URL: {redact_proxy_url(proxy_url)}")
        return errors

    def to_safe_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "default_proxy": redact_proxy_url(self.default_proxy),
            "per_domain": {
                domain: redact_proxy_url(proxy)
                for domain, proxy in self.per_domain.items()
            },
            "provider": self.provider,
        }


class ProxyManager:
    def __init__(self, config: ProxyConfig | dict[str, Any] | None = None) -> None:
        self.config = config if isinstance(config, ProxyConfig) else ProxyConfig.from_dict(config)

    def select_proxy(self, url: str) -> str:
        """Return the proxy URL for a target URL, or an empty string."""
        if not self.config.enabled:
            return ""
        domain = (urlparse(url).hostname or "").lower()
        if domain in self.config.per_domain:
            return self.config.per_domain[domain]
        parts = domain.split(".")
        for index in range(1, max(len(parts) - 1, 1)):
            wildcard = "*." + ".".join(parts[index:])
            if wildcard in self.config.per_domain:
                return self.config.per_domain[wildcard]
        return self.config.default_proxy

    def describe_selection(self, url: str) -> dict[str, Any]:
        proxy = self.select_proxy(url)
        return {
            "enabled": self.config.enabled,
            "selected": bool(proxy),
            "proxy": redact_proxy_url(proxy),
            "errors": self.config.validate(),
        }


def redact_proxy_url(proxy_url: str) -> str:
    if not proxy_url:
        return ""
    parsed = urlparse(proxy_url)
    if not parsed.username and not parsed.password:
        return proxy_url
    host = parsed.hostname or ""
    if parsed.port:
        host = f"{host}:{parsed.port}"
    return urlunparse((parsed.scheme, f"***:***@{host}", parsed.path, "", "", ""))
