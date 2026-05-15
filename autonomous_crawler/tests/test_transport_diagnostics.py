from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from autonomous_crawler.agents.recon import recon_node
from autonomous_crawler.tools.fetch_policy import BestFetchResult, FetchAttempt
from autonomous_crawler.tools.html_recon import MOCK_CHALLENGE_HTML, MOCK_PRODUCT_HTML
from autonomous_crawler.tools.transport_diagnostics import (
    diagnose_transport_modes,
)


class TransportDiagnosticsTests(unittest.TestCase):
    def test_detects_transport_sensitive_blocking(self) -> None:
        def requests_fetch(url: str, headers: dict[str, str] | None) -> FetchAttempt:
            return FetchAttempt(
                mode="requests",
                url=url,
                html=MOCK_CHALLENGE_HTML,
                status_code=403,
                response_headers={"server": "cloudflare", "set-cookie": "secret"},
                http_version="HTTP/1.1",
            )

        def curl_fetch(url: str, headers: dict[str, str] | None) -> FetchAttempt:
            return FetchAttempt(
                mode="curl_cffi",
                url=url,
                html=MOCK_PRODUCT_HTML,
                status_code=200,
                response_headers={"content-type": "text/html", "server": "nginx"},
                http_version="HTTP/2",
            )

        report = diagnose_transport_modes(
            "https://shop.example",
            modes=["requests", "curl_cffi"],
            fetchers={"requests": requests_fetch, "curl_cffi": curl_fetch},
        )
        payload = report.to_dict()

        self.assertTrue(payload["transport_sensitive"])
        self.assertEqual(payload["selected_mode"], "curl_cffi")
        self.assertIn("status_differs_by_transport", payload["findings"])
        self.assertIn("some_transports_succeed_while_others_blocked", payload["findings"])
        self.assertIn("http_version_differs", payload["findings"])
        self.assertIn("transport_profile_differs", payload["findings"])
        self.assertIn("server_header_differs", payload["findings"])
        self.assertEqual(payload["modes"][0]["transport_profile"], "httpx-default")
        self.assertEqual(payload["modes"][1]["transport_profile"], "curl_cffi:chrome124")
        self.assertEqual(payload["modes"][0]["headers"]["set-cookie"], "[redacted]")
        self.assertTrue(any("curl_cffi" in item for item in payload["recommendations"]))
        self.assertTrue(any("client profile" in item for item in payload["recommendations"]))

    def test_edge_header_presence_difference_detected(self) -> None:
        def requests_fetch(url: str, headers: dict[str, str] | None) -> FetchAttempt:
            return FetchAttempt(
                mode="requests",
                url=url,
                html=MOCK_PRODUCT_HTML,
                status_code=200,
                response_headers={"content-type": "text/html", "x-cache": "HIT"},
                http_version="HTTP/2",
            )

        def browser_fetch(url: str, headers: dict[str, str] | None) -> FetchAttempt:
            return FetchAttempt(
                mode="browser",
                url=url,
                html=MOCK_PRODUCT_HTML,
                status_code=200,
                response_headers={"content-type": "text/html"},
                http_version="HTTP/2",
            )

        report = diagnose_transport_modes(
            "https://shop.example",
            modes=["requests", "browser"],
            fetchers={"requests": requests_fetch, "browser": browser_fetch},
        )

        self.assertIn("edge_header_presence_differs", report.findings)
        self.assertTrue(any("CDN/cache headers" in item for item in report.recommendations))

    def test_no_difference_reports_no_strong_signal(self) -> None:
        def fetcher(url: str, headers: dict[str, str] | None) -> FetchAttempt:
            return FetchAttempt(
                mode="requests",
                url=url,
                html=MOCK_PRODUCT_HTML,
                status_code=200,
                response_headers={"content-type": "text/html"},
                http_version="HTTP/2",
            )

        report = diagnose_transport_modes(
            "https://shop.example",
            modes=["requests"],
            fetchers={"requests": fetcher},
        )

        self.assertFalse(report.transport_sensitive)
        self.assertEqual(report.recommendations, ["No strong transport-specific signal found"])

    def test_mode_specific_transport_error_detected(self) -> None:
        def failed(url: str, headers: dict[str, str] | None) -> FetchAttempt:
            return FetchAttempt(mode="requests", url=url, error="TLS handshake failed")

        def ok(url: str, headers: dict[str, str] | None) -> FetchAttempt:
            return FetchAttempt(mode="browser", url=url, html=MOCK_PRODUCT_HTML, status_code=200)

        report = diagnose_transport_modes(
            "https://shop.example",
            modes=["requests", "browser"],
            fetchers={"requests": failed, "browser": ok},
        )

        self.assertIn("transport_errors_are_mode_specific", report.findings)
        self.assertTrue(any("optional fallback" in item for item in report.recommendations))

    @patch("autonomous_crawler.agents.recon.diagnose_transport_modes")
    @patch("autonomous_crawler.agents.recon.fetch_best_html")
    def test_recon_opt_in_records_transport_diagnostics(
        self,
        mock_fetch_best: MagicMock,
        mock_diag: MagicMock,
    ) -> None:
        attempt = FetchAttempt(
            mode="requests",
            url="https://example.com",
            html=MOCK_PRODUCT_HTML,
            status_code=200,
            score=70,
            reasons=["status_ok"],
        )
        mock_fetch_best.return_value = BestFetchResult(
            url="https://example.com",
            html=MOCK_PRODUCT_HTML,
            status_code=200,
            mode="requests",
            score=70,
            attempts=[attempt],
        )
        mock_diag.return_value.to_dict.return_value = {
            "url": "https://example.com",
            "selected_mode": "curl_cffi",
            "transport_sensitive": True,
            "findings": ["status_differs_by_transport"],
            "recommendations": ["Prefer selected transport mode: curl_cffi"],
            "modes": [],
        }

        state = recon_node({
            "target_url": "https://example.com",
            "recon_report": {
                "constraints": {"transport_diagnostics": True},
            },
            "messages": [],
            "error_log": [],
        })

        self.assertEqual(state["status"], "recon_done")
        self.assertTrue(state["recon_report"]["transport_diagnostics"]["transport_sensitive"])
        self.assertTrue(any("Transport diagnostics" in msg for msg in state["messages"]))


