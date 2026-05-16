"""CLM-native browser context pool for session reuse and profile management.

This module provides context leasing so that multiple requests sharing the same
browser profile can reuse a single browser instance and context, reducing launch
overhead and preserving session state (cookies, localStorage) across requests.

It does NOT import Scrapling.  All browser lifecycle is handled via Playwright.
"""
from __future__ import annotations

import hashlib
import json
import time
from collections import deque
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


@dataclass
class WindowedHealthRecord:
    """A single request outcome record with timestamp for windowed scoring."""
    timestamp: float
    ok: bool
    elapsed_seconds: float
    failure_category: str = "none"


@dataclass
class BrowserProfileHealth:
    """Mutable health tracker for a single BrowserProfile.

    Records success/failure/timeout/challenge/http_blocked counts and
    computes a health score in [0.0, 1.0] where 1.0 is perfectly healthy.

    Supports two scoring modes:
    - cumulative: uses all-time counters (legacy behavior)
    - windowed: uses only records within `window_seconds` (default 300s)
      so old failures decay away and profiles can recover.

    The `health_score` property uses windowed scoring when windowed records
    are available, falling back to cumulative otherwise.
    """

    profile_id: str
    total_requests: int = 0
    success_count: int = 0
    failure_count: int = 0
    timeout_count: int = 0
    challenge_count: int = 0
    http_blocked_count: int = 0
    total_elapsed_seconds: float = 0.0
    last_failure_category: str = ""
    # Windowed tracking
    window_seconds: float = 300.0
    _records: deque[WindowedHealthRecord] = field(default_factory=lambda: deque(maxlen=500))

    @property
    def avg_elapsed_seconds(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return self.total_elapsed_seconds / self.total_requests

    @property
    def success_rate(self) -> float:
        if self.total_requests == 0:
            return 1.0  # unknown → assume healthy
        return self.success_count / self.total_requests

    def _windowed_records(self) -> list[WindowedHealthRecord]:
        """Return records within the time window."""
        if not self._records:
            return []
        cutoff = time.time() - self.window_seconds
        return [r for r in self._records if r.timestamp >= cutoff]

    def _windowed_health_score(self) -> float:
        """Compute health score from windowed records only."""
        records = self._windowed_records()
        if not records:
            return 1.0  # no recent data → assume healthy
        total = len(records)
        successes = sum(1 for r in records if r.ok)
        timeouts = sum(1 for r in records if r.failure_category == "navigation_timeout")
        challenges = sum(1 for r in records if r.failure_category in {"challenge_like", "managed_challenge", "captcha"})
        blocked = sum(1 for r in records if r.failure_category == "http_blocked")
        base = successes / total
        timeout_penalty = min(timeouts * 0.1, 0.3)
        challenge_penalty = min(challenges * 0.15, 0.3)
        blocked_penalty = min(blocked * 0.05, 0.15)
        return max(0.0, base - timeout_penalty - challenge_penalty - blocked_penalty)

    @property
    def health_score(self) -> float:
        """Score in [0.0, 1.0]. Uses windowed scoring when records exist."""
        if self._records:
            return self._windowed_health_score()
        # Fallback to cumulative (backward compat for pre-window data)
        if self.total_requests == 0:
            return 1.0
        base = self.success_rate
        timeout_penalty = min(self.timeout_count * 0.1, 0.3)
        challenge_penalty = min(self.challenge_count * 0.15, 0.3)
        blocked_penalty = min(self.http_blocked_count * 0.05, 0.15)
        return max(0.0, base - timeout_penalty - challenge_penalty - blocked_penalty)

    @property
    def windowed_request_count(self) -> int:
        """Number of records within the current window."""
        return len(self._windowed_records())

    def record(
        self,
        *,
        ok: bool,
        elapsed_seconds: float,
        failure_category: str = "none",
    ) -> None:
        """Record a single request outcome (cumulative + windowed)."""
        self.total_requests += 1
        self.total_elapsed_seconds += elapsed_seconds
        if ok:
            self.success_count += 1
        else:
            self.failure_count += 1
            self.last_failure_category = failure_category
            if failure_category == "navigation_timeout":
                self.timeout_count += 1
            elif failure_category in {"challenge_like", "managed_challenge", "captcha"}:
                self.challenge_count += 1
            elif failure_category == "http_blocked":
                self.http_blocked_count += 1
        # Windowed record
        self._records.append(WindowedHealthRecord(
            timestamp=time.time(),
            ok=ok,
            elapsed_seconds=elapsed_seconds,
            failure_category=failure_category,
        ))

    def health_summary(self) -> dict[str, Any]:
        """Compact summary for run reports."""
        records = self._windowed_records()
        windowed_total = len(records)
        windowed_success = sum(1 for r in records if r.ok)
        windowed_failures: dict[str, int] = {}
        for r in records:
            if not r.ok and r.failure_category != "none":
                windowed_failures[r.failure_category] = windowed_failures.get(r.failure_category, 0) + 1
        return {
            "profile_id": self.profile_id,
            "health_score": round(self.health_score, 3),
            "cumulative": {
                "total_requests": self.total_requests,
                "success_rate": round(self.success_rate, 3),
                "avg_elapsed_seconds": round(self.avg_elapsed_seconds, 3),
            },
            "windowed": {
                "window_seconds": self.window_seconds,
                "request_count": windowed_total,
                "success_count": windowed_success,
                "failure_breakdown": windowed_failures,
            },
            "last_failure_category": self.last_failure_category,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "total_requests": self.total_requests,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "timeout_count": self.timeout_count,
            "challenge_count": self.challenge_count,
            "http_blocked_count": self.http_blocked_count,
            "total_elapsed_seconds": self.total_elapsed_seconds,
            "avg_elapsed_seconds": round(self.avg_elapsed_seconds, 3),
            "success_rate": round(self.success_rate, 3),
            "health_score": round(self.health_score, 3),
            "last_failure_category": self.last_failure_category,
            "window_seconds": self.window_seconds,
            "windowed_request_count": self.windowed_request_count,
        }

    def to_persistable_dict(self) -> dict[str, Any]:
        """Export for JSON/SQLite persistence. Includes windowed records."""
        d = self.to_dict()
        d["_records"] = [
            {"t": r.timestamp, "ok": r.ok, "e": r.elapsed_seconds, "f": r.failure_category}
            for r in self._records
        ]
        return d

    @classmethod
    def from_persistable_dict(cls, data: dict[str, Any]) -> "BrowserProfileHealth":
        """Restore from persisted dict."""
        h = cls(
            profile_id=data["profile_id"],
            total_requests=data.get("total_requests", 0),
            success_count=data.get("success_count", 0),
            failure_count=data.get("failure_count", 0),
            timeout_count=data.get("timeout_count", 0),
            challenge_count=data.get("challenge_count", 0),
            http_blocked_count=data.get("http_blocked_count", 0),
            total_elapsed_seconds=data.get("total_elapsed_seconds", 0.0),
            last_failure_category=data.get("last_failure_category", ""),
            window_seconds=data.get("window_seconds", 300.0),
        )
        for rec in data.get("_records", []):
            h._records.append(WindowedHealthRecord(
                timestamp=rec.get("t", 0),
                ok=rec.get("ok", True),
                elapsed_seconds=rec.get("e", 0.0),
                failure_category=rec.get("f", "none"),
            ))
        return h


class BrowserProfileHealthStore:
    """Lightweight persistence adapter for BrowserProfileHealth.

    Draft implementation — saves/loads health data as JSON files.
    Can be swapped for SQLite later without changing callers.
    """

    def __init__(self, store_dir: str | Path) -> None:
        self._dir = Path(store_dir)
        self._dir.mkdir(parents=True, exist_ok=True)

    def _path_for(self, profile_id: str) -> Path:
        safe_id = profile_id.replace("/", "_").replace("\\", "_")
        return self._dir / f"{safe_id}.json"

    def save(self, health: BrowserProfileHealth) -> None:
        """Persist a single profile's health data."""
        path = self._path_for(health.profile_id)
        path.write_text(json.dumps(health.to_persistable_dict(), indent=2), encoding="utf-8")

    def load(self, profile_id: str) -> BrowserProfileHealth | None:
        """Load a profile's health data. Returns None if not found."""
        path = self._path_for(profile_id)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return BrowserProfileHealth.from_persistable_dict(data)
        except (json.JSONDecodeError, KeyError, TypeError):
            return None

    def save_all(self, health_map: dict[str, BrowserProfileHealth]) -> None:
        """Persist all profiles."""
        for health in health_map.values():
            self.save(health)

    def load_all(self) -> dict[str, BrowserProfileHealth]:
        """Load all persisted profiles."""
        result: dict[str, BrowserProfileHealth] = {}
        for path in self._dir.glob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                health = BrowserProfileHealth.from_persistable_dict(data)
                result[health.profile_id] = health
            except (json.JSONDecodeError, KeyError, TypeError):
                continue
        return result


class BrowserProfileRotator:
    """Profile rotation with optional health-aware selection.

    Maintains a list of profiles and a per-profile health tracker.
    Supports two strategies:
    - "round_robin" (default): cycle through profiles in order
    - "healthiest": pick the profile with the highest health_score
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
        self._health: dict[str, BrowserProfileHealth] = {}

    @property
    def profile_count(self) -> int:
        return len(self._profiles)

    def _get_health(self, profile_id: str) -> BrowserProfileHealth:
        if profile_id not in self._health:
            self._health[profile_id] = BrowserProfileHealth(profile_id=profile_id)
        return self._health[profile_id]

    def next_profile(self, strategy: str = "round_robin") -> BrowserProfile | None:
        """Return the next profile using the given strategy."""
        if not self._profiles:
            return None
        if strategy == "healthiest":
            return self._healthiest_profile()
        # default: round-robin
        profile = self._profiles[self._index % len(self._profiles)]
        self._index += 1
        return profile

    def _healthiest_profile(self) -> BrowserProfile:
        best = self._profiles[0]
        best_score = self._get_health(best.profile_id).health_score
        for p in self._profiles[1:]:
            score = self._get_health(p.profile_id).health_score
            if score > best_score:
                best = p
                best_score = score
        return best

    def update_health(
        self,
        profile_id: str,
        *,
        ok: bool,
        elapsed_seconds: float,
        failure_category: str = "none",
    ) -> None:
        """Feed back a request outcome to the profile's health tracker."""
        health = self._get_health(profile_id)
        health.record(ok=ok, elapsed_seconds=elapsed_seconds, failure_category=failure_category)

    def get_health(self, profile_id: str) -> BrowserProfileHealth:
        """Return the health tracker for a profile (creates if missing)."""
        return self._get_health(profile_id)

    def current_profile(self) -> BrowserProfile | None:
        """Return the most recently selected profile."""
        if not self._profiles:
            return None
        return self._profiles[(self._index - 1) % len(self._profiles)]

    def health_summaries(self) -> dict[str, dict[str, Any]]:
        """Return health summaries for all tracked profiles."""
        return {pid: h.health_summary() for pid, h in self._health.items()}

    def to_safe_dict(self) -> dict[str, Any]:
        return {
            "profile_count": self.profile_count,
            "current_index": self._index,
            "profiles": [p.to_safe_dict() for p in self._profiles],
            "health": {pid: h.to_dict() for pid, h in self._health.items()},
            "health_summaries": self.health_summaries(),
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
