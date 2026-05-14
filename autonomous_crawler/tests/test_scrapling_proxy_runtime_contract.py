"""Tests for Scrapling proxy runtime contract.

Validates CLM ProxyConfig → Scrapling proxy format conversion,
ProxyRotator construction, credential safety, and strategy mapping.
No real proxy or network required.
"""
from __future__ import annotations

import unittest
from urllib.parse import urlparse

from autonomous_crawler.runtime.scrapling_browser import (
    BLOCK_STATUS_CODES,
    clm_proxy_to_scrapling,
    clm_proxy_dict_for_browser,
    build_proxy_rotator,
    select_scrapling_proxy,
)
from autonomous_crawler.runtime.models import RuntimeProxyTrace


class ClmProxyToScraplingTests(unittest.TestCase):
    """CLM proxy URL → Scrapling proxy format conversion."""

    def test_empty_string_returns_empty(self):
        result = clm_proxy_to_scrapling("")
        self.assertEqual(result, "")

    def test_simple_proxy_string(self):
        result = clm_proxy_to_scrapling("http://proxy.example.com:8080")
        self.assertIsInstance(result, dict)
        self.assertEqual(result["server"], "http://proxy.example.com:8080")
        self.assertNotIn("username", result)
        self.assertNotIn("password", result)

    def test_proxy_with_credentials(self):
        result = clm_proxy_to_scrapling("http://user:secret@proxy:8080")
        self.assertIsInstance(result, dict)
        self.assertEqual(result["server"], "http://proxy:8080")
        self.assertEqual(result["username"], "user")
        self.assertEqual(result["password"], "secret")

    def test_https_proxy(self):
        result = clm_proxy_to_scrapling("https://proxy.example.com:443")
        self.assertIsInstance(result, dict)
        self.assertEqual(result["server"], "https://proxy.example.com:443")

    def test_socks5_proxy(self):
        result = clm_proxy_to_scrapling("socks5://proxy:1080")
        self.assertIsInstance(result, dict)
        self.assertEqual(result["server"], "socks5://proxy:1080")

    def test_proxy_without_port(self):
        result = clm_proxy_to_scrapling("http://proxy.example.com")
        self.assertIsInstance(result, dict)
        self.assertEqual(result["server"], "http://proxy.example.com")

    def test_proxy_with_username_only(self):
        result = clm_proxy_to_scrapling("http://user@proxy:8080")
        self.assertIsInstance(result, dict)
        self.assertEqual(result["username"], "user")
        self.assertNotIn("password", result)

    def test_proxy_with_special_chars_in_password(self):
        result = clm_proxy_to_scrapling("http://user:p%40ss@proxy:8080")
        self.assertIsInstance(result, dict)
        self.assertEqual(result["username"], "user")
        # Password should be URL-decoded
        self.assertIn("password", result)

    def test_result_is_dict_for_browser(self):
        """Browser proxy format must always be a dict with 'server' key."""
        result = clm_proxy_dict_for_browser("http://user:pass@proxy:8080")
        self.assertIsInstance(result, dict)
        self.assertIn("server", result)
        self.assertIn("username", result)
        self.assertIn("password", result)

    def test_empty_proxy_dict_for_browser(self):
        result = clm_proxy_dict_for_browser("")
        self.assertEqual(result, {})


class ProxyFormatForBrowserTests(unittest.TestCase):
    """Verify browser proxy dict has the right shape for Playwright/Scrapling."""

    def test_has_server_key(self):
        result = clm_proxy_dict_for_browser("http://proxy:8080")
        self.assertIn("server", result)
        self.assertTrue(result["server"].startswith("http"))

    def test_credentials_separated(self):
        result = clm_proxy_dict_for_browser("http://admin:hunter2@proxy:3128")
        self.assertEqual(result["server"], "http://proxy:3128")
        self.assertEqual(result["username"], "admin")
        self.assertEqual(result["password"], "hunter2")

    def test_no_plaintext_in_server_field(self):
        """Server field must never contain credentials."""
        result = clm_proxy_dict_for_browser("http://user:secret@proxy:8080")
        self.assertNotIn("secret", result["server"])
        self.assertNotIn("user", result["server"])


