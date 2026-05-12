"""Executable per-domain rate limiting.

`RateLimitPolicy` decides the desired delay/backoff. This module enforces the
delay in a testable way by accepting injectable clock and sleeper callables.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import threading
import time
from typing import Any

from .rate_limit_policy import RateLimitDecision, RateLimitPolicy


Clock = Callable[[], float]
Sleeper = Callable[[float], None]


@dataclass(frozen=True)
class RateLimitEvent:
    domain: str
    requested_delay_seconds: float
    slept_seconds: float
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "domain": self.domain,
            "requested_delay_seconds": self.requested_delay_seconds,
            "slept_seconds": self.slept_seconds,
            "reason": self.reason,
        }


class DomainRateLimiter:
    """Enforce per-domain spacing between requests."""

    def __init__(
        self,
        policy: RateLimitPolicy | dict[str, Any] | None = None,
        *,
        clock: Clock | None = None,
        sleeper: Sleeper | None = None,
        enabled: bool = True,
    ) -> None:
        self.policy = policy if isinstance(policy, RateLimitPolicy) else RateLimitPolicy.from_dict(policy)
        self.clock = clock or time.monotonic
        self.sleeper = sleeper or time.sleep
        self.enabled = enabled
        self._last_request_at: dict[str, float] = {}
        self._lock = threading.Lock()

    def before_request(self, url: str, *, reason: str = "standard") -> RateLimitEvent:
        decision = self.policy.decide(url)
        if not self.enabled:
            return RateLimitEvent(
                domain=decision.domain,
                requested_delay_seconds=decision.delay_seconds,
                slept_seconds=0.0,
                reason="disabled",
            )

        sleep_for = self._compute_sleep(decision)
        if sleep_for > 0:
            self.sleeper(sleep_for)

        with self._lock:
            self._last_request_at[decision.domain] = self.clock()

        return RateLimitEvent(
            domain=decision.domain,
            requested_delay_seconds=decision.delay_seconds,
            slept_seconds=round(sleep_for, 3),
            reason=reason,
        )

    def _compute_sleep(self, decision: RateLimitDecision) -> float:
        now = self.clock()
        with self._lock:
            last = self._last_request_at.get(decision.domain)
        if last is None:
            return 0.0
        elapsed = max(0.0, now - last)
        return round(max(0.0, decision.delay_seconds - elapsed), 3)


_GLOBAL_LIMITERS: dict[str, DomainRateLimiter] = {}
_GLOBAL_LOCK = threading.Lock()


def global_rate_limiter(policy: RateLimitPolicy) -> DomainRateLimiter:
    """Return a shared limiter for a policy shape.

    This keeps simple fetch paths from creating a fresh limiter per call while
    remaining deterministic for tests that pass their own limiter.
    """
    key = repr(policy)
    with _GLOBAL_LOCK:
        limiter = _GLOBAL_LIMITERS.get(key)
        if limiter is None:
            limiter = DomainRateLimiter(policy)
            _GLOBAL_LIMITERS[key] = limiter
        return limiter
