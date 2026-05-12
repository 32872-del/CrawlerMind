"""Tests for the WebSocket Observation MVP.

All tests use mocked Playwright events; no external network calls.
"""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from autonomous_crawler.tools.websocket_observer import (
    DEFAULT_MAX_CONNECTIONS,
    DEFAULT_MAX_FRAME_PREVIEW,
    DEFAULT_MAX_FRAMES,
    FRAME_DIRECTION_RECEIVED,
    FRAME_DIRECTION_SENT,
    WebSocketConnection,
    WebSocketFrame,
    WebSocketObservationResult,
    _WebSocketCollector,
    build_ws_summary,
    normalize_frame_payload,
    observe_websocket,
    redact_sensitive_preview,
    truncate_preview,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_mock_ws(url: str = "wss://example.com/ws"):
    """Create a mock WebSocket object that mimics Playwright's WebSocket."""
    ws = MagicMock()
    ws.url = url
    _listeners: dict[str, list] = {"framesent": [], "framereceived": [], "close": []}

    def on(event: str, callback):
        if event in _listeners:
            _listeners[event].append(callback)

    ws.on = MagicMock(side_effect=on)
    ws._listeners = _listeners
    return ws


def _fire_frame(ws: MagicMock, direction: str, payload):
    """Fire a frame event on a mock WebSocket."""
    event = "framesent" if direction == "sent" else "framereceived"
    for cb in ws._listeners.get(event, []):
        cb(payload)


def _fire_close(ws: MagicMock):
    """Fire close event on a mock WebSocket."""
    for cb in ws._listeners.get("close", []):
        cb()


def _make_mock_page(websockets=None):
    """Create a mock Page that fires websocket events."""
    page = MagicMock()
    websockets = websockets or []
    _ws_callbacks = []

    def on_page(event: str, callback):
        if event == "websocket":
            _ws_callbacks.append(callback)

    page.on = MagicMock(side_effect=on_page)
    page._ws_callbacks = _ws_callbacks
    page._websockets = websockets
    return page


def _make_mock_playwright(websockets=None, goto_error=None):
    """Create a mock sync_playwright context manager.

    Args:
        websockets: List of mock WebSocket objects to fire.
        goto_error: If set, page.goto raises this exception.

    Returns:
        (context_manager, page) where context_manager is a MagicMock whose
        __enter__ yields the mock Playwright object.
    """
    page = _make_mock_page(websockets)
    if goto_error is not None:
        page.goto = MagicMock(side_effect=goto_error)

    pw = MagicMock()
    browser = MagicMock()
    browser.new_page.return_value = page
    pw.chromium.launch.return_value = browser

    # sync_playwright() returns a context manager whose __enter__ yields pw
    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=pw)
    cm.__exit__ = MagicMock(return_value=False)
    return cm, page


# ---------------------------------------------------------------------------
# normalize_frame_payload
# ---------------------------------------------------------------------------

class TestNormalizeFramePayload(unittest.TestCase):

    def test_text_payload(self):
        preview, data_type, byte_length = normalize_frame_payload("hello world")
        self.assertEqual(data_type, "text")
        self.assertEqual(preview, "hello world")
        self.assertEqual(byte_length, 11)

    def test_bytes_payload(self):
        preview, data_type, byte_length = normalize_frame_payload(b"\x00\x01\x02")
        self.assertEqual(data_type, "binary")
        self.assertEqual(byte_length, 3)

    def test_bytes_utf8_decode(self):
        preview, data_type, byte_length = normalize_frame_payload("中文".encode("utf-8"))
        self.assertEqual(data_type, "binary")
        self.assertIn("中文", preview)

    def test_truncation(self):
        long_text = "x" * 1000
        preview, data_type, byte_length = normalize_frame_payload(long_text, max_preview=100)
        self.assertEqual(data_type, "text")
        self.assertTrue(preview.endswith("...[truncated]"))
        self.assertLessEqual(len(preview), 100 + len("...[truncated]"))
        self.assertEqual(byte_length, 1000)

    def test_empty_text(self):
        preview, data_type, byte_length = normalize_frame_payload("")
        self.assertEqual(data_type, "text")
        self.assertEqual(preview, "")
        self.assertEqual(byte_length, 0)

    def test_empty_bytes(self):
        preview, data_type, byte_length = normalize_frame_payload(b"")
        self.assertEqual(data_type, "binary")
        self.assertEqual(preview, "")
        self.assertEqual(byte_length, 0)

    def test_non_str_bytes_fallback(self):
        preview, data_type, byte_length = normalize_frame_payload(12345)
        self.assertEqual(data_type, "text")
        self.assertEqual(preview, "12345")

    def test_json_text(self):
        import json
        payload = json.dumps({"type": "subscribe", "channel": "trades"})
        preview, data_type, byte_length = normalize_frame_payload(payload)
        self.assertEqual(data_type, "text")
        self.assertIn("subscribe", preview)


