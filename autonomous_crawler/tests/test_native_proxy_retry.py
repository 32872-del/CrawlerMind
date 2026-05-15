"""Tests for proxy retry orchestration in NativeFetchRuntime.

Covers CAP-3.3 / SCRAPLING-ABSORB-1E acceptance criteria:
- First proxy fail → second proxy success
- All proxies unavailable / cooldown
- Max attempts exhaustion
- Credentials never leak in events or response
- Existing native static runtime tests still pass (separate file)
"""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from autonomous_crawler.runtime.native_static import NativeFetchRuntime
from autonomous_crawler.runtime.models import RuntimeRequest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _httpx_response(
    *,
    status_code: int = 200,
    url: str = "https://example.com/",
    content: bytes = b"<html><body>OK</body></html>",
    headers: dict[str, str] | None = None,
) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.url = url
    resp.headers = headers or {"Content-Type": "text/html"}
    resp.cookies = {}
    resp.content = content
    resp.text = content.decode("utf-8", errors="replace")
    resp.http_version = "HTTP/2"
    return resp


def _make_request(
    *,
    proxy_url: str = "http://user:pass@proxy-a.example:8080",
    max_attempts: int = 3,
    pool_provider: object | None = None,
    health_store: object | None = None,
) -> RuntimeRequest:
    proxy_config: dict = {
        "retry_on_proxy_failure": True,
        "max_proxy_attempts": max_attempts,
    }
    if proxy_url:
        proxy_config["proxy"] = proxy_url
    if pool_provider is not None:
        proxy_config["pool_provider"] = pool_provider
    if health_store is not None:
        proxy_config["health_store"] = health_store
    return RuntimeRequest(url="https://example.com/", proxy_config=proxy_config)


def _mock_pool_provider(
    *,
    proxies: list[str] | None = None,
    selection_proxy: str = "",
) -> MagicMock:
    """Create a mock ProxyPoolProvider."""
    provider = MagicMock()
    provider.select.return_value = MagicMock(proxy_url=selection_proxy)
    provider.report_result = MagicMock()
    return provider


def _mock_health_store() -> MagicMock:
    """Create a mock ProxyHealthStore."""
    store = MagicMock()
    store.record_failure = MagicMock()
    store.record_success = MagicMock()
    return store


def _all_event_types(response) -> list[str]:
    return [e.type for e in response.runtime_events]


def _all_event_dicts(response) -> list[dict]:
    return [e.to_dict() for e in response.runtime_events]


# ---------------------------------------------------------------------------
# Tests: first proxy fail, second proxy success
# ---------------------------------------------------------------------------

