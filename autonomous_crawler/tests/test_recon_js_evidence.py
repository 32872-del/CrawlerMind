from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from autonomous_crawler.agents.recon import recon_node
from autonomous_crawler.tools.browser_interceptor import InterceptionResult
from autonomous_crawler.tools.fetch_policy import BestFetchResult, FetchAttempt


HTML_WITH_JS = """
<html>
  <body>
    <script>
      const endpoint = "/api/v1/products";
      function signPayload(payload) { return crypto.createHmac("sha256", "k"); }
      fetch(endpoint);
    </script>
    <div class="product-card"><h2>Alpha</h2></div>
  </body>
</html>
"""


class ReconJsEvidenceTests(unittest.TestCase):
    @patch("autonomous_crawler.agents.recon.fetch_best_html")
    def test_recon_attaches_js_evidence(self, mock_fetch) -> None:
        attempt = FetchAttempt(
            mode="requests",
            url="https://example.com/catalog",
            html=HTML_WITH_JS,
            status_code=200,
            response_headers={"content-type": "text/html"},
            http_version="HTTP/2",
        )
        attempt.score = 50
        attempt.reasons = ["status_ok"]
        mock_fetch.return_value = BestFetchResult(
            url="https://example.com/catalog",
            html=HTML_WITH_JS,
            status_code=200,
            mode="requests",
            score=50,
            attempts=[attempt],
        )

        state = recon_node({
            "target_url": "https://example.com/catalog",
            "messages": [],
            "error_log": [],
        })

        evidence = state["recon_report"]["js_evidence"]
        self.assertEqual(state["status"], "recon_done")
        self.assertGreaterEqual(len(evidence["items"]), 1)
        self.assertIn("/api/v1/products", evidence["top_endpoints"])
        self.assertTrue(any("js_evidence=" in msg for msg in state["messages"]))

    @patch("autonomous_crawler.agents.recon.intercept_page_resources")
    @patch("autonomous_crawler.agents.recon.fetch_best_html")
    def test_recon_opt_in_browser_interception_feeds_js_evidence(
        self,
        mock_fetch: MagicMock,
        mock_intercept: MagicMock,
    ) -> None:
        attempt = FetchAttempt(
            mode="requests",
            url="https://example.com/app",
            html="<html><body><script src='/app.js'></script></body></html>",
            status_code=200,
            response_headers={"content-type": "text/html"},
            http_version="HTTP/2",
        )
        attempt.score = 50
        attempt.reasons = ["status_ok"]
        mock_fetch.return_value = BestFetchResult(
            url="https://example.com/app",
            html=attempt.html,
            status_code=200,
            mode="requests",
            score=50,
            attempts=[attempt],
        )
        mock_intercept.return_value = InterceptionResult(
            url="https://example.com/app",
            final_url="https://example.com/app",
            resource_counts={"script": 1},
            js_assets=[{
                "url": "https://example.com/app.js",
                "sha256": "abc123",
                "size_bytes": 120,
                "text_preview": 'function signToken(){ return fetch("/api/private"); }',
            }],
            api_captures=[{
                "url": "https://example.com/api/private",
                "method": "GET",
                "status_code": 200,
                "content_type": "application/json",
            }],
        )

        state = recon_node({
            "target_url": "https://example.com/app",
            "recon_report": {
                "constraints": {
                    "intercept_browser": True,
                    "browser_interception": {"block_resource_types": ["image"]},
                    "wait_until": "networkidle",
                    "render_time_ms": 10,
                },
            },
            "messages": [],
            "error_log": [],
        })

        self.assertEqual(state["status"], "recon_done")
        self.assertEqual(state["recon_report"]["browser_interception"]["status"], "ok")
        self.assertIn("/api/private", state["recon_report"]["js_evidence"]["top_endpoints"])
        self.assertTrue(any("Browser interception" in msg for msg in state["messages"]))
        mock_intercept.assert_called_once()

    @patch("autonomous_crawler.agents.recon.intercept_page_resources")
    @patch("autonomous_crawler.agents.recon.fetch_best_html")
    def test_browser_interception_is_opt_in_only(
        self,
        mock_fetch: MagicMock,
        mock_intercept: MagicMock,
    ) -> None:
        attempt = FetchAttempt(
            mode="requests",
            url="https://example.com/app",
            html="<html></html>",
            status_code=200,
        )
        mock_fetch.return_value = BestFetchResult(
            url="https://example.com/app",
            html=attempt.html,
            status_code=200,
            mode="requests",
            score=10,
            attempts=[attempt],
        )

        state = recon_node({
            "target_url": "https://example.com/app",
            "messages": [],
            "error_log": [],
        })

        self.assertEqual(state["status"], "recon_done")
        self.assertNotIn("browser_interception", state["recon_report"])
        mock_intercept.assert_not_called()


if __name__ == "__main__":
    unittest.main()
