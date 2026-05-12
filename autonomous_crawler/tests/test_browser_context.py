from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from autonomous_crawler.tools.browser_context import (
    BrowserContextConfig,
    BrowserViewport,
    normalize_wait_until,
)
from autonomous_crawler.tools.browser_fetch import fetch_rendered_html
from autonomous_crawler.tools.browser_network_observer import observe_browser_network
from autonomous_crawler.agents.executor import executor_node


class BrowserContextConfigTests(unittest.TestCase):
    def test_from_dict_normalizes_viewport_and_choices(self) -> None:
        config = BrowserContextConfig.from_dict({
            "headless": False,
            "user_agent": "TestAgent/1.0",
            "viewport": {"width": 99, "height": 99999},
            "locale": "nl-NL",
            "timezone_id": "Europe/Amsterdam",
            "color_scheme": "invalid",
        })

        self.assertFalse(config.headless)
        self.assertEqual(config.user_agent, "TestAgent/1.0")
        self.assertEqual(config.viewport, BrowserViewport(width=320, height=2160))
        self.assertEqual(config.locale, "nl-NL")
        self.assertEqual(config.timezone_id, "Europe/Amsterdam")
        self.assertEqual(config.color_scheme, "light")

    def test_runtime_overrides_merge_headers_and_redact_safe_output(self) -> None:
        config = BrowserContextConfig.from_dict({
            "extra_http_headers": {"X-Base": "yes"},
            "proxy_url": "http://user:secret@proxy.example:8080",
        }).with_runtime_overrides(
            headers={"Authorization": "Bearer secret"},
            storage_state_path="state.json",
        )

        context_options = config.context_options()
        self.assertEqual(context_options["extra_http_headers"]["X-Base"], "yes")
        self.assertEqual(context_options["extra_http_headers"]["Authorization"], "Bearer secret")
        self.assertEqual(context_options["storage_state"], "state.json")

        safe = config.to_safe_dict()
        self.assertEqual(safe["extra_http_headers"]["Authorization"], "[redacted]")
        self.assertEqual(safe["proxy_url"], "http://***:***@proxy.example:8080")

    def test_storage_state_path_redacted_in_safe_output(self) -> None:
        config = BrowserContextConfig.from_dict({
            "storage_state_path": r"C:\Users\Alice\profiles\state.json",
        })

        safe = config.to_safe_dict()
        self.assertEqual(safe["storage_state_path"], "[redacted-path]/state.json")
        self.assertNotIn("Alice", str(safe))

    def test_launch_and_context_options_are_playwright_ready(self) -> None:
        config = BrowserContextConfig.from_dict({
            "headless": True,
            "viewport": {"width": 1440, "height": 900},
            "proxy_url": "socks5://proxy.example:1080",
        })

        self.assertEqual(config.launch_options()["proxy"]["server"], "socks5://proxy.example:1080")
        self.assertEqual(config.context_options()["viewport"], {"width": 1440, "height": 900})

    def test_normalize_wait_until(self) -> None:
        self.assertEqual(normalize_wait_until("networkidle"), "networkidle")
        self.assertEqual(normalize_wait_until("bad", default="load"), "load")


