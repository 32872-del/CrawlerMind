"""Tests for Scrapling browser runtime contract.

Validates that CLM RuntimeRequest fields map correctly to Scrapling
DynamicFetcher / StealthyFetcher parameters.  No real browser or network
required — tests exercise config resolution and conversion logic only.
"""
from __future__ import annotations

import unittest

from autonomous_crawler.runtime.models import RuntimeRequest, RuntimeResponse, RuntimeProxyTrace
from autonomous_crawler.runtime.scrapling_browser import (
    MODE_DYNAMIC,
    MODE_PROTECTED,
    ScraplingBrowserConfig,
    ScraplingBrowserRuntime,
    clm_proxy_to_scrapling,
    clm_proxy_dict_for_browser,
    resolve_browser_config,
    select_scrapling_proxy,
    build_proxy_rotator,
)


class ResolveBrowserConfigDefaultsTests(unittest.TestCase):
    """Default config from a minimal RuntimeRequest."""

    def test_default_mode_is_dynamic(self):
        req = RuntimeRequest.from_dict({"url": "https://example.com"})
        config = resolve_browser_config(req)
        self.assertEqual(config.mode, MODE_DYNAMIC)

    def test_default_headless_true(self):
        req = RuntimeRequest.from_dict({"url": "https://example.com"})
        config = resolve_browser_config(req)
        self.assertTrue(config.headless)

    def test_default_real_chrome_false(self):
        req = RuntimeRequest.from_dict({"url": "https://example.com"})
        config = resolve_browser_config(req)
        self.assertFalse(config.real_chrome)

    def test_default_network_idle_false(self):
        req = RuntimeRequest.from_dict({"url": "https://example.com"})
        config = resolve_browser_config(req)
        self.assertFalse(config.network_idle)

    def test_default_timeout_30000(self):
        req = RuntimeRequest.from_dict({"url": "https://example.com"})
        config = resolve_browser_config(req)
        self.assertEqual(config.timeout_ms, 30000)

    def test_default_wait_selector_state_attached(self):
        req = RuntimeRequest.from_dict({"url": "https://example.com"})
        config = resolve_browser_config(req)
        self.assertEqual(config.wait_selector_state, "attached")

    def test_default_retries_3(self):
        req = RuntimeRequest.from_dict({"url": "https://example.com"})
        config = resolve_browser_config(req)
        self.assertEqual(config.retries, 3)


