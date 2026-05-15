"""Tests for CLM-native static fetch runtime (SCRAPLING-ABSORB-1)."""
from __future__ import annotations

import sys
import types
import unittest
from unittest.mock import MagicMock, patch

from autonomous_crawler.runtime import FetchRuntime, NativeFetchRuntime
from autonomous_crawler.runtime.models import RuntimeRequest


def _httpx_response(
    *,
    status_code: int = 200,
    url: str = "https://example.com/",
    headers: dict[str, str] | None = None,
    content: bytes = b"<html><body>Hello</body></html>",
) -> MagicMock:
    response = MagicMock()
    response.status_code = status_code
    response.url = url
    response.headers = headers or {"Content-Type": "text/html"}
    response.cookies = {"sid": "token"}
    response.content = content
    response.text = content.decode("utf-8", errors="replace")
    response.http_version = "HTTP/2"
    return response


def _curl_response(
    *,
    status_code: int = 200,
    url: str = "https://example.com/",
    headers: dict[str, str] | None = None,
    content: bytes = b"<html><body>Hello</body></html>",
) -> MagicMock:
    response = MagicMock()
    response.status_code = status_code
    response.url = url
    response.headers = headers or {"Content-Type": "text/html"}
    response.cookies = {"sid": "token"}
    response.content = content
    response.text = content.decode("utf-8", errors="replace")
    response.http_version = "HTTP/1.1"
    return response


class NativeFetchRuntimeHttpxTests(unittest.TestCase):
    def setUp(self) -> None:
        self.runtime = NativeFetchRuntime()

    def test_name_is_native_static(self) -> None:
        self.assertEqual(self.runtime.name, "native_static")

    def test_satisfies_fetch_runtime_protocol(self) -> None:
        self.assertIsInstance(self.runtime, FetchRuntime)

    @patch("autonomous_crawler.runtime.native_static.httpx.Client")
    def test_get_returns_clm_runtime_response(self, mock_client_cls: MagicMock) -> None:
        client = mock_client_cls.return_value.__enter__.return_value
        client.request.return_value = _httpx_response()

        response = self.runtime.fetch(RuntimeRequest(url="https://example.com"))

        self.assertTrue(response.ok)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Hello", response.html)
        self.assertEqual(response.engine_result["engine"], "native_static")
        self.assertEqual(response.engine_result["transport"], "httpx")
        self.assertEqual(response.engine_result["http_version"], "HTTP/2")
        self.assertEqual(response.runtime_events[0].type, "fetch_start")
        self.assertEqual(response.runtime_events[-1].type, "fetch_complete")

    @patch("autonomous_crawler.runtime.native_static.httpx.Client")
    def test_headers_cookies_params_json_and_timeout_are_forwarded(self, mock_client_cls: MagicMock) -> None:
        client = mock_client_cls.return_value.__enter__.return_value
        client.request.return_value = _httpx_response(content=b'{"ok": true}', headers={"Content-Type": "application/json"})
        request = RuntimeRequest(
            url="https://example.com/api",
            method="POST",
            headers={"X-Test": "1"},
            cookies={"sid": "abc"},
            params={"page": 1},
            json={"hello": "world"},
            timeout_ms=15000,
        )

        response = self.runtime.fetch(request)

        self.assertTrue(response.ok)
        client.request.assert_called_once()
        method, url = client.request.call_args.args[:2]
        self.assertEqual(method, "POST")
        self.assertEqual(url, "https://example.com/api")
        self.assertEqual(client.request.call_args.kwargs["params"], {"page": 1})
        self.assertEqual(client.request.call_args.kwargs["json"], {"hello": "world"})
        client_kwargs = mock_client_cls.call_args.kwargs
        self.assertEqual(client_kwargs["headers"], {"X-Test": "1"})
        self.assertEqual(client_kwargs["cookies"], {"sid": "abc"})

    @patch("autonomous_crawler.runtime.native_static.httpx.Client")
    def test_proxy_is_forwarded_and_redacted_in_output(self, mock_client_cls: MagicMock) -> None:
        client = mock_client_cls.return_value.__enter__.return_value
        client.request.return_value = _httpx_response()
        request = RuntimeRequest(
            url="https://example.com",
            proxy_config={"proxy": "http://user:secret@proxy.local:8080"},
        )

        response = self.runtime.fetch(request)
        payload = str(response.to_dict())

        self.assertEqual(mock_client_cls.call_args.kwargs["proxy"], "http://user:secret@proxy.local:8080")
        self.assertIn("http://***:***@proxy.local:8080", payload)
        self.assertNotIn("secret", payload)

    @patch("autonomous_crawler.runtime.native_static.httpx.Client")
    def test_403_is_not_ok(self, mock_client_cls: MagicMock) -> None:
        client = mock_client_cls.return_value.__enter__.return_value
        client.request.return_value = _httpx_response(status_code=403, content=b"Forbidden")

        response = self.runtime.fetch(RuntimeRequest(url="https://example.com"))

        self.assertFalse(response.ok)
        self.assertEqual(response.status_code, 403)

    @patch("autonomous_crawler.runtime.native_static.httpx.Client")
    def test_network_error_returns_structured_failure(self, mock_client_cls: MagicMock) -> None:
        client = mock_client_cls.return_value.__enter__.return_value
        client.request.side_effect = TimeoutError("password=secret timed out")

        response = self.runtime.fetch(RuntimeRequest(url="https://example.com"))
        payload = response.to_dict()

        self.assertFalse(response.ok)
        self.assertEqual(payload["engine_result"]["engine"], "native_static")
        self.assertNotIn("secret", payload["error"])
        self.assertEqual(response.runtime_events[-1].type, "fetch_error")


class NativeFetchRuntimeCurlCffiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.runtime = NativeFetchRuntime()

    def test_curl_cffi_transport_uses_curl_request(self) -> None:
        fake_requests = types.SimpleNamespace(request=MagicMock(return_value=_curl_response()))
        fake_package = types.SimpleNamespace(requests=fake_requests)
        with patch.dict(sys.modules, {"curl_cffi": fake_package, "curl_cffi.requests": fake_requests}):
            response = self.runtime.fetch(
                RuntimeRequest(
                    url="https://example.com",
                    method="PUT",
                    json={"x": 1},
                    meta={"transport": "curl_cffi", "impersonate": "chrome124"},
                )
            )

        self.assertTrue(response.ok)
        self.assertEqual(response.engine_result["transport"], "curl_cffi")
        fake_requests.request.assert_called_once()
        call = fake_requests.request.call_args
        self.assertEqual(call.args[:2], ("PUT", "https://example.com"))
        self.assertEqual(call.kwargs["json"], {"x": 1})
        self.assertEqual(call.kwargs["impersonate"], "chrome124")

    def test_unsupported_transport_falls_back_to_httpx(self) -> None:
        with patch("autonomous_crawler.runtime.native_static.httpx.Client") as mock_client_cls:
            client = mock_client_cls.return_value.__enter__.return_value
            client.request.return_value = _httpx_response()
            response = self.runtime.fetch(
                RuntimeRequest(url="https://example.com", meta={"transport": "unknown"})
            )

        self.assertEqual(response.engine_result["transport"], "httpx")


# ---------------------------------------------------------------------------
# Proxy health integration with native fetch
# ---------------------------------------------------------------------------

class NativeFetchProxyHealthIntegrationTests(unittest.TestCase):
    """NativeFetchRuntime proxy evidence for health scoring integration."""

    def _mock_response(self, **kwargs) -> MagicMock:
        resp = MagicMock()
        resp.status_code = kwargs.get("status_code", 200)
        resp.url = kwargs.get("url", "https://example.com")
        resp.headers = kwargs.get("headers", {"Content-Type": "text/html"})
        resp.cookies = {}
        resp.content = kwargs.get("content", b"<html>ok</html>")
        resp.text = kwargs.get("content", b"<html>ok</html>").decode()
        resp.http_version = "1.1"
        return resp

    @patch("autonomous_crawler.runtime.native_static.httpx.Client")
    def test_proxy_source_forwarded_to_trace(self, mock_client_cls: MagicMock) -> None:
        """proxy_config source is forwarded to RuntimeProxyTrace."""
        client = mock_client_cls.return_value.__enter__.return_value
        client.request.return_value = self._mock_response()

        runtime = NativeFetchRuntime()
        req = RuntimeRequest(
            url="https://example.com",
            proxy_config={"proxy": "http://p:8080", "source": "pool_round_robin", "provider": "static"},
        )
        resp = runtime.fetch(req)

        self.assertTrue(resp.proxy_trace.selected)
        self.assertEqual(resp.proxy_trace.source, "pool_round_robin")
        self.assertEqual(resp.proxy_trace.provider, "static")

    @patch("autonomous_crawler.runtime.native_static.httpx.Client")
    def test_proxy_strategy_forwarded_to_trace(self, mock_client_cls: MagicMock) -> None:
        """proxy_config strategy is forwarded to RuntimeProxyTrace."""
        client = mock_client_cls.return_value.__enter__.return_value
        client.request.return_value = self._mock_response()

        runtime = NativeFetchRuntime()
        req = RuntimeRequest(
            url="https://example.com",
            proxy_config={"proxy": "http://p:8080", "strategy": "domain_sticky"},
        )
        resp = runtime.fetch(req)

        self.assertEqual(resp.proxy_trace.strategy, "domain_sticky")

    @patch("autonomous_crawler.runtime.native_static.httpx.Client")
    def test_no_proxy_trace_source_is_none(self, mock_client_cls: MagicMock) -> None:
        """When no proxy configured, trace source is 'none'."""
        client = mock_client_cls.return_value.__enter__.return_value
        client.request.return_value = self._mock_response()

        runtime = NativeFetchRuntime()
        resp = runtime.fetch(RuntimeRequest(url="https://example.com"))

        self.assertFalse(resp.proxy_trace.selected)
        self.assertEqual(resp.proxy_trace.source, "none")

    @patch("autonomous_crawler.runtime.native_static.httpx.Client")
    def test_fetch_error_has_engine_result(self, mock_client_cls: MagicMock) -> None:
        """Failed fetch still returns engine_result with engine name."""
        client = mock_client_cls.return_value.__enter__.return_value
        client.request.side_effect = ConnectionError("refused")

        runtime = NativeFetchRuntime()
        resp = runtime.fetch(RuntimeRequest(url="https://bad.example"))

        self.assertFalse(resp.ok)
        self.assertEqual(resp.engine_result["engine"], "native_static")

    @patch("autonomous_crawler.runtime.native_static.httpx.Client")
    def test_fetch_error_has_redacted_error_message(self, mock_client_cls: MagicMock) -> None:
        """Error message in failed response has credentials redacted."""
        client = mock_client_cls.return_value.__enter__.return_value
        client.request.side_effect = ConnectionError("password=secret123 connection refused")

        runtime = NativeFetchRuntime()
        resp = runtime.fetch(RuntimeRequest(url="https://bad.example"))

        self.assertFalse(resp.ok)
        self.assertNotIn("secret123", resp.error)


if __name__ == "__main__":
    unittest.main()