class TestProxyRetryFirstFailSecondSuccess(unittest.TestCase):
    """Attempt 0 fails on connection error, attempt 1 succeeds."""

    @patch("autonomous_crawler.runtime.native_static.httpx.Client")
    def test_first_fail_second_success_returns_ok(self, mock_client_cls: MagicMock) -> None:
        pool = _mock_pool_provider(selection_proxy="http://alt-user:alt-pass@proxy-b.example:9090")
        health = _mock_health_store()
        request = _make_request(pool_provider=pool, health_store=health, max_attempts=3)

        client = mock_client_cls.return_value.__enter__.return_value
        client.request.side_effect = [
            ConnectionError("proxy-a refused"),
            _httpx_response(status_code=200, content=b"<html>OK</html>"),
        ]

        runtime = NativeFetchRuntime()
        response = runtime.fetch(request)

        self.assertTrue(response.ok)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.engine_result["engine"], "native_static")

    @patch("autonomous_crawler.runtime.native_static.httpx.Client")
    def test_first_fail_second_success_events(self, mock_client_cls: MagicMock) -> None:
        pool = _mock_pool_provider(selection_proxy="http://alt:cred@proxy-b.example:9090")
        health = _mock_health_store()
        request = _make_request(pool_provider=pool, health_store=health, max_attempts=3)

        client = mock_client_cls.return_value.__enter__.return_value
        client.request.side_effect = [
            ConnectionError("refused"),
            _httpx_response(),
        ]

        runtime = NativeFetchRuntime()
        response = runtime.fetch(request)

        event_types = _all_event_types(response)
        self.assertIn("fetch_start", event_types)
        self.assertIn("proxy_attempt", event_types)
        self.assertIn("proxy_failure_recorded", event_types)
        self.assertIn("proxy_retry", event_types)
        self.assertIn("proxy_success_recorded", event_types)
        self.assertIn("fetch_complete", event_types)

    @patch("autonomous_crawler.runtime.native_static.httpx.Client")
    def test_failure_recorded_to_health_store(self, mock_client_cls: MagicMock) -> None:
        pool = _mock_pool_provider(selection_proxy="http://alt:cred@proxy-b:9090")
        health = _mock_health_store()
        request = _make_request(
            proxy_url="http://user:pass@proxy-a:8080",
            pool_provider=pool,
            health_store=health,
            max_attempts=2,
        )

        client = mock_client_cls.return_value.__enter__.return_value
        client.request.side_effect = [
            ConnectionError("refused"),
            _httpx_response(),
        ]

        runtime = NativeFetchRuntime()
        runtime.fetch(request)

        health.record_failure.assert_called_once()
        fail_args = health.record_failure.call_args
        self.assertIn("proxy-a", fail_args[0][0])  # proxy URL contains proxy-a

    @patch("autonomous_crawler.runtime.native_static.httpx.Client")
    def test_success_recorded_to_health_store(self, mock_client_cls: MagicMock) -> None:
        pool = _mock_pool_provider(selection_proxy="http://alt:cred@proxy-b:9090")
        health = _mock_health_store()
        request = _make_request(
            proxy_url="http://user:pass@proxy-a:8080",
            pool_provider=pool,
            health_store=health,
            max_attempts=2,
        )

        client = mock_client_cls.return_value.__enter__.return_value
        client.request.side_effect = [
            ConnectionError("refused"),
            _httpx_response(),
        ]

        runtime = NativeFetchRuntime()
        runtime.fetch(request)

        health.record_success.assert_called_once()
        success_args = health.record_success.call_args
        # The second proxy was selected from pool
        self.assertIn("proxy-b", success_args[0][0])

    @patch("autonomous_crawler.runtime.native_static.httpx.Client")
    def test_pool_provider_report_result_called(self, mock_client_cls: MagicMock) -> None:
        pool = _mock_pool_provider(selection_proxy="http://alt:cred@proxy-b:9090")
        health = _mock_health_store()
        request = _make_request(
            proxy_url="http://user:pass@proxy-a:8080",
            pool_provider=pool,
            health_store=health,
            max_attempts=2,
        )

        client = mock_client_cls.return_value.__enter__.return_value
        client.request.side_effect = [
            ConnectionError("refused"),
            _httpx_response(),
        ]

        runtime = NativeFetchRuntime()
        runtime.fetch(request)

        # pool.report_result called twice: once failure, once success
        self.assertEqual(pool.report_result.call_count, 2)
        fail_call, success_call = pool.report_result.call_args_list
        self.assertFalse(fail_call.kwargs.get("ok", fail_call[1].get("ok", True) if fail_call[1] else True))
        self.assertTrue(success_call.kwargs.get("ok", success_call[1].get("ok", False) if success_call[1] else False))


# ---------------------------------------------------------------------------
# Tests: all proxies unavailable / cooldown
# ---------------------------------------------------------------------------