# ---------------------------------------------------------------------------
# truncate_preview
# ---------------------------------------------------------------------------

class TestTruncatePreview(unittest.TestCase):

    def test_short_text_unchanged(self):
        self.assertEqual(truncate_preview("hello", 10), "hello")

    def test_exact_length_unchanged(self):
        self.assertEqual(truncate_preview("hello", 5), "hello")

    def test_long_text_truncated(self):
        result = truncate_preview("hello world", 5)
        self.assertEqual(result, "hello...[truncated]")

    def test_empty_text(self):
        self.assertEqual(truncate_preview("", 10), "")

    def test_zero_max(self):
        result = truncate_preview("hello", 0)
        self.assertEqual(result, "...[truncated]")


# ---------------------------------------------------------------------------
# redact_sensitive_preview
# ---------------------------------------------------------------------------

class TestRedactSensitivePreview(unittest.TestCase):

    def test_hex_token_redacted(self):
        hex_token = "a" * 64
        result = redact_sensitive_preview(f"token={hex_token}")
        self.assertIn("[redacted_hex]", result)
        self.assertNotIn(hex_token, result)

    def test_short_hex_not_redacted(self):
        result = redact_sensitive_preview("code=abcd1234")
        self.assertNotIn("[redacted_hex]", result)

    def test_bearer_token_redacted(self):
        result = redact_sensitive_preview("Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9_longtoken")
        self.assertIn("[redacted_token]", result)
        self.assertNotIn("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9_longtoken", result)

    def test_api_key_redacted(self):
        result = redact_sensitive_preview("api_key=sk_live_abcdefghijklmnop")
        self.assertIn("[redacted]", result)
        self.assertNotIn("sk_live_abcdefghijklmnop", result)

    def test_session_id_redacted(self):
        result = redact_sensitive_preview("session_id=sess_very_long_session_id_value_here_12345")
        self.assertIn("[redacted]", result)
        self.assertNotIn("sess_very_long_session_id_value_here_12345", result)

    def test_normal_text_unchanged(self):
        result = redact_sensitive_preview("hello world, no secrets here")
        self.assertEqual(result, "hello world, no secrets here")

    def test_empty_text(self):
        self.assertEqual(redact_sensitive_preview(""), "")


# ---------------------------------------------------------------------------
# Data model construction
# ---------------------------------------------------------------------------

class TestWebSocketFrame(unittest.TestCase):

    def test_text_frame(self):
        f = WebSocketFrame(
            direction=FRAME_DIRECTION_SENT,
            data_type="text",
            preview='{"type":"ping"}',
            byte_length=15,
        )
        self.assertEqual(f.direction, "sent")
        self.assertEqual(f.data_type, "text")
        self.assertEqual(f.byte_length, 15)

    def test_binary_frame(self):
        f = WebSocketFrame(
            direction=FRAME_DIRECTION_RECEIVED,
            data_type="binary",
            preview="\\x00\\x01\\x02",
            byte_length=3,
        )
        self.assertEqual(f.direction, "received")
        self.assertEqual(f.data_type, "binary")

    def test_frozen(self):
        f = WebSocketFrame(direction="sent", data_type="text", preview="x", byte_length=1)
        with self.assertRaises(AttributeError):
            f.direction = "received"  # type: ignore[misc]


