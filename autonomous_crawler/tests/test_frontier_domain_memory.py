from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from autonomous_crawler.storage.domain_memory import DomainMemory
from autonomous_crawler.storage.frontier import URLFrontier


class FrontierTests(unittest.TestCase):
    def test_frontier_add_claim_done(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            frontier = URLFrontier(Path(tmp) / "frontier.sqlite3")
            result = frontier.add_urls(["https://example.com/a", "https://example.com/a", "ftp://bad"])

            self.assertEqual(result, {"added": 1, "skipped": 1, "invalid": 1})
            batch = frontier.next_batch(limit=1, worker_id="test")
            self.assertEqual(len(batch), 1)
            self.assertEqual(batch[0]["status"], "running")
            self.assertEqual(frontier.mark_done([batch[0]["id"]]), 1)
            self.assertEqual(frontier.stats()["done"], 1)

    def test_frontier_failed_retry_requeues(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            frontier = URLFrontier(Path(tmp) / "frontier.sqlite3")
            frontier.add_urls(["https://example.com/a"])
            batch = frontier.next_batch(limit=1)

            frontier.mark_failed([batch[0]["id"]], error="timeout", retry=True)

            self.assertEqual(frontier.stats()["queued"], 1)


class DomainMemoryTests(unittest.TestCase):
    def test_domain_memory_records_success_and_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            memory = DomainMemory(Path(tmp) / "domain.sqlite3")
            memory.record_success("Example.COM", "browser")
            memory.record_failure("example.com", challenge="cf-challenge")

            record = memory.lookup("example.com")
            self.assertEqual(record["preferred_mode"], "browser")
            self.assertEqual(record["last_challenge"], "cf-challenge")
            self.assertEqual(record["success_count"], 1)
            self.assertEqual(record["failure_count"], 1)
            self.assertEqual(memory.stats()["total_domains"], 1)


if __name__ == "__main__":
    unittest.main()
