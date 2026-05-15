"""CLM-native browser context pool for session reuse and profile management.

This module provides context leasing so that multiple requests sharing the same
browser profile can reuse a single browser instance and context, reducing launch
overhead and preserving session state (cookies, localStorage) across requests.

It does NOT import Scrapling.  All browser lifecycle is handled via Playwright.
"""
from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .models import RuntimeArtifact


# ---------------------------------------------------------------------------
# Browser profile identity
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BrowserProfile:
    """Configurable browser profile identity for rotation and reuse.

    Each field contributes to the pool fingerprint.  Profiles with identical
    field sets share a context; profiles with different fields get separate
    contexts.  This lets callers rotate across user agents, viewports, locales,
    and protection modes without manual fingerprint management.
    """

    profile_id: str
    user_agent: str = ""
    viewport: str = ""
    locale: str = "en-US"
    timezone: str = "UTC"
    color_scheme: str = "light"
    storage_state_mode: str = "ephemeral"
    block_resource_types: tuple[str, ...] = ()
    protected_mode: bool = False
    headless: bool = True
    channel: str = ""
    proxy_url: str = ""

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | BrowserProfile | None) -> BrowserProfile | None:
        if payload is None:
            return None
        if isinstance(payload, BrowserProfile):
            return payload
        profile_id = str(payload.get("profile_id") or "")
        if not profile_id:
            return None
        return cls(
            profile_id=profile_id,
            user_agent=str(payload.get("user_agent") or ""),
            viewport=str(payload.get("viewport") or ""),
            locale=str(payload.get("locale") or "en-US"),
            timezone=str(payload.get("timezone") or "UTC"),
            color_scheme=str(payload.get("color_scheme") or "light"),
            storage_state_mode=str(payload.get("storage_state_mode") or "ephemeral"),
            block_resource_types=tuple(payload.get("block_resource_types") or ()),
            protected_mode=bool(payload.get("protected_mode", False)),
            headless=bool(payload.get("headless", True)),
            channel=str(payload.get("channel") or ""),
            proxy_url=str(payload.get("proxy_url") or ""),
        )

    def to_context_options(self) -> dict[str, Any]:
        """Convert profile fields to BrowserContextConfig-compatible options."""
        viewport_parts = self.viewport.split("x") if self.viewport and "x" in self.viewport else []
        viewport_dict = {}
        if len(viewport_parts) == 2:
            try:
                viewport_dict = {"width": int(viewport_parts[0]), "height": int(viewport_parts[1])}
            except ValueError:
                pass
        return {
            "user_agent": self.user_agent or None,
            "viewport": viewport_dict or None,
            "locale": self.locale,
            "timezone_id": self.timezone,
            "color_scheme": self.color_scheme,
            "java_script_enabled": True,
        }

    def to_launch_options(self) -> dict[str, Any]:
        """Convert profile fields to Playwright launch options."""
        options: dict[str, Any] = {"headless": self.headless}
        if self.proxy_url:
            options["proxy"] = self.proxy_url
        if self.channel:
            options["channel"] = self.channel
        if self.protected_mode:
            options["args"] = [
                "--disable-blink-features=AutomationControlled",
                "--disable-features=IsolateOrigins,site-per-process",
            ]
        return options

    def to_safe_dict(self) -> dict[str, Any]:
        """Credential-safe representation for engine_result evidence."""
        return {
            "profile_id": self.profile_id,
            "user_agent": self.user_agent[:80] + "..." if len(self.user_agent) > 80 else self.user_agent,
            "viewport": self.viewport,
            "locale": self.locale,
            "timezone": self.timezone,
            "color_scheme": self.color_scheme,
            "storage_state_mode": self.storage_state_mode,
            "protected_mode": self.protected_mode,
            "headless": self.headless,
            "channel": self.channel,
            "has_proxy": bool(self.proxy_url),
            "block_resource_types": list(self.block_resource_types),
        }