class TestProxyRetryAllUnavailable(unittest.TestCase):
    """Every proxy attempt fails — all in cooldown or unavailable."""

    @patch("autonomous_crawler.runtime.native_static.httpx.Client")
    def test_all_attempts_fail_returns_failure(self, mock_client_cls: MagicMock) -> None:
        pool = _mock_pool_provider(selection_proxy="http://alt:cred@proxy-b:9090")
        health = _mock_health_store()
        request = _make_request(
            proxy_url="http://user:pass@proxy-a:8080",
            pool_provider=pool,
            health_store=health,
            max_attempts=2,
        )

        client = mock_client_cls.return_value.__enter__.return_value
        client.request.side_effect = [
            ConnectionError("proxy-a refused"),
            ConnectionError("proxy-b refused"),
        ]

        runtime = NativeFetchRuntime()
        response = runtime.fetch(request)

        self.assertFalse(response.ok)
        self.assertIn("all 2 proxy attempts failed", response.error)

    @patch("autonomous_crawler.runtime.native_static.httpx.Client")
    def test_all_attempts_fail_events(self, mock_client_cls: MagicMock) -> None:
        pool = _mock_pool_provider(selection_proxy="http://alt:cred@proxy-b:9090")
        health = _mock_health_store()
        request = _make_request(max_attempts=2, pool_provider=pool, health_store=health)

        client = mock_client_cls.return_value.__enter__.return_value
        client.request.side_effect = [
            ConnectionError("a"),
            ConnectionError("b"),
        ]

        runtime = NativeFetchRuntime()
        response = runtime.fetch(request)

        event_types = _all_event_types(response)
        # Two proxy attempts
        self.assertEqual(event_types.count("proxy_attempt"), 2)
        # Two failures recorded
        self.assertEqual(event_types.count("proxy_failure_recorded"), 2)
        # One retry event (between attempt 1 and 2)
        self.assertEqual(event_types.count("proxy_retry"), 1)
        # Final error
        self.assertIn("fetch_error", event_types)
        # No success events
        self.assertNotIn("proxy_success_recorded", event_types)
        self.assertNotIn("fetch_complete", event_types)

    @patch("autonomous_crawler.runtime.native_static.httpx.Client")
    def test_all_cooldown_health_store_records_all_failures(self, mock_client_cls: MagicMock) -> None:
        pool = _mock_pool_provider(selection_proxy="http://alt:cred@proxy-b:9090")
        health = _mock_health_store()
        request = _make_request(max_attempts=3, pool_provider=pool, health_store=health)

        client = mock_client_cls.return_value.__enter__.return_value
        client.request.side_effect = [
            ConnectionError("a"),
            ConnectionError("b"),
            ConnectionError("c"),
        ]

        runtime = NativeFetchRuntime()
        runtime.fetch(request)

        self.assertEqual(health.record_failure.call_count, 3)
        self.assertEqual(health.record_success.call_count, 0)


# ---------------------------------------------------------------------------
# Tests: max attempts exhaustion
# ---------------------------------------------------------------------------

class TestProxyRetryMaxAttempts(unittest.TestCase):
    """Verify exact number of attempts matches max_proxy_attempts."""

    @patch("autonomous_crawler.runtime.native_static.httpx.Client")
    def test_single_attempt_no_retry(self, mock_client_cls: MagicMock) -> None:
        request = _make_request(max_attempts=1)

        client = mock_client_cls.return_value.__enter__.return_value
        client.request.side_effect = ConnectionError("refused")

        runtime = NativeFetchRuntime()
        response = runtime.fetch(request)

        self.assertFalse(response.ok)
        # Only one proxy_attempt event, no proxy_retry
        event_types = _all_event_types(response)
        self.assertEqual(event_types.count("proxy_attempt"), 1)
        self.assertNotIn("proxy_retry", event_types)

    @patch("autonomous_crawler.runtime.native_static.httpx.Client")
    def test_three_attempts_three_events(self, mock_client_cls: MagicMock) -> None:
        pool = _mock_pool_provider(selection_proxy="http://alt:cred@proxy-b:9090")
        health = _mock_health_store()
        request = _make_request(max_attempts=3, pool_provider=pool, health_store=health)

        client = mock_client_cls.return_value.__enter__.return_value
        client.request.side_effect = [
            ConnectionError("a"),
            ConnectionError("b"),
            ConnectionError("c"),
        ]

        runtime = NativeFetchRuntime()
        response = runtime.fetch(request)

        self.assertFalse(response.ok)
        self.assertIn("all 3 proxy attempts failed", response.error)
        event_types = _all_event_types(response)
        self.assertEqual(event_types.count("proxy_attempt"), 3)
        self.assertEqual(event_types.count("proxy_retry"), 2)

    @patch("autonomous_crawler.runtime.native_static.httpx.Client")
    def test_default_max_attempts_is_1(self, mock_client_cls: MagicMock) -> None:
        """Without explicit max_proxy_attempts, only one attempt is made."""
        request = RuntimeRequest(
            url="https://example.com/",
            proxy_config={"proxy": "http://user:pass@proxy:8080"},
        )

        client = mock_client_cls.return_value.__enter__.return_value
        client.request.side_effect = ConnectionError("refused")

        runtime = NativeFetchRuntime()
        response = runtime.fetch(request)

        self.assertFalse(response.ok)
        event_types = _all_event_types(response)
        self.assertEqual(event_types.count("proxy_attempt"), 1)
        self.assertNotIn("proxy_retry", event_types)