class ResolveBrowserConfigDynamicTests(unittest.TestCase):
    """Dynamic mode field mapping."""

    def test_mode_dynamic(self):
        req = RuntimeRequest.from_dict({"url": "https://example.com", "mode": "dynamic"})
        config = resolve_browser_config(req)
        self.assertEqual(config.mode, MODE_DYNAMIC)

    def test_headless_false(self):
        req = RuntimeRequest.from_dict({
            "url": "https://example.com",
            "browser_config": {"headless": False},
        })
        config = resolve_browser_config(req)
        self.assertFalse(config.headless)

    def test_real_chrome_true(self):
        req = RuntimeRequest.from_dict({
            "url": "https://example.com",
            "browser_config": {"real_chrome": True},
        })
        config = resolve_browser_config(req)
        self.assertTrue(config.real_chrome)

    def test_cdp_url(self):
        req = RuntimeRequest.from_dict({
            "url": "https://example.com",
            "browser_config": {"cdp_url": "ws://localhost:9222"},
        })
        config = resolve_browser_config(req)
        self.assertEqual(config.cdp_url, "ws://localhost:9222")

    def test_wait_selector_from_request(self):
        req = RuntimeRequest.from_dict({
            "url": "https://example.com",
            "wait_selector": ".content",
        })
        config = resolve_browser_config(req)
        self.assertEqual(config.wait_selector, ".content")

    def test_wait_selector_from_browser_config(self):
        req = RuntimeRequest.from_dict({
            "url": "https://example.com",
            "browser_config": {"wait_selector": ".items"},
        })
        config = resolve_browser_config(req)
        self.assertEqual(config.wait_selector, ".items")

    def test_wait_selector_state_visible(self):
        req = RuntimeRequest.from_dict({
            "url": "https://example.com",
            "browser_config": {"wait_selector_state": "visible"},
        })
        config = resolve_browser_config(req)
        self.assertEqual(config.wait_selector_state, "visible")

    def test_wait_selector_state_invalid_falls_back(self):
        req = RuntimeRequest.from_dict({
            "url": "https://example.com",
            "browser_config": {"wait_selector_state": "bogus"},
        })
        config = resolve_browser_config(req)
        self.assertEqual(config.wait_selector_state, "attached")

    def test_network_idle_from_wait_until(self):
        req = RuntimeRequest.from_dict({
            "url": "https://example.com",
            "wait_until": "networkidle",
        })
        config = resolve_browser_config(req)
        self.assertTrue(config.network_idle)

    def test_network_idle_from_browser_config(self):
        req = RuntimeRequest.from_dict({
            "url": "https://example.com",
            "browser_config": {"network_idle": True},
        })
        config = resolve_browser_config(req)
        self.assertTrue(config.network_idle)

    def test_network_idle_default_wait_until_domcontentloaded(self):
        req = RuntimeRequest.from_dict({
            "url": "https://example.com",
            "wait_until": "domcontentloaded",
        })
        config = resolve_browser_config(req)
        self.assertFalse(config.network_idle)

    def test_timeout_ms(self):
        req = RuntimeRequest.from_dict({
            "url": "https://example.com",
            "timeout_ms": 60000,
        })
        config = resolve_browser_config(req)
        self.assertEqual(config.timeout_ms, 60000)

    def test_capture_xhr(self):
        req = RuntimeRequest.from_dict({
            "url": "https://example.com",
            "capture_xhr": r"https://api\.example\.com/.*",
        })
        config = resolve_browser_config(req)
        self.assertEqual(config.capture_xhr, r"https://api\.example\.com/.*")

    def test_blocked_domains(self):
        req = RuntimeRequest.from_dict({
            "url": "https://example.com",
            "browser_config": {"blocked_domains": ["ads.example.com", "tracker.net"]},
        })
        config = resolve_browser_config(req)
        self.assertEqual(config.blocked_domains, frozenset({"ads.example.com", "tracker.net"}))

    def test_block_ads(self):
        req = RuntimeRequest.from_dict({
            "url": "https://example.com",
            "browser_config": {"block_ads": True},
        })
        config = resolve_browser_config(req)
        self.assertTrue(config.block_ads)

    def test_disable_resources(self):
        req = RuntimeRequest.from_dict({
            "url": "https://example.com",
            "browser_config": {"disable_resources": True},
        })
        config = resolve_browser_config(req)
        self.assertTrue(config.disable_resources)

    def test_locale(self):
        req = RuntimeRequest.from_dict({
            "url": "https://example.com",
            "browser_config": {"locale": "en-US"},
        })
        config = resolve_browser_config(req)
        self.assertEqual(config.locale, "en-US")

    def test_timezone_id(self):
        req = RuntimeRequest.from_dict({
            "url": "https://example.com",
            "browser_config": {"timezone_id": "America/New_York"},
        })
        config = resolve_browser_config(req)
        self.assertEqual(config.timezone_id, "America/New_York")

    def test_useragent(self):
        req = RuntimeRequest.from_dict({
            "url": "https://example.com",
            "browser_config": {"useragent": "CustomBot/1.0"},
        })
        config = resolve_browser_config(req)
        self.assertEqual(config.useragent, "CustomBot/1.0")

    def test_extra_headers(self):
        req = RuntimeRequest.from_dict({
            "url": "https://example.com",
            "browser_config": {"extra_headers": {"X-Custom": "value"}},
        })
        config = resolve_browser_config(req)
        self.assertEqual(config.extra_headers, {"X-Custom": "value"})

    def test_google_search_default_true(self):
        req = RuntimeRequest.from_dict({"url": "https://example.com"})
        config = resolve_browser_config(req)
        self.assertTrue(config.google_search)

    def test_dns_over_https(self):
        req = RuntimeRequest.from_dict({
            "url": "https://example.com",
            "browser_config": {"dns_over_https": True},
        })
        config = resolve_browser_config(req)
        self.assertTrue(config.dns_over_https)


