"""Tests for browser request interception and JS capture (CAP-4.4).

All tests use mocked Playwright — no external network or browser required.
"""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from autonomous_crawler.tools.browser_interceptor import (
    InterceptorConfig,
    InterceptionResult,
    intercept_page_resources,
    BLOCKABLE_RESOURCE_TYPES,
    API_RESOURCE_TYPES,
)


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

class InterceptorConfigTests(unittest.TestCase):
    def test_from_dict_empty_defaults(self) -> None:
        cfg = InterceptorConfig.from_dict({})
        self.assertEqual(cfg.block_resource_types, frozenset())
        self.assertTrue(cfg.capture_js)
        self.assertTrue(cfg.capture_api)
        self.assertEqual(cfg.init_script, "")
        self.assertEqual(cfg.max_captures, 200)

    def test_from_dict_none_defaults(self) -> None:
        cfg = InterceptorConfig.from_dict(None)
        self.assertEqual(cfg.block_resource_types, frozenset())
        self.assertTrue(cfg.capture_js)

    def test_from_dict_passthrough_instance(self) -> None:
        original = InterceptorConfig(capture_js=False)
        result = InterceptorConfig.from_dict(original)
        self.assertIs(result, original)

    def test_from_dict_custom_values(self) -> None:
        cfg = InterceptorConfig.from_dict({
            "block_resource_types": ["image", "font", "media"],
            "capture_js": False,
            "capture_api": True,
            "init_script": "window.__CLM = true;",
            "max_captures": 50,
        })
        self.assertEqual(cfg.block_resource_types, {"image", "font", "media"})
        self.assertFalse(cfg.capture_js)
        self.assertTrue(cfg.capture_api)
        self.assertEqual(cfg.init_script, "window.__CLM = true;")
        self.assertEqual(cfg.max_captures, 50)

    def test_from_dict_clamps_max_captures(self) -> None:
        cfg = InterceptorConfig.from_dict({"max_captures": -5})
        self.assertEqual(cfg.max_captures, 1)
        cfg2 = InterceptorConfig.from_dict({"max_captures": 99999})
        self.assertEqual(cfg2.max_captures, 10000)

    def test_frozen(self) -> None:
        cfg = InterceptorConfig()
        with self.assertRaises(AttributeError):
            cfg.capture_js = False  # type: ignore[misc]

    def test_to_dict(self) -> None:
        cfg = InterceptorConfig(
            block_resource_types=frozenset({"image", "font"}),
            capture_js=True,
            capture_api=False,
            init_script="console.log(1)",
            max_captures=100,
        )
        d = cfg.to_dict()
        self.assertEqual(sorted(d["block_resource_types"]), ["font", "image"])
        self.assertTrue(d["capture_js"])
        self.assertFalse(d["capture_api"])
        self.assertTrue(d["init_script"])
        self.assertEqual(d["max_captures"], 100)


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------

class InterceptionResultTests(unittest.TestCase):
    def test_to_dict_default(self) -> None:
        result = InterceptionResult(url="https://example.com")
        d = result.to_dict()
        self.assertEqual(d["url"], "https://example.com")
        self.assertEqual(d["status"], "ok")
        self.assertEqual(d["resource_counts"], {})
        self.assertEqual(d["blocked_urls"], [])
        self.assertEqual(d["js_assets"], [])
        self.assertEqual(d["api_captures"], [])
        self.assertEqual(d["errors"], [])

    def test_to_dict_round_trip(self) -> None:
        result = InterceptionResult(
            url="https://example.com",
            final_url="https://example.com/page",
            status="ok",
            resource_counts={"script": 3, "image": 5},
            blocked_urls=["https://example.com/ad.png"],
            js_assets=[{"url": "https://example.com/app.js", "sha256": "abc123"}],
            api_captures=[{"url": "https://example.com/api", "method": "GET"}],
        )
        d = result.to_dict()
        self.assertEqual(d["final_url"], "https://example.com/page")
        self.assertEqual(d["resource_counts"]["script"], 3)
        self.assertEqual(len(d["blocked_urls"]), 1)
        self.assertEqual(len(d["js_assets"]), 1)
        self.assertEqual(len(d["api_captures"]), 1)

    def test_to_dict_returns_copies(self) -> None:
        result = InterceptionResult(
            url="https://example.com",
            resource_counts={"image": 1},
            blocked_urls=["a"],
        )
        d = result.to_dict()
        d["resource_counts"]["image"] = 999
        d["blocked_urls"].append("b")
        self.assertEqual(result.resource_counts["image"], 1)
        self.assertEqual(len(result.blocked_urls), 1)