# ---------------------------------------------------------------------------
# Tests: credentials never leak
# ---------------------------------------------------------------------------

class TestProxyRetryCredentialSafety(unittest.TestCase):
    """Proxy URLs with credentials must be redacted in all event/response output."""

    @patch("autonomous_crawler.runtime.native_static.httpx.Client")
    def test_credentials_not_in_events(self, mock_client_cls: MagicMock) -> None:
        pool = _mock_pool_provider(selection_proxy="http://secret-user:secret-pass@proxy-b:9090")
        health = _mock_health_store()
        request = _make_request(
            proxy_url="http://leaked-user:leaked-pass@proxy-a:8080",
            pool_provider=pool,
            health_store=health,
            max_attempts=2,
        )

        client = mock_client_cls.return_value.__enter__.return_value
        client.request.side_effect = [
            ConnectionError("refused"),
            _httpx_response(),
        ]

        runtime = NativeFetchRuntime()
        response = runtime.fetch(request)

        for event_dict in _all_event_dicts(response):
            text = str(event_dict)
            self.assertNotIn("leaked-user", text)
            self.assertNotIn("leaked-pass", text)
            self.assertNotIn("secret-user", text)
            self.assertNotIn("secret-pass", text)

    @patch("autonomous_crawler.runtime.native_static.httpx.Client")
    def test_credentials_not_in_response_to_dict(self, mock_client_cls: MagicMock) -> None:
        pool = _mock_pool_provider(selection_proxy="http://s:s@proxy-b:9090")
        health = _mock_health_store()
        request = _make_request(
            proxy_url="http://u:p@proxy-a:8080",
            pool_provider=pool,
            health_store=health,
            max_attempts=2,
        )

        client = mock_client_cls.return_value.__enter__.return_value
        client.request.side_effect = [
            ConnectionError("refused"),
            _httpx_response(),
        ]

        runtime = NativeFetchRuntime()
        response = runtime.fetch(request)
        resp_dict = response.to_dict()

        text = str(resp_dict)
        self.assertNotIn("u:p@", text)
        self.assertNotIn("s:s@", text)

    @patch("autonomous_crawler.runtime.native_static.httpx.Client")
    def test_credentials_not_in_error_response(self, mock_client_cls: MagicMock) -> None:
        request = _make_request(
            proxy_url="http://admin:topsecret@proxy:8080",
            max_attempts=1,
        )

        client = mock_client_cls.return_value.__enter__.return_value
        client.request.side_effect = ConnectionError("refused")

        runtime = NativeFetchRuntime()
        response = runtime.fetch(request)
        resp_dict = response.to_dict()

        text = str(resp_dict)
        self.assertNotIn("admin", text)
        self.assertNotIn("topsecret", text)

    @patch("autonomous_crawler.runtime.native_static.httpx.Client")
    def test_credentials_not_in_failure_response_all_attempts(self, mock_client_cls: MagicMock) -> None:
        pool = _mock_pool_provider(selection_proxy="http://b-user:b-pass@proxy-b:9090")
        health = _mock_health_store()
        request = _make_request(
            proxy_url="http://a-user:a-pass@proxy-a:8080",
            pool_provider=pool,
            health_store=health,
            max_attempts=2,
        )

        client = mock_client_cls.return_value.__enter__.return_value
        client.request.side_effect = [
            ConnectionError("refused"),
            ConnectionError("refused"),
        ]

        runtime = NativeFetchRuntime()
        response = runtime.fetch(request)
        resp_dict = response.to_dict()

        text = str(resp_dict)
        self.assertNotIn("a-user", text)
        self.assertNotIn("a-pass", text)
        self.assertNotIn("b-user", text)
        self.assertNotIn("b-pass", text)


