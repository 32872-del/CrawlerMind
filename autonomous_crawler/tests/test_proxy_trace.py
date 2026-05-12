"""Tests for proxy trace evidence chain (CAP-3.3 / CAP-6.2).

Covers: disabled trace, pool selection trace, health enrichment,
error redaction, health store summary, and credential safety.
"""
from __future__ import annotations

import tempfile
import time
import unittest
from pathlib import Path

from autonomous_crawler.storage.proxy_health import ProxyHealthStore
from autonomous_crawler.tools.proxy_manager import ProxyConfig, ProxyManager
from autonomous_crawler.tools.proxy_pool import (
    ProxySelection,
    StaticProxyPoolProvider,
)
from autonomous_crawler.tools.proxy_trace import (
    ProxyTrace,
    health_store_summary,
    redact_error_message,
)


# ======================================================================
# Error redaction
# ======================================================================

class RedactErrorMessageTests(unittest.TestCase):
    def test_redacts_http_url(self) -> None:
        msg = "connection failed to http://user:secret@proxy.example:8080/path"
        result = redact_error_message(msg)
        self.assertNotIn("secret", result)
        self.assertNotIn("user:secret", result)
        self.assertIn("[redacted_url]", result)

    def test_redacts_socks5_url(self) -> None:
        msg = "socks5://admin:pass123@socks.proxy:1080 timeout"
        result = redact_error_message(msg)
        self.assertNotIn("pass123", result)
        self.assertIn("[redacted_url]", result)

    def test_redacts_key_value_password(self) -> None:
        msg = "auth failed password=supersecret123 retry"
        result = redact_error_message(msg)
        self.assertNotIn("supersecret123", result)
        self.assertIn("password=[redacted]", result)

    def test_redacts_token_colon(self) -> None:
        msg = "invalid token: abc123xyz"
        result = redact_error_message(msg)
        self.assertNotIn("abc123xyz", result)
        self.assertIn("token=[redacted]", result)

    def test_redacts_api_key_equals(self) -> None:
        msg = "api_key=sk_live_abc123 rejected"
        result = redact_error_message(msg)
        self.assertNotIn("sk_live_abc123", result)
        self.assertIn("api_key=[redacted]", result)

    def test_empty_string(self) -> None:
        self.assertEqual(redact_error_message(""), "")

    def test_no_secrets_unchanged(self) -> None:
        msg = "connection timeout after 30s"
        self.assertEqual(redact_error_message(msg), msg)

    def test_multiple_redactions(self) -> None:
        msg = "proxy http://u:p@host:8080 failed, password=secret123"
        result = redact_error_message(msg)
        self.assertNotIn("u:p", result)
        self.assertNotIn("secret123", result)


# ======================================================================
# ProxyTrace.disabled
# ======================================================================

class ProxyTraceDisabledTests(unittest.TestCase):
    def test_disabled_trace(self) -> None:
        trace = ProxyTrace.disabled()
        self.assertFalse(trace.selected)
        self.assertEqual(trace.proxy, "")
        self.assertEqual(trace.source, "disabled")
        self.assertEqual(trace.provider, "")
        self.assertEqual(trace.strategy, "")
        self.assertEqual(trace.health, {})
        self.assertEqual(trace.errors, ())

    def test_disabled_to_dict(self) -> None:
        d = ProxyTrace.disabled().to_dict()
        self.assertFalse(d["selected"])
        self.assertEqual(d["source"], "disabled")
        self.assertNotIn("provider", d)
        self.assertNotIn("strategy", d)
        self.assertNotIn("health", d)
        self.assertNotIn("errors", d)


# ======================================================================
# ProxyTrace.from_selection
# ======================================================================

