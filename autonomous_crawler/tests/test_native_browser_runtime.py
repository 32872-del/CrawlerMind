"""Tests for CLM-native browser runtime (SCRAPLING-ABSORB-2A)."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from autonomous_crawler.runtime import BrowserRuntime, RuntimeRequest
from autonomous_crawler.runtime.native_browser import (
    NativeBrowserRuntime,
    resolve_native_browser_config,
)


def _setup_mock_playwright(mock_sync_playwright: MagicMock) -> tuple[MagicMock, MagicMock, list, list]:
    route_handlers: list = []
    response_handlers: list = []

    mock_nav_response = MagicMock()
    mock_nav_response.status = 200
    mock_nav_response.headers = {"content-type": "text/html"}

    mock_page = MagicMock()
    mock_page.url = "https://example.com/app"
    mock_page.content.return_value = "<main><h1>Rendered</h1></main>"
    mock_page.goto.return_value = mock_nav_response

    def route_side_effect(pattern: str, handler):
        route_handlers.append(handler)

    def on_side_effect(event: str, handler):
        if event == "response":
            response_handlers.append(handler)

    mock_page.route.side_effect = route_side_effect
    mock_page.on.side_effect = on_side_effect

    mock_context = MagicMock()
    mock_context.new_page.return_value = mock_page
    mock_context.cookies.return_value = [{"name": "sid", "value": "abc"}]

    mock_browser = MagicMock()
    mock_browser.new_context.return_value = mock_context

    mock_pw = MagicMock()
    mock_pw.chromium.launch.return_value = mock_browser

    mock_sync_playwright.return_value.__enter__ = MagicMock(return_value=mock_pw)
    mock_sync_playwright.return_value.__exit__ = MagicMock(return_value=False)
    return mock_page, mock_context, route_handlers, response_handlers


def _mock_response(
    url: str,
    *,
    resource_type: str = "xhr",
    content_type: str = "application/json",
    status: int = 200,
    method: str = "GET",
    body: bytes = b'{"items":[1]}',
) -> MagicMock:
    request = MagicMock()
    request.url = url
    request.resource_type = resource_type
    request.method = method

    response = MagicMock()
    response.url = url
    response.status = status
    response.headers = {"content-type": content_type}
    response.request = request
    response.body.return_value = body
    return response


class NativeBrowserConfigTests(unittest.TestCase):
    def test_resolves_wait_state_and_resource_blocking(self) -> None:
        request = RuntimeRequest.from_dict({
            "url": "https://example.com",
            "mode": "protected",
            "browser_config": {
                "wait_selector_state": "visible",
                "disable_resources": True,
                "blocked_domains": ["ads.example.com"],
                "capture_js": True,
                "max_captures": 3,
                "user_data_dir": "/tmp/clm-profile",
                "storage_state_output_path": "/tmp/clm-state/state.json",
                "visual_recon": True,
            },
        })

        config = resolve_native_browser_config(request)

        self.assertEqual(config.mode, "protected")
        self.assertEqual(config.wait_selector_state, "visible")
        self.assertIn("image", config.block_resource_types)
        self.assertIn("stylesheet", config.block_resource_types)
        self.assertEqual(config.blocked_domains, frozenset({"ads.example.com"}))
        self.assertTrue(config.capture_js)
        self.assertEqual(config.max_captures, 3)
        self.assertEqual(config.user_data_dir, "/tmp/clm-profile")
        self.assertEqual(config.storage_state_output_path, "/tmp/clm-state/state.json")
        self.assertTrue(config.visual_recon)

    def test_invalid_wait_state_falls_back(self) -> None:
        request = RuntimeRequest.from_dict({
            "url": "https://example.com",
            "browser_config": {"wait_selector_state": "bogus"},
        })

        config = resolve_native_browser_config(request)

        self.assertEqual(config.wait_selector_state, "attached")

    def test_protected_mode_adds_profile_evidence_defaults(self) -> None:
        request = RuntimeRequest.from_dict({
            "url": "https://example.com",
            "mode": "protected",
        })

        config = resolve_native_browser_config(request)

        self.assertEqual(config.mode, "protected")
        self.assertTrue(config.init_script)
        self.assertIn("--disable-blink-features=AutomationControlled", config.extra_flags)


class NativeBrowserRuntimeTests(unittest.TestCase):
    def test_runtime_satisfies_browser_protocol(self) -> None:
        runtime = NativeBrowserRuntime()
        self.assertIsInstance(runtime, BrowserRuntime)
        self.assertEqual(runtime.name, "native_browser")

    @patch("autonomous_crawler.runtime.native_browser.sync_playwright", None)
    def test_missing_playwright_returns_failure(self) -> None:
        runtime = NativeBrowserRuntime()
        response = runtime.render(RuntimeRequest.from_dict({"url": "https://example.com"}))

        self.assertFalse(response.ok)
        self.assertIn("playwright is not installed", response.error)
        self.assertEqual(response.engine_result["engine"], "native_browser")
        self.assertEqual(
            response.engine_result["failure_classification"]["category"],
            "playwright_missing",
        )
        self.assertIn("fingerprint_report", response.engine_result)

    @patch("autonomous_crawler.runtime.native_browser.sync_playwright")
    def test_render_success_captures_html_context_proxy_and_xhr(self, mock_pw: MagicMock) -> None:
        page, context, _routes, response_handlers = _setup_mock_playwright(mock_pw)

        request = RuntimeRequest.from_dict({
            "url": "https://example.com/app",
            "mode": "dynamic",
            "headers": {"X-Test": "1"},
            "cookies": {"sid": "abc"},
            "session_profile": {
                "headers": {"Authorization": "Bearer token"},
                "cookies": {"session": "xyz"},
                "storage_state_path": "state.json",
            },
            "proxy_config": {"proxy": "http://user:pass@proxy.example:8080"},
            "wait_selector": ".product",
            "wait_until": "networkidle",
            "capture_xhr": "api/products",
            "browser_config": {
                "locale": "nl-NL",
                "timezone_id": "Europe/Amsterdam",
                "capture_js": True,
                "screenshot": True,
            },
        })

        response = NativeBrowserRuntime().render(request)

        for handler in response_handlers:
            handler(_mock_response("https://example.com/api/products"))

        self.assertTrue(response.ok)
        self.assertEqual(response.final_url, "https://example.com/app")
        self.assertIn("Rendered", response.html)
        self.assertTrue(response.proxy_trace.selected)
        self.assertEqual(response.cookies, {"sid": "abc"})

        launch_kwargs = mock_pw.return_value.__enter__.return_value.chromium.launch.call_args.kwargs
        self.assertEqual(launch_kwargs["proxy"]["server"], "http://proxy.example:8080")
        self.assertEqual(launch_kwargs["proxy"]["username"], "user")
        self.assertEqual(launch_kwargs["proxy"]["password"], "pass")

        context_kwargs = mock_pw.return_value.__enter__.return_value.chromium.launch.return_value.new_context.call_args.kwargs
        self.assertEqual(context_kwargs["locale"], "nl-NL")
        self.assertEqual(context_kwargs["timezone_id"], "Europe/Amsterdam")
        self.assertEqual(context_kwargs["storage_state"], "state.json")
        self.assertEqual(context_kwargs["extra_http_headers"]["Authorization"], "Bearer token")
        self.assertEqual(context_kwargs["extra_http_headers"]["X-Test"], "1")

        context.add_cookies.assert_called_once()
        page.wait_for_selector.assert_called_once_with(".product", timeout=30000, state="attached")
        page.screenshot.assert_called_once()
        self.assertEqual(response.engine_result["engine"], "native_browser")
        self.assertEqual(response.engine_result["context"]["locale"], "nl-NL")
        self.assertEqual(response.engine_result["failure_classification"]["category"], "none")
        self.assertEqual(response.engine_result["fingerprint_report"]["profile"]["locale"], "nl-NL")

    @patch("autonomous_crawler.runtime.native_browser.sync_playwright")
    def test_response_handlers_capture_xhr_before_completion(self, mock_pw: MagicMock) -> None:
        page, _context, _routes, response_handlers = _setup_mock_playwright(mock_pw)

        def goto_side_effect(*_args, **_kwargs):
            for handler in response_handlers:
                handler(_mock_response("https://example.com/api/products"))
            nav_response = MagicMock()
            nav_response.status = 200
            nav_response.headers = {}
            return nav_response

        page.goto.side_effect = goto_side_effect

        request = RuntimeRequest.from_dict({
            "url": "https://example.com/app",
            "capture_xhr": "api/products",
        })
        response = NativeBrowserRuntime().render(request)

        self.assertEqual(len(response.captured_xhr), 1)
        self.assertEqual(response.captured_xhr[0]["url"], "https://example.com/api/products")
        self.assertIn("items", response.captured_xhr[0]["body_preview"])

    @patch("autonomous_crawler.runtime.native_browser.sync_playwright")
    def test_route_blocks_configured_resources(self, mock_pw: MagicMock) -> None:
        _page, _context, route_handlers, _response_handlers = _setup_mock_playwright(mock_pw)

        request = RuntimeRequest.from_dict({
            "url": "https://example.com",
            "browser_config": {"block_resource_types": ["image"]},
        })
        response = NativeBrowserRuntime().render(request)

        route = MagicMock()
        route.request.url = "https://example.com/photo.jpg"
        route.request.resource_type = "image"
        route_handlers[0](route)

        self.assertTrue(response.ok)
        route.abort.assert_called_once()
        route.continue_.assert_not_called()

    @patch("autonomous_crawler.runtime.native_browser.sync_playwright")
    def test_persistent_context_and_storage_state_output(self, mock_pw: MagicMock) -> None:
        _page, mock_context, _routes, _response_handlers = _setup_mock_playwright(mock_pw)
        mock_playwright = mock_pw.return_value.__enter__.return_value
        mock_playwright.chromium.launch_persistent_context.return_value = mock_context

        with tempfile.TemporaryDirectory() as tmp:
            user_data_dir = str(Path(tmp) / "profile")
            state_path = str(Path(tmp) / "state" / "storage.json")
            request = RuntimeRequest.from_dict({
                "url": "https://example.com/app",
                "browser_config": {
                    "user_data_dir": user_data_dir,
                    "storage_state_output_path": state_path,
                },
            })
            response = NativeBrowserRuntime().render(request)

        self.assertTrue(response.ok)
        mock_playwright.chromium.launch_persistent_context.assert_called_once()
        launch_args, launch_kwargs = mock_playwright.chromium.launch_persistent_context.call_args
        self.assertEqual(launch_args[0], user_data_dir)
        self.assertNotIn("storage_state", launch_kwargs)
        mock_playwright.chromium.launch.assert_not_called()
        mock_context.storage_state.assert_called_once_with(path=state_path)
        mock_context.close.assert_called_once()
        self.assertEqual(response.engine_result["session_mode"], "persistent")
        self.assertEqual(response.engine_result["config"]["user_data_dir"], "[redacted-path]/profile")
        self.assertEqual(len(response.artifacts), 1)
        self.assertEqual(response.artifacts[0].kind, "storage_state")

    @patch("autonomous_crawler.runtime.native_browser.sync_playwright")
    def test_navigation_timeout_is_classified(self, mock_pw: MagicMock) -> None:
        page, _context, _routes, _response_handlers = _setup_mock_playwright(mock_pw)
        page.goto.side_effect = TimeoutError("navigation timeout")

        response = NativeBrowserRuntime().render(RuntimeRequest.from_dict({
            "url": "https://example.com/slow",
        }))

        self.assertFalse(response.ok)
        self.assertEqual(
            response.engine_result["failure_classification"]["category"],
            "navigation_timeout",
        )
        self.assertIn("fingerprint_report", response.engine_result)

    @patch("autonomous_crawler.runtime.native_browser.sync_playwright")
    def test_challenge_like_html_is_classified(self, mock_pw: MagicMock) -> None:
        page, _context, _routes, _response_handlers = _setup_mock_playwright(mock_pw)
        nav_response = MagicMock()
        nav_response.status = 403
        nav_response.headers = {"content-type": "text/html", "cf-mitigated": "challenge"}
        page.goto.return_value = nav_response
        page.content.return_value = "<html><title>Just a moment...</title></html>"

        response = NativeBrowserRuntime().render(RuntimeRequest.from_dict({
            "url": "https://example.com/protected",
            "mode": "protected",
        }))

        self.assertFalse(response.ok)
        classification = response.engine_result["failure_classification"]
        self.assertEqual(classification["category"], "challenge_like")
        self.assertEqual(classification["challenge"]["vendor"], "cloudflare")
        self.assertEqual(response.engine_result["mode"], "protected")

    @patch("autonomous_crawler.runtime.native_browser.analyze_runtime_artifacts")
    @patch("autonomous_crawler.runtime.native_browser.sync_playwright")
    def test_visual_recon_runs_for_screenshot_artifacts(
        self,
        mock_pw: MagicMock,
        mock_visual: MagicMock,
    ) -> None:
        _page, _context, _routes, _response_handlers = _setup_mock_playwright(mock_pw)
        mock_visual.return_value = [{"status": "ok", "image_kind": "png"}]

        response = NativeBrowserRuntime().render(RuntimeRequest.from_dict({
            "url": "https://example.com/app",
            "browser_config": {
                "screenshot": True,
                "visual_recon": True,
            },
        }))

        self.assertTrue(response.ok)
        mock_visual.assert_called_once()
        self.assertEqual(response.engine_result["visual_recon"][0]["image_kind"], "png")


if __name__ == "__main__":
    unittest.main()
