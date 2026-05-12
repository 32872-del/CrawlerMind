"""Tests for WebSocket opt-in integration in Recon.

Proves that:
1. WebSocket observation is OFF by default.
2. It only runs when constraints.observe_websocket=true AND URL is http(s).
3. Results land in recon_report.websocket_observation and websocket_summary.
4. Messages are emitted in the expected format.
"""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from autonomous_crawler.agents.recon import recon_node, _should_observe_websocket
from autonomous_crawler.tools.fetch_policy import BestFetchResult, FetchAttempt
from autonomous_crawler.tools.websocket_observer import (
    WebSocketConnection,
    WebSocketFrame,
    WebSocketObservationResult,
)


# ── helpers ─────────────────────────────────────────────────────────────────

def _simple_html() -> str:
    return "<html><body><div class='item'><h2>X</h2></div></body></html>"


def _mock_fetch_result(url: str = "https://shop.example") -> BestFetchResult:
    attempt = FetchAttempt(
        mode="requests", url=url, html=_simple_html(),
        status_code=200, response_headers={"content-type": "text/html"},
        http_version="HTTP/2",
    )
    attempt.score = 50
    attempt.reasons = ["status_ok"]
    return BestFetchResult(
        url=url, html=_simple_html(), status_code=200,
        mode="requests", score=50, attempts=[attempt],
    )


def _sample_ws_result(url: str = "https://shop.example") -> WebSocketObservationResult:
    frame = WebSocketFrame(
        direction="received", data_type="text",
        preview='{"type":"update"}', byte_length=16,
    )
    conn = WebSocketConnection(
        url="wss://shop.example/ws", is_alive=True,
        frame_count=1, frames=(frame,),
    )
    return WebSocketObservationResult(
        page_url=url, status="ok",
        connections=[conn], total_frames=1, errors=[],
    )


# ── _should_observe_websocket ──────────────────────────────────────────────

class ShouldObserveWebsocketTests(unittest.TestCase):
    def test_false_by_default(self) -> None:
        self.assertFalse(_should_observe_websocket({}, "https://example.com"))

    def test_false_when_constraint_false(self) -> None:
        report = {"constraints": {"observe_websocket": False}}
        self.assertFalse(_should_observe_websocket(report, "https://example.com"))

    def test_true_when_constraint_true_and_https(self) -> None:
        report = {"constraints": {"observe_websocket": True}}
        self.assertTrue(_should_observe_websocket(report, "https://example.com"))

    def test_true_when_constraint_true_and_http(self) -> None:
        report = {"constraints": {"observe_websocket": True}}
        self.assertTrue(_should_observe_websocket(report, "http://example.com"))

    def test_false_for_non_http_scheme(self) -> None:
        report = {"constraints": {"observe_websocket": True}}
        self.assertFalse(_should_observe_websocket(report, "file:///tmp/x.html"))
        self.assertFalse(_should_observe_websocket(report, "ftp://example.com"))

    def test_false_when_constraints_missing(self) -> None:
        self.assertFalse(_should_observe_websocket({"constraints": None}, "https://x"))

    def test_false_when_constraints_key_absent(self) -> None:
        self.assertFalse(_should_observe_websocket({"other": True}, "https://x"))


# ── recon_node integration ─────────────────────────────────────────────────

