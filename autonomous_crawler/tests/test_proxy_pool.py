"""Tests for pluggable proxy pool foundation (CAP-3.3)."""
from __future__ import annotations

import unittest

from autonomous_crawler.tools.proxy_manager import ProxyConfig, ProxyManager
from autonomous_crawler.tools.proxy_pool import (
    ProxyEndpoint,
    ProxyPoolConfig,
    StaticProxyPoolProvider,
    redact_proxy_url,
)


class ProxyEndpointTests(unittest.TestCase):
    def test_from_string(self) -> None:
        endpoint = ProxyEndpoint.from_dict("http://proxy.example:8080")
        self.assertEqual(endpoint.url, "http://proxy.example:8080")
        self.assertTrue(endpoint.enabled)

    def test_validate_rejects_bad_scheme(self) -> None:
        endpoint = ProxyEndpoint.from_dict({"url": "ftp://proxy.example"})
        self.assertTrue(endpoint.validate())

    def test_safe_dict_redacts_credentials(self) -> None:
        endpoint = ProxyEndpoint.from_dict("http://user:secret@proxy.example:8080")
        safe = endpoint.to_safe_dict()
        self.assertNotIn("secret", str(safe))
        self.assertEqual(safe["url"], "http://***:***@proxy.example:8080")

    def test_cooldown_marks_unavailable(self) -> None:
        endpoint = ProxyEndpoint.from_dict({"url": "http://proxy.example:8080", "cooldown_until": 100})
        self.assertFalse(endpoint.is_available(now=10))
        self.assertTrue(endpoint.is_available(now=100))


class ProxyPoolConfigTests(unittest.TestCase):
    def test_default_disabled(self) -> None:
        config = ProxyPoolConfig.from_dict({})
        self.assertFalse(config.enabled)
        self.assertEqual(config.endpoints, ())

    def test_from_dict_accepts_proxies_alias(self) -> None:
        config = ProxyPoolConfig.from_dict({
            "enabled": True,
            "proxies": ["http://a.proxy:8080", "http://b.proxy:8080"],
        })
        self.assertEqual(len(config.endpoints), 2)

    def test_invalid_strategy_falls_back(self) -> None:
        config = ProxyPoolConfig.from_dict({"strategy": "unknown"})
        self.assertEqual(config.strategy, "round_robin")

    def test_enabled_without_endpoints_reports_error(self) -> None:
        config = ProxyPoolConfig.from_dict({"enabled": True})
        self.assertIn("proxy pool enabled but no endpoints configured", config.validate())


class StaticProxyPoolProviderTests(unittest.TestCase):
    def test_disabled_pool_selects_nothing(self) -> None:
        provider = StaticProxyPoolProvider({})
        selection = provider.select("https://example.com")
        self.assertFalse(selection.proxy_url)
        self.assertEqual(selection.source, "pool_disabled")

    def test_round_robin_rotation(self) -> None:
        provider = StaticProxyPoolProvider({
            "enabled": True,
            "strategy": "round_robin",
            "endpoints": ["http://a.proxy:8080", "http://b.proxy:8080"],
        })

        first = provider.select("https://example.com").proxy_url
        second = provider.select("https://example.com").proxy_url
        third = provider.select("https://example.com").proxy_url

        self.assertEqual(first, "http://a.proxy:8080")
        self.assertEqual(second, "http://b.proxy:8080")
        self.assertEqual(third, "http://a.proxy:8080")

    def test_domain_sticky_keeps_same_proxy_for_domain(self) -> None:
        provider = StaticProxyPoolProvider({
            "enabled": True,
            "strategy": "domain_sticky",
            "endpoints": ["http://a.proxy:8080", "http://b.proxy:8080"],
        })

        first = provider.select("https://shop.example.com/a").proxy_url
        second = provider.select("https://shop.example.com/b").proxy_url
        other = provider.select("https://other.example.com/a").proxy_url

        self.assertEqual(first, second)
        self.assertIn(other, {"http://a.proxy:8080", "http://b.proxy:8080"})

    def test_first_healthy_skips_failed_endpoint(self) -> None:
        provider = StaticProxyPoolProvider({
            "enabled": True,
            "strategy": "first_healthy",
            "max_failures": 2,
            "endpoints": ["http://a.proxy:8080", "http://b.proxy:8080"],
        })
        provider.report_result("http://a.proxy:8080", ok=False, error="timeout")
        provider.report_result("http://a.proxy:8080", ok=False, error="timeout")

        selection = provider.select("https://example.com")

        self.assertEqual(selection.proxy_url, "http://b.proxy:8080")

    def test_report_success_resets_failure_count(self) -> None:
        provider = StaticProxyPoolProvider({
            "enabled": True,
            "max_failures": 2,
            "endpoints": ["http://a.proxy:8080"],
        })
        provider.report_result("http://a.proxy:8080", ok=False, error="timeout")
        provider.report_result("http://a.proxy:8080", ok=True)

        selection = provider.select("https://example.com")

        self.assertEqual(selection.proxy_url, "http://a.proxy:8080")

    def test_safe_dict_redacts_runtime_state(self) -> None:
        provider = StaticProxyPoolProvider({
            "enabled": True,
            "endpoints": ["http://user:secret@a.proxy:8080"],
        })
        provider.report_result("http://user:secret@a.proxy:8080", ok=False, error="bad password secret")
        safe = provider.to_safe_dict()

        self.assertNotIn("user:secret", str(safe))
        self.assertIn("***", str(safe))


class ProxyManagerPoolIntegrationTests(unittest.TestCase):
    def test_pool_used_when_no_domain_rule(self) -> None:
        manager = ProxyManager(ProxyConfig.from_dict({
            "enabled": True,
            "pool": {
                "enabled": True,
                "endpoints": ["http://pool.proxy:8080"],
            },
        }))

        self.assertEqual(manager.select_proxy("https://example.com"), "http://pool.proxy:8080")
        desc = manager.describe_selection("https://example.com")
        self.assertEqual(desc["source"], "pool_round_robin")

    def test_per_domain_rule_overrides_pool(self) -> None:
        manager = ProxyManager(ProxyConfig.from_dict({
            "enabled": True,
            "per_domain": {"shop.example": "http://domain.proxy:8080"},
            "pool": {"enabled": True, "endpoints": ["http://pool.proxy:8080"]},
        }))

        self.assertEqual(manager.select_proxy("https://shop.example/a"), "http://domain.proxy:8080")
        self.assertEqual(manager.describe_selection("https://shop.example/a")["source"], "per_domain")

    def test_default_proxy_used_after_empty_pool(self) -> None:
        manager = ProxyManager(ProxyConfig.from_dict({
            "enabled": True,
            "default_proxy": "http://default.proxy:8080",
            "pool": {"enabled": False, "endpoints": ["http://pool.proxy:8080"]},
        }))

        self.assertEqual(manager.select_proxy("https://example.com"), "http://default.proxy:8080")

    def test_proxy_config_allows_pool_only(self) -> None:
        config = ProxyConfig.from_dict({
            "enabled": True,
            "pool": {"enabled": True, "endpoints": ["http://pool.proxy:8080"]},
        })

        self.assertEqual(config.validate(), [])

    def test_redact_proxy_url_helper(self) -> None:
        self.assertEqual(
            redact_proxy_url("socks5://u:p@proxy.example:1080"),
            "socks5://***:***@proxy.example:1080",
        )


if __name__ == "__main__":
    unittest.main()