# ---------------------------------------------------------------------------
# Tests: retryable vs non-retryable errors
# ---------------------------------------------------------------------------

class TestProxyRetryErrorClassification(unittest.TestCase):
    """Only connection-level errors trigger retry; application errors do not."""

    @patch("autonomous_crawler.runtime.native_static.httpx.Client")
    def test_connect_error_is_retryable(self, mock_client_cls: MagicMock) -> None:
        import httpx as _httpx

        pool = _mock_pool_provider(selection_proxy="http://alt:cred@proxy-b:9090")
        health = _mock_health_store()
        request = _make_request(max_attempts=2, pool_provider=pool, health_store=health)

        client = mock_client_cls.return_value.__enter__.return_value
        client.request.side_effect = [
            _httpx.ConnectError("connection refused"),
            _httpx_response(),
        ]

        runtime = NativeFetchRuntime()
        response = runtime.fetch(request)

        self.assertTrue(response.ok)
        event_types = _all_event_types(response)
        self.assertIn("proxy_retry", event_types)

    @patch("autonomous_crawler.runtime.native_static.httpx.Client")
    def test_timeout_is_retryable(self, mock_client_cls: MagicMock) -> None:
        import httpx as _httpx

        pool = _mock_pool_provider(selection_proxy="http://alt:cred@proxy-b:9090")
        health = _mock_health_store()
        request = _make_request(max_attempts=2, pool_provider=pool, health_store=health)

        client = mock_client_cls.return_value.__enter__.return_value
        client.request.side_effect = [
            _httpx.ConnectTimeout("timed out"),
            _httpx_response(),
        ]

        runtime = NativeFetchRuntime()
        response = runtime.fetch(request)

        self.assertTrue(response.ok)
        event_types = _all_event_types(response)
        self.assertIn("proxy_retry", event_types)

    @patch("autonomous_crawler.runtime.native_static.httpx.Client")
    def test_value_error_is_not_retryable(self, mock_client_cls: MagicMock) -> None:
        """Non-proxy errors (like ValueError) should not trigger retry."""
        pool = _mock_pool_provider(selection_proxy="http://alt:cred@proxy-b:9090")
        health = _mock_health_store()
        request = _make_request(max_attempts=3, pool_provider=pool, health_store=health)

        client = mock_client_cls.return_value.__enter__.return_value
        client.request.side_effect = ValueError("bad request")

        runtime = NativeFetchRuntime()
        response = runtime.fetch(request)

        self.assertFalse(response.ok)
        event_types = _all_event_types(response)
        # Only one attempt, no retry
        self.assertEqual(event_types.count("proxy_attempt"), 1)
        self.assertNotIn("proxy_retry", event_types)
        self.assertNotIn("proxy_failure_recorded", event_types)
        self.assertIn("fetch_error", event_types)

    @patch("autonomous_crawler.runtime.native_static.httpx.Client")
    def test_read_timeout_is_retryable(self, mock_client_cls: MagicMock) -> None:
        import httpx as _httpx

        pool = _mock_pool_provider(selection_proxy="http://alt:cred@proxy-b:9090")
        health = _mock_health_store()
        request = _make_request(max_attempts=2, pool_provider=pool, health_store=health)

        client = mock_client_cls.return_value.__enter__.return_value
        client.request.side_effect = [
            _httpx.ReadTimeout("read timeout"),
            _httpx_response(),
        ]

        runtime = NativeFetchRuntime()
        response = runtime.fetch(request)

        self.assertTrue(response.ok)