# ---------------------------------------------------------------------------
# Native runtime transport evidence
# ---------------------------------------------------------------------------

class NativeTransportEvidenceTests(unittest.TestCase):
    """NativeFetchRuntime transport evidence integrates with diagnostics."""

    def test_native_transport_profile_label(self) -> None:
        """Native httpx transport maps to 'httpx-default' profile label."""
        from autonomous_crawler.tools.transport_diagnostics import _infer_transport_profile
        from autonomous_crawler.tools.fetch_policy import FetchAttempt

        attempt = FetchAttempt(mode="requests", url="https://example.com", html="<p>ok</p>", status_code=200)
        profile = _infer_transport_profile(attempt)
        self.assertEqual(profile, "httpx-default")

    def test_curl_cffi_transport_profile_label(self) -> None:
        """curl_cffi transport maps to 'curl_cffi:chrome124' profile label."""
        from autonomous_crawler.tools.transport_diagnostics import _infer_transport_profile
        from autonomous_crawler.tools.fetch_policy import FetchAttempt

        attempt = FetchAttempt(mode="curl_cffi", url="https://example.com", html="<p>ok</p>", status_code=200)
        profile = _infer_transport_profile(attempt)
        self.assertEqual(profile, "curl_cffi:chrome124")

    def test_header_redaction_in_diagnostics(self) -> None:
        """Sensitive headers are redacted in transport diagnostics output."""
        from autonomous_crawler.tools.transport_diagnostics import _safe_header_summary

        headers = {
            "content-type": "text/html",
            "server": "nginx",
            "set-cookie": "session=abc123; HttpOnly",
            "authorization": "Bearer secret-token",
            "x-api-key": "key-12345",
        }
        safe = _safe_header_summary(headers)

        self.assertEqual(safe["content-type"], "text/html")
        self.assertEqual(safe["server"], "nginx")
        self.assertEqual(safe["set-cookie"], "[redacted]")
        self.assertEqual(safe["authorization"], "[redacted]")
        self.assertEqual(safe["x-api-key"], "[redacted]")

    def test_error_mode_specific_finding(self) -> None:
        """When one transport errors and another succeeds, finding is detected."""
        from autonomous_crawler.tools.transport_diagnostics import _find_transport_differences
        from autonomous_crawler.tools.transport_diagnostics import TransportModeReport

        modes = [
            TransportModeReport(mode="requests", url="https://example.com", error="TLS handshake failed"),
            TransportModeReport(mode="curl_cffi", url="https://example.com", status_code=200, html_chars=100),
        ]
        findings = _find_transport_differences(modes)
        self.assertIn("transport_errors_are_mode_specific", findings)

    def test_native_fetch_engine_result_transport(self) -> None:
        """NativeFetchRuntime engine_result contains transport field."""
        from unittest.mock import MagicMock, patch
        from autonomous_crawler.runtime.native_static import NativeFetchRuntime
        from autonomous_crawler.runtime.models import RuntimeRequest

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.url = "https://example.com"
        mock_resp.headers = {"Content-Type": "text/html", "server": "nginx"}
        mock_resp.cookies = {}
        mock_resp.content = b"<html>ok</html>"
        mock_resp.text = "<html>ok</html>"
        mock_resp.http_version = "HTTP/2"

        with patch("autonomous_crawler.runtime.native_static.httpx.Client") as mock_cls:
            client = mock_cls.return_value.__enter__.return_value
            client.request.return_value = mock_resp
            runtime = NativeFetchRuntime()
            resp = runtime.fetch(RuntimeRequest(url="https://example.com"))

        self.assertEqual(resp.engine_result["transport"], "httpx")
        self.assertEqual(resp.engine_result["http_version"], "HTTP/2")


if __name__ == "__main__":
    unittest.main()