# ---------------------------------------------------------------------------
# Resource blocking
# ---------------------------------------------------------------------------

def _setup_mock_pw(
    mock_pw_cls: MagicMock,
    *,
    responses: list[MagicMock] | None = None,
) -> tuple[list, list]:
    """Configure a mock Playwright class (from @patch) and return captured handlers.

    Returns (route_handlers, response_handlers) so tests can inspect them.
    """
    responses = responses or []
    route_handlers: list = []
    response_handlers: list = []

    mock_page = MagicMock()
    mock_page.url = "https://example.com"

    def on_event(event: str, callback):
        if event == "response":
            response_handlers.append(callback)

    def route_register(pattern: str, handler):
        route_handlers.append(handler)

    def goto_side_effect(*args, **kwargs):
        for handler in response_handlers:
            for resp in responses:
                handler(resp)

    mock_page.on.side_effect = on_event
    mock_page.route.side_effect = route_register
    mock_page.goto.side_effect = goto_side_effect

    mock_context = MagicMock()
    mock_context.new_page.return_value = mock_page
    mock_browser = MagicMock()
    mock_browser.new_context.return_value = mock_context

    mock_pw = MagicMock()
    mock_pw.chromium.launch.return_value = mock_browser

    mock_pw_cls.return_value.__enter__ = MagicMock(return_value=mock_pw)
    mock_pw_cls.return_value.__exit__ = MagicMock(return_value=False)

    return route_handlers, response_handlers


def _make_mock_response(
    url: str,
    *,
    status: int = 200,
    resource_type: str = "script",
    method: str = "GET",
    content_type: str = "application/javascript",
    body: bytes = b"// js content",
    headers: dict | None = None,
) -> MagicMock:
    """Build a mock Playwright Response."""
    mock_request = MagicMock()
    mock_request.method = method
    mock_request.resource_type = resource_type
    mock_request.headers = {}
    mock_request.url = url

    mock_response = MagicMock()
    mock_response.url = url
    mock_response.status = status
    mock_response.headers = headers or {"content-type": content_type}
    mock_response.request = mock_request
    mock_response.body.return_value = body
    mock_response.json.return_value = {}
    return mock_response


def _make_mock_route(url: str, resource_type: str = "script") -> MagicMock:
    mock_request = MagicMock()
    mock_request.resource_type = resource_type
    mock_request.url = url

    mock_route = MagicMock()
    mock_route.request = mock_request
    return mock_route


