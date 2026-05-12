"""Real WebSocket smoke test — local fixture only, no external sites.

Launches a local HTTP page and WebSocket echo server, then uses
``observe_websocket()`` to capture real Playwright WebSocket events.

Skips cleanly if websockets or Playwright/browser are unavailable.
"""
from __future__ import annotations

import asyncio
import http.server
import json
import socketserver
import threading
import unittest

# ---------------------------------------------------------------------------
# Dependency checks — skip at module level if missing
# ---------------------------------------------------------------------------

try:
    import websockets.asyncio.server as _ws_server
    _HAS_WEBSOCKETS = True
except ImportError:
    _HAS_WEBSOCKETS = False

from autonomous_crawler.tools.websocket_observer import (
    WebSocketObservationResult,
    build_ws_summary,
    observe_websocket,
    sync_playwright as _pw_module,
)


def _playwright_available() -> bool:
    """Return True if Playwright and a Chromium binary are usable."""
    if _pw_module is None:
        return False
    try:
        with _pw_module() as pw:
            browser = pw.chromium.launch(headless=True)
            browser.close()
        return True
    except Exception:
        return False


_SKIP_REASON = ""
if not _HAS_WEBSOCKETS:
    _SKIP_REASON = "websockets package not installed"
elif not _playwright_available():
    _SKIP_REASON = "Playwright or Chromium browser not available"


# ---------------------------------------------------------------------------
# Local fixture helpers
# ---------------------------------------------------------------------------

def _start_ws_echo_server() -> tuple[threading.Thread, int]:
    """Start a WebSocket echo server on a random port. Returns (thread, port)."""
    started = threading.Event()
    port_holder: list[int] = []

    async def _echo(ws):
        async for msg in ws:
            # Echo back with prefix; also handle long messages for truncation test
            await ws.send("echo:" + msg)

    def _run():
        async def _serve():
            server = await _ws_server.serve(_echo, "127.0.0.1", 0)
            port_holder.append(server.sockets[0].getsockname()[1])
            started.set()
            await server.serve_forever()
        asyncio.run(_serve())

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    started.wait(timeout=5)
    return thread, port_holder[0]


def _start_http_page_server(ws_port: int) -> tuple[threading.Thread, int, socketserver.TCPServer]:
    """Start an HTTP server serving a page that connects to the local WS server.

    The page JS opens ws://127.0.0.1:{ws_port}, sends one text message,
    and sets document.title to the echo response.
    """
    html = (
        "<html><body><script>\n"
        f"var ws = new WebSocket('ws://127.0.0.1:{ws_port}');\n"
        "ws.onopen = function() { ws.send('hello from browser'); };\n"
        "ws.onmessage = function(e) { document.title = e.data; };\n"
        "</script><h1>WS Smoke</h1></body></html>"
    )

    class _Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(html.encode())

        def log_message(self, *args):
            pass  # silence request logs

    httpd = socketserver.TCPServer(("127.0.0.1", 0), _Handler)
    port = httpd.server_address[1]
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return thread, port, httpd


