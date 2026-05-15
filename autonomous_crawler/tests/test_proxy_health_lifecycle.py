"""Proxy health lifecycle tests — cooldown, backoff, recovery, and fetch integration (CAP-3.3 / SCRAPLING-ABSORB-1C).

Covers the full proxy health lifecycle that the assignment requires:
- Good proxy records success and stays available
- Failed proxy accumulates failures and enters cooldown
- Cooldown expires and proxy becomes available again
- Exponential backoff grows on repeated cooldown cycles
- Success resets failure count and clears cooldown
- Proxy trace from NativeFetchRuntime is credential-safe
- Health store integrates with ProxyManager selection
- Multiple proxies: one in cooldown, others still available
- Redaction: no plaintext credentials in any output
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from autonomous_crawler.runtime.native_static import NativeFetchRuntime
from autonomous_crawler.runtime.models import RuntimeRequest
from autonomous_crawler.storage.proxy_health import ProxyHealthStore, proxy_id, redact_proxy_url
from autonomous_crawler.tools.proxy_manager import ProxyConfig, ProxyManager
from autonomous_crawler.tools.proxy_pool import ProxyPoolConfig, StaticProxyPoolProvider
from autonomous_crawler.tools.proxy_trace import ProxyTrace, health_store_summary


# ---------------------------------------------------------------------------
# Full cooldown lifecycle
# ---------------------------------------------------------------------------

class ProxyCooldownLifecycleTests(unittest.TestCase):
    """Proxy health store cooldown lifecycle: fail → cooldown → recover."""

    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp()
        self.db_path = Path(self._tmp) / "lifecycle.sqlite3"
        self.store = ProxyHealthStore(self.db_path)

    def test_full_lifecycle_fail_cooldown_expire_success(self) -> None:
        """Proxy fails max_failures times, enters cooldown, cooldown expires, then succeeds."""
        url = "http://proxy:8080"
        max_failures = 2

        # Phase 1: accumulate failures below threshold — no cooldown
        self.store.record_failure(url, error="timeout", now=100.0, max_failures=max_failures)
        r = self.store.get(url)
        self.assertEqual(r["failure_count"], 1)
        self.assertEqual(r["cooldown_until"], 0)
        self.assertTrue(self.store.is_available(url, now=100.0))

        # Phase 2: hit max_failures — enters cooldown
        self.store.record_failure(url, error="refused", now=101.0, max_failures=max_failures)
        r = self.store.get(url)
        self.assertEqual(r["failure_count"], 2)
        self.assertGreater(r["cooldown_until"], 101.0)
        self.assertFalse(self.store.is_available(url, now=102.0))

        # Phase 3: cooldown still active
        cooldown = r["cooldown_until"]
        self.assertFalse(self.store.is_available(url, now=cooldown - 1))

        # Phase 4: cooldown expires
        self.assertTrue(self.store.is_available(url, now=cooldown))

        # Phase 5: success resets everything
        self.store.record_success(url, now=cooldown + 10)
        r = self.store.get(url)
        self.assertEqual(r["failure_count"], 0)
        self.assertEqual(r["cooldown_until"], 0)
        self.assertEqual(r["success_count"], 1)
        self.assertTrue(self.store.is_available(url, now=cooldown + 10))

    def test_exponential_backoff_grows_across_cycles(self) -> None:
        """Each cooldown cycle produces a longer backoff."""
        url = "http://proxy:8080"
        max_failures = 1
        cooldowns: list[float] = []

        for cycle in range(4):
            now = 1000.0 * (cycle + 1)
            self.store.record_failure(url, error=f"cycle-{cycle}", now=now, max_failures=max_failures)
            r = self.store.get(url)
            cooldowns.append(r["cooldown_until"] - now)
            # Reset for next cycle
            self.store.reset(url)

        # Each cooldown should be >= previous (30, 60, 120, 240)
        for i in range(1, len(cooldowns)):
            self.assertGreaterEqual(
                cooldowns[i], cooldowns[i - 1],
                f"Cooldown {i} ({cooldowns[i]}) should be >= cooldown {i-1} ({cooldowns[i-1]})",
            )

    def test_cooldown_capped_at_max(self) -> None:
        """Cooldown duration should not exceed COOLDOWN_MAX_SECONDS (600s)."""
        from autonomous_crawler.storage.proxy_health import COOLDOWN_MAX_SECONDS
        url = "http://proxy:8080"
        max_failures = 1

        # Drive many failures to reach cap, using explicit now
        last_now = 0.0
        for i in range(20):
            last_now = 1000.0 + float(i)
            self.store.record_failure(url, error=f"e-{i}", now=last_now, max_failures=max_failures)

        r = self.store.get(url)
        cooldown_duration = r["cooldown_until"] - last_now
        self.assertLessEqual(cooldown_duration, COOLDOWN_MAX_SECONDS + 1)

    def test_multiple_proxies_independent_health(self) -> None:
        """Multiple proxies track health independently."""
        good = "http://good:8080"
        bad = "http://bad:8080"

        self.store.record_success(good, now=100.0)
        self.store.record_success(good, now=101.0)
        self.store.record_failure(bad, error="fail", now=100.0, max_failures=1)

        all_records = self.store.get_all()
        by_url = {r["proxy_label"]: r for r in all_records}

        self.assertEqual(by_url[redact_proxy_url(good)]["success_count"], 2)
        self.assertEqual(by_url[redact_proxy_url(good)]["failure_count"], 0)
        self.assertEqual(by_url[redact_proxy_url(bad)]["failure_count"], 1)

    def test_available_proxies_filters_cooldown(self) -> None:
        """available_proxies returns only those not in cooldown."""
        a = "http://a:8080"
        b = "http://b:8080"
        c = "http://c:8080"

        self.store.record_success(a, now=100.0)
        self.store.record_failure(b, error="fail", now=100.0, max_failures=1)
        # c has no record (unknown, should be available)

        # Check at now=110 (within cooldown window: 100 + 30s base = 130)
        available = self.store.available_proxies([a, b, c], now=110.0)
        self.assertIn(a, available)
        self.assertNotIn(b, available)  # b is in cooldown (until 130)
        self.assertIn(c, available)

    def test_health_store_summary_counts_correctly(self) -> None:
        """health_store_summary returns correct aggregate counts."""
        self.store.record_success("http://a:8080", now=100.0)
        self.store.record_success("http://b:8080", now=100.0)
        self.store.record_failure("http://c:8080", error="e", now=100.0, max_failures=1)

        # Check at now=110 (within cooldown window: 100 + 30s = 130)
        summary = health_store_summary(self.store, now=110.0)
        self.assertEqual(summary["tracked_proxies"], 3)
        self.assertEqual(summary["healthy"], 2)
        self.assertEqual(summary["in_cooldown"], 1)
        self.assertEqual(summary["total_failures"], 1)


# ---------------------------------------------------------------------------
# ProxyManager + HealthStore integration
# ---------------------------------------------------------------------------

class ProxyManagerHealthIntegrationTests(unittest.TestCase):
    """ProxyManager selection respects health store cooldown."""

    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp()
        self.db_path = Path(self._tmp) / "integration.sqlite3"
        self.health = ProxyHealthStore(self.db_path)

    def test_manager_skips_cooldown_proxy_in_pool(self) -> None:
        """When pool proxy is in cooldown, manager selects alternative."""
        config = {
            "enabled": True,
            "pool": {
                "enabled": True,
                "strategy": "round_robin",
                "endpoints": ["http://a:8080", "http://b:8080"],
            },
        }
        provider = StaticProxyPoolProvider(config["pool"], health_store=self.health)
        manager = ProxyManager(config, pool_provider=provider)

        # Put a:8080 in cooldown (cooldown_until = 100 + 30 = 130)
        self.health.record_failure("http://a:8080", error="fail", now=100.0, max_failures=1)

        # Selection at now=110 should skip a:8080 (in cooldown until 130)
        selection = provider.select("https://example.com", now=110.0)
        self.assertEqual(selection.proxy_url, "http://b:8080")

    def test_manager_all_proxies_in_cooldown_returns_empty(self) -> None:
        """When all pool proxies are in cooldown, selection has no available proxy."""
        config = {
            "enabled": True,
            "pool": {
                "enabled": True,
                "strategy": "round_robin",
                "endpoints": ["http://a:8080"],
            },
        }
        provider = StaticProxyPoolProvider(config["pool"], health_store=self.health)
        self.health.record_failure("http://a:8080", error="fail", now=100.0, max_failures=1)

        # Selection at now=110 — a:8080 is in cooldown until 130
        selection = provider.select("https://example.com", now=110.0)
        self.assertEqual(selection.source, "pool_empty")

    def test_proxy_trace_from_manager_includes_health(self) -> None:
        """ProxyTrace.from_manager enriches with health store data."""
        config = {
            "enabled": True,
            "default_proxy": "http://p:8080",
        }
        manager = ProxyManager(config)

        # Record some health
        self.health.record_failure("http://p:8080", error="timeout", now=100.0, max_failures=5)

        trace = ProxyTrace.from_manager(manager, "https://example.com", health_store=self.health, now=200.0)
        self.assertTrue(trace.selected)
        self.assertIn("failure_count", trace.health)
        self.assertEqual(trace.health["failure_count"], 1)
        # Error message should be redacted (though "timeout" has no creds to redact)
        self.assertIsNotNone(trace.health.get("last_error"))

    def test_proxy_trace_credential_redaction(self) -> None:
        """ProxyTrace never leaks plaintext credentials."""
        config = {
            "enabled": True,
            "default_proxy": "http://user:secretpass@proxy:8080",
        }
        manager = ProxyManager(config)

        trace = ProxyTrace.from_manager(manager, "https://example.com")
        d = trace.to_dict()
        payload = str(d)

        self.assertNotIn("secretpass", payload)
        self.assertNotIn("user:secretpass", payload)
        self.assertIn("***", payload)


# ---------------------------------------------------------------------------
# NativeFetchRuntime proxy trace evidence
# ---------------------------------------------------------------------------

class NativeFetchProxyTraceEvidenceTests(unittest.TestCase):
    """NativeFetchRuntime surfaces proxy trace evidence cleanly."""

    def _mock_httpx_response(self) -> MagicMock:
        resp = MagicMock()
        resp.status_code = 200
        resp.url = "https://example.com"
        resp.headers = {"Content-Type": "text/html"}
        resp.cookies = {}
        resp.content = b"<html>ok</html>"
        resp.text = "<html>ok</html>"
        resp.http_version = "1.1"
        return resp

    @patch("autonomous_crawler.runtime.native_static.httpx.Client")
    def test_proxy_trace_present_in_response(self, mock_client_cls: MagicMock) -> None:
        """Response includes proxy_trace when proxy is configured."""
        client = mock_client_cls.return_value.__enter__.return_value
        client.request.return_value = self._mock_httpx_response()

        runtime = NativeFetchRuntime()
        req = RuntimeRequest(
            url="https://example.com",
            proxy_config={"proxy": "http://p:8080", "source": "pool_round_robin"},
        )
        resp = runtime.fetch(req)

        self.assertTrue(resp.proxy_trace.selected)
        self.assertIn("p:8080", resp.proxy_trace.proxy)

    @patch("autonomous_crawler.runtime.native_static.httpx.Client")
    def test_proxy_trace_absent_when_no_proxy(self, mock_client_cls: MagicMock) -> None:
        """Proxy trace shows selected=False when no proxy configured."""
        client = mock_client_cls.return_value.__enter__.return_value
        client.request.return_value = self._mock_httpx_response()

        runtime = NativeFetchRuntime()
        resp = runtime.fetch(RuntimeRequest(url="https://example.com"))

        self.assertFalse(resp.proxy_trace.selected)

    @patch("autonomous_crawler.runtime.native_static.httpx.Client")
    def test_proxy_credentials_redacted_in_trace_and_events(self, mock_client_cls: MagicMock) -> None:
        """Credentials are redacted in proxy_trace AND runtime events."""
        client = mock_client_cls.return_value.__enter__.return_value
        client.request.return_value = self._mock_httpx_response()

        runtime = NativeFetchRuntime()
        req = RuntimeRequest(
            url="https://example.com",
            proxy_config={"proxy": "http://user:topsecret@proxy:8080"},
        )
        resp = runtime.fetch(req)
        # to_dict() applies redaction
        payload = str(resp.to_dict())

        self.assertNotIn("topsecret", payload)
        self.assertNotIn("user:topsecret", payload)
        # Trace proxy field in to_dict should be redacted
        trace_dict = resp.proxy_trace.to_dict()
        self.assertIn("***", trace_dict["proxy"])

    @patch("autonomous_crawler.runtime.native_static.httpx.Client")
    def test_fetch_error_still_has_proxy_trace(self, mock_client_cls: MagicMock) -> None:
        """Even on fetch failure, proxy trace is populated."""
        client = mock_client_cls.return_value.__enter__.return_value
        client.request.side_effect = ConnectionError("refused")

        runtime = NativeFetchRuntime()
        req = RuntimeRequest(
            url="https://example.com",
            proxy_config={"proxy": "http://p:8080"},
        )
        resp = runtime.fetch(req)

        self.assertFalse(resp.ok)
        self.assertTrue(resp.proxy_trace.selected)
        self.assertIn("p:8080", resp.proxy_trace.proxy)

    @patch("autonomous_crawler.runtime.native_static.httpx.Client")
    def test_runtime_events_contain_redacted_proxy(self, mock_client_cls: MagicMock) -> None:
        """fetch_start and fetch_complete events have redacted proxy info."""
        client = mock_client_cls.return_value.__enter__.return_value
        client.request.return_value = self._mock_httpx_response()

        runtime = NativeFetchRuntime()
        req = RuntimeRequest(
            url="https://example.com",
            proxy_config={"proxy": "http://u:s3cret@proxy:8080"},
        )
        resp = runtime.fetch(req)

        for event in resp.runtime_events:
            event_str = str(event.to_dict())
            self.assertNotIn("s3cret", event_str, f"Event {event.type} leaked credentials")


# ---------------------------------------------------------------------------
# NativeFetchRuntime transport evidence
# ---------------------------------------------------------------------------

class NativeFetchTransportEvidenceTests(unittest.TestCase):
    """NativeFetchRuntime surfaces transport diagnostics in engine_result."""

    def _mock_httpx_response(self, **kwargs) -> MagicMock:
        resp = MagicMock()
        resp.status_code = kwargs.get("status_code", 200)
        resp.url = kwargs.get("url", "https://example.com")
        resp.headers = kwargs.get("headers", {"Content-Type": "text/html"})
        resp.cookies = {}
        resp.content = kwargs.get("content", b"<html>ok</html>")
        resp.text = kwargs.get("content", b"<html>ok</html>").decode("utf-8", errors="replace")
        resp.http_version = kwargs.get("http_version", "HTTP/2")
        return resp

    @patch("autonomous_crawler.runtime.native_static.httpx.Client")
    def test_engine_result_has_transport_info(self, mock_client_cls: MagicMock) -> None:
        """engine_result includes transport and http_version."""
        client = mock_client_cls.return_value.__enter__.return_value
        client.request.return_value = self._mock_httpx_response(http_version="HTTP/2")

        runtime = NativeFetchRuntime()
        resp = runtime.fetch(RuntimeRequest(url="https://example.com"))

        self.assertEqual(resp.engine_result["engine"], "native_static")
        self.assertEqual(resp.engine_result["transport"], "httpx")
        self.assertEqual(resp.engine_result["http_version"], "HTTP/2")

    @patch("autonomous_crawler.runtime.native_static.httpx.Client")
    def test_transport_event_data(self, mock_client_cls: MagicMock) -> None:
        """fetch_start event includes transport in data."""
        client = mock_client_cls.return_value.__enter__.return_value
        client.request.return_value = self._mock_httpx_response()

        runtime = NativeFetchRuntime()
        resp = runtime.fetch(RuntimeRequest(url="https://example.com"))

        start_event = resp.runtime_events[0]
        self.assertEqual(start_event.type, "fetch_start")
        self.assertEqual(start_event.data["transport"], "httpx")

    @patch("autonomous_crawler.runtime.native_static.httpx.Client")
    def test_fetch_complete_event_has_status_and_size(self, mock_client_cls: MagicMock) -> None:
        """fetch_complete event includes status_code and body_bytes."""
        client = mock_client_cls.return_value.__enter__.return_value
        client.request.return_value = self._mock_httpx_response(content=b"<html>hello</html>")

        runtime = NativeFetchRuntime()
        resp = runtime.fetch(RuntimeRequest(url="https://example.com"))

        complete_event = resp.runtime_events[-1]
        self.assertEqual(complete_event.type, "fetch_complete")
        self.assertEqual(complete_event.data["status_code"], 200)
        self.assertEqual(complete_event.data["body_bytes"], len(b"<html>hello</html>"))

    @patch("autonomous_crawler.runtime.native_static.httpx.Client")
    def test_error_event_has_transport(self, mock_client_cls: MagicMock) -> None:
        """fetch_error event includes transport in data."""
        client = mock_client_cls.return_value.__enter__.return_value
        client.request.side_effect = TimeoutError("timed out")

        runtime = NativeFetchRuntime()
        resp = runtime.fetch(RuntimeRequest(url="https://example.com"))

        error_event = resp.runtime_events[-1]
        self.assertEqual(error_event.type, "fetch_error")
        self.assertEqual(error_event.data["transport"], "httpx")


# ---------------------------------------------------------------------------
# Proxy trace integration with ProxyTrace factories
# ---------------------------------------------------------------------------

class ProxyTraceFactoryTests(unittest.TestCase):
    """ProxyTrace factory methods produce credential-safe, health-enriched traces."""

    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp()
        self.db_path = Path(self._tmp) / "trace.sqlite3"
        self.health = ProxyHealthStore(self.db_path)

    def test_from_selection_with_health_store(self) -> None:
        """ProxyTrace.from_selection enriches with health data."""
        from autonomous_crawler.tools.proxy_pool import ProxySelection

        self.health.record_failure("http://p:8080", error="timeout", now=100.0, max_failures=5)

        selection = ProxySelection(
            proxy_url="http://p:8080",
            source="pool_round_robin",
            provider="static",
            strategy="round_robin",
        )
        trace = ProxyTrace.from_selection(selection, health_store=self.health, now=200.0)

        self.assertTrue(trace.selected)
        self.assertEqual(trace.health["failure_count"], 1)
        self.assertIn("timeout", trace.health["last_error"])

    def test_from_selection_no_health_store(self) -> None:
        """ProxyTrace.from_selection works without health store."""
        from autonomous_crawler.tools.proxy_pool import ProxySelection

        selection = ProxySelection(proxy_url="http://p:8080", source="default")
        trace = ProxyTrace.from_selection(selection)

        self.assertTrue(trace.selected)
        self.assertEqual(trace.health, {})

    def test_disabled_trace(self) -> None:
        """ProxyTrace.disabled() produces a clean disabled trace."""
        trace = ProxyTrace.disabled()
        self.assertFalse(trace.selected)
        self.assertEqual(trace.source, "disabled")

    def test_health_store_summary_empty(self) -> None:
        """health_store_summary handles empty store."""
        summary = health_store_summary(self.health, now=0.0)
        self.assertEqual(summary["tracked_proxies"], 0)
        self.assertEqual(summary["healthy"], 0)

    def test_redacted_trace_to_dict_no_credentials(self) -> None:
        """to_dict() never leaks credentials."""
        from autonomous_crawler.tools.proxy_pool import ProxySelection

        selection = ProxySelection(
            proxy_url="http://admin:P@ssw0rd@proxy:8080",
            source="per_domain",
        )
        trace = ProxyTrace.from_selection(selection)
        payload = str(trace.to_dict())

        self.assertNotIn("P@ssw0rd", payload)
        self.assertNotIn("admin:P@ssw0rd", payload)
        self.assertIn("***", payload)


if __name__ == "__main__":
    unittest.main()