class ResourceBlockingTests(unittest.TestCase):
    @patch("autonomous_crawler.tools.browser_interceptor.sync_playwright")
    def test_blocked_resource_type_aborted(self, mock_pw_cls: MagicMock) -> None:
        image_resp = _make_mock_response(
            "https://example.com/img.png",
            resource_type="image",
            content_type="image/png",
            body=b"\x89PNG",
        )
        _setup_mock_pw(mock_pw_cls, responses=[image_resp])
        result = intercept_page_resources(
            "https://example.com",
            config={"block_resource_types": ["image"]},
        )

        self.assertIn("https://example.com/img.png", result.blocked_urls)
        self.assertEqual(result.resource_counts.get("image", 0), 1)

    @patch("autonomous_crawler.tools.browser_interceptor.sync_playwright")
    def test_allowed_resource_type_continued(self, mock_pw_cls: MagicMock) -> None:
        script_resp = _make_mock_response(
            "https://example.com/app.js",
            resource_type="script",
            body=b"console.log(1)",
        )
        _setup_mock_pw(mock_pw_cls, responses=[script_resp])
        result = intercept_page_resources(
            "https://example.com",
            config={"block_resource_types": ["image"]},
        )

        self.assertNotIn("https://example.com/app.js", result.blocked_urls)

    @patch("autonomous_crawler.tools.browser_interceptor.sync_playwright")
    def test_multiple_resource_types_blocked(self, mock_pw_cls: MagicMock) -> None:
        font_resp = _make_mock_response(
            "https://example.com/font.woff2",
            resource_type="font",
            content_type="font/woff2",
            body=b"fontdata",
        )
        css_resp = _make_mock_response(
            "https://example.com/style.css",
            resource_type="stylesheet",
            content_type="text/css",
            body=b"body{}",
        )
        _setup_mock_pw(mock_pw_cls, responses=[font_resp, css_resp])
        result = intercept_page_resources(
            "https://example.com",
            config={"block_resource_types": ["font", "stylesheet"]},
        )

        self.assertEqual(len(result.blocked_urls), 2)

    @patch("autonomous_crawler.tools.browser_interceptor.sync_playwright")
    def test_resource_counts_tracked_by_type(self, mock_pw_cls: MagicMock) -> None:
        script1 = _make_mock_response("https://example.com/a.js", resource_type="script", body=b"a")
        script2 = _make_mock_response("https://example.com/b.js", resource_type="script", body=b"b")
        img = _make_mock_response(
            "https://example.com/c.png",
            resource_type="image",
            content_type="image/png",
            body=b"img",
        )
        _setup_mock_pw(mock_pw_cls, responses=[script1, script2, img])
        result = intercept_page_resources("https://example.com")

        self.assertEqual(result.resource_counts.get("script", 0), 2)
        self.assertEqual(result.resource_counts.get("image", 0), 1)


# ---------------------------------------------------------------------------
# JS capture
# ---------------------------------------------------------------------------

class JsCaptureTests(unittest.TestCase):
    @patch("autonomous_crawler.tools.browser_interceptor.sync_playwright")
    def test_js_asset_captured_with_sha256(self, mock_pw_cls: MagicMock) -> None:
        js_body = b"var x = 1;"
        resp = _make_mock_response(
            "https://example.com/app.js",
            resource_type="script",
            body=js_body,
        )
        _setup_mock_pw(mock_pw_cls, responses=[resp])
        result = intercept_page_resources("https://example.com")

        self.assertEqual(len(result.js_assets), 1)
        asset = result.js_assets[0]
        self.assertEqual(asset["url"], "https://example.com/app.js")
        self.assertEqual(asset["status_code"], 200)
        self.assertIn("javascript", asset["content_type"])
        self.assertEqual(asset["size_bytes"], len(js_body))
        self.assertEqual(asset["sha256"], __import__("hashlib").sha256(js_body).hexdigest())

    @patch("autonomous_crawler.tools.browser_interceptor.sync_playwright")
    def test_js_capture_disabled(self, mock_pw_cls: MagicMock) -> None:
        resp = _make_mock_response("https://example.com/app.js", resource_type="script", body=b"var x;")
        _setup_mock_pw(mock_pw_cls, responses=[resp])
        result = intercept_page_resources(
            "https://example.com",
            config={"capture_js": False},
        )

        self.assertEqual(len(result.js_assets), 0)

    @patch("autonomous_crawler.tools.browser_interceptor.sync_playwright")
    def test_js_body_error_recorded(self, mock_pw_cls: MagicMock) -> None:
        resp = _make_mock_response("https://example.com/app.js", resource_type="script", body=b"")
        resp.body.side_effect = RuntimeError("network error")
        _setup_mock_pw(mock_pw_cls, responses=[resp])
        result = intercept_page_resources("https://example.com")

        self.assertEqual(len(result.js_assets), 0)
        self.assertTrue(any("body_read_error" in e for e in result.errors))


