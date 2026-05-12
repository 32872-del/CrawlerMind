"""Tests for the browser fallback executor path.

All tests use mocked Playwright to avoid requiring a real browser install
or network access in CI.
"""
from __future__ import annotations

import unittest
from unittest.mock import patch, MagicMock

from autonomous_crawler.agents.executor import executor_node
from autonomous_crawler.tools.browser_context import BrowserContextConfig
from autonomous_crawler.tools.browser_fetch import BrowserFetchResult


# ---------------------------------------------------------------------------
# 1. Browser success path
# ---------------------------------------------------------------------------

class TestBrowserSuccessPath(unittest.TestCase):
    """Executor should return rendered HTML on browser success."""

    @patch("autonomous_crawler.agents.executor.fetch_rendered_html")
    def test_browser_mode_returns_rendered_html(self, mock_fetch: MagicMock) -> None:
        mock_fetch.return_value = BrowserFetchResult(
            url="https://spa.example.com/page",
            html="<html><body><h1>Rendered</h1></body></html>",
            status="ok",
        )

        state = executor_node({
            "target_url": "https://spa.example.com/page",
            "crawl_strategy": {
                "mode": "browser",
                "extraction_method": "browser_render",
                "selectors": {},
                "headers": {},
            },
            "messages": [],
            "error_log": [],
        })

        self.assertEqual(state["status"], "executed")
        self.assertIn("https://spa.example.com/page", state["raw_html"])
        self.assertIn("Rendered", state["raw_html"]["https://spa.example.com/page"])
        self.assertEqual(state["visited_urls"], ["https://spa.example.com/page"])
        mock_fetch.assert_called_once()

    @patch("autonomous_crawler.agents.executor.fetch_rendered_html")
    def test_browser_mode_passes_strategy_options(self, mock_fetch: MagicMock) -> None:
        mock_fetch.return_value = BrowserFetchResult(
            url="https://example.com", html="<html></html>", status="ok"
        )

        executor_node({
            "target_url": "https://example.com",
            "crawl_strategy": {
                "mode": "browser",
                "extraction_method": "browser_render",
                "selectors": {},
                "headers": {},
                "wait_selector": ".content-loaded",
                "wait_until": "networkidle",
                "timeout_ms": 60000,
                "screenshot": True,
            },
            "messages": [],
            "error_log": [],
        })

        kwargs = mock_fetch.call_args.kwargs
        self.assertEqual(kwargs["url"], "https://example.com")
        self.assertEqual(kwargs["wait_selector"], ".content-loaded")
        self.assertEqual(kwargs["wait_until"], "networkidle")
        self.assertEqual(kwargs["timeout_ms"], 60000)
        self.assertTrue(kwargs["screenshot"])
        self.assertEqual(kwargs["headers"], {})
        self.assertEqual(kwargs["storage_state_path"], "")
        self.assertEqual(kwargs["proxy_url"], "")
        self.assertIsInstance(kwargs["browser_context"], BrowserContextConfig)

    @patch("autonomous_crawler.agents.executor.fetch_rendered_html")
    def test_browser_mode_includes_screenshot_path(self, mock_fetch: MagicMock) -> None:
        mock_fetch.return_value = BrowserFetchResult(
            url="https://example.com",
            html="<html></html>",
            status="ok",
            screenshot_path="/tmp/screenshot.png",
        )

        state = executor_node({
            "target_url": "https://example.com",
            "crawl_strategy": {
                "mode": "browser",
                "extraction_method": "browser_render",
                "selectors": {},
                "headers": {},
                "screenshot": True,
            },
            "messages": [],
            "error_log": [],
        })

        self.assertEqual(state["screenshot_path"], "/tmp/screenshot.png")

    @patch("autonomous_crawler.agents.executor.fetch_rendered_html")
    def test_browser_mode_follows_redirects(self, mock_fetch: MagicMock) -> None:
        """Final URL from browser (after redirects) should be used."""
        mock_fetch.return_value = BrowserFetchResult(
            url="https://example.com/final-page",
            html="<html>redirected</html>",
            status="ok",
        )

        state = executor_node({
            "target_url": "https://example.com/start",
            "crawl_strategy": {
                "mode": "browser",
                "extraction_method": "browser_render",
                "selectors": {},
                "headers": {},
            },
            "messages": [],
            "error_log": [],
        })

        self.assertEqual(state["visited_urls"], ["https://example.com/final-page"])
        self.assertIn("https://example.com/final-page", state["raw_html"])


