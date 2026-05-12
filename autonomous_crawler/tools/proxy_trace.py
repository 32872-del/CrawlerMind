"""Lightweight proxy trace for evidence chains (CAP-3.3 / CAP-6.2).

Produces redacted, composable proxy selection + health snapshots that can
be embedded in fetch traces, runner summaries, or audit logs.

All output is credential-safe — no plaintext proxy passwords, tokens,
or usernames are ever emitted.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

from .proxy_pool import ProxySelection, redact_proxy_url


# ---------------------------------------------------------------------------
# Error redaction
# ---------------------------------------------------------------------------

# Patterns that might leak proxy URLs or credentials in error messages
_PROXY_URL_PATTERN = re.compile(
    r"(https?|socks5)://([^/\s@]*@)?([^/\s]+)(/[^\s]*)?",
    re.IGNORECASE,
)
_KEY_VALUE_PATTERN = re.compile(
    r"(password|token|secret|auth|credential|api_key|apikey)"
    r"\s*[:=]\s*\S+",
    re.IGNORECASE,
)


def redact_error_message(message: str) -> str:
    """Redact proxy URLs and key=value secrets from an error string."""
    if not message:
        return ""
    result = _PROXY_URL_PATTERN.sub("[redacted_url]", message)
    result = _KEY_VALUE_PATTERN.sub(r"\1=[redacted]", result)
    return result


# ---------------------------------------------------------------------------
# ProxyTrace
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ProxyTrace:
    """Redacted snapshot of a proxy selection decision + optional health state.

    Designed to be embedded in fetch traces, ``ItemProcessResult.metrics``,
    or runner summaries without leaking credentials.
    """

    selected: bool = False
    proxy: str = ""              # redacted URL or ""
    source: str = "none"         # per_domain | pool_round_robin | default | disabled | …
    provider: str = ""           # static | brightdata | …
    strategy: str = ""           # round_robin | domain_sticky | first_healthy
    health: dict[str, Any] = field(default_factory=dict)
    errors: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a credential-safe dict."""
        result: dict[str, Any] = {
            "selected": self.selected,
            "proxy": self.proxy,
            "source": self.source,
        }
        if self.provider:
            result["provider"] = self.provider
        if self.strategy:
            result["strategy"] = self.strategy
        if self.health:
            result["health"] = dict(self.health)
        if self.errors:
            result["errors"] = list(self.errors)
        return result

    # ------------------------------------------------------------------
    # Factory methods
    # ------------------------------------------------------------------

    @classmethod
    def disabled(cls) -> ProxyTrace:
        """Trace for when proxy is not enabled."""
        return cls(source="disabled")

    @classmethod
    def from_selection(
        cls,
        selection: ProxySelection,
        *,
        health_store: Any | None = None,
        now: float = 0.0,
    ) -> ProxyTrace:
        """Build trace from a ``ProxySelection`` + optional health store."""
        health: dict[str, Any] = {}
        if health_store is not None and selection.proxy_url:
            record = health_store.get(selection.proxy_url)
            if record:
                in_cooldown = record["cooldown_until"] > now
                health = {
                    "success_count": record["success_count"],
                    "failure_count": record["failure_count"],
                    "in_cooldown": in_cooldown,
                }
                if in_cooldown:
                    health["cooldown_until"] = record["cooldown_until"]
                if record["last_error"]:
                    health["last_error"] = redact_error_message(record["last_error"])
        return cls(
            selected=bool(selection.proxy_url),
            proxy=redact_proxy_url(selection.proxy_url),
            source=selection.source,
            provider=selection.provider,
            strategy=selection.strategy,
            health=health,
            errors=tuple(selection.errors),
        )

    @classmethod
    def from_manager(
        cls,
        manager: Any,
        target_url: str,
        *,
        health_store: Any | None = None,
        now: float = 0.0,
    ) -> ProxyTrace:
        """Build trace by asking a ``ProxyManager`` to select + describe.

        This is the highest-level factory — it uses ``manager.describe_selection()``
        for the redacted selection info, then enriches it with health store data.

        When *health_store* is provided, the pool provider's health store is
        temporarily set so that ``_available_endpoints()`` respects cooldown
        during selection.  The previous value is restored after the call.
        """
        # Temporarily wire health store into pool provider for cooldown-aware selection
        pool_provider = getattr(manager, "pool_provider", None)
        prev_health = None
        if health_store is not None and pool_provider is not None and hasattr(pool_provider, "set_health_store"):
            prev_health = getattr(pool_provider, "_health_store", None)
            pool_provider.set_health_store(health_store)

        try:
            desc = manager.describe_selection(target_url)
        finally:
            # Restore previous health store
            if health_store is not None and pool_provider is not None and hasattr(pool_provider, "set_health_store"):
                pool_provider.set_health_store(prev_health)

        if not desc.get("enabled", False):
            return cls.disabled()

        # Enrich with health store record for the selected proxy
        health: dict[str, Any] = {}
        if health_store is not None and desc.get("selected"):
            raw_url = manager.select_proxy(target_url)
            if raw_url:
                record = health_store.get(raw_url)
                if record:
                    in_cooldown = record["cooldown_until"] > now
                    health = {
                        "success_count": record["success_count"],
                        "failure_count": record["failure_count"],
                        "in_cooldown": in_cooldown,
                    }
                    if in_cooldown:
                        health["cooldown_until"] = record["cooldown_until"]
                    if record["last_error"]:
                        health["last_error"] = redact_error_message(record["last_error"])

        pool_info = desc.get("pool", {})
        return cls(
            selected=desc.get("selected", False),
            proxy=desc.get("proxy", ""),
            source=desc.get("source", "none"),
            provider=pool_info.get("provider", ""),
            strategy=pool_info.get("strategy", ""),
            health=health,
            errors=tuple(desc.get("errors", ())),
        )


# ---------------------------------------------------------------------------
# Health store summary (aggregate, no individual proxy identity)
# ---------------------------------------------------------------------------

def health_store_summary(
    health_store: Any,
    *,
    now: float = 0.0,
) -> dict[str, Any]:
    """Aggregate health store stats — safe for runner summaries.

    Does NOT expose individual proxy URLs or proxy_ids.
    """
    records = health_store.get_all()
    total = len(records)
    if total == 0:
        return {"tracked_proxies": 0, "healthy": 0, "in_cooldown": 0, "total_failures": 0}

    in_cooldown = 0
    total_failures = 0
    for record in records:
        total_failures += record["failure_count"]
        if record["cooldown_until"] > now:
            in_cooldown += 1

    return {
        "tracked_proxies": total,
        "healthy": total - in_cooldown,
        "in_cooldown": in_cooldown,
        "total_failures": total_failures,
    }