# ---------------------------------------------------------------------------
# API capture
# ---------------------------------------------------------------------------

class ApiCaptureTests(unittest.TestCase):
    @patch("autonomous_crawler.tools.browser_interceptor.sync_playwright")
    def test_xhr_captured(self, mock_pw_cls: MagicMock) -> None:
        resp = _make_mock_response(
            "https://example.com/api/products",
            resource_type="xhr",
            method="GET",
            content_type="application/json",
            body=b'{"items":[]}',
        )
        _setup_mock_pw(mock_pw_cls, responses=[resp])
        result = intercept_page_resources("https://example.com")

        self.assertEqual(len(result.api_captures), 1)
        cap = result.api_captures[0]
        self.assertEqual(cap["url"], "https://example.com/api/products")
        self.assertEqual(cap["method"], "GET")
        self.assertEqual(cap["status_code"], 200)
        self.assertIn("json", cap["content_type"])

    @patch("autonomous_crawler.tools.browser_interceptor.sync_playwright")
    def test_fetch_type_captured(self, mock_pw_cls: MagicMock) -> None:
        resp = _make_mock_response(
            "https://example.com/graphql",
            resource_type="fetch",
            method="POST",
            content_type="application/json",
        )
        _setup_mock_pw(mock_pw_cls, responses=[resp])
        result = intercept_page_resources("https://example.com")

        self.assertEqual(len(result.api_captures), 1)
        self.assertEqual(result.api_captures[0]["method"], "POST")

    @patch("autonomous_crawler.tools.browser_interceptor.sync_playwright")
    def test_json_content_type_captured_even_if_not_xhr(self, mock_pw_cls: MagicMock) -> None:
        resp = _make_mock_response(
            "https://example.com/data.json",
            resource_type="document",
            content_type="application/json",
        )
        _setup_mock_pw(mock_pw_cls, responses=[resp])
        result = intercept_page_resources("https://example.com")

        self.assertEqual(len(result.api_captures), 1)

    @patch("autonomous_crawler.tools.browser_interceptor.sync_playwright")
    def test_api_capture_disabled(self, mock_pw_cls: MagicMock) -> None:
        resp = _make_mock_response(
            "https://example.com/api",
            resource_type="xhr",
            content_type="application/json",
        )
        _setup_mock_pw(mock_pw_cls, responses=[resp])
        result = intercept_page_resources(
            "https://example.com",
            config={"capture_api": False},
        )

        self.assertEqual(len(result.api_captures), 0)


# ---------------------------------------------------------------------------
# Init script
# ---------------------------------------------------------------------------

class InitScriptTests(unittest.TestCase):
    @patch("autonomous_crawler.tools.browser_interceptor.sync_playwright")
    def test_init_script_injected(self, mock_pw_cls: MagicMock) -> None:
        mock_page = MagicMock()
        mock_page.url = "https://example.com"
        mock_page.on.side_effect = lambda event, cb: None
        mock_page.route.side_effect = lambda pattern, handler: None
        mock_page.goto.return_value = None

        mock_context = MagicMock()
        mock_context.new_page.return_value = mock_page
        mock_browser = MagicMock()
        mock_browser.new_context.return_value = mock_context
        mock_pw = MagicMock()
        mock_pw.chromium.launch.return_value = mock_browser
        mock_pw_cls.return_value.__enter__ = MagicMock(return_value=mock_pw)
        mock_pw_cls.return_value.__exit__ = MagicMock(return_value=False)

        intercept_page_resources(
            "https://example.com",
            config={"init_script": "window.__CLM = {version: 1};"},
        )

        mock_page.add_init_script.assert_called_once_with(
            script="window.__CLM = {version: 1};",
        )

    @patch("autonomous_crawler.tools.browser_interceptor.sync_playwright")
    def test_no_init_script_when_empty(self, mock_pw_cls: MagicMock) -> None:
        mock_page = MagicMock()
        mock_page.url = "https://example.com"
        mock_page.on.side_effect = lambda event, cb: None
        mock_page.route.side_effect = lambda pattern, handler: None
        mock_page.goto.return_value = None

        mock_context = MagicMock()
        mock_context.new_page.return_value = mock_page
        mock_browser = MagicMock()
        mock_browser.new_context.return_value = mock_context
        mock_pw = MagicMock()
        mock_pw.chromium.launch.return_value = mock_browser
        mock_pw_cls.return_value.__enter__ = MagicMock(return_value=mock_pw)
        mock_pw_cls.return_value.__exit__ = MagicMock(return_value=False)

        intercept_page_resources("https://example.com")

        mock_page.add_init_script.assert_not_called()


