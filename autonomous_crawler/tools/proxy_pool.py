"""Pluggable proxy pool foundation (CAP-3.3).

The proxy pool is opt-in infrastructure.  It lets CLM rotate across configured
proxy endpoints and later plug in paid-provider adapters without baking any
provider-specific SDK into the crawler core.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import itertools
from typing import Any, Protocol, runtime_checkable
from urllib.parse import urlparse


SUPPORTED_POOL_STRATEGIES = {"round_robin", "domain_sticky", "first_healthy"}
SUPPORTED_PROXY_SCHEMES = {"http", "https", "socks5"}


@dataclass(frozen=True)
class ProxyEndpoint:
    """One candidate proxy endpoint."""

    url: str
    label: str = ""
    weight: int = 1
    enabled: bool = True
    cooldown_until: float = 0.0
    success_count: int = 0
    failure_count: int = 0
    last_error: str = ""
    tags: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | str) -> "ProxyEndpoint":
        if isinstance(payload, str):
            return cls(url=payload)
        payload = payload or {}
        tags = payload.get("tags") if isinstance(payload.get("tags"), dict) else {}
        return cls(
            url=str(payload.get("url") or ""),
            label=str(payload.get("label") or ""),
            weight=_bounded_int(payload.get("weight"), default=1, minimum=1, maximum=100),
            enabled=bool(payload.get("enabled", True)),
            cooldown_until=_safe_float(payload.get("cooldown_until")),
            success_count=_bounded_int(payload.get("success_count"), default=0, minimum=0, maximum=10**9),
            failure_count=_bounded_int(payload.get("failure_count"), default=0, minimum=0, maximum=10**9),
            last_error=str(payload.get("last_error") or "")[:200],
            tags={str(k): str(v) for k, v in tags.items()},
        )

    def is_available(self, now: float = 0.0) -> bool:
        return bool(self.enabled and self.url and self.cooldown_until <= now)

    def validate(self) -> list[str]:
        if not self.url:
            return ["proxy endpoint missing url"]
        parsed = urlparse(self.url)
        if parsed.scheme not in SUPPORTED_PROXY_SCHEMES or not parsed.netloc:
            return [f"unsupported proxy endpoint: {redact_proxy_url(self.url)}"]
        return []

    def to_safe_dict(self) -> dict[str, Any]:
        return {
            "url": redact_proxy_url(self.url),
            "label": self.label,
            "weight": self.weight,
            "enabled": self.enabled,
            "cooldown_until": self.cooldown_until,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "last_error": self.last_error,
            "tags": dict(self.tags),
        }


@dataclass(frozen=True)
class ProxyPoolConfig:
    """Config for a pluggable proxy pool."""

    enabled: bool = False
    provider: str = "static"
    strategy: str = "round_robin"
    endpoints: tuple[ProxyEndpoint, ...] = ()
    domain_affinity: bool = True
    max_failures: int = 3

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | "ProxyPoolConfig" | None) -> "ProxyPoolConfig":
        if isinstance(payload, ProxyPoolConfig):
            return payload
        payload = payload or {}
        raw_endpoints = payload.get("endpoints") or payload.get("proxies") or []
        endpoints: list[ProxyEndpoint] = []
        if isinstance(raw_endpoints, (list, tuple)):
            endpoints = [ProxyEndpoint.from_dict(item) for item in raw_endpoints]
        strategy = str(payload.get("strategy") or "round_robin")
        if strategy not in SUPPORTED_POOL_STRATEGIES:
            strategy = "round_robin"
        return cls(
            enabled=bool(payload.get("enabled", False)),
            provider=str(payload.get("provider") or "static"),
            strategy=strategy,
            endpoints=tuple(endpoints),
            domain_affinity=bool(payload.get("domain_affinity", True)),
            max_failures=_bounded_int(payload.get("max_failures"), default=3, minimum=1, maximum=100),
        )

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.enabled:
            return errors
        if not self.endpoints:
            errors.append("proxy pool enabled but no endpoints configured")
        for endpoint in self.endpoints:
            errors.extend(endpoint.validate())
        return errors

    def to_safe_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "provider": self.provider,
            "strategy": self.strategy,
            "domain_affinity": self.domain_affinity,
            "max_failures": self.max_failures,
            "endpoints": [endpoint.to_safe_dict() for endpoint in self.endpoints],
        }


@dataclass(frozen=True)
class ProxySelection:
    """One proxy selection decision."""

    proxy_url: str = ""
    source: str = "none"
    label: str = ""
    provider: str = ""
    strategy: str = ""
    errors: tuple[str, ...] = ()

    def to_safe_dict(self) -> dict[str, Any]:
        return {
            "selected": bool(self.proxy_url),
            "proxy": redact_proxy_url(self.proxy_url),
            "source": self.source,
            "label": self.label,
            "provider": self.provider,
            "strategy": self.strategy,
            "errors": list(self.errors),
        }


@runtime_checkable
class ProxyPoolProvider(Protocol):
    """Provider interface for future paid/API-backed proxy pools."""

    def select(self, target_url: str, *, now: float = 0.0) -> ProxySelection:
        ...

    def report_result(self, proxy_url: str, *, ok: bool, error: str = "", now: float = 0.0) -> None:
        ...

    def to_safe_dict(self) -> dict[str, Any]:
        ...


class StaticProxyPoolProvider:
    """In-memory static proxy pool with deterministic rotation."""

    def __init__(self, config: ProxyPoolConfig | dict[str, Any] | None = None) -> None:
        self.config = ProxyPoolConfig.from_dict(config)
        self._cycle = itertools.count()
        self._domain_sticky: dict[str, str] = {}
        self._failures: dict[str, int] = {}
        self._last_errors: dict[str, str] = {}

    def select(self, target_url: str, *, now: float = 0.0) -> ProxySelection:
        errors = tuple(self.config.validate())
        if not self.config.enabled:
            return ProxySelection(source="pool_disabled", errors=errors)
        if errors:
            return ProxySelection(source="pool_error", provider=self.config.provider, strategy=self.config.strategy, errors=errors)

        domain = (urlparse(target_url).hostname or "").lower()
        available = self._available_endpoints(now)
        if not available:
            return ProxySelection(
                source="pool_empty",
                provider=self.config.provider,
                strategy=self.config.strategy,
                errors=("no available proxy endpoints",),
            )

        if self.config.strategy == "domain_sticky" and self.config.domain_affinity and domain:
            sticky_url = self._domain_sticky.get(domain)
            sticky = next((endpoint for endpoint in available if endpoint.url == sticky_url), None)
            if sticky:
                return self._selection_for(sticky, "pool_domain_sticky")
            selected = self._round_robin(available)
            self._domain_sticky[domain] = selected.url
            return self._selection_for(selected, "pool_domain_sticky")

        if self.config.strategy == "first_healthy":
            return self._selection_for(available[0], "pool_first_healthy")

        return self._selection_for(self._round_robin(available), "pool_round_robin")

    def report_result(self, proxy_url: str, *, ok: bool, error: str = "", now: float = 0.0) -> None:
        if not proxy_url:
            return
        if ok:
            self._failures[proxy_url] = 0
            self._last_errors.pop(proxy_url, None)
        else:
            self._failures[proxy_url] = self._failures.get(proxy_url, 0) + 1
            self._last_errors[proxy_url] = str(error or "proxy failure")[:200]

    def to_safe_dict(self) -> dict[str, Any]:
        payload = self.config.to_safe_dict()
        payload["runtime"] = {
            "failure_counts": {
                redact_proxy_url(url): count for url, count in self._failures.items()
            },
            "last_errors": {
                redact_proxy_url(url): error for url, error in self._last_errors.items()
            },
        }
        return payload

    def _available_endpoints(self, now: float) -> list[ProxyEndpoint]:
        result: list[ProxyEndpoint] = []
        for endpoint in self.config.endpoints:
            if not endpoint.is_available(now):
                continue
            failures = self._failures.get(endpoint.url, endpoint.failure_count)
            if failures >= self.config.max_failures:
                continue
            result.extend([endpoint] * max(endpoint.weight, 1))
        return result

    def _round_robin(self, endpoints: list[ProxyEndpoint]) -> ProxyEndpoint:
        index = next(self._cycle) % len(endpoints)
        return endpoints[index]

    def _selection_for(self, endpoint: ProxyEndpoint, source: str) -> ProxySelection:
        return ProxySelection(
            proxy_url=endpoint.url,
            source=source,
            label=endpoint.label,
            provider=self.config.provider,
            strategy=self.config.strategy,
        )


def redact_proxy_url(proxy_url: str) -> str:
    """Redact proxy credentials without importing proxy_manager."""
    if not proxy_url:
        return ""
    parsed = urlparse(proxy_url)
    if not parsed.username and not parsed.password:
        return proxy_url
    host = parsed.hostname or ""
    if parsed.port:
        host = f"{host}:{parsed.port}"
    return f"{parsed.scheme}://***:***@{host}{parsed.path or ''}"


def _bounded_int(value: Any, *, default: int, minimum: int, maximum: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, number))


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