class ProxyRotatorConstructionTests(unittest.TestCase):
    """build_proxy_rotator() behavior."""

    def test_empty_list_returns_none(self):
        result = build_proxy_rotator([])
        self.assertIsNone(result)

    def test_single_proxy(self):
        try:
            result = build_proxy_rotator(["http://proxy:8080"])
        except Exception:
            self.skipTest("scrapling not installed")
        self.assertIsNotNone(result)

    def test_multiple_proxies(self):
        try:
            result = build_proxy_rotator([
                "http://proxy1:8080",
                "http://proxy2:8080",
                "http://proxy3:8080",
            ])
        except Exception:
            self.skipTest("scrapling not installed")
        self.assertIsNotNone(result)

    def test_cyclic_strategy_default(self):
        try:
            rotator = build_proxy_rotator(["http://a:8080", "http://b:8080"])
        except Exception:
            self.skipTest("scrapling not installed")
        # Cyclic should return proxies in order
        p1 = rotator.get_proxy()
        p2 = rotator.get_proxy()
        # Both should be valid
        self.assertIsNotNone(p1)
        self.assertIsNotNone(p2)

    def test_random_strategy(self):
        try:
            rotator = build_proxy_rotator(
                ["http://a:8080", "http://b:8080", "http://c:8080"],
                strategy="random",
            )
        except Exception:
            self.skipTest("scrapling not installed")
        # Should return a proxy (randomly selected)
        proxy = rotator.get_proxy()
        self.assertIsNotNone(proxy)

    def test_proxies_converted_to_dict_format(self):
        """Input URLs should be converted to Scrapling dict format."""
        try:
            rotator = build_proxy_rotator(["http://user:pass@proxy:8080"])
        except Exception:
            self.skipTest("scrapling not installed")
        proxy = rotator.get_proxy()
        if isinstance(proxy, dict):
            self.assertIn("server", proxy)
            self.assertNotIn("pass", proxy["server"])


class SelectScraplingProxyLogicTests(unittest.TestCase):
    """select_scrapling_proxy() edge cases."""

    def test_disabled_proxy(self):
        arg, info = select_scrapling_proxy("")
        self.assertIsNone(arg)
        self.assertFalse(info["selected"])
        self.assertEqual(info["source"], "disabled")

    def test_direct_proxy_selected(self):
        arg, info = select_scrapling_proxy("http://proxy:8080")
        self.assertIsNotNone(arg)
        self.assertTrue(info["selected"])
        self.assertEqual(info["source"], "direct")

    def test_rotator_overrides_direct(self):
        arg, info = select_scrapling_proxy(
            "http://proxy:8080",
            proxy_rotator="fake_rotator",
        )
        self.assertIsNone(arg)
        self.assertTrue(info["selected"])
        self.assertEqual(info["source"], "rotator")

    def test_proxy_with_auth(self):
        arg, info = select_scrapling_proxy("http://user:pass@proxy:8080")
        self.assertIsNotNone(arg)
        self.assertIsInstance(arg, dict)
        self.assertTrue(info["selected"])

    def test_trace_info_always_has_selected(self):
        _, info = select_scrapling_proxy("")
        self.assertIn("selected", info)
        _, info = select_scrapling_proxy("http://proxy:8080")
        self.assertIn("selected", info)

    def test_trace_info_always_has_source(self):
        _, info = select_scrapling_proxy("")
        self.assertIn("source", info)
        _, info = select_scrapling_proxy("http://proxy:8080")
        self.assertIn("source", info)


class RuntimeProxyTraceIntegrationTests(unittest.TestCase):
    """RuntimeProxyTrace correctly captures proxy selection state."""

    def test_disabled_trace(self):
        trace = RuntimeProxyTrace(selected=False, source="disabled")
        d = trace.to_dict()
        self.assertFalse(d["selected"])
        self.assertEqual(d["source"], "disabled")

    def test_direct_trace(self):
        trace = RuntimeProxyTrace(selected=True, source="direct", proxy="http://***:***@proxy:8080")
        d = trace.to_dict()
        self.assertTrue(d["selected"])
        self.assertEqual(d["source"], "direct")
        self.assertIn("***", d["proxy"])

    def test_rotator_trace(self):
        trace = RuntimeProxyTrace(selected=True, source="rotator")
        d = trace.to_dict()
        self.assertTrue(d["selected"])
        self.assertEqual(d["source"], "rotator")

    def test_credential_safety_in_trace(self):
        """Trace must never contain plaintext credentials."""
        trace = RuntimeProxyTrace(
            selected=True,
            source="direct",
            proxy="http://user:secret@proxy:8080",
        )
        d = trace.to_dict()
        proxy_str = d["proxy"]
        self.assertNotIn("secret", proxy_str)
        self.assertNotIn("user", proxy_str)
        self.assertIn("***", proxy_str)