class TestWebSocketConnection(unittest.TestCase):

    def test_basic_connection(self):
        frames = (
            WebSocketFrame(direction="sent", data_type="text", preview="ping", byte_length=4),
            WebSocketFrame(direction="received", data_type="text", preview="pong", byte_length=4),
        )
        conn = WebSocketConnection(
            url="wss://example.com/ws",
            is_alive=True,
            frame_count=2,
            frames=frames,
        )
        self.assertEqual(conn.url, "wss://example.com/ws")
        self.assertTrue(conn.is_alive)
        self.assertEqual(conn.frame_count, 2)
        self.assertEqual(len(conn.frames), 2)

    def test_error_connection(self):
        conn = WebSocketConnection(
            url="wss://bad.example.com/ws",
            is_alive=False,
            error="connection refused",
        )
        self.assertFalse(conn.is_alive)
        self.assertEqual(conn.error, "connection refused")


class TestWebSocketObservationResult(unittest.TestCase):

    def test_to_dict(self):
        conn = WebSocketConnection(
            url="wss://example.com/ws",
            is_alive=True,
            frame_count=1,
            frames=(WebSocketFrame(direction="sent", data_type="text", preview="hi", byte_length=2),),
        )
        result = WebSocketObservationResult(
            page_url="https://example.com",
            connections=[conn],
            total_frames=1,
        )
        d = result.to_dict()
        self.assertEqual(d["page_url"], "https://example.com")
        self.assertEqual(d["status"], "ok")
        self.assertEqual(len(d["connections"]), 1)
        self.assertEqual(d["connections"][0]["url"], "wss://example.com/ws")
        self.assertEqual(d["connections"][0]["frames"][0]["direction"], "sent")
        self.assertEqual(d["total_frames"], 1)

    def test_empty_result(self):
        result = WebSocketObservationResult()
        d = result.to_dict()
        self.assertEqual(d["connections"], [])
        self.assertEqual(d["total_frames"], 0)


# ---------------------------------------------------------------------------
# _WebSocketCollector (mocked Playwright events)
# ---------------------------------------------------------------------------