# ---------------------------------------------------------------------------
# Header sanitization
# ---------------------------------------------------------------------------

class HeaderSanitizationTests(unittest.TestCase):
    @patch("autonomous_crawler.tools.browser_interceptor.sync_playwright")
    def test_sensitive_headers_not_in_js_asset(self, mock_pw_cls: MagicMock) -> None:
        resp = _make_mock_response(
            "https://example.com/app.js",
            resource_type="script",
            body=b"var x=1;",
        )
        resp.request.headers = {"Authorization": "Bearer secret", "Cookie": "sid=abc"}
        _setup_mock_pw(mock_pw_cls, responses=[resp])
        result = intercept_page_resources("https://example.com")

        for asset in result.js_assets:
            self.assertNotIn("Bearer secret", str(asset))
            self.assertNotIn("sid=abc", str(asset))

    @patch("autonomous_crawler.tools.browser_interceptor.sync_playwright")
    def test_sensitive_headers_not_in_api_capture(self, mock_pw_cls: MagicMock) -> None:
        resp = _make_mock_response(
            "https://example.com/api",
            resource_type="xhr",
            content_type="application/json",
        )
        resp.request.headers = {"X-API-Key": "my-secret-key"}
        _setup_mock_pw(mock_pw_cls, responses=[resp])
        result = intercept_page_resources("https://example.com")

        for cap in result.api_captures:
            self.assertNotIn("my-secret-key", str(cap))


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

class ErrorHandlingTests(unittest.TestCase):
    @patch("autonomous_crawler.tools.browser_interceptor.sync_playwright", None)
    def test_playwright_not_installed(self) -> None:
        result = intercept_page_resources("https://example.com")
        self.assertEqual(result.status, "failed")
        self.assertIn("playwright is not installed", result.error)

    @patch("autonomous_crawler.tools.browser_interceptor.sync_playwright")
    def test_navigation_failure(self, mock_pw_cls: MagicMock) -> None:
        mock_page = MagicMock()
        mock_page.goto.side_effect = TimeoutError("Navigation timeout")
        mock_page.on.side_effect = lambda event, cb: None
        mock_page.route.side_effect = lambda pattern, handler: None

        mock_context = MagicMock()
        mock_context.new_page.return_value = mock_page
        mock_browser = MagicMock()
        mock_browser.new_context.return_value = mock_context
        mock_pw = MagicMock()
        mock_pw.chromium.launch.return_value = mock_browser
        mock_pw_cls.return_value.__enter__ = MagicMock(return_value=mock_pw)
        mock_pw_cls.return_value.__exit__ = MagicMock(return_value=False)

        result = intercept_page_resources("https://example.com")

        self.assertEqual(result.status, "failed")
        self.assertIn("Navigation timeout", result.error)

    @patch("autonomous_crawler.tools.browser_interceptor.sync_playwright")
    def test_browser_closed_on_success(self, mock_pw_cls: MagicMock) -> None:
        mock_page = MagicMock()
        mock_page.url = "https://example.com"
        mock_page.on.side_effect = lambda event, cb: None
        mock_page.route.side_effect = lambda pattern, handler: None
        mock_page.goto.return_value = None

        mock_context = MagicMock()
        mock_context.new_page.return_value = mock_page
        mock_browser = MagicMock()
        mock_browser.new_context.return_value = mock_context
        mock_pw = MagicMock()
        mock_pw.chromium.launch.return_value = mock_browser
        mock_pw_cls.return_value.__enter__ = MagicMock(return_value=mock_pw)
        mock_pw_cls.return_value.__exit__ = MagicMock(return_value=False)

        intercept_page_resources("https://example.com")

        mock_browser.close.assert_called_once()

    @patch("autonomous_crawler.tools.browser_interceptor.sync_playwright")
    def test_browser_closed_on_error(self, mock_pw_cls: MagicMock) -> None:
        mock_page = MagicMock()
        mock_page.goto.side_effect = RuntimeError("crash")
        mock_page.on.side_effect = lambda event, cb: None
        mock_page.route.side_effect = lambda pattern, handler: None

        mock_context = MagicMock()
        mock_context.new_page.return_value = mock_page
        mock_browser = MagicMock()
        mock_browser.new_context.return_value = mock_context
        mock_pw = MagicMock()
        mock_pw.chromium.launch.return_value = mock_browser
        mock_pw_cls.return_value.__enter__ = MagicMock(return_value=mock_pw)
        mock_pw_cls.return_value.__exit__ = MagicMock(return_value=False)

        intercept_page_resources("https://example.com")

        mock_browser.close.assert_called_once()