class BrowserProfileRotator:
    """Round-robin profile rotation for anti-detection diversity.

    Maintains a list of profiles and cycles through them on each request.
    Integrates with BrowserPoolManager via fingerprint-based context reuse.
    """

    def __init__(self, profiles: list[BrowserProfile | dict[str, Any]]) -> None:
        self._profiles: list[BrowserProfile] = []
        for p in profiles:
            if isinstance(p, BrowserProfile):
                self._profiles.append(p)
            else:
                profile = BrowserProfile.from_dict(p)
                if profile is not None:
                    self._profiles.append(profile)
        self._index = 0

    @property
    def profile_count(self) -> int:
        return len(self._profiles)

    def next_profile(self) -> BrowserProfile | None:
        """Return the next profile in round-robin rotation."""
        if not self._profiles:
            return None
        profile = self._profiles[self._index % len(self._profiles)]
        self._index += 1
        return profile

    def current_profile(self) -> BrowserProfile | None:
        """Return the most recently selected profile."""
        if not self._profiles:
            return None
        return self._profiles[(self._index - 1) % len(self._profiles)]

    def to_safe_dict(self) -> dict[str, Any]:
        return {
            "profile_count": self.profile_count,
            "current_index": self._index,
            "profiles": [p.to_safe_dict() for p in self._profiles],
        }


@dataclass(frozen=True)
class BrowserPoolConfig:
    """Configuration for the browser context pool."""

    max_contexts: int = 8
    max_requests_per_context: int = 50
    max_context_age_seconds: int = 1800
    keepalive_on_release: bool = True

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | BrowserPoolConfig | None) -> BrowserPoolConfig:
        if isinstance(payload, BrowserPoolConfig):
            return payload
        payload = payload or {}
        return cls(
            max_contexts=_bounded_int(payload.get("max_contexts"), default=8, minimum=1, maximum=64),
            max_requests_per_context=_bounded_int(
                payload.get("max_requests_per_context"), default=50, minimum=1, maximum=10000
            ),
            max_context_age_seconds=_bounded_int(
                payload.get("max_context_age_seconds"), default=1800, minimum=60, maximum=86400
            ),
            keepalive_on_release=bool(payload.get("keepalive_on_release", True)),
        )

    def to_safe_dict(self) -> dict[str, Any]:
        return {
            "max_contexts": self.max_contexts,
            "max_requests_per_context": self.max_requests_per_context,
            "max_context_age_seconds": self.max_context_age_seconds,
            "keepalive_on_release": self.keepalive_on_release,
        }


