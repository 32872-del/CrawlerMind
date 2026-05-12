from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from autonomous_crawler.agents.recon import recon_node
from autonomous_crawler.tools.fetch_policy import FetchAttempt
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
    def test_recon_opt_in_records_transport_diagnostics(self, mock_diag: MagicMock) -> None:
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


if __name__ == "__main__":
    unittest.main()