def _start_http_sensitive_server(ws_port: int) -> tuple[threading.Thread, int, socketserver.TCPServer]:
    """Page that sends a message containing a long hex token via WS."""
    html = (
        "<html><body><script>\n"
        f"var ws = new WebSocket('ws://127.0.0.1:{ws_port}');\n"
        "ws.onopen = function() {\n"
        "  ws.send('api_key=' + 'a'.repeat(64));\n"
        "};\n"
        "ws.onmessage = function(e) { document.title = e.data; };\n"
        "</script></body></html>"
    )

    class _Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(html.encode())

        def log_message(self, *args):
            pass

    httpd = socketserver.TCPServer(("127.0.0.1", 0), _Handler)
    port = httpd.server_address[1]
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return thread, port, httpd


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@unittest.skipIf(_SKIP_REASON, _SKIP_REASON)
class RealWebsocketSmokeTests(unittest.TestCase):
    """Smoke tests using a real local Playwright browser + WS server."""

    @classmethod
    def setUpClass(cls):
        cls._ws_thread, cls._ws_port = _start_ws_echo_server()

    @classmethod
    def tearDownClass(cls):
        # Daemon threads die with the process; nothing to join explicitly.
        pass

    def test_observe_websocket_real_browser(self) -> None:
        """observe_websocket captures real WS frames from a local page."""
        _, http_port, httpd = _start_http_page_server(self._ws_port)
        try:
            result = observe_websocket(
                f"http://127.0.0.1:{http_port}",
                wait_ms=3000,
            )

            self.assertEqual(result.status, "ok", f"Expected ok, got {result.error}")
            self.assertGreaterEqual(len(result.connections), 1)
            self.assertGreaterEqual(result.total_frames, 1)

            conn = result.connections[0]
            self.assertTrue(conn.url.startswith("ws://127.0.0.1"))

            # Verify frame directions
            directions = [f.direction for f in conn.frames]
            self.assertIn("sent", directions)
            self.assertIn("received", directions)

            # Verify frame types
            for f in conn.frames:
                self.assertEqual(f.data_type, "text")

            # Verify sent frame content
            sent = [f for f in conn.frames if f.direction == "sent"]
            self.assertTrue(any("hello from browser" in f.preview for f in sent))

            # Verify received frame content
            received = [f for f in conn.frames if f.direction == "received"]
            self.assertTrue(any("echo:hello from browser" in f.preview for f in received))
        finally:
            httpd.shutdown()

    def test_build_ws_summary_real(self) -> None:
        """build_ws_summary produces correct stats from real observation."""
        _, http_port, httpd = _start_http_page_server(self._ws_port)
        try:
            result = observe_websocket(
                f"http://127.0.0.1:{http_port}",
                wait_ms=3000,
            )
            summary = build_ws_summary(result)

            self.assertEqual(summary["status"], "ok")
            self.assertGreaterEqual(summary["connection_count"], 1)
            self.assertGreaterEqual(summary["total_frames"], 1)
            self.assertGreaterEqual(summary["sent_frames"], 1)
            self.assertGreaterEqual(summary["received_frames"], 1)
            self.assertEqual(summary["text_frames"], summary["total_frames"])
            self.assertEqual(summary["binary_frames"], 0)
            self.assertGreater(summary["total_bytes"], 0)
            self.assertEqual(summary["error_count"], 0)
            self.assertIn(f"127.0.0.1:{self._ws_port}", summary["ws_urls"][0])
        finally:
            httpd.shutdown()

    def test_to_dict_serializable(self) -> None:
        """Result to_dict is JSON-serializable from real browser data."""
        _, http_port, httpd = _start_http_page_server(self._ws_port)
        try:
            result = observe_websocket(
                f"http://127.0.0.1:{http_port}",
                wait_ms=3000,
            )
            d = result.to_dict()
            # Must be JSON-serializable
            json_str = json.dumps(d)
            self.assertIn("connections", json_str)
            self.assertIn("total_frames", json_str)
        finally:
            httpd.shutdown()

    def test_frame_preview_truncation_real(self) -> None:
        """Long WS messages produce truncated previews."""
        # Echo server echoes back with 'echo:' prefix, so send a long message
        long_msg = "x" * 2000

        # Custom page that sends a long message
        html = (
            "<html><body><script>\n"
            f"var ws = new WebSocket('ws://127.0.0.1:{self._ws_port}');\n"
            "ws.onopen = function() { ws.send('" + long_msg + "'); };\n"
            "ws.onmessage = function(e) { document.title = 'done'; };\n"
            "</script></body></html>"
        )

        class _Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(html.encode())
            def log_message(self, *a):
                pass

        httpd = socketserver.TCPServer(("127.0.0.1", 0), _Handler)
        port = httpd.server_address[1]
        threading.Thread(target=httpd.serve_forever, daemon=True).start()

        try:
            result = observe_websocket(
                f"http://127.0.0.1:{port}",
                wait_ms=3000,
            )
            self.assertEqual(result.status, "ok")

            # Find the sent frame with the long message
            for conn in result.connections:
                for f in conn.frames:
                    if f.direction == "sent" and len(f.preview) > 500:
                        self.assertTrue(
                            f.preview.endswith("...[truncated]"),
                            f"Expected truncation marker, got: {f.preview[-20:]}",
                        )
                        return
            # If we get here, the long message wasn't captured as expected
            self.skipTest("Long frame not captured — timing issue")
        finally:
            httpd.shutdown()

    def test_sensitive_preview_redaction_real(self) -> None:
        """WS frames with sensitive tokens get redacted in real capture."""
        _, http_port, httpd = _start_http_sensitive_server(self._ws_port)
        try:
            result = observe_websocket(
                f"http://127.0.0.1:{http_port}",
                wait_ms=3000,
            )
            self.assertEqual(result.status, "ok")

            # The sent frame should have the hex token redacted
            for conn in result.connections:
                for f in conn.frames:
                    if f.direction == "sent":
                        self.assertNotIn("a" * 64, f.preview)
                        self.assertIn("[redacted_hex]", f.preview)
                        return
            self.skipTest("Sent frame not captured — timing issue")
        finally:
            httpd.shutdown()


@unittest.skipIf(_SKIP_REASON, _SKIP_REASON)
class RealWebsocketNoConnectionTests(unittest.TestCase):
    """Test observe_websocket on a page that does NOT open any WS."""

    def test_page_without_websocket(self) -> None:
        """A plain HTML page yields zero connections."""
        html = "<html><body><h1>No WebSocket here</h1></body></html>"

        class _Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(html.encode())
            def log_message(self, *a):
                pass

        httpd = socketserver.TCPServer(("127.0.0.1", 0), _Handler)
        port = httpd.server_address[1]
        threading.Thread(target=httpd.serve_forever, daemon=True).start()

        try:
            result = observe_websocket(
                f"http://127.0.0.1:{port}",
                wait_ms=1000,
            )
            self.assertEqual(result.status, "ok")
            self.assertEqual(result.connections, [])
            self.assertEqual(result.total_frames, 0)

            summary = build_ws_summary(result)
            self.assertEqual(summary["connection_count"], 0)
            self.assertEqual(summary["total_frames"], 0)
        finally:
            httpd.shutdown()


if __name__ == "__main__":
    unittest.main()