@dataclass
class BrowserContextLease:
    """A leased browser context within the pool."""

    profile_id: str
    context: Any
    browser: Any = None
    session_mode: str = "ephemeral"
    fingerprint: str = ""
    user_data_dir: str = ""
    created_at: float = field(default_factory=time.time)
    request_count: int = 0

    def record_use(self) -> None:
        self.request_count += 1

    def export_storage_state(self, path: str) -> str:
        if not path:
            return ""
        output_path = Path(path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self.context.storage_state(path=str(output_path))
            return str(output_path)
        except Exception:
            return ""

    def age_seconds(self) -> float:
        return time.time() - self.created_at


class BrowserPoolManager:
    """Pool of reusable Playwright browser contexts."""

    def __init__(self, config: BrowserPoolConfig | dict[str, Any] | None = None) -> None:
        self._config = BrowserPoolConfig.from_dict(config)
        self._leases: dict[str, BrowserContextLease] = {}
        self._events: list[dict[str, Any]] = []

    @property
    def config(self) -> BrowserPoolConfig:
        return self._config

    def compute_fingerprint(
        self,
        context_options: dict[str, Any],
        launch_options: dict[str, Any],
        session_mode: str,
        user_data_dir: str = "",
    ) -> str:
        """Compute a deterministic fingerprint for a browser profile."""
        parts = [
            f"mode:{session_mode}",
            f"ua:{context_options.get('user_agent', '')}",
            f"vp:{context_options.get('viewport', '')}",
            f"loc:{context_options.get('locale', '')}",
            f"tz:{context_options.get('timezone_id', '')}",
            f"cs:{context_options.get('color_scheme', '')}",
            f"js:{context_options.get('java_script_enabled', '')}",
            f"head:{launch_options.get('headless', '')}",
            f"proxy:{launch_options.get('proxy', '')}",
            f"chan:{launch_options.get('channel', '')}",
            f"exe:{launch_options.get('executable_path', '')}",
            f"args:{sorted(launch_options.get('args', []))}",
        ]
        if user_data_dir:
            parts.append(f"udd:{user_data_dir}")
        raw = "|".join(str(p) for p in parts)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

    def acquire(
        self,
        profile_id: str,
        fingerprint: str,
        session_mode: str = "ephemeral",
        user_data_dir: str = "",
    ) -> BrowserContextLease:
        """Acquire a context lease for the given profile.

        Returns an existing lease if one matches the fingerprint and is healthy,
        otherwise returns a new (un-initialized) lease that the caller must
        populate with a real browser and context.
        """
        existing = self._leases.get(profile_id)
        if existing is not None and self._can_reuse(existing, fingerprint):
            self._record_event("pool_reuse", profile_id, fingerprint=fingerprint)
            return existing

        self._evict_if_full()
        lease = BrowserContextLease(
            profile_id=profile_id,
            context=None,
            browser=None,
            session_mode=session_mode,
            fingerprint=fingerprint,
            user_data_dir=user_data_dir,
        )
        self._leases[profile_id] = lease
        self._record_event("pool_acquire", profile_id, fingerprint=fingerprint)
        return lease

    def release(self, profile_id: str) -> None:
        """Release a context lease.

        If keepalive is enabled and the context is healthy, the context is kept
        in the pool for reuse.  Otherwise it is closed and removed.
        """
        lease = self._leases.get(profile_id)
        if lease is None:
            return
        if not self._config.keepalive_on_release or not self._is_healthy(lease):
            self._close_lease(lease)
            del self._leases[profile_id]
            self._record_event("pool_release", profile_id, reason="closed")
        else:
            self._record_event("pool_release", profile_id, reason="keepalive")

    def mark_failed(self, profile_id: str, error: str = "") -> None:
        """Mark a context as failed and remove it from the pool.

        Call this when a navigation, selector wait, or other browser operation
        fails so the bad context is not reused blindly.
        """
        lease = self._leases.pop(profile_id, None)
        if lease is None:
            return
        self._close_lease(lease)
        self._record_event("pool_mark_failed", profile_id, error=error[:200])

    def close_all(self) -> None:
        """Close and remove all leases."""
        for lease in list(self._leases.values()):
            self._close_lease(lease)
        self._leases.clear()

    @property
    def active_count(self) -> int:
        return len(self._leases)

    def to_safe_dict(self) -> dict[str, Any]:
        return {
            "config": self._config.to_safe_dict(),
            "active_count": self.active_count,
            "leases": [
                {
                    "profile_id": lease.profile_id,
                    "session_mode": lease.session_mode,
                    "fingerprint": lease.fingerprint,
                    "user_data_dir": _redact_path(lease.user_data_dir),
                    "request_count": lease.request_count,
                    "age_seconds": round(lease.age_seconds(), 1),
                }
                for lease in self._leases.values()
            ],
            "events": list(self._events),
        }

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _can_reuse(self, lease: BrowserContextLease, fingerprint: str) -> bool:
        if lease.fingerprint != fingerprint:
            return False
        if lease.context is None:
            return False
        if not self._is_healthy(lease):
            return False
        return True

    def _is_healthy(self, lease: BrowserContextLease) -> bool:
        if lease.request_count >= self._config.max_requests_per_context:
            return False
        if lease.age_seconds() > self._config.max_context_age_seconds:
            return False
        return True

    def _evict_if_full(self) -> None:
        if len(self._leases) < self._config.max_contexts:
            return
        oldest_id = min(
            self._leases,
            key=lambda pid: self._leases[pid].created_at,
        )
        self._close_lease(self._leases[oldest_id])
        del self._leases[oldest_id]
        self._record_event("pool_evict", oldest_id, reason="pool_full")

    def _close_lease(self, lease: BrowserContextLease) -> None:
        try:
            if lease.context is not None:
                lease.context.close()
        except Exception:
            pass
        try:
            if lease.browser is not None:
                lease.browser.close()
        except Exception:
            pass

    def _record_event(self, event_type: str, profile_id: str, **data: Any) -> None:
        self._events.append({
            "type": event_type,
            "profile_id": profile_id,
            "timestamp": time.time(),
            **data,
        })


def _redact_path(path: str) -> str:
    if not path:
        return ""
    name = Path(path).name
    return f"[redacted-path]/{name}" if name else "[redacted-path]"


def _bounded_int(value: Any, *, default: int, minimum: int, maximum: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, number))