# ---------------------------------------------------------------------------
# Max captures
# ---------------------------------------------------------------------------

class MaxCapturesTests(unittest.TestCase):
    @patch("autonomous_crawler.tools.browser_interceptor.sync_playwright")
    def test_max_captures_respected(self, mock_pw_cls: MagicMock) -> None:
        responses = [
            _make_mock_response(f"https://example.com/api/{i}", resource_type="xhr", content_type="application/json")
            for i in range(10)
        ]
        _setup_mock_pw(mock_pw_cls, responses=responses)
        result = intercept_page_resources(
            "https://example.com",
            config={"max_captures": 3},
        )

        total = len(result.js_assets) + len(result.api_captures)
        self.assertLessEqual(total, 3)


# ---------------------------------------------------------------------------
# Wait selector and render time
# ---------------------------------------------------------------------------

class WaitAndRenderTests(unittest.TestCase):
    @patch("autonomous_crawler.tools.browser_interceptor.sync_playwright")
    def test_wait_selector_called(self, mock_pw_cls: MagicMock) -> None:
        _setup_mock_pw(mock_pw_cls)
        intercept_page_resources(
            "https://example.com",
            wait_selector="#content",
            timeout_ms=5000,
        )
        # Access the page mock via the context chain
        page = mock_pw_cls.return_value.__enter__.return_value.chromium.launch.return_value.new_context.return_value.new_page.return_value
        page.wait_for_selector.assert_called_once_with("#content", timeout=5000)

    @patch("autonomous_crawler.tools.browser_interceptor.sync_playwright")
    def test_render_time_waits(self, mock_pw_cls: MagicMock) -> None:
        _setup_mock_pw(mock_pw_cls)
        intercept_page_resources(
            "https://example.com",
            render_time_ms=500,
        )
        page = mock_pw_cls.return_value.__enter__.return_value.chromium.launch.return_value.new_context.return_value.new_page.return_value
        page.wait_for_timeout.assert_called_once_with(500)

    @patch("autonomous_crawler.tools.browser_interceptor.sync_playwright")
    def test_no_render_time_when_zero(self, mock_pw_cls: MagicMock) -> None:
        _setup_mock_pw(mock_pw_cls)
        intercept_page_resources("https://example.com", render_time_ms=0)
        page = mock_pw_cls.return_value.__enter__.return_value.chromium.launch.return_value.new_context.return_value.new_page.return_value
        page.wait_for_timeout.assert_not_called()


# ---------------------------------------------------------------------------
# Route handler behavior
# ---------------------------------------------------------------------------