class TestWebSocketCollector(unittest.TestCase):

    def test_single_connection_text_frames(self):
        collector = _WebSocketCollector(redact=False)
        ws = _make_mock_ws("wss://example.com/ws")
        collector.on_websocket(ws)

        _fire_frame(ws, "sent", '{"type":"subscribe","channel":"trades"}')
        _fire_frame(ws, "received", '{"type":"tick","price":42.5}')

        connections = collector.build_connections()
        self.assertEqual(len(connections), 1)
        self.assertEqual(connections[0].url, "wss://example.com/ws")
        self.assertEqual(connections[0].frame_count, 2)
        self.assertEqual(connections[0].frames[0].direction, "sent")
        self.assertEqual(connections[0].frames[0].data_type, "text")
        self.assertEqual(connections[0].frames[1].direction, "received")
        self.assertIn("tick", connections[0].frames[1].preview)
        self.assertEqual(collector.total_frames, 2)

    def test_binary_frame(self):
        collector = _WebSocketCollector(redact=False)
        ws = _make_mock_ws("wss://stream.example.com/binary")
        collector.on_websocket(ws)

        _fire_frame(ws, "received", b"\x00\x01\x02\x03")
        connections = collector.build_connections()
        self.assertEqual(connections[0].frames[0].data_type, "binary")
        self.assertEqual(connections[0].frames[0].byte_length, 4)

    def test_multiple_connections(self):
        collector = _WebSocketCollector(redact=False)
        ws1 = _make_mock_ws("wss://example.com/ws1")
        ws2 = _make_mock_ws("wss://example.com/ws2")
        collector.on_websocket(ws1)
        collector.on_websocket(ws2)

        _fire_frame(ws1, "sent", "hello")
        _fire_frame(ws2, "received", "world")

        connections = collector.build_connections()
        self.assertEqual(len(connections), 2)
        self.assertEqual(connections[0].frame_count, 1)
        self.assertEqual(connections[1].frame_count, 1)

    def test_close_event(self):
        collector = _WebSocketCollector(redact=False)
        ws = _make_mock_ws("wss://example.com/ws")
        collector.on_websocket(ws)
        self.assertTrue(collector.build_connections()[0].is_alive)

        _fire_close(ws)
        connections = collector.build_connections()
        self.assertFalse(connections[0].is_alive)

    def test_max_frames_limit(self):
        collector = _WebSocketCollector(max_frames=3, redact=False)
        ws = _make_mock_ws("wss://example.com/ws")
        collector.on_websocket(ws)

        for i in range(10):
            _fire_frame(ws, "sent", f"frame{i}")

        self.assertEqual(collector.total_frames, 3)
        connections = collector.build_connections()
        self.assertEqual(connections[0].frame_count, 3)

    def test_max_connections_limit(self):
        collector = _WebSocketCollector(max_connections=2, redact=False)
        ws1 = _make_mock_ws("wss://a.com/ws")
        ws2 = _make_mock_ws("wss://b.com/ws")
        ws3 = _make_mock_ws("wss://c.com/ws")
        collector.on_websocket(ws1)
        collector.on_websocket(ws2)
        collector.on_websocket(ws3)  # should be ignored

        connections = collector.build_connections()
        self.assertEqual(len(connections), 2)

    def test_redaction_enabled(self):
        collector = _WebSocketCollector(redact=True)
        ws = _make_mock_ws("wss://example.com/ws")
        collector.on_websocket(ws)

        hex_token = "a" * 64
        _fire_frame(ws, "sent", f"api_key={hex_token}")

        connections = collector.build_connections()
        self.assertIn("[redacted_hex]", connections[0].frames[0].preview)
        self.assertNotIn(hex_token, connections[0].frames[0].preview)

    def test_redaction_disabled(self):
        collector = _WebSocketCollector(redact=False)
        ws = _make_mock_ws("wss://example.com/ws")
        collector.on_websocket(ws)

        hex_token = "a" * 64
        _fire_frame(ws, "sent", f"api_key={hex_token}")

        connections = collector.build_connections()
        self.assertIn(hex_token, connections[0].frames[0].preview)

    def test_frame_preview_truncation(self):
        collector = _WebSocketCollector(max_frame_preview=20, redact=False)
        ws = _make_mock_ws("wss://example.com/ws")
        collector.on_websocket(ws)

        long_msg = "x" * 1000
        _fire_frame(ws, "received", long_msg)

        connections = collector.build_connections()
        preview = connections[0].frames[0].preview
        self.assertTrue(preview.endswith("...[truncated]"))
        self.assertLessEqual(len(preview), 20 + len("...[truncated]"))

    def test_empty_connections(self):
        collector = _WebSocketCollector()
        connections = collector.build_connections()
        self.assertEqual(connections, [])
        self.assertEqual(collector.total_frames, 0)

    def test_event_bind_error(self):
        collector = _WebSocketCollector(redact=False)
        ws = MagicMock()
        ws.url = "wss://bad.example.com/ws"
        ws.on = MagicMock(side_effect=Exception("bind failed"))

        collector.on_websocket(ws)
        self.assertEqual(len(collector.errors), 1)
        self.assertIn("bind failed", collector.errors[0])


# ---------------------------------------------------------------------------
# observe_websocket (mocked sync_playwright)
# ---------------------------------------------------------------------------

def _make_mock_page_with_ws(websockets, ws_frames=None):
    """Create a mock page that fires ws callbacks and frame events.

    When page.on("websocket", cb) is called, each mock ws in ``websockets``
    is passed to cb, and its events are fired with payloads from
    ``ws_frames`` (a dict mapping ws index to list of (direction, payload)).
    """
    ws_frames = ws_frames or {}
    page = MagicMock()
    page.url = "https://example.com"
    registered_ws_cbs: list = []

    def on_page(event: str, callback):
        if event == "websocket":
            registered_ws_cbs.append(callback)

    page.on = MagicMock(side_effect=on_page)

    # Store trigger function for use after goto
    def trigger_ws_events():
        for idx, ws in enumerate(websockets):
            for cb in registered_ws_cbs:
                cb(ws)
            for direction, payload in ws_frames.get(idx, []):
                _fire_frame(ws, direction, payload)

    page._trigger_ws_events = trigger_ws_events
    return page