class BrowserContextIntegrationTests(unittest.TestCase):
    @patch("autonomous_crawler.tools.browser_fetch.sync_playwright")
    def test_fetch_rendered_html_uses_context_config(self, mock_pw_cls: MagicMock) -> None:
        mock_page = MagicMock()
        mock_page.url = "https://example.com"
        mock_page.content.return_value = "<html>ok</html>"
        mock_context = MagicMock()
        mock_context.new_page.return_value = mock_page
        mock_browser = MagicMock()
        mock_browser.new_context.return_value = mock_context
        mock_pw = MagicMock()
        mock_pw.chromium.launch.return_value = mock_browser
        mock_pw_cls.return_value.__enter__ = MagicMock(return_value=mock_pw)
        mock_pw_cls.return_value.__exit__ = MagicMock(return_value=False)

        result = fetch_rendered_html(
            "https://example.com",
            headers={"Authorization": "Bearer secret"},
            proxy_url="http://user:secret@proxy.example:8080",
            browser_context={
                "headless": False,
                "viewport": {"width": 1280, "height": 720},
                "locale": "pl-PL",
                "timezone_id": "Europe/Warsaw",
            },
        )

        mock_pw.chromium.launch.assert_called_once()
        self.assertFalse(mock_pw.chromium.launch.call_args.kwargs["headless"])
        self.assertEqual(
            mock_pw.chromium.launch.call_args.kwargs["proxy"]["server"],
            "http://user:secret@proxy.example:8080",
        )
        context_kwargs = mock_browser.new_context.call_args.kwargs
        self.assertEqual(context_kwargs["viewport"], {"width": 1280, "height": 720})
        self.assertEqual(context_kwargs["locale"], "pl-PL")
        self.assertEqual(context_kwargs["timezone_id"], "Europe/Warsaw")
        self.assertEqual(context_kwargs["extra_http_headers"]["Authorization"], "Bearer secret")
        self.assertEqual(result.browser_context["extra_http_headers"]["Authorization"], "[redacted]")
        self.assertEqual(result.browser_context["proxy_url"], "http://***:***@proxy.example:8080")

    @patch("autonomous_crawler.tools.browser_network_observer.sync_playwright")
    def test_network_observer_uses_context_config(self, mock_pw_cls: MagicMock) -> None:
        mock_page = MagicMock()
        mock_page.url = "https://example.com"
        mock_page.goto.return_value = None
        mock_context = MagicMock()
        mock_context.new_page.return_value = mock_page
        mock_browser = MagicMock()
        mock_browser.new_context.return_value = mock_context
        mock_pw = MagicMock()
        mock_pw.chromium.launch.return_value = mock_browser
        mock_pw_cls.return_value.__enter__ = MagicMock(return_value=mock_pw)
        mock_pw_cls.return_value.__exit__ = MagicMock(return_value=False)

        result = observe_browser_network(
            "https://example.com",
            browser_context={
                "viewport": {"width": 390, "height": 844},
                "locale": "en-GB",
                "extra_http_headers": {"X-Test": "yes"},
            },
            headers={"Cookie": "sid=secret"},
            storage_state_path="state.json",
        )

        context_kwargs = mock_browser.new_context.call_args.kwargs
        self.assertEqual(context_kwargs["viewport"], {"width": 390, "height": 844})
        self.assertEqual(context_kwargs["locale"], "en-GB")
        self.assertEqual(context_kwargs["extra_http_headers"]["X-Test"], "yes")
        self.assertEqual(context_kwargs["extra_http_headers"]["Cookie"], "sid=secret")
        self.assertEqual(context_kwargs["storage_state"], "state.json")
        self.assertEqual(result.browser_context["extra_http_headers"]["Cookie"], "[redacted]")

    @patch("autonomous_crawler.agents.executor.fetch_rendered_html")
    def test_executor_passes_browser_context_from_state(self, mock_fetch: MagicMock) -> None:
        mock_fetch.return_value = MagicMock(
            status="ok",
            url="https://example.com",
            html="<html>ok</html>",
            screenshot_path="",
            browser_context={"viewport": {"width": 1440, "height": 900}},
        )

        state = executor_node({
            "target_url": "https://example.com",
            "crawl_strategy": {"mode": "browser"},
            "access_config": {
                "browser_context": {
                    "viewport": {"width": 1440, "height": 900},
                    "locale": "de-DE",
                },
            },
            "messages": [],
        })

        self.assertEqual(state["status"], "executed")
        self.assertEqual(state["browser_context"]["viewport"], {"width": 1440, "height": 900})
        self.assertEqual(
            mock_fetch.call_args.kwargs["browser_context"].locale,
            "de-DE",
        )


if __name__ == "__main__":
    unittest.main()
