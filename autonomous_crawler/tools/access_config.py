"""Unified Access Layer configuration resolver.

CLM accepts access configuration from workflow state, recon constraints, and
eventually CLI/FastAPI/frontend inputs. This module normalizes those inputs into
typed objects and safe summaries so crawler tools do not each invent their own
merge and redaction behavior.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .browser_context import BrowserContextConfig
from .proxy_manager import ProxyConfig, ProxyManager
from .rate_limit_policy import RateLimitPolicy
from .session_profile import SessionProfile


@dataclass(frozen=True)
class AccessConfig:
    session_profile: SessionProfile = field(default_factory=SessionProfile)
    proxy: ProxyConfig = field(default_factory=ProxyConfig)
    rate_limit: RateLimitPolicy = field(default_factory=RateLimitPolicy)
    browser_context: BrowserContextConfig = field(default_factory=BrowserContextConfig)
    source_keys: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | "AccessConfig" | None) -> "AccessConfig":
        if isinstance(payload, AccessConfig):
            return payload
        payload = payload or {}
        return cls(
            session_profile=payload.get("session_profile")
            if isinstance(payload.get("session_profile"), SessionProfile)
            else SessionProfile.from_dict(payload.get("session_profile")),
            proxy=payload.get("proxy")
            if isinstance(payload.get("proxy"), ProxyConfig)
            else ProxyConfig.from_dict(payload.get("proxy")),
            rate_limit=payload.get("rate_limit")
            if isinstance(payload.get("rate_limit"), RateLimitPolicy)
            else RateLimitPolicy.from_dict(payload.get("rate_limit")),
            browser_context=payload.get("browser_context")
            if isinstance(payload.get("browser_context"), BrowserContextConfig)
            else BrowserContextConfig.from_dict(payload.get("browser_context")),
            source_keys=sorted(str(key) for key in payload.keys()),
        )

    def has_authorized_session_for(self, url: str) -> bool:
        if not self.session_profile.headers and not self.session_profile.cookies and not self.session_profile.storage_state_path:
            return False
        return self.session_profile.applies_to(url)

    def proxy_for(self, url: str) -> str:
        return ProxyManager(self.proxy).select_proxy(url)

    def validation_errors(self) -> list[str]:
        return [
            *self.session_profile.validate(),
            *self.proxy.validate(),
        ]

    def to_safe_dict(self, url: str = "") -> dict[str, Any]:
        proxy_manager = ProxyManager(self.proxy)
        return {
            "session_profile": self.session_profile.to_safe_dict(),
            "proxy": proxy_manager.describe_selection(url) if url else self.proxy.to_safe_dict(),
            "rate_limit": self.rate_limit.decide(url).to_dict() if url else {},
            "browser_context": self.browser_context.to_safe_dict(),
            "source_keys": list(self.source_keys),
            "errors": self.validation_errors(),
        }

    def to_fetch_kwargs(self) -> dict[str, Any]:
        return {
            "session_profile": self.session_profile,
            "proxy_config": self.proxy,
            "rate_limit_policy": self.rate_limit,
            "browser_options": {"browser_context": self.browser_context},
        }


def resolve_access_config(
    state: dict[str, Any] | None = None,
    recon_report: dict[str, Any] | None = None,
) -> AccessConfig:
    """Merge access config from recon constraints first, then state overrides."""
    state = state or {}
    recon_report = recon_report or {}
    constraints = recon_report.get("constraints") or {}
    merged: dict[str, Any] = {}
    for source in (constraints.get("access_config"), state.get("access_config")):
        if isinstance(source, dict):
            merged = _deep_merge(merged, source)
    return AccessConfig.from_dict(merged)


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result