class TestObserveWebsocket(unittest.TestCase):

    @patch("autonomous_crawler.tools.websocket_observer.sync_playwright")
    def test_no_websockets(self, mock_pw_cls):
        cm, page = _make_mock_playwright([])
        mock_pw_cls.return_value = cm

        result = observe_websocket("https://example.com", wait_ms=0)
        self.assertEqual(result.status, "ok")
        self.assertEqual(result.connections, [])
        self.assertEqual(result.total_frames, 0)

    @patch("autonomous_crawler.tools.websocket_observer.sync_playwright")
    def test_websocket_with_frames(self, mock_pw_cls):
        ws = _make_mock_ws("wss://example.com/ws")
        page = _make_mock_page_with_ws(
            [ws],
            {0: [("sent", '{"subscribe":"trades"}'), ("received", '{"tick":42}')]},
        )

        # Build the full mock chain (browser.new_page, not context.new_page)
        pw = MagicMock()
        browser = MagicMock()
        browser.new_page.return_value = page
        pw.chromium.launch.return_value = browser

        cm = MagicMock()
        cm.__enter__ = MagicMock(return_value=pw)
        cm.__exit__ = MagicMock(return_value=False)
        mock_pw_cls.return_value = cm

        # Patch goto to trigger ws events during the wait
        original_goto = page.goto

        def goto_with_ws(*args, **kwargs):
            result = original_goto(*args, **kwargs)
            page._trigger_ws_events()
            return result

        page.goto = goto_with_ws

        result = observe_websocket("https://example.com", wait_ms=0, redact=False)
        self.assertEqual(result.status, "ok")
        self.assertEqual(len(result.connections), 1)
        self.assertEqual(result.connections[0].url, "wss://example.com/ws")
        self.assertEqual(result.total_frames, 2)

    @patch("autonomous_crawler.tools.websocket_observer.sync_playwright")
    def test_playwright_not_installed(self, mock_pw_cls):
        import autonomous_crawler.tools.websocket_observer as mod
        original = mod.sync_playwright
        mod.sync_playwright = None
        try:
            result = observe_websocket("https://example.com")
            self.assertEqual(result.status, "failed")
            self.assertIn("not installed", result.error)
        finally:
            mod.sync_playwright = original

    @patch("autonomous_crawler.tools.websocket_observer.sync_playwright")
    def test_navigation_error(self, mock_pw_cls):
        cm, page = _make_mock_playwright(
            goto_error=Exception("net::ERR_CONNECTION_REFUSED"),
        )
        mock_pw_cls.return_value = cm

        result = observe_websocket("https://bad.example.com", wait_ms=0)
        self.assertEqual(result.status, "failed")
        self.assertIn("ERR_CONNECTION_REFUSED", result.error)

    @patch("autonomous_crawler.tools.websocket_observer.sync_playwright")
    def test_multiple_ws_connections(self, mock_pw_cls):
        ws1 = _make_mock_ws("wss://a.com/ws")
        ws2 = _make_mock_ws("wss://b.com/ws")
        page = _make_mock_page_with_ws(
            [ws1, ws2],
            {0: [("sent", "hello")], 1: [("received", "world")]},
        )

        pw = MagicMock()
        browser = MagicMock()
        browser.new_page.return_value = page
        pw.chromium.launch.return_value = browser

        cm = MagicMock()
        cm.__enter__ = MagicMock(return_value=pw)
        cm.__exit__ = MagicMock(return_value=False)
        mock_pw_cls.return_value = cm

        original_goto = page.goto

        def goto_with_ws(*args, **kwargs):
            result = original_goto(*args, **kwargs)
            page._trigger_ws_events()
            return result

        page.goto = goto_with_ws

        result = observe_websocket("https://example.com", wait_ms=0, redact=False)
        self.assertEqual(len(result.connections), 2)
        self.assertEqual(result.total_frames, 2)

    @patch("autonomous_crawler.tools.websocket_observer.sync_playwright")
    def test_to_dict_serialization(self, mock_pw_cls):
        ws = _make_mock_ws("wss://example.com/ws")
        page = _make_mock_page_with_ws(
            [ws],
            {0: [("sent", "ping")]},
        )

        pw = MagicMock()
        browser = MagicMock()
        browser.new_page.return_value = page
        pw.chromium.launch.return_value = browser

        cm = MagicMock()
        cm.__enter__ = MagicMock(return_value=pw)
        cm.__exit__ = MagicMock(return_value=False)
        mock_pw_cls.return_value = cm

        original_goto = page.goto

        def goto_with_ws(*args, **kwargs):
            result = original_goto(*args, **kwargs)
            page._trigger_ws_events()
            return result

        page.goto = goto_with_ws

        result = observe_websocket("https://example.com", wait_ms=0, redact=False)
        d = result.to_dict()
        self.assertIn("page_url", d)
        self.assertIn("connections", d)
        self.assertEqual(d["connections"][0]["url"], "wss://example.com/ws")
        self.assertEqual(d["connections"][0]["frames"][0]["direction"], "sent")


