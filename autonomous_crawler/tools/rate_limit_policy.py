"""Per-domain rate limit and retry policy."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse


RETRYABLE_STATUS_CODES = {408, 425, 429, 500, 502, 503, 504}


@dataclass(frozen=True)
class DomainRateRule:
    delay_seconds: float = 1.0
    max_retries: int = 3
    backoff_factor: float = 2.0

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> "DomainRateRule":
        payload = payload or {}
        return cls(
            delay_seconds=max(0.0, float(payload.get("delay_seconds", 1.0))),
            max_retries=max(0, int(payload.get("max_retries", 3))),
            backoff_factor=max(1.0, float(payload.get("backoff_factor", 2.0))),
        )


@dataclass(frozen=True)
class RateLimitDecision:
    domain: str
    delay_seconds: float
    max_retries: int
    should_retry: bool
    reason: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "domain": self.domain,
            "delay_seconds": self.delay_seconds,
            "max_retries": self.max_retries,
            "should_retry": self.should_retry,
            "reason": self.reason,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class RateLimitPolicy:
    default_rule: DomainRateRule = field(default_factory=DomainRateRule)
    per_domain: dict[str, DomainRateRule] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> "RateLimitPolicy":
        payload = payload or {}
        per_domain = payload.get("per_domain") or {}
        rules = {
            str(domain).lower(): DomainRateRule.from_dict(rule if isinstance(rule, dict) else {})
            for domain, rule in per_domain.items()
        } if isinstance(per_domain, dict) else {}
        return cls(
            default_rule=DomainRateRule.from_dict(payload.get("default") if isinstance(payload.get("default"), dict) else {}),
            per_domain=rules,
        )

    def rule_for(self, url: str) -> tuple[str, DomainRateRule]:
        domain = (urlparse(url).hostname or "").lower()
        if domain in self.per_domain:
            return domain, self.per_domain[domain]
        parts = domain.split(".")
        for index in range(1, max(len(parts) - 1, 1)):
            wildcard = "*." + ".".join(parts[index:])
            if wildcard in self.per_domain:
                return domain, self.per_domain[wildcard]
        return domain, self.default_rule

    def decide(
        self,
        url: str,
        *,
        attempt: int = 0,
        status_code: int | None = None,
        error: str = "",
        robots_directives: Any = None,
    ) -> RateLimitDecision:
        domain, rule = self.rule_for(url)
        retryable = bool(error) or bool(status_code in RETRYABLE_STATUS_CODES)
        should_retry = retryable and attempt < rule.max_retries
        delay = rule.delay_seconds
        metadata: dict[str, Any] = {}
        robots_delay = getattr(robots_directives, "crawl_delay_seconds", None)
        if robots_delay is not None:
            delay = max(delay, max(0.0, float(robots_delay)))
            metadata["robots_crawl_delay_seconds"] = float(robots_delay)
        request_rate = getattr(robots_directives, "request_rate", None)
        if request_rate:
            metadata["robots_request_rate"] = list(request_rate)
        robots_source = getattr(robots_directives, "source_url", "")
        if robots_source:
            metadata["robots_source_url"] = str(robots_source)
        robots_mode = getattr(robots_directives, "mode", "")
        if robots_mode:
            metadata["robots_mode"] = str(robots_mode)
        if should_retry and attempt > 0:
            delay = delay * (rule.backoff_factor ** attempt)
        if status_code == 429:
            reason = "rate_limited"
        elif error:
            reason = "transport_error"
        elif metadata:
            reason = "robots_metadata"
        elif retryable:
            reason = f"retryable_status:{status_code}"
        else:
            reason = "standard"
        return RateLimitDecision(
            domain=domain,
            delay_seconds=round(delay, 3),
            max_retries=rule.max_retries,
            should_retry=should_retry,
            reason=reason,
            metadata=metadata,
        )
