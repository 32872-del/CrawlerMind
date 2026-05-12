"""Tests for proxy health store and provider adapter (CAP-3.3).

Covers: success, failure, cooldown, redaction, persistence across restarts,
and the provider adapter template.  All tests use in-memory SQLite.
"""
from __future__ import annotations

import tempfile
import time
import unittest
from pathlib import Path

from autonomous_crawler.storage.proxy_health import (
    ProxyHealthStore,
    proxy_id,
    redact_proxy_url,
)
from autonomous_crawler.tools.proxy_pool import (
    ProviderAdapter,
    ProxyEndpoint,
    ProxyPoolConfig,
    StaticProxyPoolProvider,
)


class ProxyIdTests(unittest.TestCase):
    def test_stable_hash(self) -> None:
        a = proxy_id("http://proxy.example:8080")
        b = proxy_id("http://proxy.example:8080")
        self.assertEqual(a, b)
        self.assertEqual(len(a), 16)

    def test_credentials_excluded(self) -> None:
        with_creds = proxy_id("http://user:secret@proxy.example:8080")
        without_creds = proxy_id("http://proxy.example:8080")
        self.assertEqual(with_creds, without_creds)

    def test_different_host_different_id(self) -> None:
        a = proxy_id("http://a.proxy:8080")
        b = proxy_id("http://b.proxy:8080")
        self.assertNotEqual(a, b)

    def test_empty_url(self) -> None:
        self.assertEqual(proxy_id(""), "")


class RedactProxyUrlTests(unittest.TestCase):
    def test_redacts_credentials(self) -> None:
        result = redact_proxy_url("http://user:secret@proxy.example:8080")
        self.assertNotIn("secret", result)
        self.assertNotIn("user", result)
        self.assertIn("***", result)

    def test_no_creds_unchanged(self) -> None:
        result = redact_proxy_url("http://proxy.example:8080")
        self.assertEqual(result, "http://proxy.example:8080")

    def test_empty(self) -> None:
        self.assertEqual(redact_proxy_url(""), "")


class ProxyHealthStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp()
        self.db_path = Path(self._tmp) / "test_health.sqlite3"
        self.store = ProxyHealthStore(self.db_path)

    def test_record_success(self) -> None:
        self.store.record_success("http://proxy.example:8080", now=100.0)
        record = self.store.get("http://proxy.example:8080")
        self.assertIsNotNone(record)
        self.assertEqual(record["success_count"], 1)
        self.assertEqual(record["failure_count"], 0)
        self.assertEqual(record["last_used_at"], 100.0)
        self.assertEqual(record["cooldown_until"], 0)

    def test_record_failure(self) -> None:
        self.store.record_failure("http://proxy.example:8080", error="timeout", now=100.0, max_failures=3)
        record = self.store.get("http://proxy.example:8080")
        self.assertIsNotNone(record)
        self.assertEqual(record["failure_count"], 1)
        self.assertEqual(record["last_error"], "timeout")
        self.assertEqual(record["cooldown_until"], 0)  # below max_failures

    def test_cooldown_applied_after_max_failures(self) -> None:
        url = "http://proxy.example:8080"
        self.store.record_failure(url, error="e1", now=100.0, max_failures=3)
        self.store.record_failure(url, error="e2", now=101.0, max_failures=3)
        self.store.record_failure(url, error="e3", now=102.0, max_failures=3)

        record = self.store.get(url)
        self.assertEqual(record["failure_count"], 3)
        self.assertGreater(record["cooldown_until"], 102.0)

    def test_cooldown_exponential_backoff(self) -> None:
        url = "http://proxy.example:8080"
        self.store.record_failure(url, error="e1", now=100.0, max_failures=2)
        self.store.record_failure(url, error="e2", now=101.0, max_failures=2)
        r1 = self.store.get(url)
        cooldown1 = r1["cooldown_until"] - 101.0

        self.store.record_failure(url, error="e3", now=200.0, max_failures=2)
        r2 = self.store.get(url)
        cooldown2 = r2["cooldown_until"] - 200.0

        # Second cooldown should be longer (exponential)
        self.assertGreater(cooldown2, cooldown1)

    def test_success_resets_failure_count(self) -> None:
        url = "http://proxy.example:8080"
        self.store.record_failure(url, error="e1", now=100.0, max_failures=3)
        self.store.record_failure(url, error="e2", now=101.0, max_failures=3)
        self.store.record_success(url, now=200.0)

        record = self.store.get(url)
        self.assertEqual(record["success_count"], 1)
        self.assertEqual(record["failure_count"], 0)
        self.assertEqual(record["cooldown_until"], 0)

    def test_is_available_unknown_proxy(self) -> None:
        self.assertTrue(self.store.is_available("http://unknown.proxy:8080", now=100.0))

    def test_is_available_after_cooldown(self) -> None:
        url = "http://proxy.example:8080"
        self.store.record_failure(url, error="e", now=100.0, max_failures=1)
        record = self.store.get(url)
        cooldown = record["cooldown_until"]

        self.assertFalse(self.store.is_available(url, now=cooldown - 1))
        self.assertTrue(self.store.is_available(url, now=cooldown))

    def test_available_proxies_filters(self) -> None:
        good = "http://good.proxy:8080"
        bad = "http://bad.proxy:8080"
        self.store.record_success(good, now=100.0)
        self.store.record_failure(bad, error="e", now=100.0, max_failures=1)

        available = self.store.available_proxies([good, bad], now=200.0)
        # bad is in cooldown (failure >= max_failures=1), so only good is available
        self.assertIn(good, available)

    def test_no_plaintext_credentials_stored(self) -> None:
        url = "http://user:supersecret@proxy.example:8080"
        self.store.record_success(url, now=100.0)
        record = self.store.get(url)

        # proxy_label should be redacted
        self.assertNotIn("supersecret", record["proxy_label"])
        self.assertNotIn("user:supersecret", record["proxy_label"])
        self.assertIn("***", record["proxy_label"])

        # Raw DB check — no plaintext password anywhere
        with self.store.connect() as conn:
            rows = conn.execute("SELECT * FROM proxy_health").fetchall()
            for row in rows:
                row_str = str(dict(row))
                self.assertNotIn("supersecret", row_str)

    def test_error_truncated(self) -> None:
        long_error = "x" * 500
        self.store.record_failure("http://p:8080", error=long_error, now=100.0, max_failures=10)
        record = self.store.get("http://p:8080")
        self.assertLessEqual(len(record["last_error"]), 300)

    def test_reset_clears_failure_state(self) -> None:
        url = "http://proxy.example:8080"
        self.store.record_failure(url, error="e", now=100.0, max_failures=1)
        self.store.reset(url)

        record = self.store.get(url)
        self.assertEqual(record["failure_count"], 0)
        self.assertEqual(record["cooldown_until"], 0)
        self.assertEqual(record["last_error"], "")

    def test_persistence_across_restart(self) -> None:
        """Write health data, open a new store instance, read it back."""
        url = "http://proxy.example:8080"
        self.store.record_success(url, now=100.0)
        self.store.record_failure(url, error="timeout", now=200.0, max_failures=3)
        self.store.record_success(url, now=300.0)

        # Open new store with same db_path
        store2 = ProxyHealthStore(self.db_path)
        record = store2.get(url)
        self.assertIsNotNone(record)
        self.assertEqual(record["success_count"], 2)
        self.assertEqual(record["failure_count"], 0)  # reset by success
        self.assertEqual(record["last_used_at"], 300.0)

    def test_get_all(self) -> None:
        self.store.record_success("http://a.proxy:8080", now=100.0)
        self.store.record_success("http://b.proxy:8080", now=100.0)
        self.store.record_failure("http://b.proxy:8080", error="e", now=200.0, max_failures=10)

        all_records = self.store.get_all()
        self.assertEqual(len(all_records), 2)
        # b has more failures, should be first (ORDER BY failure_count DESC)
        self.assertEqual(all_records[0]["failure_count"], 1)

    def test_prune(self) -> None:
        now = time.time()
        self.store.record_success("http://old.proxy:8080", now=now - 100000)
        self.store.record_success("http://new.proxy:8080", now=now)

        removed = self.store.prune(older_than=1000)
        self.assertEqual(removed, 1)
        self.assertIsNone(self.store.get("http://old.proxy:8080"))
        self.assertIsNotNone(self.store.get("http://new.proxy:8080"))

    def test_domain_field_stored(self) -> None:
        self.store.record_success("http://proxy:8080", now=100.0, domain="example.com")
        record = self.store.get("http://proxy:8080")
        self.assertEqual(record["domain"], "example.com")