# ---------------------------------------------------------------------------
# build_ws_summary
# ---------------------------------------------------------------------------

class TestBuildWsSummary(unittest.TestCase):

    def test_basic_summary(self):
        frames = (
            WebSocketFrame(direction="sent", data_type="text", preview="ping", byte_length=4),
            WebSocketFrame(direction="received", data_type="text", preview="pong", byte_length=4),
            WebSocketFrame(direction="received", data_type="binary", preview="\\x00", byte_length=1),
        )
        conn = WebSocketConnection(
            url="wss://example.com/ws",
            is_alive=True,
            frame_count=3,
            frames=frames,
        )
        result = WebSocketObservationResult(
            page_url="https://example.com",
            connections=[conn],
            total_frames=3,
        )
        summary = build_ws_summary(result)
        self.assertEqual(summary["connection_count"], 1)
        self.assertEqual(summary["ws_urls"], ["wss://example.com/ws"])
        self.assertEqual(summary["total_frames"], 3)
        self.assertEqual(summary["sent_frames"], 1)
        self.assertEqual(summary["received_frames"], 2)
        self.assertEqual(summary["text_frames"], 2)
        self.assertEqual(summary["binary_frames"], 1)
        self.assertEqual(summary["total_bytes"], 9)

    def test_empty_summary(self):
        result = WebSocketObservationResult()
        summary = build_ws_summary(result)
        self.assertEqual(summary["connection_count"], 0)
        self.assertEqual(summary["total_frames"], 0)
        self.assertEqual(summary["total_bytes"], 0)

    def test_multiple_connections_summary(self):
        conn1 = WebSocketConnection(
            url="wss://a.com/ws",
            frame_count=1,
            frames=(WebSocketFrame(direction="sent", data_type="text", preview="a", byte_length=1),),
        )
        conn2 = WebSocketConnection(
            url="wss://b.com/ws",
            frame_count=1,
            frames=(WebSocketFrame(direction="received", data_type="text", preview="b", byte_length=1),),
        )
        result = WebSocketObservationResult(
            connections=[conn1, conn2],
            total_frames=2,
        )
        summary = build_ws_summary(result)
        self.assertEqual(summary["connection_count"], 2)
        self.assertEqual(summary["sent_frames"], 1)
        self.assertEqual(summary["received_frames"], 1)

    def test_error_count_in_summary(self):
        result = WebSocketObservationResult(
            errors=["ws_event_bind_error:wss://x.com:fail"],
        )
        summary = build_ws_summary(result)
        self.assertEqual(summary["error_count"], 1)


if __name__ == "__main__":
    unittest.main()
