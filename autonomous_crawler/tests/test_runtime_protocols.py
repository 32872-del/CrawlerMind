import unittest

from autonomous_crawler.runtime import (
    RuntimeArtifact,
    RuntimeEvent,
    RuntimeProxyTrace,
    RuntimeRequest,
    RuntimeResponse,
    RuntimeSelectorRequest,
    RuntimeSelectorResult,
)


class RuntimeProtocolModelTests(unittest.TestCase):
    def test_request_from_dict_normalizes_mode_method_and_redacts_safe_output(self):
        request = RuntimeRequest.from_dict({
            "url": "https://example.com",
            "method": "TRACE",
            "mode": "bad",
            "headers": {"Authorization": "Bearer secret", "Accept": "text/html"},
            "cookies": {"sid": "secret"},
            "proxy_config": {"default_proxy": "http://user:pass@proxy.local:8080"},
            "selectors": [{"name": "title", "selector": "h1::text"}],
            "timeout_ms": "500",
        })

        self.assertEqual(request.method, "GET")
        self.assertEqual(request.mode, "static")
        self.assertEqual(request.timeout_ms, 1000)
        safe = request.to_safe_dict()
        self.assertEqual(safe["headers"]["Authorization"], "[redacted]")
        self.assertEqual(safe["cookies"]["sid"], "[redacted]")
        self.assertEqual(safe["proxy_config"]["default_proxy"], "http://***:***@proxy.local:8080")
        self.assertEqual(safe["selectors"][0]["name"], "title")

    def test_selector_request_and_result_are_structured(self):
        selector = RuntimeSelectorRequest.from_dict({
            "name": "price",
            "selector": ".price::text",
            "selector_type": "css",
            "many": False,
        })
        result = RuntimeSelectorResult(
            name=selector.name,
            values=["$10"],
            selector=selector.selector,
            selector_type=selector.selector_type,
            matched=1,
        )

        self.assertTrue(result.ok)
        self.assertEqual(result.to_dict()["values"], ["$10"])

    def test_proxy_trace_redacts_credentials_and_error_messages(self):
        trace = RuntimeProxyTrace.from_dict({
            "selected": True,
            "proxy": "http://user:pass@proxy.local:8080",
            "source": "pool",
            "errors": ["failed password=secret at http://user:pass@proxy.local:8080"],
        })

        payload = trace.to_dict()
        self.assertEqual(payload["proxy"], "http://***:***@proxy.local:8080")
        self.assertNotIn("secret", payload["errors"][0])
        self.assertNotIn("user:pass", payload["errors"][0])

    def test_runtime_response_serializes_artifacts_events_and_failures(self):
        response = RuntimeResponse(
            ok=True,
            final_url="https://example.com",
            status_code=200,
            headers={"Cookie": "sid=secret", "Content-Type": "text/html"},
            cookies={"sid": "secret"},
            html="<h1>Hello</h1>",
            artifacts=[RuntimeArtifact(kind="html", path=r"F:\private\storage_state.json")],
            runtime_events=[RuntimeEvent(type="fetch", message="ok")],
            engine_result={"engine": "scrapling", "proxy": "http://user:pass@proxy.local:8080"},
        )

        payload = response.to_dict()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["headers"]["Cookie"], "[redacted]")
        self.assertEqual(payload["cookies"]["sid"], "[redacted]")
        self.assertEqual(payload["engine_result"]["proxy"], "http://***:***@proxy.local:8080")
        self.assertEqual(payload["runtime_events"][0]["type"], "fetch")

    def test_failure_factory_returns_credential_safe_error(self):
        response = RuntimeResponse.failure(
            error="failed token=abc at http://user:pass@proxy.local:8080",
            engine="scrapling",
            proxy_trace={"selected": True, "proxy": "http://user:pass@proxy.local:8080"},
        )

        payload = response.to_dict()
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["engine_result"]["engine"], "scrapling")
        self.assertNotIn("abc", payload["error"])
        self.assertEqual(payload["proxy_trace"]["proxy"], "http://***:***@proxy.local:8080")


if __name__ == "__main__":
    unittest.main()