class ResolveBrowserConfigProtectedTests(unittest.TestCase):
    """Protected (StealthyFetcher) mode field mapping."""

    def test_mode_protected(self):
        req = RuntimeRequest.from_dict({"url": "https://example.com", "mode": "protected"})
        config = resolve_browser_config(req)
        self.assertEqual(config.mode, MODE_PROTECTED)

    def test_solve_cloudflare_default_true(self):
        req = RuntimeRequest.from_dict({"url": "https://example.com", "mode": "protected"})
        config = resolve_browser_config(req)
        self.assertTrue(config.solve_cloudflare)

    def test_solve_cloudflare_false(self):
        req = RuntimeRequest.from_dict({
            "url": "https://example.com",
            "mode": "protected",
            "browser_config": {"solve_cloudflare": False},
        })
        config = resolve_browser_config(req)
        self.assertFalse(config.solve_cloudflare)

    def test_block_webrtc_default_true(self):
        req = RuntimeRequest.from_dict({"url": "https://example.com", "mode": "protected"})
        config = resolve_browser_config(req)
        self.assertTrue(config.block_webrtc)

    def test_hide_canvas_default_true(self):
        req = RuntimeRequest.from_dict({"url": "https://example.com", "mode": "protected"})
        config = resolve_browser_config(req)
        self.assertTrue(config.hide_canvas)

    def test_allow_webgl_default_true(self):
        req = RuntimeRequest.from_dict({"url": "https://example.com", "mode": "protected"})
        config = resolve_browser_config(req)
        self.assertTrue(config.allow_webgl)

    def test_protected_mode_fetch_kwargs_include_stealth(self):
        req = RuntimeRequest.from_dict({"url": "https://example.com", "mode": "protected"})
        config = resolve_browser_config(req)
        kwargs = config.to_fetch_kwargs()
        self.assertIn("solve_cloudflare", kwargs)
        self.assertIn("block_webrtc", kwargs)
        self.assertIn("hide_canvas", kwargs)
        self.assertIn("allow_webgl", kwargs)

    def test_dynamic_mode_fetch_kwargs_exclude_stealth(self):
        req = RuntimeRequest.from_dict({"url": "https://example.com", "mode": "dynamic"})
        config = resolve_browser_config(req)
        kwargs = config.to_fetch_kwargs()
        self.assertNotIn("solve_cloudflare", kwargs)
        self.assertNotIn("block_webrtc", kwargs)
        self.assertNotIn("hide_canvas", kwargs)
        self.assertNotIn("allow_webgl", kwargs)


class SessionConfigTests(unittest.TestCase):
    """Session continuity configuration."""

    def test_user_data_dir(self):
        req = RuntimeRequest.from_dict({
            "url": "https://example.com",
            "browser_config": {"user_data_dir": "/tmp/chrome_profile"},
        })
        config = resolve_browser_config(req)
        self.assertEqual(config.user_data_dir, "/tmp/chrome_profile")

    def test_max_pages(self):
        req = RuntimeRequest.from_dict({
            "url": "https://example.com",
            "browser_config": {"max_pages": 5},
        })
        config = resolve_browser_config(req)
        self.assertEqual(config.max_pages, 5)

    def test_session_kwargs_include_max_pages(self):
        req = RuntimeRequest.from_dict({
            "url": "https://example.com",
            "browser_config": {"max_pages": 3},
        })
        config = resolve_browser_config(req)
        sk = config.to_session_kwargs()
        self.assertEqual(sk["max_pages"], 3)

    def test_session_kwargs_include_user_data_dir(self):
        req = RuntimeRequest.from_dict({
            "url": "https://example.com",
            "browser_config": {"user_data_dir": "/tmp/profile"},
        })
        config = resolve_browser_config(req)
        sk = config.to_session_kwargs()
        self.assertEqual(sk["user_data_dir"], "/tmp/profile")

    def test_session_kwargs_exclude_wait(self):
        req = RuntimeRequest.from_dict({
            "url": "https://example.com",
            "browser_config": {"wait_ms": 2000},
        })
        config = resolve_browser_config(req)
        sk = config.to_session_kwargs()
        self.assertNotIn("wait", sk)