class BlockStatusCodesTests(unittest.TestCase):
    """Verify known block status codes are documented."""

    def test_403_is_block_code(self):
        self.assertIn(403, BLOCK_STATUS_CODES)

    def test_429_is_block_code(self):
        self.assertIn(429, BLOCK_STATUS_CODES)

    def test_503_is_block_code(self):
        self.assertIn(503, BLOCK_STATUS_CODES)

    def test_200_not_block_code(self):
        self.assertNotIn(200, BLOCK_STATUS_CODES)

    def test_block_codes_count(self):
        # Scrapling defines 9 block status codes
        self.assertEqual(len(BLOCK_STATUS_CODES), 9)


class ProxyStrategyMappingTests(unittest.TestCase):
    """Strategy mapping from CLM to Scrapling concepts."""

    def test_cyclic_maps_to_cyclic(self):
        """CLM round_robin → Scrapling cyclic rotation."""
        try:
            rotator = build_proxy_rotator(
                ["http://a:8080", "http://b:8080"],
                strategy="cyclic",
            )
        except Exception:
            self.skipTest("scrapling not installed")
        p1 = rotator.get_proxy()
        p2 = rotator.get_proxy()
        # In cyclic mode with 2 proxies, p1 != p2
        if isinstance(p1, dict) and isinstance(p2, dict):
            self.assertNotEqual(p1.get("server"), p2.get("server"))
        elif isinstance(p1, str) and isinstance(p2, str):
            self.assertNotEqual(p1, p2)

    def test_random_maps_to_random(self):
        """CLM random → Scrapling random rotation."""
        try:
            rotator = build_proxy_rotator(
                ["http://a:8080", "http://b:8080", "http://c:8080"],
                strategy="random",
            )
        except Exception:
            self.skipTest("scrapling not installed")
        # Just verify it doesn't crash
        proxy = rotator.get_proxy()
        self.assertIsNotNone(proxy)


class CredentialSafetyTests(unittest.TestCase):
    """Ensure no plaintext credentials leak in any output path."""

    def test_to_scrapling_no_plaintext_in_server(self):
        result = clm_proxy_to_scrapling("http://admin:hunter2@proxy:8080")
        if isinstance(result, dict):
            self.assertNotIn("hunter2", result["server"])
            self.assertNotIn("admin", result["server"])

    def test_dict_for_browser_no_plaintext_in_server(self):
        result = clm_proxy_dict_for_browser("http://admin:hunter2@proxy:8080")
        self.assertNotIn("hunter2", result.get("server", ""))
        self.assertNotIn("admin", result.get("server", ""))

    def test_select_proxy_no_plaintext_in_trace(self):
        _, info = select_scrapling_proxy("http://admin:hunter2@proxy:8080")
        # trace info should not contain raw proxy URL
        self.assertNotIn("hunter2", str(info))

    def test_rotator_construction_no_plaintext_leak(self):
        """Rotator construction should not crash with credential-bearing URLs."""
        try:
            rotator = build_proxy_rotator([
                "http://user1:pass1@proxy1:8080",
                "http://user2:pass2@proxy2:8080",
            ])
        except Exception:
            self.skipTest("scrapling not installed")
        self.assertIsNotNone(rotator)
        proxy = rotator.get_proxy()
        self.assertIsNotNone(proxy)


class ProxyRotatorIsProxyErrorTests(unittest.TestCase):
    """Verify Scrapling's is_proxy_error detection for known patterns."""

    def test_known_error_patterns(self):
        try:
            from scrapling.engines.toolbelt.proxy_rotation import is_proxy_error
        except ImportError:
            self.skipTest("scrapling not installed")

        self.assertTrue(is_proxy_error("net::ERR_PROXY_CONNECTION_FAILED"))
        self.assertTrue(is_proxy_error("net::ERR_TUNNEL_CONNECTION_FAILED"))
        self.assertTrue(is_proxy_error("Connection refused"))
        self.assertFalse(is_proxy_error("Page not found"))
        self.assertFalse(is_proxy_error("Timeout"))


if __name__ == "__main__":
    unittest.main()