# ---------------------------------------------------------------------------
# 2. Browser failure path
# ---------------------------------------------------------------------------

class TestBrowserFailurePath(unittest.TestCase):
    """Executor should handle browser failures gracefully."""

    @patch("autonomous_crawler.agents.executor.fetch_rendered_html")
    def test_browser_timeout_returns_failed(self, mock_fetch: MagicMock) -> None:
        mock_fetch.return_value = BrowserFetchResult(
            url="https://slow.example.com",
            html="",
            status="failed",
            error="Timeout 30000ms exceeded navigating to https://slow.example.com",
        )

        state = executor_node({
            "target_url": "https://slow.example.com",
            "crawl_strategy": {
                "mode": "browser",
                "extraction_method": "browser_render",
                "selectors": {},
                "headers": {},
            },
            "messages": [],
            "error_log": [],
        })

        self.assertEqual(state["status"], "failed")
        self.assertEqual(state["raw_html"], {})
        self.assertTrue(len(state["error_log"]) > 0)
        self.assertIn("Browser fetch failed", state["error_log"][0])

    @patch("autonomous_crawler.agents.executor.fetch_rendered_html")
    def test_browser_crash_returns_failed(self, mock_fetch: MagicMock) -> None:
        mock_fetch.return_value = BrowserFetchResult(
            url="https://crash.example.com",
            html="",
            status="failed",
            error="Browser process crashed",
        )

        state = executor_node({
            "target_url": "https://crash.example.com",
            "crawl_strategy": {
                "mode": "browser",
                "extraction_method": "browser_render",
                "selectors": {},
                "headers": {},
            },
            "messages": [],
            "error_log": [],
        })

        self.assertEqual(state["status"], "failed")
        self.assertIn("Browser process crashed", state["error_log"][0])

    @patch("autonomous_crawler.agents.executor.fetch_rendered_html")
    def test_browser_playwright_not_installed(self, mock_fetch: MagicMock) -> None:
        mock_fetch.return_value = BrowserFetchResult(
            url="https://example.com",
            html="",
            status="failed",
            error="playwright is not installed",
        )

        state = executor_node({
            "target_url": "https://example.com",
            "crawl_strategy": {
                "mode": "browser",
                "extraction_method": "browser_render",
                "selectors": {},
                "headers": {},
            },
            "messages": [],
            "error_log": [],
        })

        self.assertEqual(state["status"], "failed")
        self.assertIn("playwright is not installed", state["error_log"][0])


# ---------------------------------------------------------------------------
# 3. Existing path safety
# ---------------------------------------------------------------------------

class TestExistingPathsUnchanged(unittest.TestCase):
    """HTTP, mock, and fnspider paths must still work."""

    def test_mock_catalog_still_works(self) -> None:
        state = executor_node({
            "target_url": "mock://catalog",
            "crawl_strategy": {"mode": "http", "headers": {}},
            "messages": [],
            "error_log": [],
        })
        self.assertEqual(state["status"], "executed")
        self.assertIn("Alpha Jacket", state["raw_html"]["mock://catalog"])

    def test_mock_ranking_still_works(self) -> None:
        state = executor_node({
            "target_url": "mock://ranking",
            "crawl_strategy": {"mode": "http", "headers": {}},
            "messages": [],
            "error_log": [],
        })
        self.assertEqual(state["status"], "executed")
        self.assertIn("Alpha Topic", state["raw_html"]["mock://ranking"])

    def test_unsupported_scheme_still_fails(self) -> None:
        state = executor_node({
            "target_url": "ftp://files.example.com",
            "crawl_strategy": {"mode": "http", "headers": {}},
            "messages": [],
            "error_log": [],
        })
        self.assertEqual(state["status"], "failed")