class RouteHandlerTests(unittest.TestCase):
    @patch("autonomous_crawler.tools.browser_interceptor.sync_playwright")
    def test_route_registered_with_wildcard(self, mock_pw_cls: MagicMock) -> None:
        _setup_mock_pw(mock_pw_cls)
        intercept_page_resources("https://example.com")
        page = mock_pw_cls.return_value.__enter__.return_value.chromium.launch.return_value.new_context.return_value.new_page.return_value
        page.route.assert_called_once()
        call_args = page.route.call_args
        self.assertEqual(call_args[0][0], "**/*")

    @patch("autonomous_crawler.tools.browser_interceptor.sync_playwright")
    def test_blocked_route_calls_abort(self, mock_pw_cls: MagicMock) -> None:
        route_handlers, _ = _setup_mock_pw(mock_pw_cls)
        intercept_page_resources(
            "https://example.com",
            config={"block_resource_types": ["image"]},
        )

        self.assertEqual(len(route_handlers), 1)
        route_handler = route_handlers[0]

        mock_route = _make_mock_route("https://example.com/img.png", "image")
        route_handler(mock_route)
        mock_route.abort.assert_called_once()
        mock_route.continue_.assert_not_called()

    @patch("autonomous_crawler.tools.browser_interceptor.sync_playwright")
    def test_allowed_route_calls_continue(self, mock_pw_cls: MagicMock) -> None:
        route_handlers, _ = _setup_mock_pw(mock_pw_cls)
        intercept_page_resources(
            "https://example.com",
            config={"block_resource_types": ["image"]},
        )

        route_handler = route_handlers[0]
        mock_route = _make_mock_route("https://example.com/app.js", "script")
        route_handler(mock_route)
        mock_route.continue_.assert_called_once()
        mock_route.abort.assert_not_called()


# ---------------------------------------------------------------------------
# Integration: mixed resource stream
# ---------------------------------------------------------------------------

class MixedResourceStreamTests(unittest.TestCase):
    @patch("autonomous_crawler.tools.browser_interceptor.sync_playwright")
    def test_mixed_resources_all_handled(self, mock_pw_cls: MagicMock) -> None:
        js_body = b"var app = {};"
        responses = [
            _make_mock_response(
                "https://example.com/app.js",
                resource_type="script",
                body=js_body,
            ),
            _make_mock_response(
                "https://example.com/api/data",
                resource_type="fetch",
                method="GET",
                content_type="application/json",
            ),
            _make_mock_response(
                "https://example.com/photo.jpg",
                resource_type="image",
                content_type="image/jpeg",
                body=b"\xff\xd8\xff",
            ),
            _make_mock_response(
                "https://example.com/style.css",
                resource_type="stylesheet",
                content_type="text/css",
                body=b"body{}",
            ),
        ]
        _setup_mock_pw(mock_pw_cls, responses=responses)
        result = intercept_page_resources(
            "https://example.com",
            config={
                "block_resource_types": ["image", "stylesheet"],
                "capture_js": True,
                "capture_api": True,
            },
        )

        self.assertEqual(len(result.blocked_urls), 2)
        self.assertIn("https://example.com/photo.jpg", result.blocked_urls)
        self.assertIn("https://example.com/style.css", result.blocked_urls)
        self.assertEqual(len(result.js_assets), 1)
        self.assertEqual(result.js_assets[0]["sha256"], __import__("hashlib").sha256(js_body).hexdigest())
        self.assertEqual(len(result.api_captures), 1)
        self.assertEqual(result.api_captures[0]["url"], "https://example.com/api/data")

    @patch("autonomous_crawler.tools.browser_interceptor.sync_playwright")
    def test_empty_page_returns_ok(self, mock_pw_cls: MagicMock) -> None:
        _setup_mock_pw(mock_pw_cls, responses=[])
        result = intercept_page_resources("https://example.com")

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.js_assets, [])
        self.assertEqual(result.api_captures, [])
        self.assertEqual(result.blocked_urls, [])


if __name__ == "__main__":
    unittest.main()