class FetchKwargsMappingTests(unittest.TestCase):
    """Verify to_fetch_kwargs() output structure."""

    def test_basic_kwargs(self):
        config = ScraplingBrowserConfig()
        kwargs = config.to_fetch_kwargs()
        self.assertIn("headless", kwargs)
        self.assertIn("network_idle", kwargs)
        self.assertIn("timeout", kwargs)
        self.assertIn("google_search", kwargs)
        self.assertIn("retries", kwargs)

    def test_real_chrome_kwarg(self):
        config = ScraplingBrowserConfig(real_chrome=True)
        kwargs = config.to_fetch_kwargs()
        self.assertTrue(kwargs["real_chrome"])

    def test_cdp_url_kwarg(self):
        config = ScraplingBrowserConfig(cdp_url="ws://localhost:9222")
        kwargs = config.to_fetch_kwargs()
        self.assertEqual(kwargs["cdp_url"], "ws://localhost:9222")

    def test_wait_selector_kwarg(self):
        config = ScraplingBrowserConfig(wait_selector=".item", wait_selector_state="visible")
        kwargs = config.to_fetch_kwargs()
        self.assertEqual(kwargs["wait_selector"], ".item")
        self.assertEqual(kwargs["wait_selector_state"], "visible")

    def test_blocked_domains_kwarg_is_set(self):
        config = ScraplingBrowserConfig(blocked_domains=frozenset({"ads.com"}))
        kwargs = config.to_fetch_kwargs()
        self.assertIsInstance(kwargs["blocked_domains"], set)
        self.assertIn("ads.com", kwargs["blocked_domains"])

    def test_capture_xhr_kwarg(self):
        config = ScraplingBrowserConfig(capture_xhr=r"https://api\..*")
        kwargs = config.to_fetch_kwargs()
        self.assertEqual(kwargs["capture_xhr"], r"https://api\..*")

    def test_no_optional_keys_when_empty(self):
        config = ScraplingBrowserConfig()
        kwargs = config.to_fetch_kwargs()
        self.assertNotIn("real_chrome", kwargs)
        self.assertNotIn("cdp_url", kwargs)
        self.assertNotIn("wait_selector", kwargs)
        self.assertNotIn("blocked_domains", kwargs)
        self.assertNotIn("capture_xhr", kwargs)
        self.assertNotIn("disable_resources", kwargs)
        self.assertNotIn("locale", kwargs)
        self.assertNotIn("useragent", kwargs)


class BrowserRuntimeProtocolTests(unittest.TestCase):
    """ScraplingBrowserRuntime satisfies BrowserRuntime protocol."""

    def test_has_name(self):
        runtime = ScraplingBrowserRuntime()
        self.assertEqual(runtime.name, "scrapling_browser")

    def test_has_render_method(self):
        runtime = ScraplingBrowserRuntime()
        self.assertTrue(callable(getattr(runtime, "render", None)))

    def test_runtime_checkable(self):
        from autonomous_crawler.runtime.protocols import BrowserRuntime
        runtime = ScraplingBrowserRuntime()
        self.assertIsInstance(runtime, BrowserRuntime)


class BrowserRuntimeRenderWithoutScraplingTests(unittest.TestCase):
    """render() returns failure when Scrapling is not installed."""

    def test_render_returns_failure_without_scrapling(self):
        runtime = ScraplingBrowserRuntime()
        req = RuntimeRequest.from_dict({"url": "https://example.com"})
        # Patch _HAS_SCRAPLING to False
        import autonomous_crawler.runtime.scrapling_browser as mod
        original = mod._HAS_SCRAPLING
        try:
            mod._HAS_SCRAPLING = False
            resp = runtime.render(req)
        finally:
            mod._HAS_SCRAPLING = original
        self.assertFalse(resp.ok)
        self.assertIn("not installed", resp.error)
        self.assertEqual(resp.engine_result.get("engine"), "scrapling_browser")