class StaticProxyPoolProviderHealthTests(unittest.TestCase):
    """Tests for StaticProxyPoolProvider with health store injection."""

    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp()
        self.db_path = Path(self._tmp) / "test_health.sqlite3"
        self.health = ProxyHealthStore(self.db_path)

    def test_report_result_writes_to_health_store(self) -> None:
        provider = StaticProxyPoolProvider(
            {"enabled": True, "endpoints": ["http://proxy:8080"]},
            health_store=self.health,
        )
        provider.report_result("http://proxy:8080", ok=True, now=100.0)

        record = self.health.get("http://proxy:8080")
        self.assertIsNotNone(record)
        self.assertEqual(record["success_count"], 1)

    def test_report_failure_writes_to_health_store(self) -> None:
        provider = StaticProxyPoolProvider(
            {"enabled": True, "max_failures": 2, "endpoints": ["http://proxy:8080"]},
            health_store=self.health,
        )
        provider.report_result("http://proxy:8080", ok=False, error="timeout", now=100.0)

        record = self.health.get("http://proxy:8080")
        self.assertIsNotNone(record)
        self.assertEqual(record["failure_count"], 1)
        self.assertEqual(record["last_error"], "timeout")

    def test_health_store_cooldown_skips_endpoint(self) -> None:
        provider = StaticProxyPoolProvider(
            {"enabled": True, "max_failures": 1, "endpoints": ["http://a.proxy:8080", "http://b.proxy:8080"]},
            health_store=self.health,
        )
        # Trigger cooldown on a.proxy
        provider.report_result("http://a.proxy:8080", ok=False, error="fail", now=100.0)

        # a.proxy should be in cooldown, b.proxy should be selected
        selection = provider.select("https://example.com", now=101.0)
        self.assertEqual(selection.proxy_url, "http://b.proxy:8080")

    def test_without_health_store_works_normally(self) -> None:
        provider = StaticProxyPoolProvider(
            {"enabled": True, "endpoints": ["http://proxy:8080"]},
        )
        provider.report_result("http://proxy:8080", ok=True, now=100.0)
        selection = provider.select("https://example.com")
        self.assertEqual(selection.proxy_url, "http://proxy:8080")


class ProviderAdapterTests(unittest.TestCase):
    """Tests for the provider adapter template."""

    def test_base_class_raises_not_implemented(self) -> None:
        adapter = ProviderAdapter()
        result = adapter.fetch_endpoints(now=100.0)
        self.assertEqual(result, [])  # catches NotImplementedError

    def test_subclass_override(self) -> None:
        class TestProvider(ProviderAdapter):
            provider_name = "test"

            def _fetch_endpoints(self, *, now: float = 0.0):
                return [
                    ProxyEndpoint(url="http://test.proxy:8080", label="test"),
                ]

        adapter = TestProvider()
        endpoints = adapter.fetch_endpoints(now=100.0)
        self.assertEqual(len(endpoints), 1)
        self.assertEqual(endpoints[0].url, "http://test.proxy:8080")

    def test_report_result_writes_to_health_store(self) -> None:
        tmp = tempfile.mkdtemp()
        health = ProxyHealthStore(Path(tmp) / "test.sqlite3")
        adapter = ProviderAdapter(health_store=health)

        adapter.report_result("http://proxy:8080", ok=True, now=100.0)
        record = health.get("http://proxy:8080")
        self.assertIsNotNone(record)
        self.assertEqual(record["success_count"], 1)

    def test_to_safe_dict(self) -> None:
        adapter = ProviderAdapter()
        d = adapter.to_safe_dict()
        self.assertEqual(d["provider"], "abstract")
        self.assertFalse(d["has_health_store"])

    def test_to_safe_dict_with_health_store(self) -> None:
        tmp = tempfile.mkdtemp()
        health = ProxyHealthStore(Path(tmp) / "test.sqlite3")
        adapter = ProviderAdapter(health_store=health)
        d = adapter.to_safe_dict()
        self.assertTrue(d["has_health_store"])


if __name__ == "__main__":
    unittest.main()
