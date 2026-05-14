"""Tests for ScraplingStaticRuntime adapter (SCRAPLING-RUNTIME-1).

All tests use mocked Scrapling Fetcher — no real network calls.
"""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from autonomous_crawler.runtime.models import RuntimeRequest, RuntimeResponse
from autonomous_crawler.runtime.scrapling_static import ScraplingStaticRuntime


def _mock_response(
    *,
    status: int = 200,
    url: str = "https://example.com",
    headers: dict | None = None,
    cookies: dict | None = None,
    body: bytes = b"<html><body>Hello</body></html>",
) -> MagicMock:
    resp = MagicMock()
    resp.status = status
    resp.url = url
    resp.headers = headers or {"Content-Type": "text/html"}
    resp.cookies = cookies or {}
    resp.body = body
    resp.text = body.decode("utf-8", errors="replace") if body else ""
    return resp


class ScraplingStaticRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.runtime = ScraplingStaticRuntime()

    def test_name_is_scrapling_static(self) -> None:
        self.assertEqual(self.runtime.name, "scrapling_static")

    @patch("autonomous_crawler.runtime.scrapling_static.Fetcher")
    def test_get_returns_ok_response(self, mock_fetcher: MagicMock) -> None:
        mock_fetcher.get.return_value = _mock_response()
        req = RuntimeRequest(url="https://example.com")
        resp = self.runtime.fetch(req)

        self.assertTrue(resp.ok)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Hello", resp.html)
        self.assertEqual(resp.engine_result["engine"], "scrapling_static")
        mock_fetcher.get.assert_called_once()

    @patch("autonomous_crawler.runtime.scrapling_static.Fetcher")
    def test_post_with_json_body(self, mock_fetcher: MagicMock) -> None:
        mock_fetcher.post.return_value = _mock_response(body=b'{"ok":true}')
        req = RuntimeRequest(url="https://example.com/api", method="POST", json={"key": "val"})
        resp = self.runtime.fetch(req)

        self.assertTrue(resp.ok)
        mock_fetcher.post.assert_called_once()
        call_kwargs = mock_fetcher.post.call_args
        self.assertEqual(call_kwargs[1]["json"], {"key": "val"})

    @patch("autonomous_crawler.runtime.scrapling_static.Fetcher")
    def test_post_with_form_data(self, mock_fetcher: MagicMock) -> None:
        mock_fetcher.post.return_value = _mock_response(body=b'{"ok":true}')
        req = RuntimeRequest(url="https://example.com/api", method="POST", data="form=data")
        resp = self.runtime.fetch(req)

        self.assertTrue(resp.ok)
        call_kwargs = mock_fetcher.post.call_args
        self.assertEqual(call_kwargs[1]["data"], "form=data")

    @patch("autonomous_crawler.runtime.scrapling_static.Fetcher")
    def test_headers_forwarded(self, mock_fetcher: MagicMock) -> None:
        mock_fetcher.get.return_value = _mock_response()
        req = RuntimeRequest(url="https://example.com", headers={"X-Custom": "value"})
        self.runtime.fetch(req)

        call_kwargs = mock_fetcher.get.call_args[1]
        self.assertEqual(call_kwargs["headers"]["X-Custom"], "value")

    @patch("autonomous_crawler.runtime.scrapling_static.Fetcher")
    def test_cookies_forwarded(self, mock_fetcher: MagicMock) -> None:
        mock_fetcher.get.return_value = _mock_response()
        req = RuntimeRequest(url="https://example.com", cookies={"session": "abc"})
        self.runtime.fetch(req)

        call_kwargs = mock_fetcher.get.call_args[1]
        self.assertEqual(call_kwargs["cookies"]["session"], "abc")

    @patch("autonomous_crawler.runtime.scrapling_static.Fetcher")
    def test_timeout_converted_to_seconds(self, mock_fetcher: MagicMock) -> None:
        mock_fetcher.get.return_value = _mock_response()
        req = RuntimeRequest(url="https://example.com", timeout_ms=15000)
        self.runtime.fetch(req)

        call_kwargs = mock_fetcher.get.call_args[1]
        self.assertEqual(call_kwargs["timeout"], 15.0)

    @patch("autonomous_crawler.runtime.scrapling_static.Fetcher")
    def test_proxy_config_forwarded(self, mock_fetcher: MagicMock) -> None:
        mock_fetcher.get.return_value = _mock_response()
        req = RuntimeRequest(
            url="https://example.com",
            proxy_config={"proxy": "http://proxy.example:8080"},
        )
        self.runtime.fetch(req)

        call_kwargs = mock_fetcher.get.call_args[1]
        self.assertEqual(call_kwargs["proxy"], "http://proxy.example:8080")

    @patch("autonomous_crawler.runtime.scrapling_static.Fetcher")
    def test_proxy_url_key_also_works(self, mock_fetcher: MagicMock) -> None:
        mock_fetcher.get.return_value = _mock_response()
        req = RuntimeRequest(
            url="https://example.com",
            proxy_config={"url": "http://proxy.example:8080"},
        )
        self.runtime.fetch(req)

        call_kwargs = mock_fetcher.get.call_args[1]
        self.assertEqual(call_kwargs["proxy"], "http://proxy.example:8080")

    @patch("autonomous_crawler.runtime.scrapling_static.Fetcher")
    def test_no_proxy_when_config_empty(self, mock_fetcher: MagicMock) -> None:
        mock_fetcher.get.return_value = _mock_response()
        req = RuntimeRequest(url="https://example.com")
        self.runtime.fetch(req)

        call_kwargs = mock_fetcher.get.call_args[1]
        self.assertNotIn("proxy", call_kwargs)

    @patch("autonomous_crawler.runtime.scrapling_static.Fetcher")
    def test_network_error_returns_failure(self, mock_fetcher: MagicMock) -> None:
        mock_fetcher.get.side_effect = ConnectionError("connection refused")
        req = RuntimeRequest(url="https://nonexistent.invalid")
        resp = self.runtime.fetch(req)

        self.assertFalse(resp.ok)
        self.assertIn("ConnectionError", resp.error)

    @patch("autonomous_crawler.runtime.scrapling_static.Fetcher")
    def test_timeout_error_returns_failure(self, mock_fetcher: MagicMock) -> None:
        mock_fetcher.get.side_effect = TimeoutError("request timed out")
        req = RuntimeRequest(url="https://slow.example.com")
        resp = self.runtime.fetch(req)

        self.assertFalse(resp.ok)
        self.assertIn("TimeoutError", resp.error)

    @patch("autonomous_crawler.runtime.scrapling_static._HAS_SCRAPLING", False)
    def test_missing_scrapling_returns_clear_failure(self) -> None:
        req = RuntimeRequest(url="https://example.com")
        resp = self.runtime.fetch(req)

        self.assertFalse(resp.ok)
        self.assertIn("scrapling", resp.error.lower())
        self.assertIn("not installed", resp.error.lower())

    @patch("autonomous_crawler.runtime.scrapling_static.Fetcher")
    def test_403_response_marked_not_ok(self, mock_fetcher: MagicMock) -> None:
        mock_fetcher.get.return_value = _mock_response(status=403, body=b"Forbidden")
        req = RuntimeRequest(url="https://example.com")
        resp = self.runtime.fetch(req)

        self.assertFalse(resp.ok)
        self.assertEqual(resp.status_code, 403)

    @patch("autonomous_crawler.runtime.scrapling_static.Fetcher")
    def test_301_response_marked_ok(self, mock_fetcher: MagicMock) -> None:
        mock_fetcher.get.return_value = _mock_response(status=301, body=b"Redirect")
        req = RuntimeRequest(url="https://example.com")
        resp = self.runtime.fetch(req)

        self.assertTrue(resp.ok)
        self.assertEqual(resp.status_code, 301)

    @patch("autonomous_crawler.runtime.scrapling_static.Fetcher")
    def test_response_headers_populated(self, mock_fetcher: MagicMock) -> None:
        mock_fetcher.get.return_value = _mock_response(
            headers={"Content-Type": "text/html", "X-Request-Id": "abc123"},
        )
        req = RuntimeRequest(url="https://example.com")
        resp = self.runtime.fetch(req)

        self.assertEqual(resp.headers["Content-Type"], "text/html")
        self.assertEqual(resp.headers["X-Request-Id"], "abc123")

    @patch("autonomous_crawler.runtime.scrapling_static.Fetcher")
    def test_response_cookies_populated(self, mock_fetcher: MagicMock) -> None:
        mock_fetcher.get.return_value = _mock_response(
            cookies={"session": "token123"},
        )
        req = RuntimeRequest(url="https://example.com")
        resp = self.runtime.fetch(req)

        self.assertEqual(resp.cookies["session"], "token123")

    @patch("autonomous_crawler.runtime.scrapling_static.Fetcher")
    def test_delete_method_dispatched(self, mock_fetcher: MagicMock) -> None:
        mock_fetcher.delete.return_value = _mock_response(status=204, body=b"")
        req = RuntimeRequest(url="https://example.com/api/item/1", method="DELETE")
        resp = self.runtime.fetch(req)

        self.assertTrue(resp.ok)
        mock_fetcher.delete.assert_called_once()

    @patch("autonomous_crawler.runtime.scrapling_static.Fetcher")
    def test_put_method_dispatched(self, mock_fetcher: MagicMock) -> None:
        mock_fetcher.put.return_value = _mock_response(body=b'{"updated":true}')
        req = RuntimeRequest(url="https://example.com/api/item/1", method="PUT", json={"name": "new"})
        resp = self.runtime.fetch(req)

        self.assertTrue(resp.ok)
        mock_fetcher.put.assert_called_once()

    @patch("autonomous_crawler.runtime.scrapling_static.Fetcher")
    def test_proxy_credentials_not_in_response(self, mock_fetcher: MagicMock) -> None:
        """Proxy credentials must never appear in the response payload."""
        mock_fetcher.get.return_value = _mock_response()
        req = RuntimeRequest(
            url="https://example.com",
            proxy_config={"proxy": "http://user:secret123@proxy.example:8080"},
        )
        resp = self.runtime.fetch(req)
        payload = str(resp.to_dict())

        self.assertNotIn("secret123", payload)

    @patch("autonomous_crawler.runtime.scrapling_static.Fetcher")
    def test_body_bytes_preserved(self, mock_fetcher: MagicMock) -> None:
        raw = b"<html><body>Binary content</body></html>"
        mock_fetcher.get.return_value = _mock_response(body=raw)
        req = RuntimeRequest(url="https://example.com")
        resp = self.runtime.fetch(req)

        self.assertEqual(resp.body, raw)


class ScraplingStaticRuntimeProtocolTests(unittest.TestCase):
    """Verify ScraplingStaticRuntime satisfies FetchRuntime protocol."""

    def test_satisfies_fetch_runtime_protocol(self) -> None:
        from autonomous_crawler.runtime.protocols import FetchRuntime
        runtime = ScraplingStaticRuntime()
        self.assertIsInstance(runtime, FetchRuntime)


if __name__ == "__main__":
    unittest.main()