# ---------------------------------------------------------------------------
# 4. browser_fetch.py unit tests
# ---------------------------------------------------------------------------

class TestBrowserFetchUnit(unittest.TestCase):
    """Test browser_fetch module directly (mocked Playwright)."""

    @patch("autonomous_crawler.tools.browser_fetch.sync_playwright")
    def test_fetch_returns_html_on_success(self, mock_pw_cls: MagicMock) -> None:
        mock_page = MagicMock()
        mock_page.url = "https://example.com"
        mock_page.content.return_value = "<html>rendered</html>"

        mock_context = MagicMock()
        mock_context.new_page.return_value = mock_page

        mock_browser = MagicMock()
        mock_browser.new_context.return_value = mock_context

        mock_pw = MagicMock()
        mock_pw.chromium.launch.return_value = mock_browser
        mock_pw_cls.return_value.__enter__ = MagicMock(return_value=mock_pw)
        mock_pw_cls.return_value.__exit__ = MagicMock(return_value=False)

        from autonomous_crawler.tools.browser_fetch import fetch_rendered_html
        result = fetch_rendered_html("https://example.com")

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.html, "<html>rendered</html>")
        self.assertEqual(result.url, "https://example.com")
        self.assertEqual(result.error, "")

    @patch("autonomous_crawler.tools.browser_fetch.sync_playwright")
    def test_fetch_returns_error_on_exception(self, mock_pw_cls: MagicMock) -> None:
        mock_pw = MagicMock()
        mock_pw.chromium.launch.side_effect = RuntimeError("Browser not found")
        mock_pw_cls.return_value.__enter__ = MagicMock(return_value=mock_pw)
        mock_pw_cls.return_value.__exit__ = MagicMock(return_value=False)

        from autonomous_crawler.tools.browser_fetch import fetch_rendered_html
        result = fetch_rendered_html("https://example.com")

        self.assertEqual(result.status, "failed")
        self.assertIn("Browser not found", result.error)

    @patch("autonomous_crawler.tools.browser_fetch.sync_playwright")
    def test_fetch_wait_for_selector(self, mock_pw_cls: MagicMock) -> None:
        mock_page = MagicMock()
        mock_page.url = "https://example.com"
        mock_page.content.return_value = "<html>loaded</html>"

        mock_context = MagicMock()
        mock_context.new_page.return_value = mock_page

        mock_browser = MagicMock()
        mock_browser.new_context.return_value = mock_context

        mock_pw = MagicMock()
        mock_pw.chromium.launch.return_value = mock_browser
        mock_pw_cls.return_value.__enter__ = MagicMock(return_value=mock_pw)
        mock_pw_cls.return_value.__exit__ = MagicMock(return_value=False)

        from autonomous_crawler.tools.browser_fetch import fetch_rendered_html
        fetch_rendered_html("https://example.com", wait_selector=".content")

        mock_page.wait_for_selector.assert_called_once_with(".content", timeout=30000)

    @patch("autonomous_crawler.tools.browser_fetch.sync_playwright")
    def test_fetch_screenshot(self, mock_pw_cls: MagicMock) -> None:
        mock_page = MagicMock()
        mock_page.url = "https://example.com"
        mock_page.content.return_value = "<html></html>"

        mock_context = MagicMock()
        mock_context.new_page.return_value = mock_page

        mock_browser = MagicMock()
        mock_browser.new_context.return_value = mock_context

        mock_pw = MagicMock()
        mock_pw.chromium.launch.return_value = mock_browser
        mock_pw_cls.return_value.__enter__ = MagicMock(return_value=mock_pw)
        mock_pw_cls.return_value.__exit__ = MagicMock(return_value=False)

        from autonomous_crawler.tools.browser_fetch import fetch_rendered_html
        result = fetch_rendered_html("https://example.com", screenshot=True)

        self.assertEqual(result.status, "ok")
        self.assertIn("screenshots", result.screenshot_path)
        mock_page.screenshot.assert_called_once()


if __name__ == "__main__":
    unittest.main()