class BrowserRuntimeResponseShapeTests(unittest.TestCase):
    """Verify RuntimeResponse shape from _build_response."""

    def test_build_response_ok(self):
        class FakeResponse:
            url = "https://example.com/final"
            status = 200
            headers = {"content-type": "text/html"}
            cookies = {"session": "abc"}
            body = b"<html>ok</html>"
            text = "ok"
            captured_xhr = []

        resp = ScraplingBrowserRuntime._build_response(
            "https://example.com", FakeResponse(), [],
            {"selected": False, "source": "disabled"},
        )
        self.assertTrue(resp.ok)
        self.assertEqual(resp.final_url, "https://example.com/final")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("<html>", resp.html)
        self.assertEqual(resp.engine_result["engine"], "scrapling_browser")
        self.assertFalse(resp.proxy_trace.selected)

    def test_build_response_with_xhr(self):
        class FakeXhr:
            url = "https://api.example.com/data"
            status = 200
            body = b'{"items": []}'

        class FakeResponse:
            url = "https://example.com"
            status = 200
            headers = {}
            cookies = {}
            body = b"<html></html>"
            text = ""
            captured_xhr = [FakeXhr()]

        resp = ScraplingBrowserRuntime._build_response(
            "https://example.com", FakeResponse(), [],
            {"selected": True, "source": "direct"},
        )
        self.assertEqual(len(resp.captured_xhr), 1)
        self.assertEqual(resp.captured_xhr[0]["url"], "https://api.example.com/data")
        self.assertTrue(resp.proxy_trace.selected)

    def test_build_response_failure_status(self):
        class FakeResponse:
            url = "https://example.com"
            status = 403
            headers = {}
            cookies = {}
            body = b"Forbidden"
            text = "Forbidden"
            captured_xhr = []

        resp = ScraplingBrowserRuntime._build_response(
            "https://example.com", FakeResponse(), [],
            {"selected": False, "source": "disabled"},
        )
        self.assertFalse(resp.ok)
        self.assertEqual(resp.status_code, 403)


class SelectScraplingProxyTests(unittest.TestCase):
    """select_scrapling_proxy() logic."""

    def test_no_proxy(self):
        arg, info = select_scrapling_proxy("")
        self.assertIsNone(arg)
        self.assertFalse(info["selected"])
        self.assertEqual(info["source"], "disabled")

    def test_direct_proxy(self):
        arg, info = select_scrapling_proxy("http://user:pass@proxy:8080")
        self.assertIsNotNone(arg)
        self.assertTrue(info["selected"])
        self.assertEqual(info["source"], "direct")

    def test_with_rotator(self):
        arg, info = select_scrapling_proxy("http://proxy:8080", proxy_rotator="fake_rotator")
        self.assertIsNone(arg)
        self.assertTrue(info["selected"])
        self.assertEqual(info["source"], "rotator")


class BuildProxyRotatorTests(unittest.TestCase):
    """build_proxy_rotator() behavior without real Scrapling."""

    def test_empty_urls_returns_none(self):
        result = build_proxy_rotator([])
        self.assertIsNone(result)

    def test_cyclic_strategy(self):
        # Mock ProxyRotator
        import autonomous_crawler.runtime.scrapling_browser as mod
        if not mod._HAS_SCRAPLING:
            self.skipTest("scrapling not installed")
        rotator = build_proxy_rotator(["http://a.proxy:8080", "http://b.proxy:8080"])
        self.assertIsNotNone(rotator)

    def test_random_strategy(self):
        import autonomous_crawler.runtime.scrapling_browser as mod
        if not mod._HAS_SCRAPLING:
            self.skipTest("scrapling not installed")
        rotator = build_proxy_rotator(["http://a.proxy:8080"], strategy="random")
        self.assertIsNotNone(rotator)


class InvalidModeFallbackTests(unittest.TestCase):
    """Invalid mode falls back to dynamic."""

    def test_invalid_mode_falls_back(self):
        req = RuntimeRequest.from_dict({"url": "https://example.com", "mode": "spider"})
        config = resolve_browser_config(req)
        self.assertEqual(config.mode, MODE_DYNAMIC)


if __name__ == "__main__":
    unittest.main()
