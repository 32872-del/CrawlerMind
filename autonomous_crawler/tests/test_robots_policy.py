from __future__ import annotations

import unittest

from autonomous_crawler.tools.robots_policy import RobotsPolicyHelper, robots_url_for
from autonomous_crawler.tools.rate_limit_policy import RateLimitPolicy


ROBOTS = """
User-agent: *
Disallow: /private
Crawl-delay: 3
Request-rate: 5/10
"""


class CountingFetcher:
    def __init__(self, text: str = ROBOTS) -> None:
        self.text = text
        self.calls: list[str] = []

    def __call__(self, url: str) -> str:
        self.calls.append(url)
        return self.text


class RobotsPolicyHelperTests(unittest.TestCase):
    def test_robots_url_for(self) -> None:
        self.assertEqual(
            robots_url_for("https://example.com/products/a?x=1"),
            "https://example.com/robots.txt",
        )

    def test_respect_mode_disallows_and_reads_directives(self) -> None:
        fetcher = CountingFetcher()
        helper = RobotsPolicyHelper(mode="respect", fetcher=fetcher)

        private = helper.get_directives("https://example.com/private/page")
        public = helper.get_directives("https://example.com/products/a")

        self.assertFalse(private.can_fetch)
        self.assertTrue(public.can_fetch)
        self.assertEqual(private.crawl_delay_seconds, 3)
        self.assertEqual(private.request_rate, (5, 10))
        self.assertEqual(len(fetcher.calls), 1)

    def test_record_only_records_but_allows(self) -> None:
        helper = RobotsPolicyHelper(mode="record_only", fetcher=CountingFetcher())

        directives = helper.get_directives("https://example.com/private/page")

        self.assertTrue(directives.can_fetch)
        self.assertEqual(directives.mode, "record_only")

    def test_disabled_mode_does_not_fetch(self) -> None:
        fetcher = CountingFetcher()
        helper = RobotsPolicyHelper(mode="disabled", fetcher=fetcher)

        directives = helper.get_directives("https://example.com/private/page")

        self.assertTrue(directives.can_fetch)
        self.assertEqual(fetcher.calls, [])

    def test_fetch_error_allows_with_evidence_error(self) -> None:
        def failing_fetcher(_url: str) -> str:
            raise RuntimeError("network down")

        helper = RobotsPolicyHelper(fetcher=failing_fetcher)

        directives = helper.get_directives("https://example.com/products/a")

        self.assertTrue(directives.can_fetch)
        self.assertIn("network down", directives.error)

    def test_to_events(self) -> None:
        helper = RobotsPolicyHelper(fetcher=CountingFetcher())

        events = helper.to_events("https://example.com/products/a")

        self.assertEqual(events[0].type, "spider.robots_checked")
        self.assertEqual(events[0].data["source_url"], "https://example.com/robots.txt")

    def test_robots_directives_feed_rate_limit_metadata(self) -> None:
        helper = RobotsPolicyHelper(fetcher=CountingFetcher())
        directives = helper.get_directives("https://example.com/products/a")
        policy = RateLimitPolicy.from_dict({"default": {"delay_seconds": 1, "max_retries": 4}})

        decision = policy.decide(
            "https://example.com/products/a",
            robots_directives=directives,
        )

        self.assertEqual(decision.delay_seconds, 3)
        self.assertEqual(decision.reason, "robots_metadata")
        self.assertEqual(decision.metadata["robots_crawl_delay_seconds"], 3.0)
        self.assertEqual(decision.metadata["robots_request_rate"], [5, 10])
        self.assertEqual(decision.metadata["robots_source_url"], "https://example.com/robots.txt")


if __name__ == "__main__":
    unittest.main()