class ProxyTraceFromSelectionTests(unittest.TestCase):
    def test_basic_selection(self) -> None:
        sel = ProxySelection(
            proxy_url="http://proxy.example:8080",
            source="pool_round_robin",
            provider="static",
            strategy="round_robin",
        )
        trace = ProxyTrace.from_selection(sel)
        self.assertTrue(trace.selected)
        self.assertEqual(trace.proxy, "http://proxy.example:8080")
        self.assertEqual(trace.source, "pool_round_robin")
        self.assertEqual(trace.provider, "static")
        self.assertEqual(trace.strategy, "round_robin")
        self.assertEqual(trace.health, {})

    def test_empty_selection(self) -> None:
        sel = ProxySelection(source="pool_empty", errors=("no available proxy endpoints",))
        trace = ProxyTrace.from_selection(sel)
        self.assertFalse(trace.selected)
        self.assertEqual(trace.proxy, "")
        self.assertEqual(trace.source, "pool_empty")
        self.assertEqual(len(trace.errors), 1)

    def test_with_health_store_healthy(self) -> None:
        tmp = tempfile.mkdtemp()
        health = ProxyHealthStore(Path(tmp) / "test.sqlite3")
        health.record_success("http://proxy:8080", now=100.0)

        sel = ProxySelection(proxy_url="http://proxy:8080", source="pool_round_robin")
        trace = ProxyTrace.from_selection(sel, health_store=health, now=200.0)

        self.assertTrue(trace.selected)
        self.assertEqual(trace.health["success_count"], 1)
        self.assertEqual(trace.health["failure_count"], 0)
        self.assertFalse(trace.health["in_cooldown"])

    def test_with_health_store_cooldown(self) -> None:
        tmp = tempfile.mkdtemp()
        health = ProxyHealthStore(Path(tmp) / "test.sqlite3")
        health.record_failure(
            "http://proxy:8080",
            error="connection failed to http://user:secret@proxy:8080",
            now=100.0,
            max_failures=1,
        )

        sel = ProxySelection(proxy_url="http://proxy:8080", source="pool_round_robin")
        trace = ProxyTrace.from_selection(sel, health_store=health, now=101.0)

        self.assertTrue(trace.selected)
        self.assertEqual(trace.health["failure_count"], 1)
        self.assertTrue(trace.health["in_cooldown"])
        self.assertIn("cooldown_until", trace.health)
        self.assertIn("last_error", trace.health)
        # Error URL is redacted
        self.assertNotIn("secret", trace.health.get("last_error", ""))
        self.assertIn("[redacted_url]", trace.health.get("last_error", ""))

    def test_with_health_store_unknown_proxy(self) -> None:
        tmp = tempfile.mkdtemp()
        health = ProxyHealthStore(Path(tmp) / "test.sqlite3")

        sel = ProxySelection(proxy_url="http://unknown:8080", source="pool_round_robin")
        trace = ProxyTrace.from_selection(sel, health_store=health, now=100.0)

        self.assertTrue(trace.selected)
        self.assertEqual(trace.health, {})  # no record → empty health

    def test_without_health_store(self) -> None:
        sel = ProxySelection(proxy_url="http://proxy:8080", source="default")
        trace = ProxyTrace.from_selection(sel, health_store=None)
        self.assertEqual(trace.health, {})

    def test_errors_preserved(self) -> None:
        sel = ProxySelection(
            source="pool_error",
            errors=("proxy pool enabled but no endpoints configured",),
        )
        trace = ProxyTrace.from_selection(sel)
        self.assertEqual(len(trace.errors), 1)
        self.assertIn("no endpoints", trace.errors[0])


# ======================================================================
# ProxyTrace.from_manager
# ======================================================================

