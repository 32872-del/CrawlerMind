from __future__ import annotations

import unittest

from autonomous_crawler.tools.rate_limiter import DomainRateLimiter
from autonomous_crawler.tools.rate_limit_policy import RateLimitPolicy


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def clock(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


class DomainRateLimiterTests(unittest.TestCase):
    def test_first_request_does_not_sleep(self) -> None:
        fake = FakeClock()
        limiter = DomainRateLimiter(
            RateLimitPolicy.from_dict({"default": {"delay_seconds": 2}}),
            clock=fake.clock,
            sleeper=fake.sleep,
        )

        event = limiter.before_request("https://example.com/a")

        self.assertEqual(event.slept_seconds, 0.0)
        self.assertEqual(fake.sleeps, [])

    def test_second_same_domain_request_sleeps_remaining_delay(self) -> None:
        fake = FakeClock()
        limiter = DomainRateLimiter(
            RateLimitPolicy.from_dict({"default": {"delay_seconds": 2}}),
            clock=fake.clock,
            sleeper=fake.sleep,
        )

        limiter.before_request("https://example.com/a")
        fake.now += 0.5
        event = limiter.before_request("https://example.com/b")

        self.assertEqual(event.slept_seconds, 1.5)
        self.assertEqual(fake.sleeps, [1.5])

    def test_different_domains_are_independent(self) -> None:
        fake = FakeClock()
        limiter = DomainRateLimiter(
            RateLimitPolicy.from_dict({"default": {"delay_seconds": 2}}),
            clock=fake.clock,
            sleeper=fake.sleep,
        )

        limiter.before_request("https://a.example/one")
        event = limiter.before_request("https://b.example/two")

        self.assertEqual(event.slept_seconds, 0.0)

    def test_disabled_limiter_never_sleeps(self) -> None:
        fake = FakeClock()
        limiter = DomainRateLimiter(
            RateLimitPolicy.from_dict({"default": {"delay_seconds": 2}}),
            clock=fake.clock,
            sleeper=fake.sleep,
            enabled=False,
        )

        limiter.before_request("https://example.com/a")
        event = limiter.before_request("https://example.com/b")

        self.assertEqual(event.reason, "disabled")
        self.assertEqual(event.slept_seconds, 0.0)
        self.assertEqual(fake.sleeps, [])


if __name__ == "__main__":
    unittest.main()