class ReconWebsocketIntegrationTests(unittest.TestCase):
    @patch("autonomous_crawler.agents.recon.observe_websocket")
    @patch("autonomous_crawler.agents.recon.fetch_best_html")
    def test_websocket_observed_when_enabled(
        self, mock_fetch: MagicMock, mock_ws: MagicMock,
    ) -> None:
        mock_fetch.return_value = _mock_fetch_result()
        mock_ws.return_value = _sample_ws_result()

        state = recon_node({
            "target_url": "https://shop.example",
            "recon_report": {"constraints": {"observe_websocket": True}},
            "messages": [],
            "error_log": [],
        })

        self.assertEqual(state["status"], "recon_done")
        report = state["recon_report"]

        # websocket_observation stored
        self.assertIn("websocket_observation", report)
        self.assertEqual(report["websocket_observation"]["status"], "ok")
        self.assertEqual(len(report["websocket_observation"]["connections"]), 1)

        # websocket_summary stored
        self.assertIn("websocket_summary", report)
        self.assertEqual(report["websocket_summary"]["connection_count"], 1)
        self.assertEqual(report["websocket_summary"]["total_frames"], 1)

        # message emitted
        ws_messages = [m for m in state["messages"] if "WebSocket observation" in m]
        self.assertEqual(len(ws_messages), 1)
        self.assertIn("status=ok", ws_messages[0])
        self.assertIn("connections=1", ws_messages[0])
        self.assertIn("frames=1", ws_messages[0])

    @patch("autonomous_crawler.agents.recon.observe_websocket")
    @patch("autonomous_crawler.agents.recon.fetch_best_html")
    def test_websocket_not_observed_by_default(
        self, mock_fetch: MagicMock, mock_ws: MagicMock,
    ) -> None:
        mock_fetch.return_value = _mock_fetch_result()

        state = recon_node({
            "target_url": "https://shop.example",
            "recon_report": {},
            "messages": [],
            "error_log": [],
        })

        self.assertEqual(state["status"], "recon_done")
        report = state["recon_report"]

        # No websocket keys
        self.assertNotIn("websocket_observation", report)
        self.assertNotIn("websocket_summary", report)

        # observe_websocket never called
        mock_ws.assert_not_called()

        # No WS message
        ws_messages = [m for m in state["messages"] if "WebSocket" in m]
        self.assertEqual(len(ws_messages), 0)

    @patch("autonomous_crawler.agents.recon.observe_websocket")
    @patch("autonomous_crawler.agents.recon.fetch_best_html")
    def test_websocket_not_observed_when_constraint_false(
        self, mock_fetch: MagicMock, mock_ws: MagicMock,
    ) -> None:
        mock_fetch.return_value = _mock_fetch_result()

        state = recon_node({
            "target_url": "https://shop.example",
            "recon_report": {"constraints": {"observe_websocket": False}},
            "messages": [],
            "error_log": [],
        })

        self.assertNotIn("websocket_observation", state["recon_report"])
        mock_ws.assert_not_called()

    @patch("autonomous_crawler.agents.recon.observe_websocket")
    @patch("autonomous_crawler.agents.recon.fetch_best_html")
    def test_websocket_not_observed_for_non_http(
        self, mock_fetch: MagicMock, mock_ws: MagicMock,
    ) -> None:
        mock_fetch.return_value = _mock_fetch_result(url="ftp://files.example/data")

        state = recon_node({
            "target_url": "ftp://files.example/data",
            "recon_report": {"constraints": {"observe_websocket": True}},
            "messages": [],
            "error_log": [],
        })

        mock_ws.assert_not_called()
        self.assertNotIn("websocket_observation", state["recon_report"])

    @patch("autonomous_crawler.agents.recon.observe_websocket")
    @patch("autonomous_crawler.agents.recon.fetch_best_html")
    def test_websocket_failed_result_still_stored(
        self, mock_fetch: MagicMock, mock_ws: MagicMock,
    ) -> None:
        mock_fetch.return_value = _mock_fetch_result()
        mock_ws.return_value = WebSocketObservationResult(
            page_url="https://shop.example",
            status="failed",
            error="playwright is not installed",
        )

        state = recon_node({
            "target_url": "https://shop.example",
            "recon_report": {"constraints": {"observe_websocket": True}},
            "messages": [],
            "error_log": [],
        })

        report = state["recon_report"]
        self.assertIn("websocket_observation", report)
        self.assertEqual(report["websocket_observation"]["status"], "failed")
        self.assertIn("websocket_summary", report)

        ws_messages = [m for m in state["messages"] if "WebSocket" in m]
        self.assertIn("status=failed", ws_messages[0])

    @patch("autonomous_crawler.agents.recon.observe_websocket")
    @patch("autonomous_crawler.agents.recon.fetch_best_html")
    def test_websocket_multiple_connections_summary(
        self, mock_fetch: MagicMock, mock_ws: MagicMock,
    ) -> None:
        mock_fetch.return_value = _mock_fetch_result()
        f1 = WebSocketFrame(direction="sent", data_type="text", preview="ping", byte_length=4)
        f2 = WebSocketFrame(direction="received", data_type="text", preview="pong", byte_length=4)
        f3 = WebSocketFrame(direction="received", data_type="binary", preview="\\x00\\x01", byte_length=2)
        c1 = WebSocketConnection(url="wss://a.example/ws", is_alive=True, frame_count=2, frames=(f1, f2))
        c2 = WebSocketConnection(url="wss://b.example/ws", is_alive=False, frame_count=1, frames=(f3,))
        mock_ws.return_value = WebSocketObservationResult(
            page_url="https://shop.example", status="ok",
            connections=[c1, c2], total_frames=3,
        )

        state = recon_node({
            "target_url": "https://shop.example",
            "recon_report": {"constraints": {"observe_websocket": True}},
            "messages": [],
            "error_log": [],
        })

        summary = state["recon_report"]["websocket_summary"]
        self.assertEqual(summary["connection_count"], 2)
        self.assertEqual(summary["total_frames"], 3)
        self.assertEqual(summary["sent_frames"], 1)
        self.assertEqual(summary["received_frames"], 2)
        self.assertEqual(summary["text_frames"], 2)
        self.assertEqual(summary["binary_frames"], 1)
        self.assertEqual(len(summary["ws_urls"]), 2)

        ws_messages = [m for m in state["messages"] if "WebSocket" in m]
        self.assertIn("connections=2", ws_messages[0])
        self.assertIn("frames=3", ws_messages[0])

    @patch("autonomous_crawler.agents.recon.observe_websocket")
    @patch("autonomous_crawler.agents.recon.fetch_best_html")
    def test_websocket_with_other_constraints_preserved(
        self, mock_fetch: MagicMock, mock_ws: MagicMock,
    ) -> None:
        """WebSocket opt-in does not interfere with other constraint flags."""
        mock_fetch.return_value = _mock_fetch_result()
        mock_ws.return_value = _sample_ws_result()

        state = recon_node({
            "target_url": "https://shop.example",
            "recon_report": {
                "constraints": {
                    "observe_websocket": True,
                    "observe_network": False,
                    "intercept_browser": False,
                },
            },
            "messages": [],
            "error_log": [],
        })

        report = state["recon_report"]
        self.assertIn("websocket_observation", report)
        # Other observations should NOT be present
        self.assertNotIn("network_observation", report)
        self.assertNotIn("browser_interception", report)


if __name__ == "__main__":
    unittest.main()