class ProxyTraceFromManagerTests(unittest.TestCase):
    def test_disabled_config(self) -> None:
        manager = ProxyManager({"enabled": False})
        trace = ProxyTrace.from_manager(manager, "https://example.com")
        self.assertFalse(trace.selected)
        self.assertEqual(trace.source, "disabled")

    def test_enabled_no_pool(self) -> None:
        manager = ProxyManager({
            "enabled": True,
            "default_proxy": "http://default.proxy:8080",
        })
        trace = ProxyTrace.from_manager(manager, "https://example.com")
        self.assertTrue(trace.selected)
        self.assertEqual(trace.proxy, "http://default.proxy:8080")
        self.assertEqual(trace.source, "default")

    def test_pool_selection(self) -> None:
        manager = ProxyManager({
            "enabled": True,
            "pool": {
                "enabled": True,
                "endpoints": ["http://a.proxy:8080", "http://b.proxy:8080"],
            },
        })
        trace = ProxyTrace.from_manager(manager, "https://example.com")
        self.assertTrue(trace.selected)
        self.assertIn(trace.source, {"pool_round_robin"})
        self.assertEqual(trace.provider, "static")
        self.assertEqual(trace.strategy, "round_robin")

    def test_per_domain_selection(self) -> None:
        manager = ProxyManager({
            "enabled": True,
            "per_domain": {"shop.example.com": "http://domain.proxy:8080"},
            "pool": {"enabled": True, "endpoints": ["http://pool.proxy:8080"]},
        })
        trace = ProxyTrace.from_manager(manager, "https://shop.example.com/page")
        self.assertTrue(trace.selected)
        self.assertEqual(trace.proxy, "http://domain.proxy:8080")
        self.assertEqual(trace.source, "per_domain")

    def test_with_health_store(self) -> None:
        tmp = tempfile.mkdtemp()
        health = ProxyHealthStore(Path(tmp) / "test.sqlite3")
        health.record_failure("http://a.proxy:8080", error="err", now=100.0, max_failures=1)

        manager = ProxyManager({
            "enabled": True,
            "pool": {
                "enabled": True,
                "max_failures": 1,
                "endpoints": ["http://a.proxy:8080", "http://b.proxy:8080"],
            },
        })
        # a.proxy is in cooldown, b.proxy should be selected
        trace = ProxyTrace.from_manager(manager, "https://example.com", health_store=health, now=101.0)
        self.assertTrue(trace.selected)
        self.assertEqual(trace.proxy, "http://b.proxy:8080")

    def test_no_proxy_configured(self) -> None:
        manager = ProxyManager({"enabled": True})
        trace = ProxyTrace.from_manager(manager, "https://example.com")
        self.assertFalse(trace.selected)
        self.assertEqual(trace.source, "none")

    def test_credentials_redacted_in_trace(self) -> None:
        manager = ProxyManager({
            "enabled": True,
            "default_proxy": "http://user:supersecret@proxy.example:8080",
        })
        trace = ProxyTrace.from_manager(manager, "https://example.com")
        d = trace.to_dict()
        trace_str = str(d)
        self.assertNotIn("supersecret", trace_str)
        self.assertNotIn("user:supersecret", trace_str)
        self.assertIn("***", trace_str)


# ======================================================================
# ProxyTrace.to_dict
# ======================================================================

class ProxyTraceToDictTests(unittest.TestCase):
    def test_minimal(self) -> None:
        d = ProxyTrace().to_dict()
        self.assertFalse(d["selected"])
        self.assertEqual(d["proxy"], "")
        self.assertEqual(d["source"], "none")
        self.assertNotIn("provider", d)
        self.assertNotIn("strategy", d)
        self.assertNotIn("health", d)
        self.assertNotIn("errors", d)

    def test_full(self) -> None:
        trace = ProxyTrace(
            selected=True,
            proxy="http://***:***@proxy:8080",
            source="pool_round_robin",
            provider="static",
            strategy="round_robin",
            health={"success_count": 5, "failure_count": 0, "in_cooldown": False},
            errors=(),
        )
        d = trace.to_dict()
        self.assertTrue(d["selected"])
        self.assertEqual(d["provider"], "static")
        self.assertEqual(d["strategy"], "round_robin")
        self.assertEqual(d["health"]["success_count"], 5)

    def test_with_errors(self) -> None:
        trace = ProxyTrace(errors=("error one", "error two"))
        d = trace.to_dict()
        self.assertEqual(d["errors"], ["error one", "error two"])


# ======================================================================
# health_store_summary
# ======================================================================

class HealthStoreSummaryTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp()
        self.health = ProxyHealthStore(Path(self._tmp) / "test.sqlite3")

    def test_empty_store(self) -> None:
        summary = health_store_summary(self.health, now=100.0)
        self.assertEqual(summary["tracked_proxies"], 0)
        self.assertEqual(summary["healthy"], 0)
        self.assertEqual(summary["in_cooldown"], 0)
        self.assertEqual(summary["total_failures"], 0)

    def test_all_healthy(self) -> None:
        self.health.record_success("http://a.proxy:8080", now=100.0)
        self.health.record_success("http://b.proxy:8080", now=100.0)

        summary = health_store_summary(self.health, now=200.0)
        self.assertEqual(summary["tracked_proxies"], 2)
        self.assertEqual(summary["healthy"], 2)
        self.assertEqual(summary["in_cooldown"], 0)
        self.assertEqual(summary["total_failures"], 0)

    def test_mixed_health(self) -> None:
        self.health.record_success("http://good.proxy:8080", now=100.0)
        self.health.record_failure("http://bad.proxy:8080", error="e", now=100.0, max_failures=1)

        summary = health_store_summary(self.health, now=101.0)
        self.assertEqual(summary["tracked_proxies"], 2)
        self.assertEqual(summary["healthy"], 1)
        self.assertEqual(summary["in_cooldown"], 1)
        self.assertEqual(summary["total_failures"], 1)

    def test_all_cooldown(self) -> None:
        self.health.record_failure("http://a.proxy:8080", error="e", now=100.0, max_failures=1)
        self.health.record_failure("http://b.proxy:8080", error="e", now=100.0, max_failures=1)

        summary = health_store_summary(self.health, now=101.0)
        self.assertEqual(summary["tracked_proxies"], 2)
        self.assertEqual(summary["healthy"], 0)
        self.assertEqual(summary["in_cooldown"], 2)

    def test_no_individual_proxy_exposed(self) -> None:
        """Summary must not leak individual proxy URLs or proxy_ids."""
        self.health.record_success("http://super-secret-proxy:9999", now=100.0)
        summary = health_store_summary(self.health, now=200.0)
        summary_str = str(summary)
        self.assertNotIn("super-secret-proxy", summary_str)
        self.assertNotIn("9999", summary_str)

    def test_success_resets_failure_count_in_summary(self) -> None:
        self.health.record_failure("http://proxy:8080", error="e", now=100.0, max_failures=1)
        self.health.record_success("http://proxy:8080", now=200.0)

        summary = health_store_summary(self.health, now=300.0)
        self.assertEqual(summary["total_failures"], 0)
        self.assertEqual(summary["in_cooldown"], 0)


# ======================================================================
# Credential safety (end-to-end)
# ======================================================================

class CredentialSafetyTests(unittest.TestCase):
    """Ensure no trace output contains plaintext proxy credentials."""

    def test_no_plaintext_in_disabled_trace(self) -> None:
        d = ProxyTrace.disabled().to_dict()
        # Disabled trace has no proxy URL at all
        self.assertEqual(d["proxy"], "")
        self.assertFalse(d["selected"])

    def test_no_plaintext_in_selection_trace(self) -> None:
        sel = ProxySelection(
            proxy_url="http://admin:hunter2@proxy.example:8080",
            source="pool_round_robin",
            provider="static",
            strategy="round_robin",
        )
        trace = ProxyTrace.from_selection(sel)
        d = trace.to_dict()
        d_str = str(d)
        self.assertNotIn("hunter2", d_str)
        self.assertNotIn("admin:hunter2", d_str)
        self.assertIn("***", d_str)

    def test_no_plaintext_in_manager_trace(self) -> None:
        manager = ProxyManager({
            "enabled": True,
            "default_proxy": "http://root:p@ssw0rd@proxy.example:8080",
        })
        trace = ProxyTrace.from_manager(manager, "https://example.com")
        d_str = str(trace.to_dict())
        self.assertNotIn("p@ssw0rd", d_str)
        self.assertNotIn("root:p@ssw0rd", d_str)

    def test_no_plaintext_in_health_error(self) -> None:
        tmp = tempfile.mkdtemp()
        health = ProxyHealthStore(Path(tmp) / "test.sqlite3")
        health.record_failure(
            "http://user:secret@proxy:8080",
            error="auth failed for http://user:secret@proxy:8080",
            now=100.0,
            max_failures=1,
        )

        sel = ProxySelection(proxy_url="http://user:secret@proxy:8080", source="pool_round_robin")
        trace = ProxyTrace.from_selection(sel, health_store=health, now=101.0)
        d_str = str(trace.to_dict())
        self.assertNotIn("secret", d_str)

    def test_no_plaintext_in_summary(self) -> None:
        tmp = tempfile.mkdtemp()
        health = ProxyHealthStore(Path(tmp) / "test.sqlite3")
        health.record_success("http://admin:topsecret@proxy:8080", now=100.0)

        summary = health_store_summary(health, now=200.0)
        summary_str = str(summary)
        self.assertNotIn("topsecret", summary_str)
        self.assertNotIn("admin", summary_str)

    def test_trace_frozen(self) -> None:
        """ProxyTrace is immutable — no post-creation mutation."""
        trace = ProxyTrace.disabled()
        with self.assertRaises(AttributeError):
            trace.selected = True  # type: ignore[misc]


if __name__ == "__main__":
    unittest.main()
