"""Proxy configuration helpers with safe defaults.

Proxy support is opt-in. The manager only selects configured proxy URLs and
redacts credentials from any serializable output.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse, urlunparse

from .proxy_pool import ProxyPoolConfig, ProxyPoolProvider, StaticProxyPoolProvider


SUPPORTED_PROXY_SCHEMES = {"http", "https", "socks5"}


@dataclass(frozen=True)
class ProxyConfig:
    enabled: bool = False
    default_proxy: str = ""
    per_domain: dict[str, str] = field(default_factory=dict)
    provider: str = "manual"
    pool: ProxyPoolConfig = field(default_factory=ProxyPoolConfig)

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
            pool=ProxyPoolConfig.from_dict(payload.get("pool")),
        )

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.enabled:
            return errors
        proxies = [self.default_proxy, *self.per_domain.values()]
        if not any(proxies):
            if not self.pool.enabled:
                errors.append("proxy enabled but no proxy URL configured")
        for proxy_url in [value for value in proxies if value]:
            parsed = urlparse(proxy_url)
            if parsed.scheme not in SUPPORTED_PROXY_SCHEMES or not parsed.netloc:
                errors.append(f"unsupported proxy URL: {redact_proxy_url(proxy_url)}")
        errors.extend(self.pool.validate())
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
            "pool": self.pool.to_safe_dict(),
        }


class ProxyManager:
    def __init__(
        self,
        config: ProxyConfig | dict[str, Any] | None = None,
        *,
        pool_provider: ProxyPoolProvider | None = None,
    ) -> None:
        self.config = config if isinstance(config, ProxyConfig) else ProxyConfig.from_dict(config)
        self.pool_provider = pool_provider or StaticProxyPoolProvider(self.config.pool)

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
        if self.config.pool.enabled:
            pool_selection = self.pool_provider.select(url)
            if pool_selection.proxy_url:
                return pool_selection.proxy_url
        return self.config.default_proxy

    def describe_selection(self, url: str) -> dict[str, Any]:
        proxy = ""
        source = "none"
        pool_selection = None
        if self.config.enabled:
            domain = (urlparse(url).hostname or "").lower()
            if domain in self.config.per_domain:
                proxy = self.config.per_domain[domain]
                source = "per_domain"
            else:
                parts = domain.split(".")
                for index in range(1, max(len(parts) - 1, 1)):
                    wildcard = "*." + ".".join(parts[index:])
                    if wildcard in self.config.per_domain:
                        proxy = self.config.per_domain[wildcard]
                        source = "per_domain_wildcard"
                        break
            if not proxy and self.config.pool.enabled:
                pool_selection = self.pool_provider.select(url)
                proxy = pool_selection.proxy_url
                source = pool_selection.source
            if not proxy and self.config.default_proxy:
                proxy = self.config.default_proxy
                source = "default"
        return {
            "enabled": self.config.enabled,
            "selected": bool(proxy),
            "proxy": redact_proxy_url(proxy),
            "source": source,
            "errors": self.config.validate(),
            "pool": pool_selection.to_safe_dict() if pool_selection else self.config.pool.to_safe_dict(),
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