# ---------------------------------------------------------------------------
# Tests: pool provider integration
# ---------------------------------------------------------------------------

class TestProxyRetryPoolProviderIntegration(unittest.TestCase):
    """Verify pool provider is called correctly for subsequent attempts."""

    @patch("autonomous_crawler.runtime.native_static.httpx.Client")
    def test_pool_provider_select_called_for_retry(self, mock_client_cls: MagicMock) -> None:
        pool = _mock_pool_provider(selection_proxy="http://alt:cred@proxy-b:9090")
        health = _mock_health_store()
        request = _make_request(max_attempts=2, pool_provider=pool, health_store=health)

        client = mock_client_cls.return_value.__enter__.return_value
        client.request.side_effect = [
            ConnectionError("refused"),
            _httpx_response(),
        ]

        runtime = NativeFetchRuntime()
        runtime.fetch(request)

        # pool.select called once (for attempt 1, not attempt 0)
        pool.select.assert_called_once()

    @patch("autonomous_crawler.runtime.native_static.httpx.Client")
    def test_no_pool_provider_falls_back_to_request_proxy(self, mock_client_cls: MagicMock) -> None:
        """Without pool_provider, retries use the same request proxy."""
        health = _mock_health_store()
        request = _make_request(max_attempts=2, health_store=health)

        client = mock_client_cls.return_value.__enter__.return_value
        client.request.side_effect = [
            ConnectionError("refused"),
            _httpx_response(),
        ]

        runtime = NativeFetchRuntime()
        response = runtime.fetch(request)

        self.assertTrue(response.ok)

    @patch("autonomous_crawler.runtime.native_static.httpx.Client")
    def test_pool_provider_select_exception_falls_back(self, mock_client_cls: MagicMock) -> None:
        """If pool.select raises, fallback to request proxy."""
        pool = MagicMock()
        pool.select.side_effect = RuntimeError("pool exhausted")
        pool.report_result = MagicMock()
        health = _mock_health_store()
        request = _make_request(max_attempts=2, pool_provider=pool, health_store=health)

        client = mock_client_cls.return_value.__enter__.return_value
        client.request.side_effect = [
            ConnectionError("refused"),
            _httpx_response(),
        ]

        runtime = NativeFetchRuntime()
        response = runtime.fetch(request)

        # Should still succeed by falling back to original proxy
        self.assertTrue(response.ok)


# ---------------------------------------------------------------------------
# Tests: retry with different transport errors
# ---------------------------------------------------------------------------

class TestProxyRetryVariousConnectionErrors(unittest.TestCase):
    """Various connection-level errors should all trigger retry."""

    @patch("autonomous_crawler.runtime.native_static.httpx.Client")
    def test_connection_reset_error_retryable(self, mock_client_cls: MagicMock) -> None:
        pool = _mock_pool_provider(selection_proxy="http://alt:cred@proxy-b:9090")
        request = _make_request(max_attempts=2, pool_provider=pool)

        client = mock_client_cls.return_value.__enter__.return_value
        client.request.side_effect = [
            ConnectionResetError("reset"),
            _httpx_response(),
        ]

        runtime = NativeFetchRuntime()
        response = runtime.fetch(request)
        self.assertTrue(response.ok)

    @patch("autonomous_crawler.runtime.native_static.httpx.Client")
    def test_pool_timeout_retryable(self, mock_client_cls: MagicMock) -> None:
        import httpx as _httpx

        pool = _mock_pool_provider(selection_proxy="http://alt:cred@proxy-b:9090")
        request = _make_request(max_attempts=2, pool_provider=pool)

        client = mock_client_cls.return_value.__enter__.return_value
        client.request.side_effect = [
            _httpx.PoolTimeout("pool timeout"),
            _httpx_response(),
        ]

        runtime = NativeFetchRuntime()
        response = runtime.fetch(request)
        self.assertTrue(response.ok)


if __name__ == "__main__":
    unittest.main()
